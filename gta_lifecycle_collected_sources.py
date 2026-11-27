"""Check the watchlist against public evidence already collected by Radar today."""

import csv
import datetime as dt
import re
from urllib.parse import urlsplit

from gta_freshness import _date
from gta_utility_milestones import OUTPUT as UTILITY_MILESTONES

SOURCES = {
    "GTA_RADAR_UNIFIED_MUNICIPAL_DAILY_CHANGES.csv":
        ("source_record_date", "record_source_url", ("description", "company_name", "current_status")),
    "GTA_RADAR_FRESH_INDUSTRIAL_ANNOUNCEMENTS.csv":
        ("publisher_reported_date", "source_url", ("title", "industrial_scope_quote")),
    "GTA_RADAR_FULLTEXT_EQUIPMENT_FRESH_RESEARCH.csv":
        ("publisher_reported_date", "source_url", ("title", "scope_quote", "project_scope_quote",
                                                  "industrial_scope_quote", "equipment_excerpt")),
    "GTA_RADAR_EQUIPMENT_COMMERCIAL_INDEX.csv":
        ("source_date", "source_url", ("company", "equipment_or_scope", "municipality")),
    UTILITY_MILESTONES:
        ("source_event_date", "source_url", ("company", "title", "scope", "location")),
}


def _normalize(text):
    return " ".join(re.findall(r"[^\W_]+", text.casefold()))


def scan(root, projects, day, not_before):
    """Return source-dated name matches for human review and explicit coverage."""
    files = {}
    evidence = []
    for filename, (date_col, url_col, scope_cols) in SOURCES.items():
        path = root / filename
        if (not path.is_file() or path.is_symlink() or path.stat().st_mtime < not_before
                or path.stat().st_size > 20_000_000):
            continue
        files[filename] = 0
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                date = _date(row.get(date_col))
                url = (row.get(url_col) or "").strip()
                if not (date and day - dt.timedelta(days=4) <= date <= day):
                    continue
                try:
                    parsed = urlsplit(url)
                    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                        continue
                except ValueError:
                    continue
                scope = " ".join(row.get(field) or "" for field in scope_cols).strip()
                if not scope:
                    continue
                files[filename] += 1
                evidence.append((_normalize(scope), {
                    "source_url": url, "source_event_date": date.isoformat(),
                    "source_feed": filename, "source_excerpt": scope[:500],
                }))
    results = {}
    for project in projects:
        names = {_normalize(project.get(field) or "") for field in ("name", "search_name")}
        names = {name for name in names if len(name) >= 4}
        location = _normalize((project.get("location") or "").split(" / ")[0])
        mentions = {}
        for text, record in evidence:
            padded = f" {text} "
            if any(f" {name} " in padded and
                   (" " in name or (location and f" {location} " in padded))
                   for name in names):
                mentions[(record["source_url"], record["source_event_date"])] = record
        results[project["project_id"]] = list(mentions.values())
    return files, results
