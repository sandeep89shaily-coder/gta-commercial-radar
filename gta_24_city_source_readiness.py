"""City-by-city live SOURCE readiness for unified GTA Radar 16+8.

Reads one full-run's per-source diagnostics after the collector stages, never
reuses the combined project's historical file count as proof of current live
source success or full-city coverage. A blocked or merely index-only source
remains a recorded gap. Zero paid model calls or new network requests.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

from gta_24_city_combined import CITIES, CORE_CITIES, EXPANSION_CITIES

COVERAGE = "GTA_RADAR_COMBINED_24_CITY_COVERAGE.csv"
OUTPUT = "GTA_RADAR_COMBINED_24_CITY_LIVE_SOURCE_READINESS.csv"
STATUS = "GTA_RADAR_COMBINED_24_CITY_LIVE_SOURCE_READINESS.json"
COLUMNS = (
    "city", "cohort", "combined_application_files_historical_or_current",
    "live_source_attempts_reported", "live_sources_with_application_ids",
    "live_application_id_source_rows_not_deduplicated", "blocked_or_failed_lanes",
    "index_only_or_project_signal_lanes", "source_status_summary",
    "measured_source_readiness", "citywide_complete_coverage_verified",
    "first_publication_dates_verified", "buyer_contact_verified",
    "procurement_open_verified", "recommended_access_action",
)

SUCCESS = ("COLLECTED", "BASELINED", "OK_BASELINE", "OK_MONITORED",
           "BASELINE_COMPLETE", "INDEX_FETCHED",
           "DETAILS_CAPTURED_REVIEW_ONLY",
           "DATED_NOTICE_REVIEW_ONLY",
           "OFFICIAL_LAYER_RECORDS_REVIEW_ONLY",
           "GIS_ROWS_FETCHED_NOT_FRESH_VERIFIED",
           "BOUNDED_GIS_SAMPLE_NOT_CITYWIDE")
FAILED = ("FAILED", "BLOCK", "DENIED", "SOURCE_HELD", "SOURCE_FETCH_FAILED",
          "NO_PUBLISHED_PERMIT_NUMBER_HOLD", "FETCH_FAILED",
          "PARTIAL_OR_HELD", "ROBOTS", "HTTP_403")
INDEX = ("INDEX_ONLY", "NO_APPLICATION_ID", "NO_EXACT", "PROJECT_SIGNALS_ONLY",
         "NOTICE_DOCUMENT_LINKS_ONLY", "NO_PLANNING", "NO_ELIGIBLE",
         "SOURCE_BLOCKED_OR_UNSUPPORTED")


def _obj(path):
    try:
        j = json.loads(path.read_text(encoding="utf-8"))
        return j if isinstance(j, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def _rows(path):
    try:
        with path.open(encoding="utf-8-sig", newline="") as fp:
            return list(csv.DictReader(fp))
    except (OSError, csv.Error, UnicodeError):
        return []


def _number(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _check(city, source, status, count, observations):
    if city not in CITIES:
        return
    # Count a source's positive application IDs only where its own status
    # explicitly reports such a collection; permit-only lanes are excluded.
    status = str(status or "UNKNOWN").strip()
    upper = status.upper()
    n = _number(count)
    failed = any(t in upper for t in FAILED) or any(
        t in str(observations or "").upper()
        for t in ("ROBOTS_DENIED", "ROBOTS_ACCESS_DENIED", "HTTP 403", "HTTP_403",
                  "CERTIFICATE_VERIFY_FAILED", "ACCESS_DENIED"))
    index = any(t in upper for t in INDEX)
    actual = n > 0 and not failed and (any(t in upper for t in SUCCESS)
                or upper == "INDEX_FETCHED" or
                "REVIEW_ONLY" in upper or "PARTIAL" in upper)
    return {
        "city":city, "source":str(source)[:100],
        "status":status[:100], "application_id_rows":n if actual else 0,
        "failed":failed, "index_only":index or (not actual and n == 0),
        "note":str(observations or "")[:220],
    }


def _sources(root):
    out = defaultdict(list)
    def add(city, source, status, count=0, note=""):
        item = _check(city, source, status, count, note)
        if item is not None:
            out[city].append(item)
    # Old 16-city collectors. One HTML index can coexist with separate
    # functioning municipal/GIS/permit feeds: do not erase either.
    early = _obj(root/"GTA_RADAR_EARLY_APPLICATION_SOURCE_STATUS.json")
    for x in early.get("city_status",[]):
        if isinstance(x,dict):
            add(x.get("city"), "CORE_HTML_INDEX",
                x.get("fetch_status"), x.get("actual_application_rows"),
                x.get("reason",""))
    municipal = _obj(root/"GTA_RADAR_MUNICIPAL_PROJECT_FEED_STATUS.json")
    for x in municipal.get("source_status",[]):
        if isinstance(x,dict):
            add(x.get("city"), "CORE_MUNICIPAL_PAGES",
                x.get("state"), x.get("application_id_rows"),
                x.get("failures",""))
    for name in (
            "GTA_RADAR_STRUCTURED_APPLICATION_SOURCE_STATUS.json",
            "GTA_RADAR_ADDITIONAL_CITY_GIS_STATUS.json",
            "GTA_RADAR_FIVE_CITY_RECOVERY_STATUS.json"):
        result = _obj(root/name)
        for x in result.get("source_status",[]):
            if isinstance(x,dict):
                add(x.get("city"),name,
                    x.get("status") or x.get("state"),
                    x.get("application_id_rows_this_stage") or
                    x.get("commercial_candidates") or x.get("records") or 0,
                    x.get("error",""))
    ckan = _obj(root/"GTA_RADAR_TORONTO_OPEN_DATA_STATUS.json")
    add("Toronto","TORONTO_CKAN",ckan.get("status","NOT_REPORTED"),
        ckan.get("commercial_candidates",0))
    # Source-specific expansion lanes, not synthetic coverage counts.
    ggh = _obj(root/"GTA_RADAR_GGH_EXPANSION_SOURCE_STATUS.json")
    for x in ggh.get("source_status",[]):
        if isinstance(x,dict) and x.get("city") in EXPANSION_CITIES:
            add(x["city"],"GGH_APPLICATION",x.get("state"),
                x.get("application_id_rows"),x.get("notice_page_errors",""))
    three = _obj(root/"GTA_RADAR_THREE_CITY_EVIDENCE_STATUS.json")
    for x in three.get("sources",[]):
        if not isinstance(x,dict):
            continue
        city=x.get("city")
        # St Catharines notices with explicit IDs get counted later from
        # the actual candidate file, never by pages fetched alone.
        count = x.get("fetched") if city=="Niagara Falls" else 0
        add(city,x.get("source_lane","THREE_CITY"),
            x.get("status"),count,x.get("failures",""))
    northern = _obj(root/"GTA_RADAR_NORTHERN_MAJOR_CITY_STATUS.json")
    for x in northern.get("source_details",[]):
        if not isinstance(x,dict):
            continue
        city=x.get("city")
        lane=x.get("lane")
        count=x.get("records") if (city=="Barrie" and lane=="PLANNING") else 0
        add(city,"NORTHERN_"+str(lane),x.get("status"),count,x.get("error",""))
    nxt = _obj(root/"GTA_RADAR_NEXT_FOUR_MUNICIPALITIES_STATUS.json")
    for x in nxt.get("source_status",[]):
        if isinstance(x,dict) and x.get("city") in EXPANSION_CITIES:
            add(x["city"],"NEXT_FOUR_NOTICE",x.get("status"),
                x.get("application_id_rows"),x.get("notice_page_errors",""))
    return out


def run(results, *, today=None):
    root=Path(results)
    if not root.is_dir():
        raise FileNotFoundError("EXISTING_RESULTS_DIRECTORY_REQUIRED")
    day=today or dt.date.today()
    coverage = _rows(root/COVERAGE)
    if len(coverage)!=24 or {r.get("city") for r in coverage}!=set(CITIES):
        raise ValueError("COMBINED_24_CITY_COVERAGE_MISSING_OR_INVALID")
    per = _sources(root)
    core = {r["city"]:r for r in coverage}
    allrows = []
    for city in CITIES:
        lines=per.get(city,[])
        good=[x for x in lines if x["application_id_rows"] > 0]
        bad=[x for x in lines if x["failed"]]
        index=[x for x in lines if x["index_only"] and not x["failed"]]
        saved=_number(core[city].get("application_files"))
        if bad:
            readiness="PARTIAL_LIVE_WITH_FAILED_SOURCES" if good else "FAILED_OR_BLOCKED_SOURCE_ATTEMPTS"
        elif good:
            readiness="LIVE_APPLICATION_SOURCE_RECORDS_NOT_CITYWIDE_VERIFIED"
        elif index:
            readiness="INDEX_OR_PROJECT_SIGNALS_ONLY_NO_LIVE_APPLICATION_IDS"
        elif saved:
            readiness="SAVED_FILES_WITHOUT_CURRENT_SOURCE_SUCCESS_EVIDENCE"
        else:
            readiness="NO_VERIFIED_LIVE_APPLICATION_SOURCE_EVIDENCE"
        if bad:
            action="Restore permitted official data source or request municipal export. Do not bypass robots/auth/TLS."
        elif not good:
            action="Find official project-file feed with exact IDs; current index-only evidence is insufficient."
        else:
            action="Verify original issue/publication dates, scope, legal company roles and source completeness."
        allrows.append({
            "city":city, "cohort":core[city].get("cohort",""),
            "combined_application_files_historical_or_current":saved,
            "live_source_attempts_reported":len(lines),
            "live_sources_with_application_ids":len(good),
            "live_application_id_source_rows_not_deduplicated":sum(
                x["application_id_rows"] for x in good),
            "blocked_or_failed_lanes":len(bad),
            "index_only_or_project_signal_lanes":len(index),
            "source_status_summary":" | ".join(x["source"]+":"+x["status"]
                for x in lines)[:950],
            "measured_source_readiness":readiness,
            "citywide_complete_coverage_verified":"False",
            "first_publication_dates_verified":0,
            "buyer_contact_verified":0, "procurement_open_verified":0,
            "recommended_access_action":action,
        })
    with (root/OUTPUT).open("w",encoding="utf-8-sig",newline="") as fp:
        w=csv.DictWriter(fp,fieldnames=COLUMNS)
        w.writeheader();w.writerows(allrows)
    status={
        "status":"24_CITY_SOURCE_READINESS_AUDITED_PARTIAL_UNLESS_PROVEN",
        "as_of":day.isoformat(),"configured_cities":24,
        "cities_with_reported_live_application_source_rows":sum(
            x["live_sources_with_application_ids"]>0 for x in allrows),
        "cities_with_failed_or_blocked_source_lanes":sum(
            x["blocked_or_failed_lanes"]>0 for x in allrows),
        "cities_with_only_index_or_saved_records":sum(
            x["live_sources_with_application_ids"]==0 and
            x["blocked_or_failed_lanes"]==0 for x in allrows),
        "citywide_complete_coverage_verified":0,
        "source_health_checked_for_every_configured_city":len(allrows)==24,
        "blocked_city_names":[x["city"] for x in allrows if
                              x["blocked_or_failed_lanes"]],
        "cities_without_live_application_source_rows":[x["city"] for x in allrows
            if not x["live_sources_with_application_ids"]],
        "buyer_contacts_verified":0,"new_publications_verified":0,
        "open_supplier_packages_verified":0,"paid_ai_calls":0,
        "warning":"The original 16 and eight expansion cities have one "
            "combined research output, but citywide live feed completeness "
            "is NOT verified for any city. A saved application count, an "
            "index-only HTTP success, a site-planner email or a first-seen "
            "local date must not become a citywide coverage or new lead claim.",
        "source_readiness_csv":OUTPUT,
    }
    (root/STATUS).write_text(json.dumps(status,indent=2),encoding="utf-8")
    return status
