"""Evidence-first municipal health and collector recovery scorecard.

Reads existing *measured* outputs; never polls blocked sources or changes
source ledgers. A configured official page is not working citywide coverage,
and a source-record candidate is not verified fresh purchasing demand.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from gta_early_applications import SOURCES as MAIN_CITIES
from gta_opportunity_lanes import _city, _region

OUTPUT = "GTA_RADAR_MUNICIPAL_RECOVERY_SCORECARD.csv"
STATUS = "GTA_RADAR_MUNICIPAL_RECOVERY_STATUS.json"
COLUMNS = (
    "scope", "municipality", "region", "application_candidate_rows_not_unique",
    "project_only_signals", "private_research_candidates", "top_ten_investigations",
    "blocked_or_failed_sources", "access_failure_details", "source_state",
    "municipality_readiness", "verified_recent_publications",
    "buyer_contacts_verified", "open_supplier_packages_verified",
    "recommended_next_action",
)

SPECIAL_ACTIONS = {
    "Toronto": ("Keep Toronto CKAN as a partial official feed; request an "
                "authorized Application Information Centre export/alternative "
                "rather than bypassing blocked AIC pages; audit historical dates."),
    "Brampton": ("Preserve live permit records; obtain permitted OPA/ZBA and "
                 "site-plan feeds from the City, cross-check official project IDs "
                 "and normalize Peel-labelled Brampton addresses."),
    "Vaughan": ("Await a permitted City planning export/API response; do not "
                "circumvent robots or 403, and keep regional York GIS separate "
                "from municipal application-ID coverage."),
    "Kitchener": ("Await permitted official CSV/GeoJSON access, validate application "
                  "file IDs against City originals and distinguish index-only pages."),
    "Burlington": ("Repeat two separate owner-side official page runs, compare exact "
                   "application IDs, decision stages and original publication dates."),
    "Mississauga": ("Join the existing V6 official site-plan records to municipal "
                    "application and company/source records; verify current stage."),
}


def _read(path):
    if not path.is_file():
        return []
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except (OSError, UnicodeError, csv.Error):
        return []


def _json(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, UnicodeError, ValueError):
        return {}


def _count(value):
    try:
        return max(0, int(value or 0))
    except (ValueError, TypeError):
        return 0


def _csv_safe(value):
    txt = str(value if value is not None else "")
    return "'" + txt if txt.lstrip().startswith(("=", "+", "-", "@")) else txt


def _write(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _csv_safe(row.get(k, "")) for k in COLUMNS})


def _action(city, applications, signals, failures):
    if city in SPECIAL_ACTIONS:
        return SPECIAL_ACTIONS[city]
    if failures:
        return ("Check original official source policy and published download/export "
                "options; retain successful baseline, do not bypass restrictions.")
    if not applications and not signals:
        return ("Locate an original public application list or request an authorized "
                "file-ID export; an index page alone is not coverage.")
    if not applications:
        return ("Recover explicitly labelled application IDs and exact civic sites "
                "from permitted official notices; project links are review-only.")
    if applications < 5:
        return ("Audit exact City file numbers against original notices and check "
                "whether this is a sparse or partial collection.")
    return ("Audit 20 original files across commercial/industrial projects; verify "
            "posting age, status, company role and unawarded work before outreach.")


def build(results):
    root = Path(results)
    if not root.is_dir():
        raise FileNotFoundError("EXISTING_GTA_RADAR_RESULTS_REQUIRED")
    summary = _json(root / "GTA_RADAR_COLLECTION_ACCEPTANCE.json")
    coverage = _json(root / "GTA_RADAR_CITY_COVERAGE_STATUS.json")
    main_acceptance = {x.get("city"): x for x in summary.get("per_city", [])
                       if isinstance(x, dict) and x.get("city")}
    main_coverage = {x.get("city"): x for x in coverage.get("city_status", [])
                     if isinstance(x, dict) and x.get("city")}
    qualified = Counter()
    for q in _read(root / "GTA_RADAR_QUALIFIED_OPPORTUNITY_SHORTLIST.csv"):
        city = _city(q.get("city"), q.get("address"))
        if city in MAIN_CITIES:
            qualified[city] += 1
    investigation = Counter()
    for q in _read(root / "GTA_RADAR_PRIVATE_DEVELOPMENT_REVIEW.csv"):
        city = _city(q.get("city"), q.get("address"))
        if city:
            investigation[city] += 1
    top = Counter()
    for q in _read(root / "GTA_RADAR_PRIVATE_TOP_10.csv"):
        city = _city(q.get("city"), q.get("address"))
        if city:
            top[city] += 1
    rows = []
    for city in MAIN_CITIES:
        health = main_acceptance.get(city, {})
        coverage_row = main_coverage.get(city, {})
        # Use canonical application files, not cumulative source rows.
        apps = _count(health.get("application_files"))
        signals = _count(health.get("project_only_signals"))
        failures = _count(health.get("source_failures"))
        reason = str(health.get("source_notes") or "")[:400]
        if failures:
            readiness = ("PARTIAL_RECORDS_WITH_SOURCE_FAILURES" if apps
                         else "BLOCKED_OR_FAILED_APPLICATION_SOURCES")
        elif apps:
            readiness = "APPLICATION_RECORDS_EXTRACTED_NOT_CITYWIDE_VERIFIED"
        elif signals:
            readiness = "PROJECT_SIGNALS_ONLY_NO_APPLICATION_IDS"
        else:
            readiness = "INDEX_ONLY_OR_NO_APPLICATION_RECORDS"
        if not health and not coverage_row:
            readiness = "NO_CURRENT_OWNER_RUN_EVIDENCE"
        rows.append({
            "scope": "MAIN_16_MEASURED",
            "municipality": city,
            "region": _region(city),
            "application_candidate_rows_not_unique": apps,
            "project_only_signals": signals,
            "private_research_candidates": investigation[city],
            "top_ten_investigations": top[city],
            "blocked_or_failed_sources": failures,
            "access_failure_details": reason,
            "source_state": coverage_row.get("measured_source_state", "NO_STATUS"),
            "municipality_readiness": readiness,
            "verified_recent_publications": 0,
            "buyer_contacts_verified": 0,
            "open_supplier_packages_verified": 0,
            "recommended_next_action": _action(city, apps, signals, failures),
        })

    # Experimental GGH and next-four sources are explicitly separate from
    # measured original coverage; same city in two pilots cannot be double counted.
    extra = (
        ("EXPERIMENTAL_GGH_12", _json(root/"GTA_RADAR_GGH_EXPANSION_SOURCE_STATUS.json")),
        ("EXPERIMENTAL_NEXT_4", _json(root/"GTA_RADAR_NEXT_FOUR_MUNICIPALITIES_STATUS.json")),
    )
    for scope, status in extra:
        for city_row in status.get("source_status", []):
            if not isinstance(city_row, dict) or not city_row.get("city"):
                continue
            city = str(city_row["city"])
            apps = _count(city_row.get("application_id_rows"))
            signals = _count(city_row.get("project_only_signals"))
            source_state = str(city_row.get("status") or city_row.get("state") or "UNKNOWN")
            error = str(city_row.get("error") or "")[:400]
            failed = source_state in ("FAILED", "SOURCE_ACCESS_OR_PARSE_BLOCKED")
            readiness = ("PILOT_SOURCE_FAILED_HOLD" if failed
                         else "PILOT_APPLICATION_IDS_NEED_ACCEPTANCE" if apps
                         else "PILOT_PROJECT_ONLY_NOT_COVERAGE" if signals
                         else "PILOT_INDEX_ONLY_NOT_COVERAGE")
            rows.append({
                "scope": scope, "municipality": city, "region": _region(city),
                "application_candidate_rows_not_unique": apps,
                "project_only_signals": signals,
                "private_research_candidates": 0, "top_ten_investigations": 0,
                "blocked_or_failed_sources": int(failed),
                "access_failure_details": error,
                "source_state": source_state,
                "municipality_readiness": readiness,
                "verified_recent_publications": 0,
                "buyer_contacts_verified": 0,
                "open_supplier_packages_verified": 0,
                "recommended_next_action": _action(city, apps, signals, int(failed)),
            })
    _write(root / OUTPUT, rows)
    primary = [r for r in rows if r["scope"] == "MAIN_16_MEASURED"]
    pilots = [r for r in rows if r["scope"] != "MAIN_16_MEASURED"]
    data = {
        "status": "SOURCE_QUALITY_SCORECARD_REVIEW_ONLY",
        "main_municipalities_configured": len(MAIN_CITIES),
        "main_municipalities_with_application_records": sum(
            r["application_candidate_rows_not_unique"] > 0 for r in primary),
        "main_municipalities_with_failed_sources": sum(
            r["blocked_or_failed_sources"] > 0 for r in primary),
        "main_municipalities_with_no_applications": sum(
            r["application_candidate_rows_not_unique"] == 0 for r in primary),
        "experimental_city_source_rows_not_added_to_main": len(pilots),
        "regions_with_balanced_investigation_slots": sorted({
            r["region"] for r in primary if r["top_ten_investigations"]
        }),
        "citywide_coverage_verified": 0,
        "fresh_publication_and_buyer_validation_in_this_stage": False,
        "paid_ai_calls": 0, "automated_outreach": False,
        "source": {
            "main_collection_acceptance": "GTA_RADAR_COLLECTION_ACCEPTANCE.json",
            "city_coverage": "GTA_RADAR_CITY_COVERAGE_STATUS.json",
            "qualifications": "GTA_RADAR_QUALIFIED_OPPORTUNITY_SHORTLIST.csv",
            "private_research_queue": "GTA_RADAR_PRIVATE_DEVELOPMENT_REVIEW.csv",
            "private_shortlist": "GTA_RADAR_PRIVATE_TOP_10.csv",
        },
        "output_csv": OUTPUT,
        "warning": (
            "Candidate numbers reflect stored source evidence, not municipality-wide "
            "completeness or fresh publications. No buyer, tender, contact consent "
            "or available supplier scope was verified by this read-only scorecard. "
            "Experimental city pilots do not increase the verified 16-city numerator."
        ),
    }
    (root / STATUS).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.results), indent=2))
