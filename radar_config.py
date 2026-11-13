"""Single source of truth for shared GTA Radar settings.

Change the DeepSeek daily ceiling HERE and nowhere else. Every investigator,
ledger check, dashboard label and test reads it from this module.
"""
from __future__ import annotations

# US$ per day across ALL paid DeepSeek work (shared ledger). Debugging-phase
# ceiling for Phase 2 research. This is a local software cap, NOT a provider-side spending limit.
DEEPSEEK_DAILY_LIMIT_USD = 2.00


def budget_label(prefix: str = "US$") -> str:
    """Human-readable ceiling for dashboards, e.g. 'US$2.00'."""
    return f"{prefix}{DEEPSEEK_DAILY_LIMIT_USD:.2f}"
