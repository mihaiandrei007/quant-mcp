# Carrd landing copy — quant-mcp.carrd.co

Source copy for the v0 one-pager. Each `## Section` maps to a Carrd section. Text is short on purpose — Carrd is a one-pager, not a docs site; the README is the deep dive.

---

## Section 1 — Hero (Carrd type: Title + button)

**Title:**

> quant-mcp

**Subtitle / tagline (one line, ≤ 90 chars):**

> Auditable UCITS ETF analytics for your AI client — Claude, Cursor, Continue, and any MCP host.

**Primary button:** `Install →` linking to the `#install` anchor.
**Secondary link:** `View on GitHub` linking to `https://github.com/mihaiandrei007/quant-mcp`.

---

## Section 2 — What you get (Carrd type: Container with 4 columns / icon list)

**Section heading:**

> Four tools, one MCP server.

| Tool | One-line description |
|---|---|
| `ping` | Liveness check — confirms the server is reachable. |
| `compare_etfs` | Two ISINs in, side-by-side metadata + OCF delta + AUM ratio + same-index check out. |
| `get_etf_factors` | 1y / 3y / 5y / 10y annualised return, volatility, Sharpe, max drawdown, Calmar. |
| `monte_carlo_projection` | p10 / p50 / p90 percentile bands across N years for a weighted ETF basket. |

---

## Section 3 — Why this exists (Carrd type: Text)

> Most AI clients can talk to spreadsheets. Few can talk to ETF data with formulas, source URLs, and an audit trail attached. quant-mcp is a thin Model Context Protocol server that wraps a curated UCITS dataset + the standard finance formulas (Sharpe, drawdown, Calmar, weighted Monte Carlo) and exposes them as tools any MCP-compatible client can call.
>
> Every output ships with the formula that produced it, links to issuer factsheets, and a disclaimer. No subjective language. No "buy / sell / hold". Data only — you decide what to do with it.

---

## Section 4 — Install (Carrd type: Code snippet / embed; anchor `#install`)

**Section heading:**

> Install in 60 seconds.

**Pre-snippet text:**

> Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/). Clone the repo, sync deps, then point your MCP client at the directory.

```bash
git clone https://github.com/mihaiandrei007/quant-mcp.git
cd quant-mcp
uv sync
```

Add to `claude_desktop_config.json` (or any MCP client config — same schema):

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

Restart your client → run `/mcp` → confirm `quant-mcp ✓ connected` with 4 tools.

**Footer link under snippet:** `Full install docs (Claude Desktop / Claude Code / Cursor) →` linking to the GitHub README.

---

## Section 5 — Try it (Carrd type: Code snippet)

**Heading:**

> Paste this into your AI client.

```
use monte_carlo_projection with portfolio
[{"isin": "IE00BFMXXD54", "weight": 0.6},
 {"isin": "IE00BK5BQT80", "weight": 0.4}],
years 10, n_sims 2000
```

**Caption under the snippet:**

> Projects a 60/40 VUAA / VWCE basket forward 10 years across 2 000 simulated paths. Returns p10 / p50 / p90 percentile bands per year + terminal multiplier + both disclaimers.

---

## Section 6 — Closing (Carrd type: Text + button)

**Heading:**

> v0 is free.

**Body:**

> 12 curated broad-market UCITS ETFs. MIT licensed. No accounts, no auth, no billing — install it, use it, file an issue if something breaks.

**Primary button:** `Open on GitHub` → `https://github.com/mihaiandrei007/quant-mcp`.

---

## Section 7 — Footer (Carrd type: Text, small)

> Educational tool. Not investment advice. Always verify outputs against issuer factsheets.
>
> Built by [@mihaiandrei007](https://github.com/mihaiandrei007) — feedback welcome.

---

## Carrd build notes

- Use the **Free** plan for the v0 subdomain (`quant-mcp.carrd.co`). Upgrade to **Pro Lite** ($9/yr) only if/when buying a custom domain post 50-install signal.
- Suggested theme: clean / monochrome — match the README's no-hype tone.
- Embed the JSON / bash snippets as **Code** elements, not Text — preserves formatting on mobile.
- After publishing, paste the live URL into:
  - GitHub repo's "Website" field (top-right of repo page)
  - `package.json` / `pyproject.toml` `homepage` (when we add it)
  - mcp.so + claudemarketplaces + aitmpl listings (Session 5)
