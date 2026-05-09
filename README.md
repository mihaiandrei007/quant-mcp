# quant-mcp

A [Model Context Protocol](https://modelcontextprotocol.io) server that exposes UCITS ETF analytics — factor metrics, side-by-side comparison, and Monte Carlo projection — as tools your AI client (Claude Desktop, Claude Code, Cursor, or any MCP-compatible client) can call.

Every numeric output ships with its formula, source URLs, and a disclaimer. **No buy/sell advice. No rankings. No subjective language. Data only.**

---

## Tools

| Tool | Returns |
|---|---|
| `ping` | Liveness check (`"pong from quant-mcp v0.0.3"`). |
| `compare_etfs(isin_a, isin_b)` | Side-by-side metadata + `ocf_delta_bps`, `fund_size_ratio_a_over_b`, `same_index`. |
| `get_etf_factors(isin)` | 1y / 3y / 5y / 10y annualised return, volatility, Sharpe, max drawdown, Calmar. |
| `monte_carlo_projection(portfolio, years, n_sims)` | p10 / p50 / p90 percentile bands per year + terminal multiplier. |

All tools accept ISINs from the curated v0 list — see [Supported ISINs](#supported-isins-v0).

---

## Install

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) 0.11+

### Clone & sync

```bash
git clone https://github.com/mihaiandrei007/quant-mcp.git
cd quant-mcp
uv sync
```

### Claude Desktop

Edit your `claude_desktop_config.json`:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Add the server block (replace the directory with your absolute clone path):

```json
{
  "mcpServers": {
    "quant-mcp": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/quant-mcp", "run", "main.py"]
    }
  }
}
```

Restart Claude Desktop. In any chat, type `/mcp` and confirm `quant-mcp ✓ connected` with 4 tools.

### Claude Code

Drop a `.mcp.json` into your working directory (or your home dir):

```json
{
  "mcpServers": {
    "quant-mcp": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/quant-mcp", "run", "main.py"]
    }
  }
}
```

Restart Claude Code, approve the MCP when prompted, then `/mcp` to confirm.

### Cursor & other MCP clients

The server block above is portable — Cursor, Continue, Zed, and any other client that consumes [the MCP config schema](https://modelcontextprotocol.io/quickstart/user) will work with the same JSON.

---

## Example prompts

Once `/mcp` shows the server connected, paste any of these:

**Compare two S&P 500 trackers:**

```
use compare_etfs to compare VUAA (IE00BFMXXD54) and CSPX (IE00B5BMR087)
```

Returns OCF delta in basis points, AUM ratio, and `same_index=true` (both track S&P 500).

**Get historical factors for one ETF:**

```
use get_etf_factors with ISIN IE00BK5BQT80
```

Returns 1y / 3y / 5y / 10y annualised return, volatility, Sharpe, max drawdown, and Calmar for VWCE.

**Project a 60/40 portfolio:**

```
use monte_carlo_projection with portfolio
[{"isin": "IE00BFMXXD54", "weight": 0.6},
 {"isin": "IE00BK5BQT80", "weight": 0.4}],
years 10, n_sims 2000
```

Returns p10 / p50 / p90 percentile bands across 10 years plus terminal multipliers, with both `disclaimer` and `monte_carlo_disclaimer` fields.

---

## Supported ISINs (v0)

| ISIN | Ticker | Name | Index | OCF |
|---|---|---|---|---|
| IE00BK5BQT80 | VWCE | Vanguard FTSE All-World UCITS ETF (Acc) | FTSE All-World | 0.22% |
| IE00B3RBWM25 | VWRL | Vanguard FTSE All-World UCITS ETF (Dist) | FTSE All-World | 0.22% |
| IE00B4L5Y983 | IWDA | iShares Core MSCI World UCITS ETF (Acc) | MSCI World | 0.20% |
| IE00BFMXXD54 | VUAA | Vanguard S&P 500 UCITS ETF (Acc) | S&P 500 | 0.07% |
| IE00B3XXRP09 | VUSA | Vanguard S&P 500 UCITS ETF (Dist) | S&P 500 | 0.07% |
| IE00B5BMR087 | CSPX | iShares Core S&P 500 UCITS ETF (Acc) | S&P 500 | 0.07% |
| IE00BKM4GZ66 | EIMI | iShares Core MSCI EM IMI UCITS ETF (Acc) | MSCI Emerging Markets IMI | 0.18% |
| IE00B3VVMM84 | VFEM | Vanguard FTSE Emerging Markets UCITS ETF (Dist) | FTSE Emerging | 0.22% |
| IE00BDBRDM35 | AGGH | iShares Core Global Aggregate Bond UCITS ETF (EUR Hedged Acc) | Bloomberg Global Aggregate Bond | 0.10% |
| IE0032077012 | EQQQ | Invesco EQQQ NASDAQ-100 UCITS ETF (Dist) | NASDAQ-100 | 0.30% |
| IE00B53SZB19 | CNDX | iShares NASDAQ 100 UCITS ETF (Acc) | NASDAQ-100 | 0.33% |
| IE00B8GKDB10 | VHYL | Vanguard FTSE All-World High Dividend Yield UCITS ETF (Dist) | FTSE All-World High Dividend Yield | 0.29% |

Snapshot date: see `data/curated_etfs.json` field `as_of`. AUM figures are quarterly snapshots — for live values, follow the `justetf_url` returned by each tool.

---

## Compliance / disclaimer policy

Every tool obeys these rules:

- **Data only.** No buy / sell / hold recommendations, no rankings, no "this fund is better".
- **No subjective language** in any output (no "risky", "safe", "bullish", "bearish", "hot", "defensive").
- **Every numeric field's formula** appears in the tool's docstring AND as a sibling key in the JSON response (`formulas` block).
- **Returns are decimal:** `0.08` means +8% annualised, not 8%.
- **Annualisation:** 252 trading days daily, 52 weekly, 12 monthly.
- **Sharpe ratio:** `mean(daily_excess) / std(daily_excess) * sqrt(252)` with `rf_annual = 0.02`.
- **Max drawdown:** `min(prices / running_max - 1)`.
- **Every response includes a `disclaimer` field.** `monte_carlo_projection` additionally returns a `monte_carlo_disclaimer` flagging the normal-return assumption (real markets have fat tails).

This is an educational / analytical tool, not investment advice. Always verify outputs against issuer factsheets (`kid_url` returned by each tool) before acting on them.

---

## Tech notes

- **Stack:** Python 3.12, [mcp](https://github.com/modelcontextprotocol/python-sdk) 1.27 (FastMCP), [yfinance](https://github.com/ranaroussi/yfinance) 1.3, pandas, numpy.
- **Price data** is fetched via yfinance and cached in a local SQLite DB (`data/quant-mcp.db`). TTLs: 15 min for prices, 7 days for fund info. Delete the file to force a refresh.
- **Graceful degradation:** if a network call fails but the cache has data, the tool returns the cached series rather than erroring.

### Known limitations

- Yahoo Finance caps `.DE`-listed UCITS tickers to ~340 trading days even when `period="10y"` is requested. The tool surfaces `n_observations` and `first_obs_date` so you can see the actual coverage; in that case the 3y / 5y / 10y windows can collapse to identical numbers because the underlying data is shorter than 1 year.
- AUM figures in `compare_etfs` are quarterly snapshots. For live values, follow `justetf_url`.
- `tracking_difference_delta_pct` is `null` in v0. Pull from issuer factsheets or [trackingdifferences.com](https://www.trackingdifferences.com).
- v0 supports 12 broad-market UCITS ETFs. Extending the curated list is a JSON edit (`data/curated_etfs.json`) + server restart.

---

## Roadmap

Prioritised:

- Expand curated ETF list (sector / regional / thematic UCITS).
- Fallback exchange (`.MI` / `.AS` / `.L`) when Yahoo caps `.DE` history.
- `tracking_difference_delta_pct` in `compare_etfs` (currently `null`).
- Additional tools as install signal grows: backtest a strategy, correlation matrix, factor regression.

Stripe metered billing, paid tiers, and auth are deliberately out of scope until 50+ install signal.

---

## License

MIT — see [LICENSE](LICENSE).
