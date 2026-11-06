"""Unified collection truth layer for GTA Radar.

Reads already-generated official intake CSVs and diagnostics. It NEVER fetches,
runs AI, changes an upstream collector baseline or publishes a baseline as a new
commercial lead. Distinguishes application files from project-page signals and
preserves evidence provenance on cross-source deduplication.
"""
from __future__ import annotations
import csv
import datetime as dt
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from gta_early_applications import SOURCES

INPUTS={
    "TORONTO_CKAN":"GTA_RADAR_TORONTO_OPEN_DATA_APPLICATIONS.csv",
    "GUELPH_GIS":"GTA_RADAR_GUELPH_GIS_APPLICATIONS.csv",
    "BURLINGTON_GIS":"GTA_RADAR_BURLINGTON_GIS_PROJECTS.csv",
    "MUNICIPAL_HTML":"GTA_RADAR_MUNICIPAL_PROJECT_FEED.csv",
    "EARLY_HTML":"GTA_RADAR_EARLY_APPLICATION_CANDIDATES.csv",
    "TORONTO_BRAMP_GIS":"GTA_RADAR_STRUCTURED_APPLICATIONS_TORONTO_BRAMPTON.csv",
    "HAMILTON_KITCHENER_GIS":"GTA_RADAR_ADDITIONAL_CITY_GIS_APPLICATIONS.csv",
    "MARKHAM_CIRCULATION_PDF":"GTA_RADAR_MARKHAM_CIRCULATED_APPLICATIONS.csv",
    "OFFICIAL_CITY_NOTICE_RECOVERY":"GTA_RADAR_FIVE_CITY_OFFICIAL_APPLICATIONS.csv",
}
OUTPUT_ALL="GTA_RADAR_COLLECTION_MASTER.csv"
OUTPUT_REVIEW="GTA_RADAR_COLLECTION_NEW_OR_CHANGED_REVIEW.csv"
OUTPUT_HEALTH="GTA_RADAR_COLLECTION_HEALTH.csv"
OUTPUT_AUDIT="GTA_RADAR_COLLECTION_ACCEPTANCE.json"
FIELDS=("canonical_id","city","record_kind","application_id","address","description",
        "current_status","date","date_basis","application_year_hint",
        "source_count","source_types","evidence_urls","first_seen_local",
        "observation","commercial_screen","quality_flag","review_priority",
        "reason","verification_required")
HEALTH_COLUMNS=("city","application_files","project_only_signals",
                "new_or_changed_review","official_sources_with_records",
                "source_failures","access_failures","source_notes",
                "quality_status")
ACTIVITY_CLOSED=re.compile(r"\b(?:inactive|withdrawn|cancelled|canceled|refused|rejected|closed|omb approved|olt approved|"
                           r"final approval completed)\b",re.I)
STRONG_COMMERCIAL=re.compile(r"\b(?:industrial|warehouse|logistics|manufactur\w*|"
    r"hotel|restaurant|retail|office|commercial|distribution|factory|"
    r"storage|medical|hospital|clinic|data.cent(?:er|re)|business.park|"
    r"transport.terminal|trucking|cold.storage|banquet|mixed.use)\b",re.I)
LOW_VALUE=re.compile(r"\b(?:minor variance|fence only|demolition only|"
    r"part lot control exemption)\b",re.I)

def _csv(path):
    if not path.is_file():return []
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def _json(path):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError):return {}

def _text(value):
    return re.sub(r"\s+"," ",str(value or "")).strip()

def _year_hint(ident):
    """Filing identifier year is NOT a posting date. Return only a year hint."""
    ident=_text(ident)
    m=re.match(r"^([012]\d)[ -]\d{5,}",ident)
    if not m:
        m=re.search(r"(?:^|[-./A-Z])([012]\d)[.]\d{3}",ident,re.I)
    if not m:
        m=re.search(r"[-/](2\d)\b",ident)
    if not m:return ""
    year=2000+int(m.group(1))
    return str(year) if 2007<=year<=dt.date.today().year else ""

