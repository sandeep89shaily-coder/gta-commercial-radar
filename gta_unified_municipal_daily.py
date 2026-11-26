"""Reconcile independent municipal change lanes without fabricating freshness.

The V6 daily opportunity list only covers its monitored permit sources. This
bridge preserves those 159 rows but also ingests explicitly NEW/CHANGED records
from other municipal application collectors, with a city-by-city accounting of
source activity and failures. Baselines, historic masters and unchanged source
records cannot become today's new projects. No network or paid work.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import re
from collections import Counter,defaultdict
from pathlib import Path

from gta_freshness import _date
from gta_york_hamilton_open_data import LIVE, OBSERVATIONS, PUBLISHERS, STATUS as REGIONAL_STATUS

BASE="GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv"
OUTPUT="GTA_RADAR_UNIFIED_MUNICIPAL_DAILY_CHANGES.csv"
CITY="GTA_RADAR_UNIFIED_MUNICIPAL_CITY_AUDIT.csv"
STATUS="GTA_RADAR_UNIFIED_MUNICIPAL_DAILY_STATUS.json"
# These source-specific files are re-created by the full run, and describe
# explicit changes relative to a preserved municipal collection baseline.
FEEDS=(
 ("GTA_RADAR_GUELPH_GIS_NEW_OR_CHANGED.csv","GUELPH_GIS"),
 ("GTA_RADAR_MUNICIPAL_PROJECT_CHANGES.csv","MUNICIPAL_HTML"),
 ("GTA_RADAR_GGH_OFFICIAL_GIS_NEW_OR_CHANGED.csv","GGH_GIS"),
 ("GTA_RADAR_REGIONAL_PROJECT_DETAILS_NEW_OR_CHANGED.csv","REGIONAL_DETAIL"),
 # Independent file-ID collectors already run in the full municipal pipeline.
 # Only explicit FIRST_OBSERVED/RECORD_CHANGED rows are considered. The
 # historical project master and baseline outputs are never daily changes.
 ("GTA_RADAR_ADDITIONAL_CITY_GIS_NEW_OR_CHANGED.csv","ADDITIONAL_GIS"),
 ("GTA_RADAR_FIVE_CITY_OFFICIAL_NEW_OR_CHANGED.csv","FIVE_CITY_OFFICIAL"),
 ("GTA_RADAR_GGH_EXPANSION_NEW_OR_CHANGED.csv","GGH_EXPANSION"),
 ("GTA_RADAR_EARLY_APPLICATION_NEW_OR_CHANGED.csv","EARLY_APPLICATION"),
 ("GTA_RADAR_STRUCTURED_APPLICATION_CHANGES.csv","STRUCTURED_APPLICATION"),
 ("GTA_RADAR_OFFICIAL_CSV_IMPORT_NEW_OR_CHANGED.csv","AUTHORIZED_CSV"),
 ("GTA_RADAR_BURLINGTON_GIS_NEW_OR_CHANGED.csv","BURLINGTON_GIS"),
 ("GTA_RADAR_BURLINGTON_OFFICIAL_PAGES_NEW_OR_CHANGED.csv","BURLINGTON_PAGES"),
 ("GTA_RADAR_VAUGHAN_OFFICIAL_NOTICES_NEW_OR_CHANGED.csv","VAUGHAN_NOTICES"),
 ("GTA_RADAR_MARKHAM_CIRCULATION_CHANGES.csv","MARKHAM_CIRCULATION"),
 ("GTA_RADAR_NORTHERN_MAJOR_CITY_SOURCE_CHANGES.csv","NORTHERN_MAJOR"),
 ("GTA_RADAR_FOUR_CITY_LIVE_APPLICATIONS.csv","FOUR_CITY_LIVE"),
 (OBSERVATIONS,"REGIONAL_OPEN_DATA"),
 # Toronto remains served by the canonical daily permit feed; do not import
 # legacy Toronto CKAN changes dated weeks ago as current-day observations.
)
FIELDS=("observation","first_seen_local","last_seen_local","project_id","address",
        "city","source_id","source_keys","lane","description","event_date",
        "date_basis","source_record_date","changed_fields","freshness_band",
        "freshness_date","freshness_date_basis","source_age_days",
        "paid_freshness_eligible","current_source_status",
        "stage_from_local_status","record_source_url","record_source_url_basis",
        "official_source_portal_url","official_source_portal_basis",
        "source_observation_original","source_event_date_basis_original",
        "manual_research_url","service_hypotheses","source_group",
        "review_priority","follow_up","warning")
CITY_FIELDS=("city","primary_daily_new","primary_daily_changed",
             "secondary_new","secondary_changed",
             "public_feed_unchanged","municipal_master_application_rows",
             "source_collection_health","source_failures",
             "live_source_change_evidence","first_observed_today","changed_today",
             "first_observed_without_source_date","unchanged_live_rows",
             "source_access_state","daily_activity","notes")
KNOWN=("Toronto","Brampton","Mississauga","Hamilton","Burlington","Oakville",
       "Vaughan","Kitchener","Markham","Oshawa","Milton","Halton Hills",
       "Caledon","Cambridge","Waterloo","Guelph","Niagara Falls",
       "St. Catharines","Brantford","Barrie","Greater Sudbury","North Bay",
       "Peterborough","Whitby","Ajax","Newmarket","Richmond Hill","Windsor","Pickering",
       "London","Sarnia","Chatham-Kent")
OBS={"FIRST_OBSERVED","RECORD_CHANGED"}
OBS_ALIASES={
    "NORTHERN_MAJOR":{"SOURCE_CHANGED_REVIEW":"RECORD_CHANGED"},
    "FOUR_CITY_LIVE":{"FIRST_OBSERVED_NOT_FIRST_PUBLICATION":"FIRST_OBSERVED",
                      "SOURCE_UPDATED_NOT_FIRST_PUBLICATION":"RECORD_CHANGED"},
}
NON_EVENTS={"UNCHANGED","INITIAL_BASELINE","INITIAL_BASELINE_NOT_NEW"}

VALID_DATE=re.compile(r"^20\d\d-\d\d-\d\d")
def read(path):
    if not path.is_file():return []
    if path.is_symlink() or path.stat().st_size>60_000_000:
        raise ValueError("UNSAFE_DAILY_SOURCE")
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))
def write(path,rows,fields):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k:("'"+str(r.get(k,"")) if str(r.get(k,"")).lstrip().startswith(
                 ("=","+","-","@")) else r.get(k,"")) for k in fields})
def norm(s):
    return re.sub(r"[^a-z0-9]","",str(s or "").casefold())
def identity(row):
    city=norm(row.get("city"))
    # Prefer explicit application ID; never merge unrelated sites just
    # because the same address is used by multiple permit tenants.
    key=norm(row.get("source_keys") or row.get("application_id") or "")
    if key:return city,key
    return city,norm(row.get("project_id"))
def run(results,*,today=None,not_before=None):
    root=Path(results)
    if not root.is_dir():raise FileNotFoundError("RESULTS_DIRECTORY_REQUIRED")
    day=_date(today) or dt.date.today()
    def current(filename):
        path=root/filename
        return path.is_file() and (not_before is None or path.stat().st_mtime >= not_before)

    def current_rows(filename):
        return read(root/filename) if current(filename) else []

    def current_status(filename):
        if not current(filename):
            return {}
        path=root/filename
        if path.is_symlink() or path.stat().st_size>4_000_000:
            raise ValueError("UNSAFE_MUNICIPAL_SOURCE_STATUS")
        return json.loads(path.read_text(encoding="utf-8-sig"))

    base=current_rows(BASE)
    rows=[]; city_counts=defaultdict(Counter)
    exact=set();secondary_seen=set()
    for r in base:
        obs=str(r.get("observation") or "").strip().upper()
        if obs not in OBS or _date(r.get("last_seen_local")) != day:continue
        entry={k:r.get(k,"") for k in FIELDS}
        rows.append(entry)
        exact.add(identity(entry))
        city_counts[r.get("city","Unknown")]["primary_"+("new" if obs=="FIRST_OBSERVED" else "changed")]+=1
        if obs=="FIRST_OBSERVED" and not _date(entry["source_record_date"]):
            city_counts[r.get("city","Unknown")]["undated_first"]+=1
    secondary_sources={}
    four=current_status("GTA_RADAR_FOUR_CITY_SOURCE_STATUS.json")
    four_health={r["city"]:r for r in four.get("city_status", [])}
    regional_state=current_status(REGIONAL_STATUS) if current(OBSERVATIONS) else {}
    regional=regional_state.get("source_status", {})
    for filename,lane in FEEDS:
        data=current_rows(filename)
        rejected_reasons=Counter()
        audit=secondary_sources[lane]={"input_rows":len(data),"accepted":0,"rejected":0,
            "rejected_reasons":rejected_reasons,
            "unchanged":0,"baseline":0,"source_file_present":(root/filename).is_file(),
            "source_file_current":current(filename)}
        for r in data:
            raw_obs=str(r.get("observation") or r.get("source_observation") or "").strip().upper()
            obs=OBS_ALIASES.get(lane,{}).get(raw_obs,raw_obs)
            city=str(r.get("city") or "").strip()
            if lane=="FOUR_CITY_LIVE":
                city_source=four_health.get(city,{})
                if city_source.get("status") != "LIVE_APPLICATION_IDS_RETRIEVED_PARTIAL_COVERAGE":
                    audit["rejected"]+=1
                    rejected_reasons["NO_CURRENT_SUCCESSFUL_CITY_SOURCE"]+=1
                    continue
                if city_source.get("initial_baseline") and obs=="FIRST_OBSERVED":
                    obs="INITIAL_BASELINE"
            if lane=="REGIONAL_OPEN_DATA" and regional.get(PUBLISHERS.get(city),{}).get("status")!=LIVE:
                audit["rejected"]+=1
                rejected_reasons["NO_CURRENT_SUCCESSFUL_CITY_SOURCE"]+=1
                continue
            if obs in NON_EVENTS or obs.startswith("INITIAL_BASELINE_"):
                label="unchanged" if obs=="UNCHANGED" else "baseline"
                audit[label]+=1
                if city:
                    city_counts[city][label]+=1
                continue
            appid=str(r.get("application_id") or r.get("file_number") or "").strip()
            projectid=str(r.get("project_id") or r.get("candidate_id") or "").strip()
            scope=str(r.get("description") or r.get("scope") or
                      r.get("proposed_use") or r.get("project_description") or "").strip()
            first=_date(r.get("first_seen_local"))
            if obs not in OBS or not city or not (appid or projectid) or len(scope)<25:
                secondary_sources[lane]["rejected"]+=1
                rejected_reasons["MISSING_OBSERVATION_ID_OR_SCOPE"]+=1
                continue
            # A first-observed row can only be called new if it was first
            # observed this run. Otherwise it is retained as a review change.
            if obs=="FIRST_OBSERVED" and first!=day:
                secondary_sources[lane]["rejected"]+=1
                rejected_reasons["FIRST_OBSERVED_OUTSIDE_RUN_DAY"]+=1
                continue
            key=(norm(city),norm(appid or projectid))
            if key in secondary_seen or key in exact:
                secondary_sources[lane]["rejected"]+=1
                rejected_reasons["DUPLICATE_CITY_AND_SOURCE_ID"]+=1
                continue
            secondary_seen.add(key)
            date=str(r.get("source_record_date") or r.get("source_date") or
                     r.get("date") or r.get("circulation_date") or "")
            # An old filing's new recorded digest is a review event, not
            # today's first-publication or fresh commercial opportunity.
            portal=r.get("source_index_url") or ""
            record_url=(r.get("record_source_url") or r.get("original_record_url")
                        or r.get("official_record_url") or r.get("source_url")
                        or r.get("pdf_url") or "")
            if record_url == portal or (lane=="FOUR_CITY_LIVE" and r.get("source_kind") in {"INDEX_ONLY","OFFICIAL_INDEX"}):
                portal,record_url=record_url,""
            entry={k:"" for k in FIELDS}
            entry.update({
                "observation":obs,"first_seen_local":r.get("first_seen_local",""),
                "last_seen_local":day.isoformat(),
                "project_id":f"{lane}:{city}:{appid or projectid}",
                "address":r.get("address") or "",
                "city":city,"source_id":lane,
                "source_keys":appid or projectid,
                "lane":"MUNICIPAL_APPLICATION_CHANGE_REVIEW",
                "description":scope,"date_basis":"MUNICIPAL_SOURCE_CHANGE_NOT_FIRST_PUBLICATION",
                "source_record_date":date,
                "source_observation_original":raw_obs,
                "source_event_date_basis_original":r.get("source_date_basis") or r.get("date_basis") or "",
                "changed_fields":r.get("changed_fields") or "UNKNOWN",
                "current_source_status":r.get("current_status") or r.get("stage") or r.get("status") or "",
                "record_source_url":record_url,
                "record_source_url_basis":"SOURCE_RECORD_URL_NOT_INDEPENDENTLY_RECHECKED" if record_url else "",
                "official_source_portal_url":portal,
                "source_group":"MUNICIPAL_APPLICATION_SOURCE_CHANGE",
                "paid_freshness_eligible":"False",
                "follow_up":"Verify exact source change, current project scope and original disclosure date.",
                "warning":"Source collector change is NOT a new public announcement; no verified buyer or open RFQ.",
            })
            age=(day-_date(date)).days if _date(date) else None
            if age is not None and 0<=age<=4:
                entry["freshness_band"]="RECENT_APPLICATION_EVENT_REVIEW_NOT_PUBLICATION"
            else:
                entry["freshness_band"]="OLDER_OR_UNKNOWN_APPLICATION_EVENT_REVIEW"
            rows.append(entry)
            if obs=="FIRST_OBSERVED" and not _date(date):
                city_counts[city]["undated_first"]+=1
            city_counts[city]["secondary_"+("new" if obs=="FIRST_OBSERVED" else "changed")]+=1
            secondary_sources[lane]["accepted"]+=1
    for r in current_rows("GTA_RADAR_DAILY_PUBLIC_RECORDS.csv"):
        if str(r.get("observation") or "").strip().upper()=="UNCHANGED":
            city_counts[str(r.get("city") or "Unknown")]["public_unchanged"]+=1
    for r in current_rows("GTA_RADAR_COMBINED_31_CITY_PROJECT_MASTER.csv"):
        if r.get("record_kind")=="APPLICATION":
            city_counts[str(r.get("city") or "Unknown")]["master_applications"]+=1
    health={}
    for r in current_rows("GTA_RADAR_COLLECTION_HEALTH.csv"):
        city=str(r.get("city") or "")
        health[city]=r
    readiness={r["city"]:r for r in current_rows("GTA_RADAR_COMBINED_24_CITY_LIVE_SOURCE_READINESS.csv")}
    combined={r["city"]:r for r in current_rows("GTA_RADAR_COMBINED_31_CITY_COVERAGE.csv")}
    alternatives=current_status("GTA_RADAR_ALTERNATIVE_OFFICIAL_STATUS.json").get("cities",{})
    for source in current_rows("GTA_RADAR_CROSS_COLLECTOR_SOURCE_FAILURES.csv"):
        city_counts[source["city"]]["source_failures"]+=1
    city_rows=[]
    for city in dict.fromkeys((*KNOWN,*sorted(city_counts))):
        x=city_counts[city];h=health.get(city,{})
        failures=str(h.get("source_failures") or "0")
        status=str(h.get("quality_status") or "NOT_REPORTED_BY_16_CITY_HEALTH")
        first=x["secondary_new"]+x["primary_new"]
        updates=x["secondary_changed"]+x["primary_changed"]
        changed=first+updates
        scope=readiness.get(city,{})
        extra=four_health.get(city,{})
        wider=combined.get(city,{})
        recorded=wider.get("source_health") or extra.get("status") or scope.get("measured_source_readiness") or status
        regional_source=regional.get(PUBLISHERS.get(city), {})
        regional_live=regional_source.get("status")==LIVE and bool(
            regional_state.get("records_by_city", {}).get(city, 0))
        if regional_live:
            recorded += " | REGIONAL_OPEN_DATA_LIVE_PARTIAL"
        failed=max(int(failures or 0),int(scope.get("blocked_or_failed_lanes") or 0),
                   int(wider.get("failed_or_blocked_source_count") or 0),x["source_failures"])
        if extra.get("status")=="BLOCKED_OR_FAILED_NO_NEW_LIVE_RECORDS":
            failed=max(failed,1)
        live=bool(regional_live or changed or x["unchanged"] or x["baseline"] or x["public_unchanged"]
                  or int(scope.get("live_sources_with_application_ids") or 0)
                  or int(extra.get("retrieved_application_id_records") or 0)
                  or int(alternatives.get(city,{}).get("valid_application_rows") or 0))
        blocked=failed or any(word in recorded.upper() for word in ("BLOCKED","FAIL","RIGHTS_NOT","NOT_VERIFIED_NO"))
        access=("LIVE_WITH_SOURCE_GAPS" if live and blocked else "LIVE_PARTIAL" if live
                else "BLOCKED_OR_FAILED" if blocked else "NO_CURRENT_LIVE_EVIDENCE")
        activity=("CHANGED_AND_FIRST_OBSERVED" if first and updates else "CHANGED" if updates
                  else "FIRST_OBSERVED" if first else "BASELINE" if x["baseline"]
                  else "UNCHANGED" if x["unchanged"] or x["public_unchanged"]
                  else "LIVE_NO_ADMITTED_CHANGE" if live else "NO_CURRENT_ACTIVITY_EVIDENCE")
        note=("CHANGE_FEED_HAS_OBSERVATIONS" if changed
              else "NO_NEW_OR_CHANGED_IN_MONITORED_FEEDS_NOT_CITYWIDE_ZERO")
        if not live and not x["master_applications"]:
            note="NO_LIVE_RECORDS_IN_RECONCILED_FEEDS_CHECK_SOURCE_ACCESS"
        city_rows.append({
            "city":city,"primary_daily_new":x["primary_new"],
            "primary_daily_changed":x["primary_changed"],
            "secondary_new":x["secondary_new"],
            "secondary_changed":x["secondary_changed"],
            "public_feed_unchanged":x["public_unchanged"],
            "municipal_master_application_rows":x["master_applications"],
            "source_collection_health":recorded,"source_failures":failed,
            "live_source_change_evidence":changed,"first_observed_today":first,"changed_today":updates,
            "first_observed_without_source_date":x["undated_first"],
            "unchanged_live_rows":x["unchanged"]+x["public_unchanged"],
            "source_access_state":access,"daily_activity":activity,
            "notes":note,
        })
    write(root/OUTPUT,rows,FIELDS)
    write(root/CITY,city_rows,CITY_FIELDS)
    report={"status":"UNIFIED_MUNICIPAL_SOURCE_CHANGE_RECONCILED_RESEARCH_ONLY",
        "as_of":day.isoformat(),"primary_daily_new":sum(x["primary_daily_new"] for x in city_rows),
        "primary_daily_changed":sum(x["primary_daily_changed"] for x in city_rows),
        "secondary_new":sum(x["secondary_new"] for x in city_rows),
        "secondary_changed":sum(x["secondary_changed"] for x in city_rows),
        "unified_change_rows":len(rows),
        "first_observed_without_source_date":sum(x["first_observed_without_source_date"] for x in city_rows),
        "city_activity_counts":dict(Counter(x["daily_activity"] for x in city_rows)),
        "city_access_counts":dict(Counter(x["source_access_state"] for x in city_rows)),
        "secondary_source_audit":secondary_sources,
        "cities_with_any_change_rows":[x["city"] for x in city_rows if x["live_source_change_evidence"]],
        "cities_with_unchanged_public_records":[x["city"] for x in city_rows if x["public_feed_unchanged"]],
        "citywide_collection_completeness_verified":False,
        "verified_first_publications":0,"verified_buyers":0,"verified_open_contracts":0,
        "secondary_feed_count":len(FEEDS),
        "secondary_feeds_with_data":sum(v["input_rows"]>0 for v in secondary_sources.values()),
        "no_network_or_paid_calls":True,
        "warning":"Baseline/historical records are never new opportunities. Zero changes can mean unchanged records, unavailable feeds or true quiet activity; citywide completeness is not established.",
        "outputs":[OUTPUT,CITY,STATUS]}
    (root/STATUS).write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results",required=True)
    p.add_argument("--as-of",default=None)
    a=p.parse_args()
    print(json.dumps(run(a.results,today=a.as_of),indent=2))
if __name__=="__main__":main()
