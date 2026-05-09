# 90-second Loom demo script — quant-mcp

**Goal:** show a stranger that the MCP connects, lists 4 tools, and produces a real, formula-backed payload from a single prompt that exercises 2 tools. No editing tricks, no time-lapses — one continuous take.

**Recording setup:** Loom desktop app, 1080p, system audio off (no music), microphone on, webcam bubble bottom-right (small).

---

## Pre-recording checklist

- [ ] `claude_desktop_config.json` already has the `quant-mcp` block; restart Claude Desktop **before** hitting record so the MCP is fresh.
- [ ] Open Claude Desktop on a new conversation. Don't pre-load history — the demo should look first-run.
- [ ] Browser tab open to the GitHub repo (you'll alt-tab to it once at the end).
- [ ] Caps Lock off, notifications muted (Do Not Disturb on macOS / Focus Assist on Windows).
- [ ] Have the prompt ready in a scratch text file so you can paste it cleanly without typos.

---

## Timing budget

| Time | Beat |
|---|---|
| 0:00 – 0:10 | **Hook.** What this is, in 1 sentence. |
| 0:10 – 0:25 | `/mcp` shows the 4 tools. |
| 0:25 – 1:05 | One prompt that calls 2 tools (compare → Monte Carlo). |
| 1:05 – 1:30 | Show the payload's formula + disclaimer fields. CTA. |

---

## Script (read out loud while recording)

### 0:00 – 0:10 (Hook — face on cam, Claude Desktop visible)

> "This is quant-mcp — a Model Context Protocol server that gives Claude four ETF analytics tools. I'm going to show you the install working and one prompt that runs two of the tools end to end. About a minute."

### 0:10 – 0:25 (Slash-command `/mcp`)

**Action:** Type `/mcp` in Claude Desktop and hit enter.

> "First — the server is connected. Four tools listed: ping, compare_etfs, get_etf_factors, monte_carlo_projection. I configured this with one JSON block in claude_desktop_config — install instructions are in the README."

**On-screen:** the `/mcp` output. Pause for 2 seconds so the viewer can read the tool list.

### 0:25 – 1:05 (Combined prompt)

**Action:** Paste this prompt into the chat box and hit send:

```
Compare VUAA (IE00BFMXXD54) and CSPX (IE00B5BMR087) using compare_etfs,
then run a 10-year monte_carlo_projection on a 60% VUAA, 40% VWCE
(IE00BK5BQT80) basket with 2000 simulations.
```

> "I'm asking it to compare two S&P 500 trackers — VUAA and CSPX — then run a Monte Carlo on a 60/40 VUAA / VWCE basket. Claude calls compare_etfs first…"

**Wait** for `compare_etfs` tool call to render. Hover over or scroll-highlight the response.

> "…and we get OCF delta in basis points, the AUM ratio, and same_index equals true — both track the S&P 500. Then it calls monte_carlo_projection…"

**Wait** for `monte_carlo_projection` tool call to render.

> "…and we get percentile bands across ten years. Median terminal multiplier around 2.7-ish, with the p10 and p90 bracketing the spread."

### 1:05 – 1:30 (Audit trail + CTA)

**Action:** Scroll the second response to the `formulas` and `disclaimer` blocks.

> "Notice — every metric has its formula returned in the payload. There's the Sharpe formula, the path equation. And both disclaimers — the standard one plus the Monte Carlo fat-tail caveat. No buy / sell language anywhere. Data only."

**Action:** Alt-tab to the GitHub repo tab.

> "Repo is github-dot-com slash my-username slash quant-mcp. MIT licensed, twelve curated UCITS ETFs in v0, install instructions in the README. Link in the description. Thanks."

**Stop recording.**

---

## Post-recording

- Trim only the leading silence and trailing tail. Do not cut anything in the middle — a continuous take is the whole point.
- Title: `quant-mcp — 90-second demo`
- Description: ≤ 300 chars. Include the GitHub link, "MIT licensed, no auth, no billing", and a one-line CTA "install it and try the prompt above."
- Generate a Loom thumbnail showing the 4-tool `/mcp` output frame (it's the most read-at-a-glance moment).
- Privacy: Public, "anyone with the link". Embed code goes into the Carrd landing + the GitHub README (replace the badge area).

---

## If something goes wrong mid-take

- `/mcp` doesn't show 4 tools → stop, restart Claude Desktop, re-record. Don't ship a take that shows the server unconfirmed.
- A tool returns `error: no_price_data` → likely yfinance hiccup. Retry once; if it fails twice, switch the prompt to use `get_etf_factors` on `IE00B4L5Y983` (IWDA) which has a longer Yahoo history than the `.DE` tickers.
- Latency > 8 seconds on a tool call → cut and re-record. Viewer attention falls off a cliff at 10 seconds of dead air.
