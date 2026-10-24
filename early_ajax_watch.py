"""Read-only Ajax official planning GIS preconsultation & active records, no paid APIs/login.

The old HTML index was removed/changed. Collector now uses municipal
ArcGIS MapServer/0 preconsultation and /1 active, skipping /3 duplicate view.

This is NOT an early investment claim: portal application index may include
minor variances/residential cases. Status "Open" = planning file, not tender.
"""
from __future__ import annotations
import argparse
import csv
import json
import re
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from early_cue_watch import db_setup,save_source,_write_csv
from early_ajax_arcgis import collect as collect_official_gis

URL="https://ajaxmaps.ajax.ca/bootrest/planningapps/property.html"
SOURCE="ajax_planning_properties"
STREET=re.compile(r"\b(?:Street|St|Road|Rd|Drive|Dr|Avenue|Ave|"
   r"Boulevard|Blvd|Court|Ct|Crescent|Cres|Lane|Way|Parkway|"
   r"Trail|Terrace)\b",re.I)
CIVIC=re.compile(r"^\d{1,6}\b")
CORNER=re.compile(r"^(?:Southeast|Southwest|Northeast|Northwest)\s+corner\b",re.I)
FILE=re.compile(r"\b((?:OPA\d{2}-A\d+|SPA\d{1,4}/\d{2}|SP\d{1,4}/\d{2}|"
  r"Z\d{1,4}/\d{2}|A\d{1,4}/\d{2}|LD\d{1,4}/\d{2}))\s*"
  r"(Open|Approved|Closed|Refused|Withdrawn|Appealed|Pending)?\b",re.I)
STATUS=("source_id","status","parsed","source_property_count","source_application_count",
    "new","updated","baseline","warning","error")
COLUMNS=("source_id","record_id","title","site","company","company_role",
         "stage","source_application_date","source_date","source_url","commercial_fit","procurement_status",
         "verification","first_seen_at","last_seen_at","current_snapshot_status")


def parse_ajax(html):
    soup=BeautifulSoup(html,"html.parser")
    text=soup.get_text("\n",strip=True)
    if "All applications" not in text:
        raise RuntimeError("Ajax public application index heading not found")
    size=re.search(r"\b(\d{1,5})\s+properties\s*,?\s*(\d{1,5})\s+applications\b",text,re.I)
    expected=(int(size.group(1)),int(size.group(2))) if size else (0,0)
    lines=[re.sub(r"\s+"," ",x).strip() for x in text.splitlines()]
    current=""
    rows={}
    start=next((i for i,l in enumerate(lines) if l.casefold()=="all applications"),0)
    for line_index,line in enumerate(lines[start+1:], start+1):
        if len(line)>280:continue
        if ((CIVIC.search(line) and STREET.search(line)) or CORNER.search(line)):
            current=line
            continue
        if not current:continue
        m=FILE.search(line)
        if not m:continue
        number=m.group(1).upper()
        status=m.group(2) or ""
        # Original DOM may split file number and status into adjacent lines.
        if not status:
            if line_index+1<len(lines) and lines[line_index+1] in (
               "Open","Approved","Closed","Refused","Withdrawn","Appealed","Pending"):
                status=lines[line_index+1]
        status=status.upper() if status else "STATUS_NOT_PARSED"
        key=re.sub(r"\W+","",current.upper())+"|"+number
        rows[key]=dict(source_id=SOURCE,record_id=key,
           title="Ajax public planning file "+number,site=current,
           company="",company_role="APPLICANT_NOT_PUBLISHED_IN_INDEX",
           stage="PLANNING_FILE_"+status,source_date="",source_url=URL,
           commercial_fit="USE_UNKNOWN",procurement_status="UNKNOWN",
           verification="AJAX_PLANNING_APPLICATION_NOT_BUSINESS_OR_TENDER",
           attributes={"file_number":number,"published_status":status,
                       "date_basis":"NO_PUBLIC_POSTED_DATE_ON_INDEX"})
    if not rows:raise RuntimeError("No Ajax application numbers parsed; preserve previous snapshots")
    # A low row count indicates layout/pagination failure, not an empty city.
    if expected[1] and len(rows)<max(3,int(expected[1]*0.6)):
        raise RuntimeError("Ajax HTML extraction coverage too low; index shape/pagination changed")
    return list(rows.values()),expected


def fetch(session):
    r=session.get(URL,headers={"User-Agent":"GTA-Radar-EarlyReview/0.1"},
        timeout=(10,60))
    r.raise_for_status()
    if len(r.text)<250 or "<html" not in r.text[:4000].lower():
        raise RuntimeError("Ajax did not return a usable HTML index")
    return r.text


def run(data_dir="data",out_dir="GTA_RADAR_RESULTS",session=None,stamp=None):
    session=session or requests.Session()
    stamp=stamp or datetime.now(timezone.utc).isoformat(timespec="seconds")
    d=Path(data_dir);o=Path(out_dir);d.mkdir(parents=True,exist_ok=True)
    o.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(d/"early_ajax_review.sqlite")
    db_setup(db)
    try:
        try:
            records,counts_by_layer=collect_official_gis(session)
            counts=(counts_by_layer[0],counts_by_layer[1])
            saved=save_source(db,SOURCE,records,stamp)
            stat=dict(source_id=SOURCE,status="SUCCESS",
                parsed=len(records),source_property_count=counts[0],
                source_application_count=counts[1],
                warning="PUBLIC_GIS_COMPLETE_IDS;PRECONSULT_AND_ACTIVE;SUBMISSION_DATE_NOT_PUBLIC_POSTING;BUYER_UNVERIFIED",
                error="",**saved)
            exit_code=0
        except (requests.RequestException,ValueError,RuntimeError,sqlite3.Error) as exc:
            db.rollback()
            stat=dict(source_id=SOURCE,status="FAILED",parsed=0,
                 source_property_count=0,source_application_count=0,new=0,updated=0,
                 baseline="NO",warning="SOURCE_FAILURE_NOT_ZERO",
                 error=str(exc)[:230])
            exit_code=1
        _write_csv(o/"EARLY_AJAX_SOURCE_STATUS.csv",STATUS,[stat])
        review=[]
        for sid,rid,seen,last,body in db.execute(
              "SELECT source_id,record_id,first_seen_at,last_seen_at,content FROM snapshots"):
            if sid!=SOURCE:continue
            item=json.loads(body)
            review.append(dict(item,first_seen_at=seen,last_seen_at=last,
              current_snapshot_status=("SOURCE_FAILED" if exit_code else
                 "OBSERVED_LATEST" if last==stamp else "NOT_LATEST_LISTING")))
        _write_csv(o/"EARLY_AJAX_PLANNING_REVIEW.csv",COLUMNS,review)
        print(SOURCE,stat["status"],"public ArcGIS features",stat["parsed"],
             "post-baseline changes",stat["new"]+stat["updated"],
             "| unknown commercial use; no AI")
        return exit_code
    finally:db.close()


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir",default="data")
    p.add_argument("--output-dir",default="GTA_RADAR_RESULTS")
    a=p.parse_args();raise SystemExit(run(a.data_dir,a.output_dir))
