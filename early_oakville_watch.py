"""Official Oakville active planning & site-plan applications -- review-only.

Discovers seven Town ward indexes, captures the published planning/applicant
title and planning stage, then optionally reads a bounded number of detail
pages for scope and submission-document *labels*. Never treat submission month
as public posting date or town planning contact as purchaser. Index snapshots
and details are separate to prevent partial enrichment causing false alerts.
"""
from __future__ import annotations
import argparse
import csv
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from early_cue_watch import db_setup, save_source, _write_csv

BASE="https://www.oakville.ca/business-development/planning-development/active-development-applications/"
SOURCE="oakville_development"
HOSTS={"www.oakville.ca","oakville.ca"}
STAGES={
 "Development Applications":"DEVELOPMENT_APPLICATION",
 "Site Plan Applications":"SITE_PLAN",
 "Recently Approved Development Plan Applications":"RECENTLY_APPROVED_DEVELOPMENT",
 "Recently Approved Site Plan Applications":"RECENTLY_APPROVED_SITE_PLAN",
}
COMMERCIAL=re.compile(r"\b(?:industrial|warehous\w*|manufactur\w*|"
 r"brewery|food processing|commercial|retail|hotel|hospitality|"
 r"self.storage|cold.storage|office|factory|warehouse|clinic|"
 r"health centre|data cent(?:er|re)|loading dock\w*|plant)\b",re.I)
RESIDENTIAL=re.compile(r"\b(?:apartment|townhouse|residential|condominium|"
                       r"dwelling|housing)\b",re.I)
FIELDS=("source_id","record_id","title","site","company","company_role","stage",
        "source_date","date_basis","source_url","commercial_fit",
        "procurement_status","verification","first_seen_at","last_seen_at",
        "current_snapshot_status")
DETAILS=("record_id","title","stage","site","source_url","file_number",
         "description","detail_classification","source_document_labels",
         "document_label_months_not_posting_dates","detail_status",
         "purchasing_contact","procurement_status")
STAT=("source_id","status","ward_indexes","indexed_records","new","updated",
      "baseline","details_requested","details_complete","warning","error")
CHANGES=("observed_at","source_id","record_id","change_type","title","site",
         "source_url","stage","commercial_fit")
WARD_RE=re.compile(r"ward-([1-7])-development-and-site-plan-applications/?$",re.I)

def txt(node):
    return " ".join(node.stripped_strings).strip() if node else ""

def local_url(base,href):
    url=urljoin(base,str(href or ""))
    p=urlparse(url)
    if p.scheme!="https" or p.hostname not in HOSTS or len(url)>600:
        raise ValueError("Untrusted official Oakville link")
    return url.split("#",1)[0].split("?",1)[0]

def fetch(session,url):
    local_url(url,url)
    r=session.get(url,timeout=(10,45),
          headers={"User-Agent":"GTA-Radar-PublicPlanningReview/0.1"})
    r.raise_for_status()
    if len(r.text)<220 or "<html" not in r.text[:5000].lower():
        raise RuntimeError("Oakville returned blocked, empty or unexpected HTML")
    return r.text

def ward_urls(html):
    soup=BeautifulSoup(html,"html.parser")
    urls={}
    for a in soup.find_all("a",href=True):
        if not re.match(r"^Ward\s+[1-7]\s*-\s*Development",txt(a),re.I):
            continue
        try:url=local_url(BASE,a["href"])
        except ValueError:continue
        m=WARD_RE.search(urlparse(url).path)
        if m:urls[int(m.group(1))]=url
    if set(urls)!=set(range(1,8)):
        raise RuntimeError("Incomplete Oakville ward index; seven published wards required")
    return [urls[x] for x in range(1,8)]

def category(title):
    good=bool(COMMERCIAL.search(title));home=bool(RESIDENTIAL.search(title))
    if good and home:return "MIXED_USE_REVIEW"
    if good:return "POSSIBLE_COMMERCIAL"
    if home:return "RESIDENTIAL_LIKELY"
    return "USE_UNKNOWN"

