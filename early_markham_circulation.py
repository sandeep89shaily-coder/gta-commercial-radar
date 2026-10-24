"""Markham official biweekly application circulation PDFs: early publication watcher.

A PDF hyperlink is a DOCUMENT discovery event, not a new development project.
Report circulation-window dates are not the original PDF first-public date.
We monitor the official index to learn when a new biweekly source arrives
without guessing company buyers or submitting to any public portal.
"""
from __future__ import annotations
import argparse
import json
import re
import sqlite3
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup
from early_cue_watch import db_setup,save_source,_write_csv

PAGE="https://www.markham.ca/economic-development-business/planning-development-services/current-planning-applications-and-agendas"
SOURCE="markham_circulated_application_reports"
COLUMNS=("source_id","record_id","title","source_url","period_text",
 "source_date","date_basis","first_seen_at","last_seen_at",
 "current_snapshot_status","verification","procurement_status")
STATUS=("source_id","status","reports_indexed","2026_reports","new","updated",
        "baseline","warning","error")
EVENTS=("observed_at","source_id","record_id","change_type","title",
        "source_url","period_text")
HOSTS={"www.markham.ca","markham.ca"}
PERIOD=re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|"
                  r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|"
                  r"Nov|Dec)\s+\d{1,2}\b",re.I)
YEAR=re.compile(r"\b20(?:2\d|3\d)\b")

def txt(node):return " ".join(node.stripped_strings).strip() if node else ""

def parse_index(html):
    soup=BeautifulSoup(html,"html.parser")
    if "Circulated Planning and Development Applications" not in txt(soup):
        raise RuntimeError("Markham circulated application section not present")
    out={}
    for a in soup.find_all("a",href=True):
        label=txt(a)
        if not re.search(r"Circulated\s+Planning\s*(?:&|and)?\s*Development\s+Applications",
               label,re.I):continue
        url=urljoin(PAGE,a["href"])
        p=urlparse(url)
        if p.scheme!="https" or p.hostname not in HOSTS or not p.path.lower().endswith(".pdf"):
            continue
        if not YEAR.search(label) or not PERIOD.search(label):
            continue
        rid=p.path.casefold()
        if rid in out:continue
        out[rid]=dict(source_id=SOURCE,record_id=rid,title=label[:260],
          source_url=url,period_text=label[:240],
          source_date="",date_basis="CIRCULATION_WINDOW_NOT_PDF_PUBLICATION_DATE",
          verification="OFFICIAL_REPORT_LINK_NOT_INDIVIDUAL_APPLICATION",
          procurement_status="UNKNOWN")
    if len(out)<2:raise RuntimeError("Too few official biweekly PDF links for Markham index")
    return list(out.values())

def fetch(session):
    response=session.get(PAGE,headers={"User-Agent":"GTA-Radar-MarkhamEarlyReview/0.1"},
                         timeout=(10,45))
    response.raise_for_status()
    if "<html" not in response.text[:5000].lower() or len(response.text)<300:
        raise RuntimeError("Markham page blocked or unexpectedly empty")
    return response.text

def run(data_dir="data",output_dir="GTA_RADAR_RESULTS",session=None,observed=None):
    session=session or requests.Session()
    stamp=observed or datetime.now(timezone.utc).isoformat(timespec="seconds")
    d=Path(data_dir);o=Path(output_dir);d.mkdir(parents=True,exist_ok=True)
    o.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(d/"early_markham_reports_review.sqlite");db_setup(db)
    try:
        try:
            records=parse_index(fetch(session))
            saved=save_source(db,SOURCE,records,stamp)
            status=dict(source_id=SOURCE,status="SUCCESS_REPORT_INDEX",
              reports_indexed=len(records),
              **{"2026_reports":sum("2026" in r["title"] for r in records)},
              warning="INDEX_ONLY;CIRCULATION_DATE_NOT_PUBLIC_POST_DATE;PDF_CONTENTS_NEED_VERIFICATION",
              error="",**saved)
            rc=0
        except (requests.RequestException,RuntimeError,ValueError,sqlite3.DatabaseError) as e:
            db.rollback()
            status=dict(source_id=SOURCE,status="FAILED",
              reports_indexed=0,**{"2026_reports":0},
              new=0,updated=0,baseline="NO",
              warning="PUBLISHER_FAILURE_NOT_ZERO_APPLICATIONS",error=str(e)[:230])
            rc=1
        _write_csv(o/"EARLY_MARKHAM_REPORT_SOURCE_STATUS.csv",STATUS,[status])
        result=[]
        for sid,rid,first,last,content in db.execute(
             "SELECT source_id,record_id,first_seen_at,last_seen_at,content FROM snapshots "
             "WHERE source_id=?",(SOURCE,)):
            row=json.loads(content)
            result.append(dict(row,first_seen_at=first,last_seen_at=last,
              current_snapshot_status="SOURCE_FAILED" if rc else
                 "LINKED_LAST_SNAPSHOT" if last==stamp else "HISTORICAL_NOT_ON_CURRENT_INDEX"))
        _write_csv(o/"EARLY_MARKHAM_CIRCULATION_REPORT_INDEX.csv",COLUMNS,result)
        changes=[dict(json.loads(content),observed_at=at,
                    source_id=sid,record_id=rid,change_type=typ)
          for at,sid,rid,typ,content in db.execute(
            "SELECT observed_at,source_id,record_id,change_type,content "
            "FROM changes WHERE observed_at=? AND source_id=?",(stamp,SOURCE))]
        _write_csv(o/"EARLY_MARKHAM_NEW_REPORTS_REVIEW_ONLY.csv",EVENTS,changes)
        print("Markham circulation PDF index:",status["status"],
          "files",status["reports_indexed"],"postbaseline new",status["new"],
          "| no individual project/buyer inferred")
        return rc
    finally:db.close()

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir",default="data")
    p.add_argument("--output-dir",default="GTA_RADAR_RESULTS")
    a=p.parse_args()
    raise SystemExit(run(a.data_dir,a.output_dir))
