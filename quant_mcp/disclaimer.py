"""
Single source of truth for the disclaimer texts returned by every tool.

Mirrored verbatim from `etf-dashboard/lib/disclaimer.py` so a buyer who uses
both products sees identical legal posture. If the source ever changes,
update this copy too — do not divergence-edit.
"""
from __future__ import annotations

DISCLAIMER_TEXT = (
    "This tool provides historical analysis and educational content only. "
    "It is not investment advice. Consult a licensed financial advisor "
    "before making investment decisions. Past performance does not predict "
    "future results."
)

MONTE_CARLO_DISCLAIMER = (
    "This visualisation assumes returns are normally distributed (they are "
    "not — real markets have fat tails). The 10/50/90 percentile bands are "
    "a teaching tool to illustrate the dispersion of outcomes implied by "
    "the chosen mean and volatility. They are not predictions."
)