def parse_ward(html,ward_url):
    soup=BeautifulSoup(html,"html.parser")
    stage=""
    rows={}
    ward_path=urlparse(ward_url).path.rstrip("/")+"/"
    for node in soup.find_all(["h2","h3","a"]):
        if node.name in ("h2","h3"):
            heading=txt(node)
            stage=STAGES.get(heading,"") if node.name=="h2" else stage
            continue
        if not stage or not node.has_attr("href"):
            continue
        try:url=local_url(ward_url,node["href"])
        except ValueError:continue
        p=urlparse(url)
        if not p.path.startswith(ward_path) or not p.path.rstrip("/").split("/")[-1]:
            continue
        label=txt(node)
        if len(label)<6:continue
        if url in rows:
            if rows[url]["stage"]!=stage:raise RuntimeError("One Oakville file linked under contradictory stages")
            continue
        # Town's card title often has "Applicant - street address - municipal file".
        # Company is a printed title segment, NOT buyer/developer role proof.
        segments=re.split(r"\s+-\s+",label)
        company=segments[0][:180] if len(segments)>1 else ""
        address=segments[-2].strip()[:250] if len(segments)>=3 else ""
        key=p.path.rstrip("/").casefold()
        rows[url]=dict(source_id=SOURCE,record_id=key,title=label[:400],
             site=address,company=company,
             company_role="PUBLISHED_PROJECT_TITLE_ENTITY_ROLE_NOT_VERIFIED",
             stage=stage,source_date="",date_basis="NO_OFFICIAL_PUBLIC_POSTING_DATE",
             source_url=url,commercial_fit=category(label),
             procurement_status="UNKNOWN",
             verification="OAKVILLE_PLANNING_RECORD_NOT_BUYER_OR_UNAWARDED_WORK")
    if not rows:
        raise RuntimeError("No application links extracted from a ward index")
    return list(rows.values())

def detail(html,record):
    soup=BeautifulSoup(html,"html.parser")
    content=soup.find("main") or soup.find("article") or soup
    h=next((x for x in content.find_all(["h2","h3"])
            if txt(x).lower()=="description"),None)
    description=""
    if h:
        parts=[]
        for sibling in h.next_siblings:
            if getattr(sibling,"name",None) in ("h2","h3"):break
            value=txt(sibling) if hasattr(sibling,"stripped_strings") else str(sibling).strip()
            if value:parts.append(value)
            if len(" ".join(parts))>=1600:break
        description=" ".join(parts)[:1600]
    if not description:
        # Avoid treating navigation/footer as application scope.
        raise RuntimeError("Oakville detail description not found")
    whole=txt(content)
    m=re.search(r"\bFile\s*No:?\s*([A-Za-z0-9./,\s-]{3,75})",whole,re.I)
    number=m.group(1).split("Description")[0].strip()[:75] if m else ""
    docs=[]
    for a in content.find_all("a",href=True):
        label=txt(a)
        if label.lower().startswith("submission ") and re.search(r"\b(?:site plan|elevation|landscape|floor plan|technical|servicing)\b",label,re.I):
            docs.append(label[:190])
    month_labels=sorted(set(re.findall(
        r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2}\b",
        " ".join(docs),re.I)))
    return dict(record_id=record["record_id"],title=record["title"],
       stage=record["stage"],site=record["site"],source_url=record["source_url"],
       file_number=number,description=description,
       detail_classification=category(record["title"]+" "+description),
       source_document_labels="; ".join(docs[:25]),
       document_label_months_not_posting_dates="; ".join(month_labels),
       detail_status="OFFICIAL_DETAIL_READ",
       purchasing_contact="NOT_IDENTIFIED_TOWN_PLANNING_ADDRESS_IS_NOT_BUYER",
       procurement_status="UNKNOWN")

