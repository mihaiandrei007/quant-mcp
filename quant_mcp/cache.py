"""
SQLite cache for yfinance prices and fund metadata.

Mirrors the schema of `etf-dashboard/lib/db.py` (the `prices_cache` and
`fund_info_cache` tables) but uses stdlib ``sqlite3`` instead of SQLAlchemy
to keep the MCP server's dependency footprint small. Yahoo Finance throttles
aggressively on bursty traffic, and a hot tool inside an MCP client can
fire many calls in a row — so every fetch goes through this cache.

Tables
------
- ``prices_cache``    Daily OHLCV per ticker. PK = (ticker, date).
- ``fund_info_cache`` Static fund metadata (name, expense ratio, sector
                      breakdown JSON, top holdings JSON). PK = ticker.

Both rows carry a ``fetched_at`` UTC timestamp; callers decide TTL via
``PRICE_CACHE_TTL`` and ``INFO_CACHE_TTL`` re-exported from ``prices.py``.

DB path: ``<project_root>/data/quant-mcp.db`` (created on first call).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "quant-mcp.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS prices_cache (
    ticker     TEXT NOT NULL,
    date       TEXT NOT NULL,   -- ISO YYYY-MM-DD
    open       REAL,
    high       REAL,
    low        REAL,
    close      REAL NOT NULL,
    adj_close  REAL,
    volume     REAL,
    fetched_at TEXT NOT NULL,   -- ISO UTC
    PRIMARY KEY (ticker, date)
);

CREATE TABLE IF NOT EXISTS fund_info_cache (
    ticker              TEXT PRIMARY KEY,
    long_name           TEXT,
    expense_ratio       REAL,
    category            TEXT,
    currency            TEXT,
    inception_date      TEXT,
    sector_weights_json TEXT,
    top_holdings_json   TEXT,
    fetched_at          TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema() -> None:
    """Idempotent — safe to call on every server start."""
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def utc_now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


# ── prices ──────────────────────────────────────────────────────────────────

def read_prices(ticker: str) -> list[sqlite3.Row]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM prices_cache WHERE ticker = ? ORDER BY date ASC",
            (ticker,),
        ).fetchall()
    return rows


def upsert_prices(ticker: str, records: list[dict]) -> None:
    """Upsert a list of price records. Each record must include the keys:
    ``date, open, high, low, close, adj_close, volume``.

    Uses SQLite's ``INSERT OR REPLACE`` so re-fetching the same date is a
    no-op vs. an error.
    """
    if not records:
        return
    now = utc_now_iso()
    rows = [
        (
            ticker,
            r["date"],
            r.get("open"),
            r.get("high"),
            r.get("low"),
            r["close"],
            r.get("adj_close"),
            r.get("volume"),
            now,
        )
        for r in records
    ]
    with _connect() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO prices_cache
                (ticker, date, open, high, low, close, adj_close, volume, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


# ── fund info ───────────────────────────────────────────────────────────────

def read_fund_info(ticker: str) -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM fund_info_cache WHERE ticker = ?",
            (ticker,),
        ).fetchone()


def upsert_fund_info(
    ticker: str,
    long_name: str | None,
    expense_ratio: float | None,
    category: str | None,
    currency: str | None,
    inception_date: str | None,
    sector_weights_json: str,
    top_holdings_json: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO fund_info_cache
                (ticker, long_name, expense_ratio, category, currency,
                 inception_date, sector_weights_json, top_holdings_json,
                 fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker, long_name, expense_ratio, category, currency,
                inception_date, sector_weights_json, top_holdings_json,
                utc_now_iso(),
            ),
        )
