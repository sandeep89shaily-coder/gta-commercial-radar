"""Prioritize uncertain, sourced commercial projects for the existing AI executor.

The model still has NO authority to verify buyer or supplier availability.
Ranking is based on source record (not model claims), source-event age and
sector; it never converts Radar first observation into a publication date.
The executor enforces the unchanged shared US$1 daily software cap.
"""
from __future__ import annotations

import datetime as dt
import re

from gta_freshness import assess as source_freshness

INDUSTRIAL = re.compile(
    r"\b(industrial|manufactur\w*|warehouse|logistics|distribution|"
    r"data cent(?:er|re)|factory|production line|cleanroom|"
    r"processing plant|cold storage|laborator\w*|self[- ]storage)\b", re.I)
COMMERCIAL = re.compile(
    r"\b(hotel|retail|office|restaurant|commercial|shopping|"
    r"grocery|medical clinic)\b", re.I)
RESIDENTIAL = re.compile(
    r"\b(residential|condominium|dwelling|apartments?|rental units)\b", re.I)


def key(row, score, today=None):
    """Small deterministic lexicographic sort; lower tuple is researched first."""
    today = today or dt.date.today()
    freshness = source_freshness(row, today=today)
    text = str(row.get("description") or "")
    if INDUSTRIAL.search(text):
        sector = 0
    elif COMMERCIAL.search(text):
        sector = 1
    elif RESIDENTIAL.search(text):
        sector = 4
    else:
        sector = 2
    status = str(row.get("current_source_status") or "").casefold()
    if any(x in status for x in ("under review", "application received", "pending",
                                  "applied", "pre-consultation")):
        lifecycle = 0
    elif any(x in status for x in ("completed", "issued", "final", "occupancy")):
        lifecycle = 3
    else:
        lifecycle = 1
    # Source event freshness first; then sector fit. No AI-generated dates,
    # claimed buyer roles or first-seen timestamps can improve the rank.
    return (freshness["freshness_sort_bucket"], sector, lifecycle,
            -score["score"], str(row.get("project_id") or ""))
