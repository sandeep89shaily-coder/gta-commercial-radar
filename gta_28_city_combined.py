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

from gta_24_city_combined import (_csv, _rank, _write, CITIES as LEGACY_CITIES,
                                  COLS, COVERAGE_COLS, CORE_CITIES, EXPANSION_CITIES)
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
    try:
        base = _csv(root / "GTA_RADAR_COMBINED_24_CITY_PROJECT_MASTER.csv",
                    required_fields=("canonical_id", "city", "record_kind", "application_id"))
    except ValueError as exc:
        raise ValueError("CURRENT_24_CITY_MASTER_REQUIRED") from exc
    original_coverage=_read(root/"GTA_RADAR_COMBINED_24_CITY_COVERAGE.csv")
    if len(original_coverage) != len(LEGACY_CITIES) or {r.get("city") for r in original_coverage} != set(LEGACY_CITIES):
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
        if canonical.endswith(":FILE:"):
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
    # Newly recovered official alternative sources join the same 28-city
    # research universe, WITHOUT replacing established source records.
    # Caledon publisher-reuse permission is not certified: retain as research
    # evidence only; do not elevate those rows into commercial Top 10.
    fallback=[]
    alt_status_path=root/"GTA_RADAR_ALTERNATIVE_OFFICIAL_STATUS.json"
    alt_path=root/"GTA_RADAR_ALTERNATIVE_OFFICIAL_APPLICATIONS.csv"
    try:
        alt_status=json.loads(alt_status_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        alt_status={}
    if alt_status.get("status")=="OFFICIAL_ALTERNATIVE_FEEDS_AUDITED":
        for row in _read(alt_path):
            city=row.get("city","")
            city_state=alt_status.get("cities",{}).get(city,{})
            if (city not in ("Kitchener","Caledon") or
                    city_state.get("status")!="LIVE_EXACT_IDS_PARTIAL" or
                    not all(row.get(k) for k in ("application_id","address","scope","source_url"))):
                continue
            ident=row["application_id"]
            safeid="".join(c for c in ident.upper() if c.isalnum())
            if not safeid:continue
            released=(city=="Kitchener" and
                row.get("source_permission")=="PUBLISHED_OPEN_DATA_LICENCE_REUSE")
            scope=row["scope"]
            fallback.append({
                "canonical_id":city.upper()+":FILE:"+safeid,
                "city":city,"cohort":"CORE_16","record_kind":"APPLICATION",
                "application_id":ident,"address":row["address"],
                "project_title":"","scope":scope,"current_status":row.get("stage",""),
                "applicant_or_agent_source_claim":row.get("applicant",""),
                "published_contact_name":"","published_contact_email":"",
                "contact_role":"","source_date":row.get("date",""),
                "source_date_basis":row.get("date_basis",""),
                "webpage_posted_date_not_first_disclosure":"",
                "source_observation":"ALTERNATIVE_SOURCE_BASELINE_NOT_PUBLICATION",
                "first_seen_local":"","official_evidence_urls":row["source_url"],
                "source_lanes":row.get("source_lane","OFFICIAL_ALTERNATIVE"),
                "commercial_text_match":str(released and any(word in scope.casefold()
                  for word in ("industrial","commercial","manufactur",
                  "warehouse","logistics","office","distribution","retail","factory"))),
                "source_event_age_band_not_publication":"",
                "original_publication_verified":"False",
                "purchasing_contact_verified":"False",
                "open_supplier_contract_verified":"False",
                "commercial_research_priority":"BASELINE_OR_UNVERIFIED",
                "verification_required":"Publisher notice, actual buying role and procurement unverified",
            })
    # Additional publicly licensed open-data sources are included alongside
    # 24-city history, but a regional application must not be called complete
    # municipality coverage. Repeated exact file IDs are deduplicated.
    regional=[]
    regional_status_path=root/"GTA_RADAR_ADDITIONAL_OFFICIAL_OPEN_DATA_STATUS.json"
    try:
        regional_status=json.loads(regional_status_path.read_text(encoding="utf-8"))
    except (OSError,ValueError,UnicodeError):
        regional_status={}
    allowed_sources={
        "Vaughan":"YORK_REGION_OPEN_DATA_LICENCE",
        "Markham":"YORK_REGION_OPEN_DATA_LICENCE",
        "Richmond Hill":"YORK_REGION_OPEN_DATA_LICENCE",
        "Hamilton":"HAMILTON_OPEN_DATA_COMMERCIAL_LICENCE",
        "Brantford":"BRANTFORD_OPEN_DATA_COMMERCIAL_LICENCE",
    }
    if regional_status.get("status")==\
            "PUBLISHED_OPEN_DATA_RECOVERY_PARTIAL_UNTIL_LIVE_VERIFIED":
        regional_health=regional_status.get("source_status",{})
        for item in _read(root/"GTA_RADAR_ADDITIONAL_OFFICIAL_OPEN_DATA.csv"):
            city=item.get("city","")
            source_health=regional_health.get(city if city in ("Hamilton","Brantford") else "York Region",{})
            if (city not in allowed_sources or
                    source_health.get("status")!="LIVE_APPLICATION_FILES_RETRIEVED" or
                    item.get("source_permission")!=allowed_sources[city] or
                    not all(item.get(k) for k in ("application_id","address","scope","source_url"))):
                continue
            ident=item["application_id"]
            safeid="".join(char for char in ident.upper() if char.isalnum())
            if not safeid:continue
            scope=item["scope"]
            regional.append({
                "canonical_id":city.upper().replace(" ","_")+":FILE:"+safeid,
                "city":city,"cohort":"CORE_16","record_kind":"APPLICATION",
                "application_id":ident,"address":item["address"],
                "project_title":"","scope":scope,
                "current_status":item.get("stage",""),
                "applicant_or_agent_source_claim":item.get("applicant",""),
                "published_contact_name":"","published_contact_email":"",
                "contact_role":"","source_date":item.get("date",""),
                "source_date_basis":item.get("date_basis",""),
                "webpage_posted_date_not_first_disclosure":"",
                "source_observation":"OFFICIAL_OPEN_DATA_BASELINE_NOT_FIRST_PUBLICATION",
                "first_seen_local":"","official_evidence_urls":item["source_url"],
                "source_lanes":item.get("source_lane","REGIONAL_OPEN_DATA"),
                "commercial_text_match":str(any(word in (scope+" "+item.get("category","")).casefold()
                    for word in ("industrial","commercial","manufactur",
                        "warehouse","logistics","distribution","retail",
                        "office","hotel","factory","business park"))),
                "source_event_age_band_not_publication":"",
                "original_publication_verified":"False",
                "purchasing_contact_verified":"False",
                "open_supplier_contract_verified":"False",
                "commercial_research_priority":"BASELINE_OR_UNVERIFIED",
                "verification_required":
                   "Regional review only; confirm local file, project stage, buyer and open work",
            })
    # Peel official planning datasets enrich the established 28-city source
    # universe without replacing earlier HTML or collector records.
    # Mississauga's custom licence has not been cleared for resale/reuse;
    # its records remain evidence inventory, not AI/customer-ranked leads.
    peel=[]
    peel_status_path=root/"GTA_RADAR_BR_MISS_OPEN_PLANNING_STATUS.json"
    try:
        peel_status=json.loads(peel_status_path.read_text(encoding="utf-8"))
    except (OSError,ValueError,UnicodeError):
        peel_status={}
    peel_source_status=peel_status.get("source_status",{})
    if peel_status.get("status")=="BRAMPTON_MISSISSAUGA_OFFICIAL_DATA_ATTEMPT_AUDITED":
        for item in _read(root/"GTA_RADAR_BR_MISS_OPEN_PLANNING_APPLICATIONS.csv"):
            city=item.get("city","")
            lane=item.get("source_lane","")
            status=peel_source_status.get(lane,{})
            if (city not in ("Brampton","Mississauga") or
                    status.get("status")!="LIVE_VALID_APPLICATION_FILES_PARTIAL" or
                    not all(item.get(k) for k in ("application_id","address","scope","source_url"))):
                continue
            ident=item["application_id"]
            fileid="".join(char for char in ident.upper() if char.isalnum())
            if not fileid:continue
            # Some Brampton layers have CC BY 4.0, but other source-level
            # licences and the Mississauga custom licence are unverified.
            licence=item.get("licence_status","")
            eligible=licence=="CC_BY_4_0_PUBLISHED_DATASET"
            scope=item["scope"]
            peel.append({
                "canonical_id":city.upper()+":FILE:"+fileid,
                "city":city,"cohort":"CORE_16","record_kind":"APPLICATION",
                "application_id":ident,"address":item["address"],
                "project_title":item.get("project_title",""),"scope":scope,
                "current_status":item.get("stage",""),
                "applicant_or_agent_source_claim":item.get("applicant",""),
                "published_contact_name":"","published_contact_email":"",
                "contact_role":"","source_date":item.get("source_date",""),
                "source_date_basis":item.get("source_date_basis",""),
                "webpage_posted_date_not_first_disclosure":"",
                "source_observation":"OFFICIAL_PLANNING_SNAPSHOT_NOT_PUBLICATION",
                "first_seen_local":"","official_evidence_urls":item["source_url"],
                "source_lanes":lane,
                "commercial_text_match":str(eligible and any(w in
                    (scope+" "+item.get("category","")).casefold()
                    for w in ("industrial","commercial","manufactur","warehouse",
                              "logistics","retail","office","distribution","factory"))),
                "source_event_age_band_not_publication":"",
                "original_publication_verified":"False",
                "purchasing_contact_verified":"False",
                "open_supplier_contract_verified":"False",
                "commercial_research_priority":"BASELINE_OR_UNVERIFIED",
                "verification_required":"Confirm original notice, applicant, buyer, reuse rights and open supplier work",
            })
    records={}
    for row in base+extra+fallback+regional:
        if row.get("canonical_id"):
            records.setdefault(row["canonical_id"],row)
    brampton_peel_overlaps = 0
    for row in peel:
        ident = row["canonical_id"]
        previous = records.setdefault(ident, row)
        if previous is row or row["city"] != "Brampton":
            continue
        brampton_peel_overlaps += 1
        if previous["source_lanes"] == "AUTHORIZED_CITY_CSV_OFFLINE":
            # A public search result supplies current status but only a file
            # type for its scope. Keep the richer City GeoHub description.
            if previous["scope"]:
                row["scope"] = previous["scope"]
            if not row["current_status"]:
                row["current_status"] = previous["current_status"]
            if not row["source_date"]:
                row["source_date"] = previous["source_date"]
                row["source_date_basis"] = previous["source_date_basis"]
            row["source_lanes"] += " | AUTHORIZED_CITY_CSV_OFFLINE"
            records[ident] = row
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
    new_coverage=[dict(x) for x in original_coverage]
    # The original 24-city coverage report may mark a blocked municipal GIS
    # collector even when a separate licensed regional/open-data source now
    # successfully retrieves exact planning file IDs. Preserve the old
    # failure count and explicitly identify the recovered *partial* source.
    # Do not overwrite legacy application counts or claim citywide coverage.
    alternative_by_city=Counter(x["city"] for x in fallback+regional+peel)
    for entry in new_coverage:
        city=entry.get("city","")
        recovered=alternative_by_city.get(city,0)
        if not recovered:
            continue
        new_files = recovered - (brampton_peel_overlaps if city == "Brampton" else 0)
        entry["application_files"]=str(max(0,int(entry.get("application_files") or 0))+new_files)
        entry["source_rows"]=str(max(0,int(entry.get("source_rows") or 0))+recovered)
        legacy_status=entry.get("source_health","")
        entry["source_health"]=(legacy_status+" | "+
            "LICENSED_OR_RESEARCH_ONLY_ALTERNATE_EXACT_FILE_IDS_PARTIAL").strip(" |")
        entry["source_limitations"]=(entry.get("source_limitations","")+" | "+
            "Official alternative provided "+str(recovered)+
            " application IDs; prior failed/blocked source remains unresolved; "+
            "regional sources are not citywide complete.")[:850]
        entry["coverage_verified_citywide"]="False"
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
        "official_alternative_source_rows_joined":len(fallback),
        "regional_open_data_rows_joined":len(regional),
        "peel_open_data_rows_joined":len(peel),
        "peel_by_city":dict(Counter(x["city"] for x in peel)),
        "mississauga_custom_licence_ai_eligible":False,
        "regional_open_data_by_city":dict(Counter(x["city"] for x in regional)),
        "recovered_existing_city_application_rows":dict(alternative_by_city),
        "legacy_source_failures_retained":True,
        "alternative_source_cities":dict(Counter(x["city"] for x in fallback)),
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
