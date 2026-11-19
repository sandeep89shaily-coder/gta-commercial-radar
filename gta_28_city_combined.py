"""28-city reconciliation: retain validated 24-city baseline, append four live lanes.

Produces combined 28-city master, source coverage, research queue and Top 10.
No extra AI. These outputs are input to the existing shared-budget AI reviewer
only when it is explicitly routed through the 28-city candidate selection.
"""
from __future__ import annotations
import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path

from gta_24_city_combined import (_rank, _write, COLS, COVERAGE_COLS,
                                  CORE_CITIES, EXPANSION_CITIES)
from gta_four_city_live_daily import (CITIES as ADDED, MASTER as LIVE,
                                      STATUS as LIVE_STATUS)

MASTER="GTA_RADAR_COMBINED_28_CITY_PROJECT_MASTER.csv"
COVERAGE="GTA_RADAR_COMBINED_28_CITY_COVERAGE.csv"
QUEUE="GTA_RADAR_COMBINED_28_CITY_RESEARCH_QUEUE.csv"
TOP10="GTA_RADAR_COMBINED_28_CITY_RESEARCH_TOP10.csv"
STATUS="GTA_RADAR_COMBINED_28_CITY_STATUS.json"

def _read(path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size>80_000_000:
        return []
    with path.open(encoding="utf-8-sig",newline="") as fp:
        return list(csv.DictReader(fp))

def _age(row,day):
    try:
        days=(day-dt.date.fromisoformat(row.get("source_date") or "")).days
    except ValueError:
        days=None
    if days is None:return "SOURCE_EVENT_DATE_UNKNOWN_NOT_FRESH"
    if days<0:return "FUTURE_OR_INVALID_DATE_REVIEW"
    if days<=7:return "SOURCE_EVENT_0_TO_7_DAYS"
    if days<=30:return "SOURCE_EVENT_8_TO_30_DAYS"
    if days<=90:return "SOURCE_EVENT_31_TO_90_DAYS"
    if days<=365:return "SOURCE_EVENT_91_TO_365_DAYS"
    return "HISTORICAL_SOURCE_EVENT_OVER_365_DAYS"

def _band(row,day):
    age=_age(row,day)
    if age in ("SOURCE_EVENT_0_TO_7_DAYS","SOURCE_EVENT_8_TO_30_DAYS"):
        return 0
    if age=="SOURCE_EVENT_31_TO_90_DAYS":return 1
    if age=="SOURCE_EVENT_91_TO_365_DAYS":return 2
    return 3

def run(results,*,today=None):
    root=Path(results)
    day=today or dt.date.today()
    base=_read(root/"GTA_RADAR_COMBINED_24_CITY_PROJECT_MASTER.csv")
    original_coverage=_read(root/"GTA_RADAR_COMBINED_24_CITY_COVERAGE.csv")
    if len(original_coverage)!=24 or not base:
        raise ValueError("CURRENT_24_CITY_MASTER_REQUIRED")
    try:
        live=json.loads((root/LIVE_STATUS).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        raise ValueError("CURRENT_FOUR_CITY_SOURCE_STATUS_REQUIRED")
    if (live.get("configured_added_municipalities")!=4 or
            not isinstance(live.get("city_status"),list) or
            {x.get("city") for x in live["city_status"]}!=set(ADDED)):
        raise ValueError("FOUR_CITY_SOURCE_STATUS_MALFORMED")
    live_rows=_read(root/LIVE)
    health={x["city"]:x for x in live["city_status"]}
    extra=[]
    for row in live_rows:
        city=row.get("city")
        if city not in ADDED or not all(row.get(k) for k in (
                "application_id","address","scope","source_url")):
            continue
        if health[city]["status"]!="LIVE_APPLICATION_IDS_RETRIEVED_PARTIAL_COVERAGE":
            continue
        ident=row["application_id"]
        canonical=city.upper().replace(" ","_")+":FILE:"+ "".join(
            ch for ch in ident.upper() if ch.isalnum())
        if not canonical.endswith(":FILE:"):
            continue
        scope=row["scope"]
        extra.append({
            "canonical_id":canonical,"city":city,"cohort":"ADDED_4",
            "record_kind":"APPLICATION","application_id":ident,
            "address":row["address"],"project_title":"",
            "scope":scope,"current_status":row.get("stage",""),
            "applicant_or_agent_source_claim":row.get("applicant",""),
            "published_contact_name":"","published_contact_email":"",
            "contact_role":"","source_date":row.get("date",""),
            "source_date_basis":row.get("date_basis",""),
            "webpage_posted_date_not_first_disclosure":"",
            "source_observation":row.get("source_observation",""),
            "first_seen_local":row.get("first_seen_local",""),
            "official_evidence_urls":row["source_url"],
            "source_lanes":"FOUR_CITY_LIVE_POLICY_GATED",
            "commercial_text_match":"True" if any(
                token in (" "+scope+" "+row.get("category","")).lower()
                for token in ("industrial","commercial","manufactur",
                              "warehouse","logistic","office","retail","hotel",
                              "data cent","distribution","mixed use",
                              "storage","factory")) else "False",
            "source_event_age_band_not_publication":"",
            "original_publication_verified":"False",
            "purchasing_contact_verified":"False",
            "open_supplier_contract_verified":"False",
            "commercial_research_priority":"BASELINE_OR_UNVERIFIED",
            "verification_required":"Check original notice, seller, actual buying role and procurement",
        })
    records={}
    for row in base+extra:
        if row.get("canonical_id"):
            records.setdefault(row["canonical_id"],row)
    allrows=list(records.values())
    for row in allrows:
        row["source_event_age_band_not_publication"]=_age(row,day)
    ranked=[]
    for row in allrows:
        score=_rank(row,day)
        if score is not None:
            row["commercial_research_priority"]="RESEARCH_ONLY_NOT_SALE_READY"
            ranked.append((score,row))
    ranked.sort(key=lambda pair:(
        _band(pair[1],day),-pair[0],pair[1]["city"],
        pair[1]["application_id"]))
    research=[r for _,r in ranked]
    city_slots=Counter();top=[]
    for row in research:
        if city_slots[row["city"]]>=4:continue
        city_slots[row["city"]]+=1
        top.append(row)
        if len(top)>=10:break
    new_coverage=list(original_coverage)
    for city in ADDED:
        info=health[city]
        count=sum(x["city"]==city for x in extra)
        new_coverage.append({
            "city":city,"cohort":"ADDED_4","application_files":count,
            "building_permits_historical":0,"project_only_signals":0,
            "source_rows":count,
            "commercial_research_candidates":sum(
                row["city"]==city for row in research),
            "published_contact_email_records":0,
            "failed_or_blocked_source_count":int(
                info["status"]!="LIVE_APPLICATION_IDS_RETRIEVED_PARTIAL_COVERAGE"),
            "source_health":info["status"],"coverage_verified_citywide":"False",
            "first_publications_verified":0,"verified_buyers":0,
            "open_supplier_contracts_verified":0,
            "source_limitations":info.get("failure","")+
                " Source count does not imply full application coverage.",
        })
    _write(root/MASTER,COLS,allrows)
    _write(root/COVERAGE,COVERAGE_COLS,new_coverage)
    _write(root/QUEUE,COLS,research[:250])
    _write(root/TOP10,COLS,top)
    report={
        "status":"COMBINED_28_CITY_RESEARCH_ONLY_LIVE_SOURCE_GATED",
        "configured_city_count":28,
        "legacy_city_count":24,"new_city_count":4,
        "added_cities_with_live_application_ids":sum(
            info["retrieved_application_id_records"]>0 for info in health.values()),
        "added_cities_source_health":{x:xinfo["status"]
            for x,xinfo in health.items()},
        "all_four_added_city_source_rows":len(extra),
        "combined_master_rows":len(allrows),
        "combined_research_candidates":len(research),
        "top10_cities":dict(Counter(x["city"] for x in top)),
        "full_citywide_coverage_verified":False,
        "buyer_verified":0,"open_supplier_package_verified":0,
        "first_original_publications_verified":0,
        "additional_paid_ai_calls":0,
        "output_files":[MASTER,COVERAGE,QUEUE,TOP10,STATUS],
    }
    (root/STATUS).write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report
