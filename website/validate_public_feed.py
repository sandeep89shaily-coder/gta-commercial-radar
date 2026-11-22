"""Validate the curated five-day public website feed before GitHub Pages deployment.

A research-only CSV is never equivalent to operator-approved publication.
This module is deliberately read-only and never contacts external services.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlsplit

SITE = Path(__file__).resolve().parent
DATA = SITE / "data" / "opportunities.json"
LANES = {"industrial_equipment", "commercial_development"}
MAX_BYTES = 4_000_000
MAX_RECORDS = 5000
TEXT_FIELDS = ("id", "title", "city", "scope", "source_project_id",
               "stage", "date_basis", "company", "address", "first_seen",
               "observation")
SAFE_KEYS = set(TEXT_FIELDS) | {
    "lane", "source_url", "source_date",
    "approved_for_publication", "rights_checked", "source_checked",
    "first_publication_verified", "buyer_verified",
    "open_supplier_package_verified"
}

def date(value):
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError("Date must have YYYY-MM-DD format")
    try:
        parsed = dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Invalid calendar date") from exc
    if parsed.isoformat() != value:
        raise ValueError("Date must have YYYY-MM-DD format")
    return parsed

def official_https(value):
    if not isinstance(value, str) or len(value) > 1600:
        return False
    try:
        u = urlsplit(value)
    except ValueError:
        return False
    return (u.scheme == "https" and bool(u.hostname)
            and not u.username and not u.password and not u.fragment
            and not any(c.isspace() for c in value))

def validate(path=DATA):
    path = Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_BYTES:
        raise ValueError("MISSING_OR_UNSAFE_PUBLIC_FEED")
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(obj, dict) or obj.get("schema_version") != 1:
        raise ValueError("BAD_PUBLICATION_SCHEMA")
    if obj.get("window_days") != 5:
        raise ValueError("WINDOW_MUST_BE_FIVE_CALENDAR_DAYS")
    entries = obj.get("records")
    if not isinstance(entries, list) or len(entries) > MAX_RECORDS:
        raise ValueError("INVALID_OR_OVERSIZED_PUBLIC_RECORDS")
    issued = obj.get("published_on") or ""
    if entries and not issued:
        raise ValueError("PUBLICATION_DATE_REQUIRED")
    day = date(issued) if issued else None
    seen = set()
    for i, row in enumerate(entries):
        if not isinstance(row, dict) or not set(row).issubset(SAFE_KEYS):
            raise ValueError(f"UNAPPROVED_PUBLIC_FIELDS:{i}")
        required = ("id", "lane", "title", "city", "scope", "source_url", "source_date")
        if not all(isinstance(row.get(k), str) and row.get(k).strip()
                   for k in required):
            raise ValueError(f"MISSING_SOURCE_OR_IDENTITY:{i}")
        if row["id"] in seen or len(row["id"]) > 420:
            raise ValueError(f"DUPLICATE_OR_OVERSIZED_ID:{i}")
        seen.add(row["id"])
        if row["lane"] not in LANES:
            raise ValueError(f"UNKNOWN_OPPORTUNITY_LANE:{i}")
        if any(not isinstance(row.get(k), str) or len(row[k]) > cap
               for k, cap in (("title", 180), ("city", 90),
                              ("scope", 1050))):
            raise ValueError(f"OVERSIZED_OR_INVALID_PUBLIC_TEXT:{i}")
        if not official_https(row["source_url"]):
            raise ValueError(f"UNSAFE_OR_MISSING_SOURCE_URL:{i}")
        if any(row.get(flag) is not True for flag in (
                "approved_for_publication", "source_checked", "rights_checked")):
            raise ValueError(f"EXPLICIT_EDITORIAL_APPROVAL_REQUIRED:{i}")
        if any(row.get(flag) is not False for flag in (
                "first_publication_verified", "buyer_verified",
                "open_supplier_package_verified")):
            raise ValueError(f"UNSUPPORTED_VERIFICATION_CLAIM:{i}")
        source_day = date(row["source_date"])
        if day is None or not 0 <= (day - source_day).days <= 4:
            raise ValueError(f"STALE_OR_FUTURE_SOURCE_DATE:{i}")
        for field in TEXT_FIELDS:
            value = row.get(field, "")
            if not isinstance(value, str) or len(value) > 1100:
                raise ValueError(f"INVALID_PUBLIC_TEXT:{i}:{field}")
    return {"records":len(entries), "published_on":issued,
            "window_days":5, "validated":True}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DATA)
    args = parser.parse_args()
    print(json.dumps(validate(args.file), indent=2))

if __name__ == "__main__":
    main()