def run(data_dir="data",output_dir="GTA_RADAR_RESULTS",session=None,observed=None,
        max_details=30):
    if not 0<=max_details<=100:raise ValueError("max_details must be between 0 and 100")
    session=session or requests.Session()
    observed=observed or datetime.now(timezone.utc).isoformat(timespec="seconds")
    d=Path(data_dir);o=Path(output_dir);d.mkdir(parents=True,exist_ok=True)
    o.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(d/"early_oakville_review.sqlite");db_setup(db)
    details=[]
    try:
        try:
            wards=ward_urls(fetch(session,BASE))
            records=[]
            for ward in wards:
                records.extend(parse_ward(fetch(session,ward),ward))
            unique={r["record_id"]:r for r in records}
            if len(unique)!=len(records):
                raise RuntimeError("Duplicate file pages across Oakville wards; review rather than silently merge")
            if len(unique)>900:raise RuntimeError("Oakville index exceeded safe item cap")
            # The index snapshot is independent of details. Avoid false UPDATE
            # events if detail sampling or document labels change between runs.
            saved=save_source(db,SOURCE,records,observed)
            focus=sorted((r for r in records if r["commercial_fit"] in
                     ("POSSIBLE_COMMERCIAL","MIXED_USE_REVIEW")),key=lambda r:(
                      r["stage"].startswith("RECENTLY_APPROVED"),r["record_id"]))
            for r in focus[:max_details]:
                try:details.append(detail(fetch(session,r["source_url"]),r))
                except (requests.RequestException,RuntimeError,ValueError) as e:
                    details.append(dict(record_id=r["record_id"],title=r["title"],
                        stage=r["stage"],site=r["site"],source_url=r["source_url"],
                        detail_status="DETAIL_UNAVAILABLE:"+type(e).__name__,
                        detail_classification=r["commercial_fit"],
                        purchasing_contact="UNVERIFIED",procurement_status="UNKNOWN"))
            warning="NO_PUBLIC_POSTING_DATES;INDEX_NOT_ALL_SITE_PLANS;DETAILS_SAMPLED;ROLE_UNVERIFIED"
            status=dict(source_id=SOURCE,status="SUCCESS_INDEX_ONLY",
                ward_indexes=len(wards),indexed_records=len(records),
                details_requested=min(len(focus),max_details),
                details_complete=sum(x["detail_status"]=="OFFICIAL_DETAIL_READ" for x in details),
                warning=warning,error="",**saved)
            rc=0
        except (requests.RequestException,RuntimeError,ValueError,sqlite3.DatabaseError) as e:
            db.rollback()
            status=dict(source_id=SOURCE,status="FAILED",
                ward_indexes=0,indexed_records=0,new=0,updated=0,baseline="NO",
                details_requested=0,details_complete=0,
                warning="FAILED_INDEX_NOT_ZERO_PROJECTS",error=str(e)[:230])
            rc=1
        _write_csv(o/"EARLY_OAKVILLE_SOURCE_STATUS.csv",STAT,[status])
        _write_csv(o/"EARLY_OAKVILLE_DETAILS_REVIEW.csv",DETAILS,details)
        review=[]
        for sid,rid,first,last,content in db.execute(
              "SELECT source_id,record_id,first_seen_at,last_seen_at,content FROM snapshots WHERE source_id=?",
              (SOURCE,)):
            item=json.loads(content)
            if item["commercial_fit"] not in ("POSSIBLE_COMMERCIAL","MIXED_USE_REVIEW"):
                continue
            review.append(dict(item,first_seen_at=first,last_seen_at=last,
                current_snapshot_status="INDEX_FAILED" if rc else
                "OBSERVED_LATEST" if last==observed else "HISTORICAL_NOT_ON_LATEST_INDEX"))
        _write_csv(o/"EARLY_OAKVILLE_RESEARCH_QUEUE.csv",FIELDS,review)
        changes=[dict(json.loads(content),observed_at=at,source_id=sid,
            record_id=rid,change_type=typ)
            for at,sid,rid,typ,content in db.execute(
            "SELECT observed_at,source_id,record_id,change_type,content "
            "FROM changes WHERE observed_at=? AND source_id=?",(observed,SOURCE))]
        _write_csv(o/"EARLY_OAKVILLE_CHANGES_REVIEW_ONLY.csv",CHANGES,changes)
        print("Oakville",status["status"],"indexed",status["indexed_records"],
              "details",status["details_complete"],"post-baseline new",status["new"],
              "No DeepSeek or verified purchasing contacts")
        return rc
    finally:db.close()

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir",default="data")
    p.add_argument("--output-dir",default="GTA_RADAR_RESULTS")
    p.add_argument("--max-details",type=int,default=30)
    a=p.parse_args()
    raise SystemExit(run(a.data_dir,a.output_dir,max_details=a.max_details))
