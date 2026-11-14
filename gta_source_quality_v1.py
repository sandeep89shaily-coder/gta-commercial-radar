"""Read-only source quality scorecard for the existing Radar daily collection.

No network, AI, outreach, SQLite access or edits to source evidence.
A stage reporting PASSED is not proof of citywide or source completeness.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path

INPUT = "GTA_RADAR_COLLECTION_HEALTH.csv"
OUTPUT = "GTA_RADAR_SOURCE_QUALITY_V1.json"
CITIES = (
    "Toronto", "Brampton", "Mississauga", "Hamilton", "Burlington",
    "Oakville", "Vaughan", "Kitchener", "Markham", "Oshawa", "Milton",
    "Halton Hills", "Caledon", "Cambridge", "Waterloo", "Guelph",
)
FIELDS = {"city", "application_files", "official_sources_with_records",
          "source_failures", "access_failures", "quality_status"}


def _number(raw):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError("INVALID_SOURCE_COUNT") from None
    if value < 0:
        raise ValueError("NEGATIVE_SOURCE_COUNT")
    return value


def build(results: Path, *, generated_at=None):
    """Summarize source evidence without inventing coverage/freshness dates."""
    results = Path(results)
    source = results / INPUT
    if not source.is_file():
        return {"status": "NO_CURRENT_HEALTH_CSV", "cities": [],
                "citywide_verified": 0, "warning": "No evidence of completeness"}
    with source.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not FIELDS.issubset(reader.fieldnames):
            raise ValueError("HEALTH_CSV_SCHEMA_MISMATCH")
        rows = list(reader)
    seen = {}
    for raw in rows:
        name = (raw.get("city") or "").strip()
        if name not in CITIES or name in seen:
            raise ValueError("DUPLICATE_OR_UNKNOWN_CITY")
        counts = {k: _number(raw.get(k)) for k in (
            "application_files", "official_sources_with_records",
            "source_failures", "access_failures")}
        if counts["access_failures"] > counts["source_failures"]:
            raise ValueError("ACCESS_FAILURE_COUNT_CONFLICT")
        seen[name] = {
            "city": name,
            **counts,
            "quality_status": (raw.get("quality_status") or "").strip(),
            "source_notes": (raw.get("source_notes") or "")[:500],
            "data_present": bool(counts["application_files"]),
            "citywide_complete": False,
            "source_freshness_verified": False,
            "new_buyer_leads_verified": False,
        }
    cities = [seen.get(name, {
        "city": name, "application_files": 0,
        "official_sources_with_records": 0, "source_failures": 0,
        "access_failures": 0, "quality_status": "NO_HEALTH_ROW",
        "source_notes": "", "data_present": False,
        "citywide_complete": False, "source_freshness_verified": False,
        "new_buyer_leads_verified": False,
    }) for name in CITIES]
    return {
        "status": "EVIDENCE_ONLY_NOT_CITYWIDE_VERIFIED",
        "generated_utc": generated_at or dt.datetime.now(dt.timezone.utc).isoformat(),
        "input": INPUT,
        "municipalities_targeted": len(CITIES),
        "municipalities_with_records": sum(c["data_present"] for c in cities),
        "municipalities_with_source_access_failures": sum(c["access_failures"] > 0 for c in cities),
        "application_files_reported": sum(c["application_files"] for c in cities),
        "citywide_verified": 0,
        "buyer_leads_verified": 0,
        "warning": ("Application file counts are not unique verified projects, "
                    "fresh public disclosures, or actionable buyer leads. "
                    "A city with records is NOT citywide complete."),
        "cities": cities,
    }


def run(results: Path):
    path = Path(results) / OUTPUT
    report = build(results)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    report = run(Path(args.results))
    print(json.dumps({k: v for k, v in report.items() if k != "cities"},
                     indent=2))
