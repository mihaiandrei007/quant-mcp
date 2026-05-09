"""
Curated UCITS ETF metadata loader.

The MCP tools resolve user-supplied ISINs against this list. The list is
deliberately small (~12 broad-market UCITS ETFs) — same philosophy as
etf-dashboard's curated_funds: surface a small set of well-understood,
low-cost, broad-market funds rather than thousands of narrow-theme ETFs.

Source of truth: `data/curated_etfs.json`. Loaded once on first access and
cached in-process. Restart the MCP server to pick up edits.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "curated_etfs.json"


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    with _DATA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def all_etfs() -> list[dict[str, Any]]:
    return list(_load()["etfs"])


def supported_isins() -> list[str]:
    return [e["isin"] for e in _load()["etfs"]]


def lookup_by_isin(isin: str) -> dict[str, Any] | None:
    """Return the curated ETF record for an ISIN (case-insensitive), or None."""
    needle = isin.strip().upper()
    for etf in _load()["etfs"]:
        if etf["isin"].upper() == needle:
            return etf
    return None


def dataset_as_of() -> str:
    """ISO date when the curated metadata snapshot was taken."""
    return _load()["as_of"]
