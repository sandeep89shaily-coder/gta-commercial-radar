"""Manual Brampton/Mississauga/Toronto official meeting index audit.

Invokes the conservative city-isolated link delta pilot only. Does not infer
projects from links, spend AI, schedule work or touch the main radar DB.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from gta_council_document_delta import run

CITIES = ("Brampton", "Mississauga", "Toronto")
STATUS = "THREE_CITY_COUNCIL_SOURCE_AUDIT.json"


def audit(results, *, fetch_by_city=None, now=None):
    root = Path(results)
    root.mkdir(parents=True, exist_ok=True)
    at = now or dt.datetime.now(dt.timezone.utc)
    cities = []
    for city in CITIES:
        fetch = fetch_by_city.get(city) if fetch_by_city is not None else None
        try:
            status = run(city, root, fetch=fetch, now=at)
        except (OSError, ValueError, RuntimeError) as exc:
            status = {"city": city, "status": "AUDIT_ERROR_NO_SUCCESS_CLAIM",
                      "reason": type(exc).__name__}
        cities.append(status)
    result = {
        "checked_utc": at.astimezone(dt.timezone.utc).isoformat(),
        "cities": cities,
        "cities_checked": len(cities),
        "index_pages_fetched": sum(
            item.get("official_index_status") == "INDEX_FETCHED_LINK_ONLY"
            for item in cities),
        "index_link_collections": sum(
            item.get("valid_individual_document_links", 0) > 0
            for item in cities),
        "cities_with_zero_eligible_document_links": [
            item.get("city") for item in cities
            if item.get("source_gap_review_required")],
        "historical_ineligible_links_retained": sum(
            item.get("legacy_ineligible_links_retained_not_promoted", 0)
            for item in cities),
        "new_publications_verified": 0,
        "verified_new_projects": 0,
        "deepseek_spend_usd": 0,
        "warning": "A fetched calendar index is not document collection. Zero eligible links requires downstream authorized calendar/source adapter review. Historical false links remain audit-only; no new verified projects."
    }
    (root / STATUS).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.out), indent=2))


if __name__ == "__main__":
    main()
