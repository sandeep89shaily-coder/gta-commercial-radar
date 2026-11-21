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
)
FIELDS=("observation","first_seen_local","last_seen_local","project_id","address",
        "city","source_id","source_keys","lane","description","event_date",
        "date_basis","source_record_date","changed_fields","freshness_band",
        "freshness_date","freshness_date_basis","source_age_days",
        "paid_freshness_eligible","current_source_status",
        "stage_from_local_status","record_source_url","record_source_url_basis",
        "official_source_portal_url","official_source_portal_basis",
        "manual_research_url","service_hypotheses","source_group",
        "review_priority","follow_up","warning")
CITY_FIELDS=("city","primary_daily_new","primary_daily_changed",
             "secondary_new","secondary_changed",
             "public_feed_unchanged","municipal_master_application_rows",
             "source_collection_health","source_failures",
             "live_source_change_evidence","notes")
KNOWN=("Toronto","Brampton","Mississauga","Hamilton","Burlington","Oakville",
       "Vaughan","Kitchener","Markham","Oshawa","Milton","Halton Hills",
       "Caledon","Cambridge","Waterloo","Guelph","Niagara Falls",
       "St. Catharines","Brantford","Barrie","Greater Sudbury","North Bay",
       "Peterborough","Whitby","Ajax","Newmarket","Windsor","Pickering",
       "London","Sarnia","Chatham-Kent")
OBS={"FIRST_OBSERVED","RECORD_CHANGED"}
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
def run(results,*,today=None):
    root=Path(results)
    if not root.is_dir():raise FileNotFoundError("RESULTS_DIRECTORY_REQUIRED")
    day=_date(today) or dt.date.today()
    base=read(root/BASE)
    rows=[]; counts=Counter();city_counts=defaultdict(Counter)
    exact=set();secondary_seen=set()
    for r in base:
        obs=str(r.get("observation") or "").strip().upper()
        if obs not in OBS:continue
        entry={k:r.get(k,"") for k in FIELDS}
        rows.append(entry)
        exact.add(identity(entry))
        city_counts[r.get("city","Unknown")]["primary_"+("new" if obs=="FIRST_OBSERVED" else "changed")]+=1
        counts["primary"]+=1
    secondary_sources={}
    for filename,lane in FEEDS:
        data=read(root/filename)
        secondary_sources[lane]={"input_rows":len(data),"accepted":0,"rejected":0,
            "source_file_present":(root/filename).is_file()}
        for r in data:
            obs=str(r.get("observation") or "").strip().upper()
            city=str(r.get("city") or "").strip()
            appid=str(r.get("application_id") or r.get("file_number") or "").strip()
            projectid=str(r.get("project_id") or "").strip()
            scope=str(r.get("description") or r.get("scope") or "").strip()
            first=_date(r.get("first_seen_local"))
            if obs not in OBS or not city or not (appid or projectid) or len(scope)<25:
                secondary_sources[lane]["rejected"]+=1
                continue
            # A first-observed row can only be called new if it was first
            # observed this run. Otherwise it is retained as a review change.
            if obs=="FIRST_OBSERVED" and first!=day:
                secondary_sources[lane]["rejected"]+=1
                continue
            key=(norm(city),norm(appid or projectid))
            if key in secondary_seen or key in exact:
                secondary_sources[lane]["rejected"]+=1
                continue
            secondary_seen.add(key)
            date=str(r.get("source_record_date") or r.get("date") or "")
            # An old filing's new recorded digest is a review event, not
            # today's first-publication or fresh commercial opportunity.
            entry={k:"" for k in FIELDS}
            entry.update({
                "observation":obs,"first_seen_local":r.get("first_seen_local",""),
                "last_seen_local":day.isoformat(),
                "project_id":f"{lane}:{city}:{appid or projectid}",
                "address":r.get("address") or r.get("project_title") or "",
                "city":city,"source_id":lane,
                "source_keys":appid or projectid,
                "lane":"MUNICIPAL_APPLICATION_CHANGE_REVIEW",
                "description":scope,"date_basis":"MUNICIPAL_SOURCE_CHANGE_NOT_FIRST_PUBLICATION",
                "source_record_date":date,"changed_fields":"UNKNOWN",
                "current_source_status":r.get("current_status",""),
                "record_source_url":r.get("source_url") or r.get("official_record_url") or "",
                "record_source_url_basis":"SOURCE_RECORD_URL_NOT_INDEPENDENTLY_RECHECKED",
                "source_group":"MUNICIPAL_APPLICATION_SOURCE_CHANGE",
                "paid_freshness_eligible":"False",
                "follow_up":"Verify exact source change, current project scope and original disclosure date.",
                "warning":"Source collector change is NOT a new public announcement; no verified buyer or open RFQ.",
            })
            age=(day-_date(date)).days if _date(date) else None
            if age is not None and 0<=age<=2:
                entry["freshness_band"]="RECENT_APPLICATION_EVENT_REVIEW_NOT_PUBLICATION"
            else:
                entry["freshness_band"]="OLDER_OR_UNKNOWN_APPLICATION_EVENT_REVIEW"
            rows.append(entry)
            city_counts[city]["secondary_"+("new" if obs=="FIRST_OBSERVED" else "changed")]+=1
            secondary_sources[lane]["accepted"]+=1
    for r in read(root/"GTA_RADAR_DAILY_PUBLIC_RECORDS.csv"):
        if str(r.get("observation") or "").strip().upper()=="UNCHANGED":
            city_counts[str(r.get("city") or "Unknown")]["public_unchanged"]+=1
    for r in read(root/"GTA_RADAR_COMBINED_31_CITY_PROJECT_MASTER.csv"):
        if r.get("record_kind")=="APPLICATION":
            city_counts[str(r.get("city") or "Unknown")]["master_applications"]+=1
    health={}
    for r in read(root/"GTA_RADAR_COLLECTION_HEALTH.csv"):
        city=str(r.get("city") or "")
        health[city]=r
    city_rows=[]
    for city in dict.fromkeys((*KNOWN,*sorted(city_counts))):
        x=city_counts[city];h=health.get(city,{})
        failures=str(h.get("source_failures") or "0")
        status=str(h.get("quality_status") or "NOT_REPORTED_BY_16_CITY_HEALTH")
        changed=x["secondary_new"]+x["secondary_changed"]+x["primary_new"]+x["primary_changed"]
        note=("CHANGE_FEED_HAS_OBSERVATIONS" if changed
              else "NO_NEW_OR_CHANGED_IN_MONITORED_FEEDS_NOT_CITYWIDE_ZERO")
        if not changed and not x["public_unchanged"] and not x["master_applications"]:
            note="NO_LIVE_RECORDS_IN_RECONCILED_FEEDS_CHECK_SOURCE_ACCESS"
        city_rows.append({
            "city":city,"primary_daily_new":x["primary_new"],
            "primary_daily_changed":x["primary_changed"],
            "secondary_new":x["secondary_new"],
            "secondary_changed":x["secondary_changed"],
            "public_feed_unchanged":x["public_unchanged"],
            "municipal_master_application_rows":x["master_applications"],
            "source_collection_health":status,"source_failures":failures,
            "live_source_change_evidence":changed,
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
        "secondary_source_audit":secondary_sources,
        "cities_with_any_change_rows":[x["city"] for x in city_rows if x["live_source_change_evidence"]],
        "cities_with_unchanged_public_records":[x["city"] for x in city_rows if x["public_feed_unchanged"]],
        "citywide_collection_completeness_verified":False,
        "verified_first_publications":0,"verified_buyers":0,"verified_open_contracts":0,
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
