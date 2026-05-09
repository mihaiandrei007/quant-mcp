"""
Quant-MCP server.

Wraps the paper-trader + etf-dashboard stack as MCP tools so Claude Desktop /
Claude Code / Cursor users can run real backtests, fetch ETF factors, and
project portfolios from inside their AI client.

Hard rules inherited from etf-dashboard CLAUDE.md (do not violate):
- Tools return DATA only — never buy/sell/hold advice or rankings.
- No subjective language (bullish, bearish, risky, safe, hot, defensive).
- Every numeric output's formula must be in the tool docstring AND repeated
  as a sibling field in the JSON payload.
- Returns are decimal (0.08, not 8). Annualisation factor: 252 daily.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from mcp.server.fastmcp import FastMCP

from quant_mcp import curated, finance, prices
from quant_mcp.disclaimer import DISCLAIMER_TEXT, MONTE_CARLO_DISCLAIMER

mcp = FastMCP("quant-mcp")

RF_ANNUAL_ASSUMED = 0.02
TRADING_DAYS = 252
MAX_N_SIMS = 10_000
MAX_YEARS = 50


# ── ping ────────────────────────────────────────────────────────────────────

@mcp.tool()
def ping() -> str:
    """Return 'pong' to verify the quant-mcp server is reachable from a client."""
    return "pong from quant-mcp v0.0.3"


# ── compare_etfs ────────────────────────────────────────────────────────────

def _project_etf(record: dict[str, Any]) -> dict[str, Any]:
    """Trim a curated record to the public-facing per-ETF payload shape."""
    return {
        "isin": record["isin"],
        "name": record["name"],
        "ticker_yahoo": record["ticker_yahoo"],
        "ticker_native": record["ticker_native"],
        "issuer": record["issuer"],
        "domicile": record["domicile"],
        "ucits": record["ucits"],
        "index_tracked": record["index_tracked"],
        "replication_method": record["replication_method"],
        "dividend_treatment": record["dividend_treatment"],
        "ocf_pct": record["ocf_pct"],
        "fund_size_aum_eur": record["fund_size_aum_eur"],
        "fund_size_aum_as_of": record["fund_size_aum_as_of"],
        "inception_date": record["inception_date"],
        "currency": record["currency"],
    }


def _normalise_index(name: str) -> str:
    return " ".join(name.lower().split())


@mcp.tool()
def compare_etfs(isin_a: str, isin_b: str) -> dict[str, Any]:
    """Compare two UCITS ETFs side by side using curated metadata.

    Inputs
    ------
    isin_a, isin_b : str
        12-character ISINs (e.g. 'IE00BFMXXD54' for VUAA). Case-insensitive.
        Both ISINs must exist in the curated list — call this tool with no
        args to retrieve the supported set if unsure (or pass an unsupported
        ISIN and read the `supported_isins` field of the error response).

    Output (dict)
    -------------
    On success:
        - etf_a, etf_b: per-ETF metadata (name, ISIN, ticker, OCF, AUM,
          domicile, replication, dividend treatment, inception, index).
        - comparison:
            ocf_delta_bps           = (etf_a.ocf_pct - etf_b.ocf_pct) * 10000
            fund_size_ratio_a_over_b = etf_a.fund_size_aum_eur / etf_b.fund_size_aum_eur
            same_index               = case-insensitive equality of `index_tracked`
            tracking_difference_delta_pct = null in v0 — fetch via the issuer
                                            factsheet or trackingdifferences.com
        - dataset_as_of: ISO date the curated metadata snapshot was taken.
        - sources: per-ETF KID + justETF profile URLs for audit.
        - disclaimer: identical to etf-dashboard's DISCLAIMER_TEXT.

    On unsupported ISIN:
        - error: 'unsupported_isin'
        - unsupported: [list of the ISINs the caller passed that aren't curated]
        - supported_isins: full list of currently supported ISINs.

    Compliance notes
    ----------------
    - Returns data only. Never recommends one ETF over the other.
    - `same_index` is a factual string comparison, not a "they're equivalent"
      claim — two physical-replication funds tracking the same index can
      still have different OCF, tracking difference, and AUM.
    - AUM figures are approximate quarterly snapshots — for live values,
      follow the linked justETF URL.
    """
    a = curated.lookup_by_isin(isin_a)
    b = curated.lookup_by_isin(isin_b)

    missing = []
    if a is None:
        missing.append(isin_a)
    if b is None:
        missing.append(isin_b)
    if missing:
        return {
            "error": "unsupported_isin",
            "unsupported": missing,
            "supported_isins": curated.supported_isins(),
            "dataset_as_of": curated.dataset_as_of(),
        }

    ocf_delta_bps = (a["ocf_pct"] - b["ocf_pct"]) * 10000
    fund_size_ratio = a["fund_size_aum_eur"] / b["fund_size_aum_eur"]
    same_index = _normalise_index(a["index_tracked"]) == _normalise_index(b["index_tracked"])

    return {
        "etf_a": _project_etf(a),
        "etf_b": _project_etf(b),
        "comparison": {
            "ocf_delta_bps": round(ocf_delta_bps, 4),
            "ocf_delta_bps_formula": "(etf_a.ocf_pct - etf_b.ocf_pct) * 10000",
            "fund_size_ratio_a_over_b": round(fund_size_ratio, 4),
            "fund_size_ratio_formula": "etf_a.fund_size_aum_eur / etf_b.fund_size_aum_eur",
            "same_index": same_index,
            "tracking_difference_delta_pct": None,
            "tracking_difference_note": (
                "Not available in v0 of compare_etfs. Fetch via issuer factsheet "
                "or trackingdifferences.com. Tracking difference is the realised "
                "drag/lift of fund NAV vs index NAV after fees and securities-"
                "lending revenue."
            ),
        },
        "dataset_as_of": curated.dataset_as_of(),
        "sources": [
            {"isin": a["isin"], "kid_url": a["kid_url"], "justetf_url": a["justetf_url"]},
            {"isin": b["isin"], "kid_url": b["kid_url"], "justetf_url": b["justetf_url"]},
        ],
        "disclaimer": DISCLAIMER_TEXT,
    }


# ── helpers shared by get_etf_factors and monte_carlo_projection ────────────

def _resolve_isin_or_error(isin: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return (record, None) on success or (None, error_payload) on miss."""
    record = curated.lookup_by_isin(isin)
    if record is None:
        return None, {
            "error": "unsupported_isin",
            "unsupported": [isin],
            "supported_isins": curated.supported_isins(),
            "dataset_as_of": curated.dataset_as_of(),
        }
    return record, None


def _price_series(ticker: str, lookback: prices.Period) -> pd.Series:
    """Download (or read from cache) the adjusted close price series."""
    df = prices.get_price_history(ticker, lookback)
    if df.empty:
        return pd.Series(dtype=float)
    series = df["adj_close"].dropna()
    if series.empty:
        # Some yfinance responses populate close but not adj_close — fall back.
        series = df["close"].dropna()
    return series


def _factors_for_window(price_window: pd.Series) -> dict[str, Any]:
    if price_window.empty or len(price_window) < 2:
        return {
            "available": False,
            "note": "Not enough observations in the lookback window.",
            "n_observations": int(len(price_window)),
        }
    rets = finance.daily_returns(price_window)
    ann_ret = finance.annualised_return(rets)
    ann_vol = finance.annualised_volatility(rets)
    sharpe = finance.sharpe_ratio(rets, rf_annual=RF_ANNUAL_ASSUMED)
    mdd = finance.max_drawdown(price_window)
    calmar = finance.calmar_ratio(ann_ret, mdd)
    return {
        "available": True,
        "n_observations": int(len(price_window)),
        "first_obs_date": price_window.index.min().strftime("%Y-%m-%d"),
        "last_obs_date":  price_window.index.max().strftime("%Y-%m-%d"),
        "annualised_return": round(ann_ret, 6),
        "annualised_volatility": round(ann_vol, 6),
        "sharpe_ratio": round(sharpe, 6),
        "max_drawdown": round(mdd, 6),
        "calmar_ratio": round(calmar, 6),
    }


# ── get_etf_factors ─────────────────────────────────────────────────────────

@mcp.tool()
def get_etf_factors(isin: str) -> dict[str, Any]:
    """Compute rolling 1y / 3y / 5y / 10y annualised return, volatility, Sharpe,
    max drawdown, and Calmar ratio for a curated UCITS ETF.

    Inputs
    ------
    isin : str
        12-character ISIN. Resolved via the curated list to a Yahoo Finance
        ticker; prices are fetched (cached) via yfinance.

    Output (dict)
    -------------
    On success:
        - isin, name, ticker_yahoo: identity fields.
        - lookback_period: "10y" — the window pulled from yfinance.
        - n_observations, first_obs_date, last_obs_date: covered range.
        - factors:
            "1y" / "3y" / "5y" / "10y" -> {available, n_observations,
                annualised_return, annualised_volatility, sharpe_ratio,
                max_drawdown, calmar_ratio} or {available: false, note}.
        - rf_annual_assumed: 0.02 (used in Sharpe excess-return calc).
        - formulas: explicit string formula for every numeric output.
        - sources: KID + justETF + Yahoo Finance URLs for audit.
        - disclaimer: same DISCLAIMER_TEXT as compare_etfs.

    On unsupported ISIN: structured error mirroring compare_etfs.

    Formulas (also returned in the payload's `formulas` field)
    ----------------------------------------------------------
    - daily_returns       = P_t / P_{t-1} - 1
    - annualised_return   = (1 + mean(daily_returns)) ** 252 - 1
    - annualised_vol      = std(daily_returns) * sqrt(252)
    - sharpe_ratio        = mean(excess) / std(excess) * sqrt(252)
                            excess = daily_returns - rf_daily
                            rf_daily = (1 + 0.02) ** (1/252) - 1
    - max_drawdown        = min(prices / running_max - 1)   (negative number)
    - calmar_ratio        = annualised_return / abs(max_drawdown)

    Compliance notes
    ----------------
    - Returns data only. No "this fund is risky/safe/better."
    - Returns are decimal: 0.08 means +8% annualised, not 8%.
    - Sharpe uses an assumed 2% annual risk-free rate; this is a fixed
      assumption, not a recommendation.
    """
    record, err = _resolve_isin_or_error(isin)
    if err is not None:
        return err

    ticker = record["ticker_yahoo"]
    series = _price_series(ticker, "10y")
    if series.empty:
        return {
            "error": "no_price_data",
            "isin": record["isin"],
            "ticker_yahoo": ticker,
            "note": (
                "yfinance returned no usable price data and the local cache is "
                "empty. The ETF may be too new for the requested lookback or "
                "the network call failed."
            ),
        }

    today_ts = pd.Timestamp.utcnow().tz_localize(None)
    windows = {"1y": 365, "3y": 365 * 3, "5y": 365 * 5, "10y": 365 * 10}
    factors: dict[str, Any] = {}
    for label, days in windows.items():
        cutoff = today_ts - pd.Timedelta(days=days)
        sliced = series.loc[series.index >= cutoff]
        factors[label] = _factors_for_window(sliced)

    return {
        "isin": record["isin"],
        "name": record["name"],
        "ticker_yahoo": ticker,
        "lookback_period": "10y",
        "data_source": "yfinance (Yahoo Finance) via local SQLite cache",
        "n_observations": int(len(series)),
        "first_obs_date": series.index.min().strftime("%Y-%m-%d"),
        "last_obs_date":  series.index.max().strftime("%Y-%m-%d"),
        "factors": factors,
        "rf_annual_assumed": RF_ANNUAL_ASSUMED,
        "formulas": {
            "daily_returns":         "P_t / P_{t-1} - 1",
            "annualised_return":     "(1 + mean(daily_returns)) ** 252 - 1",
            "annualised_volatility": "std(daily_returns) * sqrt(252)",
            "sharpe_ratio":          "mean(excess) / std(excess) * sqrt(252); excess = daily_returns - rf_daily; rf_daily = (1 + rf_annual) ** (1/252) - 1",
            "max_drawdown":          "min(prices / running_max - 1)",
            "calmar_ratio":          "annualised_return / abs(max_drawdown)",
        },
        "sources": [{
            "isin": record["isin"],
            "kid_url": record["kid_url"],
            "justetf_url": record["justetf_url"],
            "yahoo_url": f"https://finance.yahoo.com/quote/{ticker}/",
        }],
        "disclaimer": DISCLAIMER_TEXT,
    }


# ── monte_carlo_projection ──────────────────────────────────────────────────

def _validate_portfolio(portfolio: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not isinstance(portfolio, list) or not portfolio:
        return {"error": "invalid_portfolio", "note": "portfolio must be a non-empty list of {isin, weight} objects."}
    total_weight = 0.0
    for entry in portfolio:
        if not isinstance(entry, dict) or "isin" not in entry or "weight" not in entry:
            return {"error": "invalid_portfolio", "note": "each portfolio entry must be a dict with keys `isin` and `weight`."}
        try:
            w = float(entry["weight"])
        except (TypeError, ValueError):
            return {"error": "invalid_portfolio", "note": f"weight for ISIN {entry.get('isin')!r} is not numeric."}
        if w < 0:
            return {"error": "invalid_portfolio", "note": f"weight for ISIN {entry.get('isin')!r} is negative; weights must be >= 0."}
        total_weight += w
    if not (0.999 <= total_weight <= 1.001):
        return {"error": "invalid_portfolio", "note": f"weights sum to {total_weight:.4f}; expected ~1.0 (decimal, not percent)."}
    return None


@mcp.tool()
def monte_carlo_projection(
    portfolio: list[dict[str, Any]],
    years: int = 10,
    n_sims: int = 5000,
) -> dict[str, Any]:
    """Project a portfolio forward by simulating `n_sims` lognormal price paths.

    Inputs
    ------
    portfolio : list[{isin: str, weight: float}]
        Weights are decimal and must sum to ~1.0 (e.g. 0.6 + 0.4). All ISINs
        must be in the curated list. Negative weights (shorts) are rejected.
    years : int
        Projection horizon in years. Capped at 50.
    n_sims : int
        Number of simulated paths. Capped at 10000.

    Output (dict)
    -------------
    On success:
        - inputs: echoes portfolio, years, n_sims, lookback used.
        - portfolio_stats: mean_daily_return, std_daily_return,
          annualised_return, annualised_volatility — computed from the
          weighted historical daily returns of the supplied basket.
        - percentile_bands:
            years_axis: [1, 2, ..., years]
            p10/p50/p90: terminal-multiplier percentiles at end of each year
                         (e.g. p50[2] = 1.18 means the median path is at 118%
                          of the initial value after 2 years).
        - terminal_multiplier: p10/p50/p90 at the final year.
        - formulas: every numeric output's formula as a string.
        - disclaimer + monte_carlo_disclaimer (fat-tail caveat).
        - sources: per-ISIN KID/justETF URLs.

    On unsupported ISIN / invalid portfolio: structured error.

    Formulas (also returned in the payload)
    ---------------------------------------
    - For each ISIN: daily_returns_i = P_t / P_{t-1} - 1
    - portfolio_daily_return_t = sum_i weight_i * daily_returns_i,t
    - mu_d = mean(portfolio_daily_return), sigma_d = std(portfolio_daily_return)
    - Per simulation path:
          V_0 = 1.0
          V_t = V_{t-1} * (1 + r_t)   where r_t ~ N(mu_d, sigma_d)
    - Percentiles taken across paths at the end of each year.

    Compliance notes
    ----------------
    - Returns DATA only. No "this portfolio will return X%."
    - Normal-return assumption is a teaching tool, not a forecast — the
      `monte_carlo_disclaimer` field repeats this fat-tail caveat verbatim
      from the etf-dashboard project.
    - Lookback window is fixed at 5y of historical daily returns — a longer
      window would smooth recent regime changes, a shorter one would amplify
      noise. We surface n_observations so the caller can audit.
    """
    portfolio_err = _validate_portfolio(portfolio)
    if portfolio_err is not None:
        return portfolio_err

    if years <= 0:
        return {"error": "invalid_years", "note": f"years must be a positive integer; got {years}."}
    years = min(int(years), MAX_YEARS)

    if n_sims <= 0:
        return {"error": "invalid_n_sims", "note": f"n_sims must be a positive integer; got {n_sims}."}
    n_sims = min(int(n_sims), MAX_N_SIMS)

    # Resolve every ISIN, fail fast on the first miss.
    resolved = []
    unsupported = []
    for entry in portfolio:
        rec = curated.lookup_by_isin(entry["isin"])
        if rec is None:
            unsupported.append(entry["isin"])
        else:
            resolved.append({"record": rec, "weight": float(entry["weight"])})
    if unsupported:
        return {
            "error": "unsupported_isin",
            "unsupported": unsupported,
            "supported_isins": curated.supported_isins(),
            "dataset_as_of": curated.dataset_as_of(),
        }

    # Pull each ISIN's price series, compute daily returns, align dates.
    return_series_by_isin: dict[str, pd.Series] = {}
    for r in resolved:
        rec = r["record"]
        s = _price_series(rec["ticker_yahoo"], "5y")
        if s.empty or len(s) < 2:
            return {
                "error": "no_price_data",
                "isin": rec["isin"],
                "ticker_yahoo": rec["ticker_yahoo"],
                "note": "yfinance returned no usable price data for this leg.",
            }
        return_series_by_isin[rec["isin"]] = finance.daily_returns(s)

    aligned = pd.concat(return_series_by_isin, axis=1, join="inner").dropna(how="any")
    if aligned.empty:
        return {
            "error": "no_overlap",
            "note": "Daily-return series of the supplied legs do not overlap on enough dates to simulate.",
        }

    weights = np.array([r["weight"] for r in resolved], dtype=float)
    isins_in_order = [r["record"]["isin"] for r in resolved]
    aligned = aligned[isins_in_order]
    portfolio_daily = aligned.values @ weights  # shape (n_obs,)

    mu_d = float(portfolio_daily.mean())
    sigma_d = float(portfolio_daily.std(ddof=1))

    rng = np.random.default_rng()
    n_steps = years * TRADING_DAYS
    shocks = rng.normal(loc=mu_d, scale=sigma_d, size=(n_sims, n_steps))
    growth = 1.0 + shocks
    paths = np.cumprod(growth, axis=1)  # shape (n_sims, n_steps)

    year_indices = [TRADING_DAYS * y - 1 for y in range(1, years + 1)]
    yearly = paths[:, year_indices]  # shape (n_sims, years)
    p10 = np.percentile(yearly, 10, axis=0).tolist()
    p50 = np.percentile(yearly, 50, axis=0).tolist()
    p90 = np.percentile(yearly, 90, axis=0).tolist()

    return {
        "inputs": {
            "portfolio": [{"isin": r["record"]["isin"], "weight": r["weight"]} for r in resolved],
            "years": years,
            "n_sims": n_sims,
            "lookback_period": "5y",
            "n_observations": int(len(aligned)),
            "first_obs_date": aligned.index.min().strftime("%Y-%m-%d"),
            "last_obs_date":  aligned.index.max().strftime("%Y-%m-%d"),
        },
        "portfolio_stats": {
            "mean_daily_return": round(mu_d, 8),
            "std_daily_return":  round(sigma_d, 8),
            "annualised_return":     round((1.0 + mu_d) ** TRADING_DAYS - 1.0, 6),
            "annualised_volatility": round(sigma_d * np.sqrt(TRADING_DAYS), 6),
        },
        "percentile_bands": {
            "years_axis": list(range(1, years + 1)),
            "p10": [round(v, 6) for v in p10],
            "p50": [round(v, 6) for v in p50],
            "p90": [round(v, 6) for v in p90],
        },
        "terminal_multiplier": {
            "p10": round(p10[-1], 6),
            "p50": round(p50[-1], 6),
            "p90": round(p90[-1], 6),
        },
        "formulas": {
            "portfolio_daily_return": "sum_i weight_i * daily_returns_i,t  (weighted sum across legs after date-aligning on inner-join)",
            "mu_d":                   "mean(portfolio_daily_return)",
            "sigma_d":                "std(portfolio_daily_return, ddof=1)",
            "annualised_return":      "(1 + mu_d) ** 252 - 1",
            "annualised_volatility":  "sigma_d * sqrt(252)",
            "path":                   "V_0 = 1.0; V_t = V_{t-1} * (1 + r_t); r_t ~ N(mu_d, sigma_d)",
            "percentile_bands":       "Across n_sims paths, percentiles 10/50/90 of V_t at the last trading day of each simulated year (step index = 252*y - 1).",
        },
        "sources": [
            {
                "isin": r["record"]["isin"],
                "kid_url": r["record"]["kid_url"],
                "justetf_url": r["record"]["justetf_url"],
                "yahoo_url": f"https://finance.yahoo.com/quote/{r['record']['ticker_yahoo']}/",
            }
            for r in resolved
        ],
        "disclaimer": DISCLAIMER_TEXT,
        "monte_carlo_disclaimer": MONTE_CARLO_DISCLAIMER,
    }


if __name__ == "__main__":
    mcp.run()
