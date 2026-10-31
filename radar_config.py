"""Single source of truth for shared GTA Radar settings.

Change the DeepSeek daily ceiling HERE and nowhere else. Every investigator,
ledger check, dashboard label and test reads it from this module.
"""
from __future__ import annotations

# US$ per day across ALL paid DeepSeek work (shared ledger). Debugging-phase
# ceiling; raise it only after the system produces verified commercial leads.
DEEPSEEK_DAILY_LIMIT_USD = 0.25


def budget_label(prefix: str = "US$") -> str:
    """Human-readable ceiling for dashboards, e.g. 'US$0.25'."""
    return f"{prefix}{DEEPSEEK_DAILY_LIMIT_USD:.2f}"
