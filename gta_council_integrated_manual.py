"""One optional, review-only council item stage in GTA Radar's manual full run.

Runs existing three-city official index audit and the three *distinct* item
extractors over explicitly registered local source documents. No second Radar
collection, no scheduling, no paid AI, no implicit PDF downloads or leads.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from gta_three_city_council_audit import audit as audit_indexes
from gta_toronto_agenda_item_extraction import build as toronto_items
from gta_brampton_bookmarked_agenda import inspect as brampton_items
from gta_mississauga_pdc_agenda import run as mississauga_items, OUT as MISS_CSV
from gta_agenda_application_permit_20_case import run as compare_20

CONFIG = "GTA_RADAR_COUNCIL_INPUTS.json"
STATUS = "COUNCIL_INTEGRATED_REVIEW_STATUS.json"
ALLOWED = {"Toronto", "Brampton", "Mississauga"}
MAX_DOCS = 20


def _local_path(workspace, raw):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("LOCAL_SOURCE_PATH_REQUIRED")
    root = Path(workspace).resolve()
    path = Path(raw)
    path = (path if path.is_absolute() else root / path).resolve()
    # Source files are explicitly owner-provided local evidence; do not let
    # config load arbitrary paths outside the selected workspace.
    if not path.is_relative_to(root):
        raise ValueError("SOURCE_OUTSIDE_WORKSPACE")
    return path


def _inputs(workspace):
    config = Path(workspace) / CONFIG
    if not config.is_file():
        return [], None, None, "NO_SOURCE_MANIFEST_REGISTERED"
    if config.stat().st_size > 128_000:
        raise ValueError("OVERSIZED_SOURCE_MANIFEST")
    obj = json.loads(config.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or obj.get("version") != 1:
        raise ValueError("INVALID_COUNCIL_SOURCE_MANIFEST")
    entries = obj.get("documents", [])
    if not isinstance(entries, list) or len(entries) > MAX_DOCS:
        raise ValueError("INVALID_COUNCIL_DOCUMENT_LIST")
    for item in entries:
        if not isinstance(item, dict) or item.get("city") not in ALLOWED:
            raise ValueError("UNEXPECTED_COUNCIL_DOCUMENT_CITY")
    exports = obj.get("matching_exports") or {}
    if not isinstance(exports, dict):
        raise ValueError("INVALID_MATCHING_EXPORTS")
    return entries, exports.get("applications_csv"), exports.get("permits_csv"), "SOURCE_MANIFEST_LOADED"


def execute(workspace, results, *, index_auditor=None):
    root = Path(workspace).resolve()
    out = Path(results).resolve() / "COUNCIL_INTELLIGENCE_REVIEW"
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "mode": "REVIEW_ONLY_THREE_CITY_COUNCIL_INTELLIGENCE",
        "run_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "REVIEW_ONLY",
        "cities": {}, "documents_considered": 0,
        "documents_parsed": 0, "source_documents_missing": 0,
        "source_documents_failed": 0, "source_documents_held": 0,
        "agenda_to_application_permit_chains_verified": 0,
        "publisher_first_publications_verified": 0,
        "commercial_buyers_verified": 0, "paid_ai_usd": 0,
        "notices": [],
        "warning": "Council indexes and downloaded document content are different evidence levels. Nothing here is a verified project, first-publication date, buyer or procurement opportunity."
    }

    # A source/index failure does not erase previously saved item research.
    try:
        check = (index_auditor or audit_indexes)(out / "SOURCE_INDEX")
        report["official_index_audit"] = {
            "cities_checked": check.get("cities_checked", 0),
            "index_link_collections": check.get("index_link_collections", 0),
            "statuses": [
                {"city": row.get("city"), "status": row.get("status"),
                 "source_status": row.get("official_index_status")}
                for row in check.get("cities", [])
            ]
        }
    except Exception as exc:
        report["official_index_audit"] = {
            "status": "SOURCE_INDEX_AUDIT_FAILED",
            "reason": type(exc).__name__
        }
        report["notices"].append("SOURCE_INDEX_AUDIT_FAILED")

    try:
        documents, applications, permits, origin = _inputs(root)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        documents, applications, permits = [], None, None
        origin = "INVALID_SOURCE_MANIFEST"
        report["notices"].append(type(exc).__name__)
        report["status"] = "SOURCE_MANIFEST_HELD"
    report["source_manifest_status"] = origin
    mississauga_files = []
    for i, item in enumerate(documents):
        city = item["city"]
        docid = "doc_" + str(i + 1).zfill(2)
        entry = {"id": docid, "status": "HOLD", "reason": "",
                 "source_type": city}
        report["documents_considered"] += 1
        report["cities"].setdefault(city, {"considered": 0, "parsed": 0})
        report["cities"][city]["considered"] += 1
        try:
            source = _local_path(root, item.get("file"))
            if not source.is_file():
                entry["reason"] = "REGISTERED_LOCAL_SOURCE_NOT_FOUND"
                report["source_documents_missing"] += 1
            else:
                folder = out / city.upper() / docid
                if city == "Toronto":
                    result = toronto_items(source, item["meeting_url"], folder)
                    count = result["item_count"]
                    level = "SAVED_TMMIS_HTML_ITEM_HEADINGS"
                elif city == "Brampton":
                    result = brampton_items(
                        source, meeting_url=item["meeting_url"],
                        agenda_pdf_url=item["agenda_pdf_url"], results=folder)
                    count = result["bookmarks_parsed"]
                    level = "SAVED_BRAMPton_PDF_BOOKMARKS"
                else:
                    result = mississauga_items(source, item["agenda_pdf_url"], folder)
                    count = result["toc_items"]
                    level = "SAVED_ESCRIBE_PDF_AGENDA_ITEMS"
                    if result["status"] == "REVIEW_ONLY_ITEM_EXTRACTION":
                        mississauga_files.append(folder / MISS_CSV)
                if count == 0 or (
                        city == "Mississauga"
                        and result["status"] != "REVIEW_ONLY_ITEM_EXTRACTION"):
                    entry["reason"] = "NO_ITEM_STRUCTURE_RECOVERED_REQUIRES_REVIEW"
                    report["source_documents_held"] += 1
                else:
                    entry.update(status="PARSED_REVIEW_ONLY",
                                 items=count, evidence_level=level)
                    report["documents_parsed"] += 1
                    report["cities"][city]["parsed"] += 1
        except (KeyError, OSError, ValueError, TypeError, RuntimeError) as exc:
            entry["reason"] = "SOURCE_PARSE_FAILED_" + type(exc).__name__
            report["source_documents_failed"] += 1
        report["notices"].append(entry)

    # Do not call the identity join on a synthetic or absent agenda export.
    # A missing CSV is handled by the join itself, which explicitly reports HOLD.
    if mississauga_files:
        try:
            apps = _local_path(root, applications) if applications else None
            pts = _local_path(root, permits) if permits else None
            report["mississauga_20_case_comparison"] = compare_20(
                mississauga_files, apps, pts, out / "MATCHING_REVIEW", limit=20)
        except (OSError, ValueError, TypeError) as exc:
            report["mississauga_20_case_comparison"] = {
                "status": "MATCHING_REVIEW_HELD",
                "reason": type(exc).__name__, "source_verified_same_project_matches": 0,
                "early_detection_advantage_proven": False}
            report["source_documents_held"] += 1
    else:
        report["mississauga_20_case_comparison"] = {
            "status": "NO_ACTUAL_MISSISSAUGA_AGENDA_ITEMS_TO_COMPARE",
            "cases_reviewed": 0, "source_verified_same_project_matches": 0,
            "early_detection_advantage_proven": False}

    if report["source_documents_failed"] or report["source_documents_missing"] or report["source_documents_held"]:
        report["status"] = "PARTIAL_SOURCE_REVIEW_HOLDS"
    if origin == "INVALID_SOURCE_MANIFEST":
        report["status"] = "SOURCE_MANIFEST_HELD"
    (out / STATUS).write_text(json.dumps(report, indent=2),
                              encoding="utf-8")
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--workspace", required=True)
    cli.add_argument("--results", required=True)
    args = cli.parse_args()
    report = execute(args.workspace, args.results)
    print(json.dumps({
        "status": report["status"],
        "documents_considered": report["documents_considered"],
        "documents_parsed": report["documents_parsed"],
        "mississauga_matching": report["mississauga_20_case_comparison"],
        "paid_ai_usd": report["paid_ai_usd"]
    }, indent=2))


if __name__ == "__main__":
    main()