def _canonical(city,ident,source_id,record_kind):
    if ident:
        # File numbers are unique within a city, not across the entire GTA.
        key=re.sub(r"[^A-Z0-9]","",ident.upper())
        return city.upper().replace(" ","_")+":FILE:"+key
    return city.upper().replace(" ","_")+":SIGNAL:"+hashlib.sha256(
        source_id.encode()).hexdigest()[:20]

def _normalize(source,row):
    city=_text(row.get("city") or ("Markham" if source=="MARKHAM_CIRCULATION_PDF" else ""))
    if city not in SOURCES:return None
    ident=_text(row.get("application_id"))
    kind="APPLICATION_ID" if ident else "PROJECT_ONLY_SIGNAL"
    url=_text(row.get("record_source_url") or row.get("official_record_link")
        or row.get("pdf_url") or row.get("source_url") or row.get("source_dataset_url")
        or row.get("source_layer_url"))
    if url and not url.startswith("https://"):url=""
    title=_text(row.get("project_title"))
    addr=_text(row.get("address"))
    desc=_text(row.get("description") or row.get("proposed_use") or title)
    if not desc and not addr:return None
    source_id=_text(row.get("project_id")) or (url+"|"+title)
    if not source_id:return None
    status=_text(row.get("current_status") or row.get("status"))
    date=_text(row.get("source_record_date") or row.get("circulation_date"))
    basis=_text(row.get("date_basis") or row.get("source_record_date_basis"))
    observation=_text(row.get("observation"))
    positive=bool(STRONG_COMMERCIAL.search(desc+" "+title))
    inactive=bool(ACTIVITY_CLOSED.search(status) or
                  re.search(r"^\s*INACTIVE\b",desc,re.I))
    low_value=bool(LOW_VALUE.search(desc))
    quality=("INACTIVE_OR_CLOSED" if inactive else
             "LOW_VALUE_SCOPE" if low_value else
             "COMMERCIAL_SCOPE_REVIEW" if positive else "SCOPE_UNCLASSIFIED")
    return {"city":city,"application_id":ident,"record_kind":kind,
            "canonical_id":_canonical(city,ident,source_id,kind),
            "source":source,"source_url":url,
            "address":addr,"description":desc[:900],
            "current_status":status,"date":date,"date_basis":basis,
            "application_year_hint":_year_hint(ident),
            "first_seen_local":_text(row.get("first_seen_local")),
            "observation":observation,"quality_flag":quality,
            "positive":positive,"inactive":inactive,"low_value":low_value}

