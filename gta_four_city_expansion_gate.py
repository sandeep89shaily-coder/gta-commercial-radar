"""Read-only four-city expansion ACCEPTANCE GATE, not a new live collector.

Uses existing GGH pilot diagnostics. Pickering, Niagara Falls and Barrie are
already configured as experimental sources; Ajax remains NOT ENABLED pending
official schema/permissions checks. Nothing may be promoted to production
from raw row counts or a source index, and no first-publication date is inferred.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path

from gta_ggh_early_planning import SOURCES

CITIES = ("Pickering", "Ajax", "Niagara Falls", "Barrie")
GGH_STATUS = "GTA_RADAR_GGH_EXPANSION_SOURCE_STATUS.json"
OUTPUT = "GTA_RADAR_FOUR_CITY_EXPANSION_ACCEPTANCE.csv"
STATUS = "GTA_RADAR_FOUR_CITY_EXPANSION_ACCEPTANCE_STATUS.json"
AJAX_OFFICIAL_INDEX = (
    "https://ajax.ca/build-invest/for-developers-builders/"
    "planning-development-applications/"
)
AJAX_MAP_SERVICE = (
    "https://ajaxmaps.ajax.ca/gisernie/rest/services/"
    "Planning/Apps_Dev/MapServer"
)
ACTIONS = {
    "Pickering": (
        "Check original City development proposal pages and exact file numbers; "
        "compare official posting date to Radar first-observed time and existing "
        "Durham/early-notice candidates; filter residential-only proposals."
    ),
    "Ajax": (
        "First confirm official ArcGIS active layer 1/3 field schema, reuse rights, "
        "robots-permitted API or City-authorized CSV export with planningservices@ajax.ca. "
        "Only then create a separate manual application pilot; do not count the dashboard."
    ),
    "Niagara Falls": (
        "Recheck at least 20 distinct official planning file IDs and exact civic sites; "
        "separate industrial/commercial proposals from historical/duplicate applications "
        "and verify notice publication timestamps."
    ),
    "Barrie": (
        "Test permitted ArcGIS field schema and complete pagination with real local results; "
        "cross-check application ID and original filing record, publication timing and "
        "commercial site scope against competing sources."
    ),
}
FIELDS = (
    "city", "registered_in_existing_ggh_pilot", "source_url",
    "reported_state", "file_id_candidate_rows_not_unique_leads",
    "source_candidate_changes_not_new_publications", "commercial_text_matches_unverified",
    "index_or_dataset_only", "automated_source_recovered",
    "verified_citywide_coverage", "verified_source_publication_dates",
    "verified_open_supplier_work", "pilot_acceptance",
    "failure_reason", "next_action",
)

def _read(path):
    if not path.is_file():
        return {}, "STATUS_FILE_MISSING"
    try:
        d=json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(d,dict) or not isinstance(d.get("source_status"),list):
            return {}, "STATUS_FILE_INVALID_SCHEMA"
        by_city={}
        for item in d["source_status"]:
            if not isinstance(item,dict):
                return {}, "STATUS_FILE_INVALID_CITY_ROW"
            city=str(item.get("city") or "")
            if city in by_city:
                return {}, "DUPLICATE_CITY_STATUS_HOLD"
            if city:
                by_city[city]=item
        return by_city, "PREVIOUSLY_EXPORTED_UNVERIFIED_SOURCE_STATUS"
    except (ValueError,UnicodeError,OSError):
        return {}, "STATUS_FILE_UNREADABLE"

def _count(value):
    try:
        n=int(value or 0)
        return n if n>=0 else 0
    except (TypeError,ValueError):
        return 0

def _csv_safe(value):
    value=str(value if value is not None else "")
    return "'" + value if value.lstrip().startswith(("=","+","-","@")) else value

def build(results, *, today=None):
    root=Path(results)
    if not root.is_dir():
        raise FileNotFoundError("EXISTING_RADAR_RESULTS_REQUIRED")
    known, evidence_basis=_read(root/GGH_STATUS)
    records=[]
    for city in CITIES:
        registered=city in SOURCES
        snapshot=known.get(city,{}) if registered else {}
        if not registered:
            source_url=AJAX_OFFICIAL_INDEX
            state="NOT_REGISTERED_AS_GGH_APPLICATION_COLLECTOR"
            failure="ArcGIS public dashboard is not a verified permitted application feed"
        else:
            source_url=SOURCES[city]
            state=str(snapshot.get("state") or "NO_CURRENT_SOURCE_STATUS")
            failure=str(snapshot.get("error") or "")[:180]
        n=_count(snapshot.get("application_id_rows"))
        changes=_count(snapshot.get("new_or_changed"))
        commercial=_count(snapshot.get("commercial_text_matches"))
        # The previous exported source status is NOT independent proof of
        # current live availability, completeness, first posting or buyer.
        if not registered:
            classification="SOURCE_RESEARCH_ONLY_NOT_ENABLED"
        elif evidence_basis!="PREVIOUSLY_EXPORTED_UNVERIFIED_SOURCE_STATUS":
            classification="SOURCE_STATUS_MISSING_OR_UNREADABLE_HOLD"
        elif state in ("FAILED","SOURCE_ACCESS_OR_PARSE_BLOCKED"):
            classification="SOURCE_BLOCKED_OR_FAILED"
        elif n>0 and state in ("BASELINE_COMPLETE","COLLECTED"):
            classification="APPLICATION_IDS_EXTRACTED_MANUAL_REVIEW_REQUIRED"
        else:
            classification="NO_VERIFIED_APPLICATION_ID_COVERAGE"
        records.append({
            "city":city,
            "registered_in_existing_ggh_pilot":"YES" if registered else "NO",
            "source_url":source_url,
            "reported_state":state,
            "file_id_candidate_rows_not_unique_leads":n,
            "source_candidate_changes_not_new_publications":changes,
            "commercial_text_matches_unverified":commercial,
            "index_or_dataset_only":"YES" if not n else "NO",
            "automated_source_recovered":"NO" if not registered else "NOT_INDEPENDENTLY_RECHECKED",
            "verified_citywide_coverage":"NO",
            "verified_source_publication_dates":0,
            "verified_open_supplier_work":0,
            "pilot_acceptance":classification,
            "failure_reason":failure,
            "next_action":ACTIONS[city],
        })
    with (root/OUTPUT).open("w",encoding="utf-8-sig",newline="") as fp:
        writer=csv.DictWriter(fp,fieldnames=FIELDS)
        writer.writeheader()
        for item in records:
            writer.writerow({key:_csv_safe(item.get(key,"")) for key in FIELDS})
    report={
        "mode":"MANUAL_READ_ONLY_FOUR_CITY_EXPANSION_GATE",
        "as_of":str(today or dt.date.today()),
        "cities_requested":4,
        "cities_already_configured_in_experimental_ggh_source_list":
            sum(x["registered_in_existing_ggh_pilot"]=="YES" for x in records),
        "new_live_collectors_enabled":0,
        "cities_verified_citywide_complete":0,
        "cities_with_verified_live_source_publication_date":0,
        "verified_fresh_commercial_leads":0,
        "verified_buyers":0,
        "verified_open_supplier_work_packages":0,
        "source_status_file":str(root/GGH_STATUS),
        "source_status_basis":evidence_basis,
        "ajax_official_dashboard_reference":AJAX_OFFICIAL_INDEX,
        "ajax_candidate_arcgis_map_service_not_approved":AJAX_MAP_SERVICE,
        "municipalities":records,
        "output_csv":str(root/OUTPUT),
        "warning":(
            "This is an audit of PRIOR exported pilot statuses, not a fresh "
            "network test. Ajax source not enabled; a dashboard does not "
            "count as a municipal collector. Candidate rows are not unique "
            "new projects, proof of public posting, or open purchasing."
        ),
    }
    (root/STATUS).write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report

if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--results",required=True)
    args=cli.parse_args()
    print(json.dumps(build(args.results),indent=2))
