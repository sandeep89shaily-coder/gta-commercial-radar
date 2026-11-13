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
from gta_brampton_featured_pdc import run as collect_featured
from gta_mississauga_discovered_pdc_run import run as collect_mississauga_discovered
from gta_toronto_tmmis_authorized_agendas import run as fetch_toronto_agendas
from toronto_tmmis_documents import agenda_url
from gta_toronto_official_schedule import run as collect_toronto_schedule

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


def _toronto_meeting_urls(workspace):
    config = Path(workspace) / CONFIG
    if not config.is_file():
        return []
    data = json.loads(config.read_text(encoding="utf-8"))
    urls = data.get("toronto_meeting_urls", [])
    if not isinstance(urls, list) or len(urls) > 3:
        raise ValueError("INVALID_TORONTO_MEETING_URL_LIST")
    if any(not isinstance(url, str) or not agenda_url(url) for url in urls):
        raise ValueError("NON_OFFICIAL_TORONTO_MEETING_URL")
    return urls


def execute(workspace, results, *, index_auditor=None, fetch_brampton_featured=False,
            featured_collector=None, fetch_mississauga_pdc=False,
            mississauga_discovered_collector=None,
            fetch_toronto_official_agendas=False, toronto_fetcher=None,
            fetch_toronto_schedule=False, schedule_collector=None):
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

    # Separate first-party Brampton planning featured-application source.
    # This does not require the operator's locally saved agenda PDFs; the
    # public source is read only after explicit --fetch-brampton-featured
    # on the MANUAL launcher and passes robots/DNS/source policy checks.
    if fetch_brampton_featured:
        try:
            featured = (featured_collector or collect_featured)(
                out / "BRAMPTON_FEATURED_PDC", fetch=True)
            report["brampton_featured_public_applications"] = {
                key: featured.get(key) for key in (
                    "status", "cards_parsed", "commercial_keyword_cards_review_only",
                    "newly_observed_cards_not_new_publications",
                    "changed_cards_not_new_projects", "first_publications_verified",
                    "paid_ai_calls", "failure_type")
            }
        except Exception as exc:
            report["brampton_featured_public_applications"] = {
                "status": "SOURCE_FAILURE_HELD",
                "reason": type(exc).__name__, "verified_projects": 0}
    else:
        report["brampton_featured_public_applications"] = {
            "status": "NOT_REQUESTED_IN_THIS_STAGE", "verified_projects": 0}
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
                    level = "SAVED_BRAMPTON_PDF_BOOKMARKS"
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

    # Pass only actual, presently observed official PDC links through the
    # explicit bounded robots-checked eSCRIBE PDF fetch path.
    if fetch_mississauga_pdc:
        try:
            discovered = (mississauga_discovered_collector
                          or collect_mississauga_discovered)(
                out / "SOURCE_INDEX", out / "MISSISSAUGA_DISCOVERED_PDC", fetch=True)
            report["mississauga_discovered_pdc"] = {
                key: discovered.get(key) for key in (
                    "status", "source_status", "eligible_pdc_links",
                    "selected_for_fetch", "captured_pdfs", "parsed_agenda_pdfs",
                    "paid_ai_calls", "fetch_statuses", "error_type")
            }
            mississauga_files.extend(Path(path) for path in
                                     discovered.get("agenda_item_csvs", []))
            if (discovered.get("status") not in (
                    "EXTRACTED_REVIEW_ONLY",)
                    and discovered.get("eligible_pdc_links", 0)):
                report["source_documents_held"] += 1
        except Exception as exc:
            report["mississauga_discovered_pdc"] = {
                "status": "SOURCE_FAILURE_HELD",
                "reason": type(exc).__name__, "captured_pdfs": 0}
            report["source_documents_held"] += 1
    else:
        report["mississauga_discovered_pdc"] = {
            "status": "NOT_REQUESTED", "captured_pdfs": 0}

    # Toronto City Clerk official open-data meeting schedule: upstream
    # meeting-date inventory, *not* dynamic agenda or project discovery.
    if fetch_toronto_schedule:
        try:
            scheduled = (schedule_collector or collect_toronto_schedule)(
                out / "TORONTO_OFFICIAL_MEETING_SCHEDULE", fetch=True)
            report["toronto_official_meeting_schedule"] = {
                key: scheduled.get(key) for key in (
                    "status", "schedule_rows_read", "recent_scheduled_meetings",
                    "high_priority_committee_meetings", "agenda_urls_discovered",
                    "publisher_first_publications_verified", "paid_ai_calls",
                    "error_type", "error_reason")
            }
        except Exception as exc:
            report["toronto_official_meeting_schedule"] = {
                "status": "SCHEDULE_SOURCE_HELD",
                "error_type": type(exc).__name__, "agenda_urls_discovered": 0}
    else:
        report["toronto_official_meeting_schedule"] = {
            "status": "NOT_REQUESTED", "agenda_urls_discovered": 0}

    # Fetch only explicitly listed, exact official Toronto TMMIS meeting
    # agendas. No meeting-number enumeration or historical auto-promotion.
    report["toronto_exact_agenda_retrieval"] = {
        "status": "NO_REGISTERED_OFFICIAL_TMMIS_MEETING_URLS",
        "meetings_with_items": 0
    }
    if fetch_toronto_official_agendas:
        try:
            urls = _toronto_meeting_urls(root)
            if urls:
                toronto = (toronto_fetcher or fetch_toronto_agendas)(
                    urls, out / "TORONTO_TMMIS_OFFICIAL", authorized=True)
                report["toronto_exact_agenda_retrieval"] = {
                    "status": toronto.get("status"),
                    "meetings_considered": toronto.get("meetings_considered", 0),
                    "meetings_with_items": toronto.get("meetings_with_items", 0),
                    "meeting_results": [
                        {"meeting_url": record.get("meeting_url"),
                         "status": record.get("status"),
                         "reason": record.get("reason", "")}
                        for record in toronto.get("meeting_results", [])
                    ],
                    "paid_ai_calls": toronto.get("paid_ai_calls", 0)
                }
            elif origin == "INVALID_SOURCE_MANIFEST":
                report["toronto_exact_agenda_retrieval"]["status"] = "INVALID_MANIFEST_HOLD"
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            report["toronto_exact_agenda_retrieval"] = {
                "status": "OFFICIAL_TMMIS_FETCH_OR_MANIFEST_HELD",
                "reason": type(exc).__name__, "meetings_with_items": 0}
            report["source_documents_held"] += 1

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
    cli.add_argument("--fetch-toronto-schedule", action="store_true",
                     help="Bounded public Toronto City Clerk schedule CSV source check")
    cli.add_argument("--fetch-toronto-official-agendas", action="store_true",
                     help="Fetch only exact official TMMIS agenda URLs registered in workspace")
    cli.add_argument("--fetch-mississauga-pdc", action="store_true",
                     help="Fetch only newly observed official PDC PDF links through robots gate")
    cli.add_argument("--fetch-brampton-featured", action="store_true",
                     help="Bounded, robots-checked official Brampton featured planning cards")
    args = cli.parse_args()
    report = execute(args.workspace, args.results,
                     fetch_brampton_featured=args.fetch_brampton_featured,
                     fetch_mississauga_pdc=args.fetch_mississauga_pdc,
                     fetch_toronto_official_agendas=args.fetch_toronto_official_agendas,
                     fetch_toronto_schedule=args.fetch_toronto_schedule)
    print(json.dumps({
        "status": report["status"],
        "documents_considered": report["documents_considered"],
        "documents_parsed": report["documents_parsed"],
        "mississauga_matching": report["mississauga_20_case_comparison"],
        "paid_ai_usd": report["paid_ai_usd"],
        "brampton_featured": report["brampton_featured_public_applications"],
        "mississauga_discovered_pdc": report["mississauga_discovered_pdc"],
        "toronto_exact_agenda_retrieval": report["toronto_exact_agenda_retrieval"],
        "toronto_official_meeting_schedule": report["toronto_official_meeting_schedule"]
    }, indent=2))


if __name__ == "__main__":
    main()