def _aggregate(records):
    groups=defaultdict(list)
    for record in records:groups[record["canonical_id"]].append(record)
    allrows=[]
    for key,members in sorted(groups.items()):
        # Prefer a row with a filing ID, substantive description, and an
        # exact source document. Keep every source URL separately.
        ranked=sorted(members,key=lambda r:(
            r["record_kind"]=="APPLICATION_ID",
            len(r["description"]),bool(r["source_url"])),reverse=True)
        best=ranked[0]
        sources=sorted(set(r["source"] for r in members))
        links=sorted(set(r["source_url"] for r in members if r["source_url"]))
        observed=[r["first_seen_local"] for r in members if r["first_seen_local"]]
        changes=[r["observation"] for r in members]
        change=("RECORD_CHANGED" if "RECORD_CHANGED" in changes else
                "FIRST_OBSERVED" if "FIRST_OBSERVED" in changes else
                "INITIAL_BASELINE" if "INITIAL_BASELINE" in changes else "UNCHANGED")
        positive=any(r["positive"] for r in members)
        inactive=all(r["inactive"] for r in members)
        low=all(r["low_value"] for r in members)
        scope=("COMMERCIAL_SCOPE_REVIEW" if positive else "SCOPE_UNCLASSIFIED")
        quality=("INACTIVE_OR_CLOSED" if inactive else "LOW_VALUE_SCOPE" if low else scope)
        # A re-observed 2013 file with an ambiguous current scrape timestamp
        # is not a newly available contract. Preserve it in the master ledger.
        historical=bool(best["application_year_hint"] and
            int(best["application_year_hint"])<dt.date.today().year-3 and
            not any(r["date_basis"]=="VERIFIED_FIRST_PUBLICATION_DATE" for r in members))
        is_new=change in ("FIRST_OBSERVED","RECORD_CHANGED")
        review=(is_new and best["record_kind"]=="APPLICATION_ID"
                and positive and not inactive and not low and not historical)
        if inactive:why="inactive_or_closed_in_source"
        elif low:why="low_value_scope"
        elif historical:why="historical_application_year_no_verified_recent_publication"
        elif best["record_kind"]!="APPLICATION_ID":why="no_verifiable_application_id"
        elif not positive:why="commercial_scope_not_established"
        elif not is_new:why="historical_or_unchanged_baseline"
        else:why="new_to_radar_or_changed;verify_before_sales_use"
        allrows.append({"canonical_id":key,"city":best["city"],
            "record_kind":best["record_kind"],"application_id":best["application_id"],
            "address":best["address"],"description":best["description"],
            "current_status":best["current_status"],"date":best["date"],
            "date_basis":best["date_basis"],
            "application_year_hint":best["application_year_hint"],
            "source_count":len(sources),"source_types":"; ".join(sources),
            "evidence_urls":"; ".join(links),
            "first_seen_local":min(observed) if observed else "",
            "observation":change,
            "commercial_screen":"POTENTIAL_COMMERCIAL" if positive else "UNCLASSIFIED",
            "quality_flag":quality,
            "review_priority":"MANUAL_REVIEW" if review else "BASELINE_OR_UNVERIFIED",
            "reason":why,
            "verification_required":"Verify application identity, project date, construction stage, owner and procurement before outreach"})
    return allrows

def _write(path,columns,records):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=columns,extrasaction="ignore")
        writer.writeheader();writer.writerows(records)

