"""
Pure financial calculations — no Streamlit, no I/O, just pandas/numpy.

Copied verbatim (formula-wise) from `etf-dashboard/lib/finance/calc.py` so
that quant-mcp returns numbers a buyer can reconcile against the dashboard.
The docstrings here are the audit trail referenced from each MCP tool's
output payload (e.g. `sharpe_formula` field).

Conventions (etf-dashboard CLAUDE.md hard rules)
------------------------------------------------
- Returns are decimal (0.08 = +8%, never 8).
- Annualisation factor: 252 trading days for daily data.
- Daily risk-free rate is derived from the annual rate as
  ``(1 + rf_annual) ** (1/252) - 1``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def daily_returns(prices: pd.Series) -> pd.Series:
    """Simple daily returns: ``r_t = P_t / P_{t-1} - 1``."""
    return prices.pct_change().dropna()


def annualised_return(daily_returns_series: pd.Series) -> float:
    """Geometric annualised return.

    Formula: ``(1 + mean_daily_return) ** 252 - 1``.
    """
    if daily_returns_series.empty:
        return 0.0
    mean_daily = float(daily_returns_series.mean())
    return (1.0 + mean_daily) ** TRADING_DAYS_PER_YEAR - 1.0


def annualised_volatility(daily_returns_series: pd.Series) -> float:
    """Annualised standard deviation of daily returns.

    Formula: ``std(daily_returns) * sqrt(252)``.
    """
    if daily_returns_series.empty:
        return 0.0
    return float(daily_returns_series.std(ddof=1)) * np.sqrt(TRADING_DAYS_PER_YEAR)


def sharpe_ratio(daily_returns_series: pd.Series, rf_annual: float = 0.02) -> float:
    """Annualised Sharpe ratio over the supplied daily returns.

    Daily risk-free rate ``rf_d = (1 + rf_annual) ** (1/252) - 1``.
    Excess returns ``e_t = r_t - rf_d``.
    Sharpe = ``mean(e) / std(e) * sqrt(252)``.
    """
    if daily_returns_series.empty:
        return 0.0
    rf_daily = (1.0 + rf_annual) ** (1.0 / TRADING_DAYS_PER_YEAR) - 1.0
    excess = daily_returns_series - rf_daily
    sigma = float(excess.std(ddof=1))
    if sigma == 0:
        return 0.0
    return float(excess.mean()) / sigma * np.sqrt(TRADING_DAYS_PER_YEAR)


def max_drawdown(prices: pd.Series) -> float:
    """Maximum peak-to-trough drawdown as a negative number.

    Formula: ``min(prices / running_max - 1)``.
    """
    if prices.empty:
        return 0.0
    running_max = prices.cummax()
    drawdown = prices / running_max - 1.0
    return float(drawdown.min())


def calmar_ratio(annualised_ret: float, max_dd: float) -> float:
    """Calmar ratio = annualised_return / abs(max_drawdown).

    Returns 0.0 if max_drawdown is 0 (no drawdown observed in the window).
    """
    if max_dd == 0:
        return 0.0
    return annualised_ret / abs(max_dd)
