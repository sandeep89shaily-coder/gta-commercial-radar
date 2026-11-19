"""31-city western corridor *reconciliation* over the existing 28-city master.

Configures London, Sarnia, Chatham-Kent, while Windsor stays in 28-city
collection. Source access/licensing and evidence are independent dimensions.
Only validated official exports whose publisher's reuse rights were recorded
are joined. They remain research-only; not inserted into paid AI Top 10
before application/status/publication/buyer gates.

This stage does not run a second 28-city fetch, rewrite source ledgers,
or spend AI budget. Fails closed on missing same-run 28-city records.
"""
from __future__ import annotations
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from gta_24_city_combined import COLS,COVERAGE_COLS,_write
from gta_western_corridor_source_audit import (
    NEW,OUTPUT as WEST,STATUS as WEST_STATUS)

MASTER="GTA_RADAR_COMBINED_31_CITY_PROJECT_MASTER.csv"
COVERAGE="GTA_RADAR_COMBINED_31_CITY_COVERAGE.csv"
QUEUE="GTA_RADAR_COMBINED_31_CITY_RESEARCH_QUEUE.csv"
TOP10="GTA_RADAR_COMBINED_31_CITY_RESEARCH_TOP10.csv"
STATUS="GTA_RADAR_COMBINED_31_CITY_STATUS.json"
CURRENT28="GTA_RADAR_COMBINED_28_CITY_STATUS.json"
SOURCE28="GTA_RADAR_COMBINED_28_CITY_PROJECT_MASTER.csv"
COVERAGE28="GTA_RADAR_COMBINED_28_CITY_COVERAGE.csv"
QUEUE28="GTA_RADAR_COMBINED_28_CITY_RESEARCH_QUEUE.csv"
TOP28="GTA_RADAR_COMBINED_28_CITY_RESEARCH_TOP10.csv"

def read_csv(path):
    if (not path.is_file() or path.is_symlink() or
            path.stat().st_size>80_000_000):
        return []
    with path.open(encoding="utf-8-sig",newline="") as fp:
        return list(csv.DictReader(fp))

def run(results):
    root=Path(results)
    status28=json.loads((root/CURRENT28).read_text(encoding="utf-8"))
    west=json.loads((root/WEST_STATUS).read_text(encoding="utf-8"))
    base=read_csv(root/SOURCE28)
    coverage=read_csv(root/COVERAGE28)
    if (status28.get("configured_city_count")!=28 or len(coverage)!=28 or not base):
        raise ValueError("SAME_RUN_VALID_28_CITY_MASTER_REQUIRED")
    states=west.get("source_states",{})
    if (west.get("status")!="WESTERN_CORRIDOR_SOURCE_RIGHTS_AND_APPLICATION_AUDIT"
            or set(states)!=(set(NEW)|{"Windsor"})):
        raise ValueError("WESTERN_SOURCE_STATUS_INCOMPLETE")
    known={row.get("city") for row in coverage}
    if "Windsor" not in known or any(x in known for x in NEW):
        raise ValueError("DUPLICATE_OR_MISSING_WESTERN_CITY_CONFIG")
    imported=read_csv(root/WEST)
    allowed={}
    bycity=Counter()
    for row in imported:
        city=row.get("city","")
        state=states.get(city,{})
        if (city not in NEW or
            state.get("status")!="AUTHORIZED_IMPORTED_EXACT_APPLICATION_IDS_RESEARCH_ONLY" or
            not all(row.get(k) for k in ("application_id","address","scope","source_url"))):
            continue
        ident="".join(c for c in row["application_id"].upper() if c.isalnum())
        if not ident:continue
        cid=city.upper().replace(" ","_").replace("-","_")+":FILE:"+ident
        bycity[city]+=1
        allowed.setdefault(cid,{
            "canonical_id":cid,"city":city,"cohort":"WEST_3",
            "record_kind":"APPLICATION","application_id":row["application_id"],
            "address":row["address"],"scope":row["scope"],
            "project_title":"","current_status":row.get("stage",""),
            "applicant_or_agent_source_claim":row.get("applicant",""),
            "source_date":row.get("source_date",""),
            "source_date_basis":row.get("source_date_basis",""),
            "official_evidence_urls":row["source_url"],
            "source_lanes":"WESTERN_OPERATOR_AUTHORIZED_OFFICIAL_EXPORT",
            "commercial_text_match":"False",
            "original_publication_verified":"False",
            "purchasing_contact_verified":"False",
            "open_supplier_contract_verified":"False",
            "commercial_research_priority":"AWAIT_INDEPENDENT_PROJECT_QUALIFICATION",
            "verification_required":"Source licensed, but project freshness/buyer/contract unverified",
        })
    ids={row.get("canonical_id") for row in base if row.get("canonical_id")}
    extra=[record for cid,record in allowed.items() if cid not in ids]
    coverage31=[dict(x) for x in coverage]
    for city in NEW:
        state=states[city]
        count=sum(x["city"]==city for x in extra)
        coverage31.append({
            "city":city,"cohort":"WEST_3",
            "application_files":count,
            "building_permits_historical":0,"project_only_signals":0,
            "source_rows":count,"commercial_research_candidates":0,
            "published_contact_email_records":0,
            "failed_or_blocked_source_count":int(
                state.get("status") not in (
                    "AUTHORIZED_IMPORTED_EXACT_APPLICATION_IDS_RESEARCH_ONLY",
                    "AUTHORIZED_EXPORT_ZERO_VALID_EXACT_APPLICATION_IDS")),
            "source_health":state.get("status","UNVERIFIED"),
            "coverage_verified_citywide":"False",
            "first_publications_verified":0,"verified_buyers":0,
            "open_supplier_contracts_verified":0,
            "source_limitations":state.get("site_policy_problem","")+
                " Commercial opportunity qualification still pending.",
        })
    queue=read_csv(root/QUEUE28)
    top10=read_csv(root/TOP28)
    _write(root/MASTER,COLS,base+extra)
    _write(root/COVERAGE,COVERAGE_COLS,coverage31)
    # Do not promote manual exports to new AI candidates merely because
    # their source-level licence is approved.
    _write(root/QUEUE,COLS,queue)
    _write(root/TOP10,COLS,top10)
    summary={
        "status":"COMBINED_31_CITY_SOURCE_RIGHTS_GATED_RESEARCH",
        "configured_city_count":31,"existing_city_count":28,
        "new_configured_cities":list(NEW),"existing_windsor_not_duplicated":True,
        "new_sources_with_verified_automatic_live_application_ids":0,
        "authorized_imported_new_city_rows":len(extra),
        "new_city_source_status":{c:states[c]["status"] for c in NEW},
        "windsor_existing_live_source_status":states["Windsor"]["status"],
        "commercial_ai_scope":"UNCHANGED_28_CITY_UNTIL_NEW_SOURCES_QUALIFIED",
        "top10_source_scope":"EXISTING_28_CITY_ONLY",
        "candidate_rows_new_cities_promoted_to_ai":0,
        "source_full_coverage_verified":False,"verified_buyers":0,
        "verified_first_publications":0,"additional_paid_ai_calls":0,
        "output_files":[MASTER,COVERAGE,QUEUE,TOP10,STATUS],
    }
    (root/STATUS).write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--results",required=True)
    print(json.dumps(run(p.parse_args().results),indent=2))