def build(results):
    root=Path(results)
    records=[]
    by_input={}
    for name,filename in INPUTS.items():
        rows=_csv(root/filename)
        by_input[name]={"filename":filename,"source_rows":len(rows),
                         "file_exists":(root/filename).is_file()}
        records.extend(item for row in rows if (item:=_normalize(name,row)) is not None)
    master=_aggregate(records)
    review=[r for r in master if r["review_priority"]=="MANUAL_REVIEW"]
    by_city=defaultdict(list)
    for row in master:by_city[row["city"]].append(row)

    statuses=_json(root/"GTA_RADAR_EARLY_APPLICATION_SOURCE_STATUS.json")
    html_status={r.get("city"):r for r in statuses.get("city_status",[])}
    municipal_status=_json(root/"GTA_RADAR_MUNICIPAL_PROJECT_FEED_STATUS.json")
    municipal={r.get("city"):r for r in municipal_status.get("source_status",[])}
    gis_1=_json(root/"GTA_RADAR_STRUCTURED_APPLICATION_SOURCE_STATUS.json")
    gis_2=_json(root/"GTA_RADAR_ADDITIONAL_CITY_GIS_STATUS.json")
    gis=defaultdict(list)
    for data in (gis_1,gis_2):
        for item in data.get("source_status",[]):
            gis[item.get("city")].append(item)
    ckan=_json(root/"GTA_RADAR_TORONTO_OPEN_DATA_STATUS.json")
    guelph=_json(root/"GTA_RADAR_GUELPH_GIS_STATUS.json")
    burlington=_json(root/"GTA_RADAR_BURLINGTON_GIS_STATUS.json")
    health=[]
    for city in SOURCES:
        items=by_city[city]
        h=html_status.get(city,{})
        mun=municipal.get(city,{})
        g=gis.get(city,[])
        sources_with_records=sorted(set(
            s for r in items for s in r["source_types"].split("; ") if s))
        failures=[]
        if h.get("fetch_status")=="FETCH_FAILED":
            failures.append("HTML:"+_text(h.get("reason")))
        for entry in mun.get("failures",[]):
            failures.append("MUNICIPAL:"+_text(entry.get("error")))
        for entry in g:
            if entry.get("status") in ("FAILED","FAILED_OR_INCOMPLETE"):
                failures.append(_text(entry.get("source"))+":"+_text(entry.get("error")))
        if city=="Burlington" and burlington.get("status")=="FAILED":
            failures.append("BURLINGTON_GIS:"+_text(burlington.get("error")))
        if city=="Guelph" and guelph.get("source_status"):
            gi=guelph["source_status"][0]
            if gi.get("status")=="FAILED":
                failures.append("GUELPH_GIS:"+_text(gi.get("error")))
        if city=="Toronto" and ckan.get("status")=="FAILED":
            failures.append("CKAN:"+_text(ckan.get("error")))
        n_app=sum(r["record_kind"]=="APPLICATION_ID" for r in items)
        n_signal=sum(r["record_kind"]=="PROJECT_ONLY_SIGNAL" for r in items)
        # A city's application feed is not automatically exhaustive.
        state=("APPLICATION_RECORDS_EXTRACTED_NOT_CITYWIDE_VERIFIED" if n_app else
               "PROJECT_SIGNALS_ONLY" if n_signal else
               "SOURCE_FAILURE_NO_RECORDS" if failures else
               "NO_RECORDS_VERIFIED")
        health.append({"city":city,"application_files":n_app,
                       "project_only_signals":n_signal,
                       "new_or_changed_review":sum(r["review_priority"]=="MANUAL_REVIEW" for r in items),
                       "official_sources_with_records":len(sources_with_records),
                       "source_failures":len(failures),
                       "access_failures":sum("ROBOTS" in x or "HTTP_403" in x for x in failures),
                       "source_notes":"; ".join(failures)[:1200],
                       "quality_status":state})
    _write(root/OUTPUT_ALL,FIELDS,master)
    _write(root/OUTPUT_REVIEW,FIELDS,review)
    _write(root/OUTPUT_HEALTH,HEALTH_COLUMNS,health)
    summary={"status":"COLLECTION_QUALITY_AUDIT_COMPLETE",
      "total_source_rows":len(records),"unique_application_files":
          sum(r["record_kind"]=="APPLICATION_ID" for r in master),
      "unique_project_only_signals":
          sum(r["record_kind"]=="PROJECT_ONLY_SIGNAL" for r in master),
      "excluded_inactive_or_closed":
          sum(r["quality_flag"]=="INACTIVE_OR_CLOSED" for r in master),
      "new_or_changed_commercial_manual_review":len(review),
      "cities_with_application_files":
          sum(r["application_files"]>0 for r in health),
      "cities_with_only_project_signals":
          sum(r["application_files"]==0 and r["project_only_signals"]>0 for r in health),
      "cities_without_any_project_signal":
          sum(r["application_files"]==0 and r["project_only_signals"]==0 for r in health),
      "verified_citywide_complete_coverage":0,
      "all_inputs":by_input,"per_city":health,"paid_ai_calls":0,
      "raw_applications_not_verified_active_projects":True,
      "application_year_hint_is_not_a_date":True,
      "review_is_manual_only":True,
      "outputs":{"master":str(root/OUTPUT_ALL),"review":str(root/OUTPUT_REVIEW),
                 "health":str(root/OUTPUT_HEALTH)},
      "warning":"Historical/unchanged data is not a new lead. Project-only URLs are not application files. Access failures are preserved; no citywide coverage claims."}
    (root/OUTPUT_AUDIT).write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary
