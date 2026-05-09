"""
yfinance wrapper that goes through the local SQLite cache.

Mirrors the cache philosophy of `etf-dashboard/lib/data/yfinance_client.py`:
Yahoo throttles aggressive bursty traffic, so every call checks the cache
first, refreshes only when stale, and degrades gracefully to stale cache
if the network call fails.

Two entry points used by the MCP tools:

- ``get_price_history(ticker, period)`` -> pandas.DataFrame of OHLCV.
- ``get_fund_info(ticker)``              -> dict of static metadata.

Both swallow yfinance exceptions internally and surface either fresh data,
cached data, or an empty result. The MCP tool layer turns "no data" into
a structured error response.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

import pandas as pd
import yfinance as yf

from quant_mcp import cache

Period = Literal["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]

PRICE_CACHE_TTL = timedelta(minutes=15)
INFO_CACHE_TTL  = timedelta(days=7)


@dataclass(frozen=True)
class FundInfo:
    ticker: str
    long_name: str | None
    expense_ratio: float | None
    category: str | None
    currency: str | None
    inception_date: str | None
    sector_weights: dict[str, float]
    top_holdings: list[dict]


def _period_start(period: Period) -> datetime | None:
    today = datetime.utcnow()
    table = {
        "1mo": 30, "3mo": 91, "6mo": 182, "1y": 365,
        "2y": 365 * 2, "5y": 365 * 5, "10y": 365 * 10,
    }
    days = table.get(period)
    return today - timedelta(days=days) if days else None


def _cached_to_df(ticker: str) -> pd.DataFrame:
    rows = cache.read_prices(ticker)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([dict(r) for r in rows])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df[["open", "high", "low", "close", "adj_close", "volume"]]


def _cache_covers_period(cached: pd.DataFrame, period: Period) -> bool:
    if cached.empty:
        return False
    needed_start = _period_start(period)
    if needed_start is None:
        return True  # "max" — whatever is cached
    return cached.index.min() <= pd.Timestamp(needed_start)


def _cache_fresh(cached: pd.DataFrame) -> bool:
    if cached.empty:
        return False
    last_close = cached.index.max()
    return (pd.Timestamp.utcnow().tz_localize(None) - last_close) < pd.Timedelta(PRICE_CACHE_TTL)


def _slice_period(df: pd.DataFrame, period: Period) -> pd.DataFrame:
    start = _period_start(period)
    if start is None:
        return df
    return df.loc[df.index >= pd.Timestamp(start)]


def get_price_history(ticker: str, period: Period = "5y") -> pd.DataFrame:
    """Return adjusted OHLCV for the requested period.

    On cache hit (full coverage of the requested period AND fresh enough)
    returns cached data without touching the network. Otherwise downloads
    from yfinance, persists, and returns the slice.
    """
    cache.init_schema()
    cached = _cached_to_df(ticker)
    if _cache_covers_period(cached, period) and _cache_fresh(cached):
        return _slice_period(cached, period)

    try:
        df = yf.download(
            ticker, period=period, auto_adjust=False,
            progress=False, threads=False,
        )
    except Exception:
        return cached if not cached.empty else pd.DataFrame()

    if df.empty:
        return cached if not cached.empty else df

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    records = []
    for idx, row in df.iterrows():
        close = row.get("Close")
        if pd.isna(close):
            continue
        records.append({
            "date": idx.strftime("%Y-%m-%d"),
            "open":  float(row["Open"])      if pd.notna(row.get("Open"))      else None,
            "high":  float(row["High"])      if pd.notna(row.get("High"))      else None,
            "low":   float(row["Low"])       if pd.notna(row.get("Low"))       else None,
            "close": float(close),
            "adj_close": float(row["Adj Close"]) if pd.notna(row.get("Adj Close")) else None,
            "volume":    float(row["Volume"])    if pd.notna(row.get("Volume"))    else None,
        })

    cache.upsert_prices(ticker, records)
    return _slice_period(_cached_to_df(ticker), period)


def get_fund_info(ticker: str) -> FundInfo:
    """Cached fund metadata. Refreshes from yfinance when older than a week."""
    cache.init_schema()
    row = cache.read_fund_info(ticker)
    if row is not None:
        fetched_at = datetime.fromisoformat(row["fetched_at"])
        if (datetime.utcnow() - fetched_at) < INFO_CACHE_TTL:
            return _row_to_info(row)

    info = _download_info(ticker)
    cache.upsert_fund_info(
        ticker=info.ticker,
        long_name=info.long_name,
        expense_ratio=info.expense_ratio,
        category=info.category,
        currency=info.currency,
        inception_date=info.inception_date,
        sector_weights_json=json.dumps(info.sector_weights),
        top_holdings_json=json.dumps(info.top_holdings),
    )
    return info


def _download_info(ticker: str) -> FundInfo:
    t = yf.Ticker(ticker)
    raw: dict = {}
    try:
        raw = t.info or {}
    except Exception:
        raw = {}

    sector_weights: dict[str, float] = {}
    funds_data = getattr(t, "funds_data", None)
    if funds_data is not None:
        try:
            sw = funds_data.sector_weightings
            if hasattr(sw, "to_dict"):
                sector_weights = {str(k): float(v) for k, v in sw.to_dict().items()}
            elif isinstance(sw, dict):
                sector_weights = {str(k): float(v) for k, v in sw.items()}
        except Exception:
            sector_weights = {}

    top_holdings: list[dict] = []
    if funds_data is not None:
        try:
            th = funds_data.top_holdings
            if th is not None and not th.empty:
                top_holdings = [
                    {"name": str(idx), **{k: _to_jsonable(v) for k, v in row.items()}}
                    for idx, row in th.iterrows()
                ]
        except Exception:
            top_holdings = []

    return FundInfo(
        ticker=ticker,
        long_name=raw.get("longName") or raw.get("shortName"),
        expense_ratio=_safe_float(raw.get("expenseRatio") or raw.get("netExpenseRatio")),
        category=raw.get("category"),
        currency=raw.get("currency"),
        inception_date=str(raw.get("fundInceptionDate") or "") or None,
        sector_weights=sector_weights,
        top_holdings=top_holdings,
    )


def _row_to_info(row) -> FundInfo:
    return FundInfo(
        ticker=row["ticker"],
        long_name=row["long_name"],
        expense_ratio=row["expense_ratio"],
        category=row["category"],
        currency=row["currency"],
        inception_date=row["inception_date"],
        sector_weights=json.loads(row["sector_weights_json"] or "{}"),
        top_holdings=json.loads(row["top_holdings_json"] or "[]"),
    )


def _safe_float(v) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_jsonable(v):
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    try:
        return float(v)
    except (TypeError, ValueError):
        return str(v)
