"""Ontario public investment announcements + federal OPEN tenders, two review lanes.

Sources are official public RSS/CSV. Never equate a company mentioned in a press
release with an open procurement or imply federal notices are GTA projects.
No V8, no scheduler, no DeepSeek or private-contact discovery.
"""
from __future__ import annotations
import argparse
import csv
import io
import json
import re
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse
import requests
from early_cue_watch import db_setup,save_source,_write_csv

RSS_URL="https://news.ontario.ca/newsroom/en/rss/allnews.rss"
TENDERS_URL="https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv"
SOURCES=("ontario_investment_news","federal_open_tenders")
ALLOWED={"news.ontario.ca","canadabuys.canada.ca"}
FIELDS=("source_id","record_id","title","site","company","company_role",
        "source_date","date_basis","source_url","signal_type","description",
        "commercial_fit","geographic_confidence","procurement_status",
        "first_seen_at","last_seen_at","current_snapshot_status","verification")
STATUS=("source_id","status","fetched","new","updated","baseline",
        "source_scope","date_coverage","warning","error")
CHANGE=("observed_at","source_id","record_id","change_type","title","site",
        "source_date","source_url","procurement_status")
GTA=re.compile(r"\b(?:Brampton|Mississauga|Toronto|Burlington|Milton|Oakville|"
               r"Vaughan|Markham|Richmond Hill|Ajax|Pickering|Whitby|Oshawa|"
               r"Etobicoke|Scarborough|Hamilton|Durham|Peel|Halton)\b",re.I)
INVEST=re.compile(r"\b(?:new (?:plant|factory|facility|distribution cent(?:re|er)|warehouse)|"
                  r"expan\w* (?:plant|factory|facility|manufactur\w*|production)|"
                  r"\$[\d.,]+\s*(?:million|billion)\s+invest\w*|"
                  r"breaks ground|manufactur\w* expansion|"
                  r"new production line|cold storage|data cent(?:re|er))\b",re.I)
SUPPLIERS=re.compile(r"\b(?:HVAC|refrigeration|electrical|electromechanical|"
                     r"warehouse|cooling|fire alarm|security|automation|"
                     r"manufacturing equipment|industrial equip\w*|"
                     r"building mechanical|boiler|chiller|cold storage|"
                     r"generator|fire protection|ventilation)\b",re.I)


def _get(session,url,max_bytes):
    p=urlparse(url)
    if p.scheme!="https" or p.hostname not in ALLOWED:
        raise ValueError("Source URL must be approved HTTPS publisher")
    r=session.get(url,headers={"User-Agent":"GTA-Radar-ManualPublicPreview/0.1"},
                  timeout=(10,60))
    r.raise_for_status()
    raw=r.content
    if len(raw)>max_bytes or len(raw)<20:
        raise RuntimeError("Official file empty or exceeds safety cap")
    return raw


def _iso(raw):
    if not raw:return ""
    try:
        dt=parsedate_to_datetime(raw)
        return dt.date().isoformat()
    except (TypeError,ValueError,IndexError):
        return ""


def parse_ontario_rss(raw):
    # Only process original XML; refuse HTML search errors as empty feed.
    if len(raw)>1_000_000:raise RuntimeError("Oversized public RSS")
    try:root=ET.fromstring(raw)
    except ET.ParseError as err:raise RuntimeError("RSS is not valid XML") from err
    channel=root.find("channel")
    if channel is None:raise RuntimeError("Ontario RSS channel not found")
    items=[]
    for article in channel.findall("item"):
        title=(article.findtext("title") or "").strip()
        link=(article.findtext("link") or "").strip()
        desc=re.sub(r"<[^>]+>"," ",article.findtext("description") or "")
        guid=(article.findtext("guid") or link).strip()
        if not link.startswith("https://news.ontario.ca/") or not title or not guid:
            continue
        text=" ".join((title,desc))
        geo="GTA_TEXT_MENTION_UNVERIFIED_SITE" if GTA.search(text) else "ONTARIO_WIDE_NOT_GTA_VERIFIED"
        match=bool(INVEST.search(text))
        items.append(dict(source_id="ontario_investment_news",record_id=guid,
             title=title,site="",company="",
             company_role="COMPANY_NOT_EXTRACTED_FROM_NEWS_RELEASE",
             source_date=_iso(article.findtext("pubDate")),
             date_basis="RSS_PUBLICATION_DATE",source_url=link,
             signal_type="PUBLIC_INVESTMENT_ANNOUNCEMENT",
             description=desc[:700],commercial_fit="REVIEW" if match else "LOW",
             geographic_confidence=geo,procurement_status="UNKNOWN",
             verification="PRESS_ANNOUNCEMENT_NOT_PROCUREMENT"))
    if not items:raise RuntimeError("No valid Ontario RSS items")
    if len({x["record_id"] for x in items})!=len(items):
        raise RuntimeError("Duplicate Ontario RSS GUID")
    return items


def parse_canadabuys_csv(raw):
    try:decoded=raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:raise RuntimeError("CanadaBuys CSV encoding changed") from exc
    reader=csv.DictReader(io.StringIO(decoded,newline=""))
    columns=set(reader.fieldnames or [])
    def col(*names):
        return next((n for n in names if n in columns),"")
    key=col("referenceNumber-numeroReference","referenceNumber-numeroReference-eng")
    title=col("title-titre-eng")
    posted=col("publicationDate-datePublication")
    stat=col("tenderStatus-appelOffresStatut-eng","tenderStatus-tenderStatut-eng")
    if not all((key,title,posted,stat)):
        raise RuntimeError("CanadaBuys CSV required columns absent; inspect dictionary")
    desc=col("description-description-eng")
    buyer=col("organizationName-nomOrganisation-eng","buyerName-nomAcheteur-eng",
              "organization-organisme-eng")
    location=col("deliveryLocation-lieuLivraison-eng","deliveryRegion-regionLivraison-eng",
                 "deliveryRegions-regionsLivraison-eng","province-province-eng")
    due=col("tenderClosingDate-appelOffresdateCloture",
            "tenderClosingDate-appelOffresDateCloture")
    notice=col("noticeURL-urlAvis","noticeUrl-urlAvis","link-lien-eng")
    items={}
    for r in reader:
        if (r.get(stat) or "").strip().lower()!="open":continue
        ident=(r.get(key) or "").strip()
        headline=(r.get(title) or "").strip()
        pub=(r.get(posted) or "").strip()
        if not ident or not headline or not pub:continue
        if ident in items:raise RuntimeError("Duplicate CanadaBuys notice reference")
        text=" ".join((headline,r.get(desc) or ""))
        loc=(r.get(location) or "").strip()
        page=(r.get(notice) or "").strip()
        if page and not page.startswith("https://canadabuys.canada.ca/"):page=""
        items[ident]=dict(source_id="federal_open_tenders",record_id=ident,
           title=headline,site=loc,company=(r.get(buyer) or "").strip(),
           company_role="PUBLISHED_FEDERAL_ORGANIZATION_NOT_PRIVATE_DEVELOPER",
           source_date=pub[:10] if re.fullmatch(r"20\d{2}-\d{2}-\d{2}.*",pub) else "",
           date_basis="FEDERAL_TENDER_PUBLICATION_DATE",
           source_url=page or "https://canadabuys.canada.ca/en/tender-opportunities",
           signal_type="FEDERAL_OPEN_BID_SOURCE_SNAPSHOT",
           description=text[:850],commercial_fit="REVIEW" if SUPPLIERS.search(text) else "LOW",
           geographic_confidence=("GTA_LOCATION_TEXT_REVIEW" if GTA.search(loc+" "+headline)
              else "CANADA_WIDE_DELIVERY_NOT_CONFIRMED_GTA"),
           procurement_status="OPEN_AT_SOURCE_SNAPSHOT_VERIFY_DEADLINE",
           verification="PUBLISHED_OPEN_TENDER_NOT_PRIVATE_DEVELOPMENT",
           attributes={"closing_date_original":(r.get(due) or "").strip()})
    if not items:raise RuntimeError("No valid OPEN records in public tender CSV")
    return list(items.values())


def run(data_dir="data",out_dir="GTA_RADAR_RESULTS",sources=None,session=None,now=None):
    selected=set(sources or SOURCES)
    if not selected or selected-set(SOURCES):raise ValueError("Invalid source")
    data_dir=Path(data_dir);out_dir=Path(out_dir)
    data_dir.mkdir(parents=True,exist_ok=True);out_dir.mkdir(parents=True,exist_ok=True)
    session=session or requests.Session()
    stamp=now or datetime.now(timezone.utc).isoformat(timespec="seconds")
    db=sqlite3.connect(data_dir/"early_investment_procurement_review.sqlite")
    db_setup(db)
    statuses=[]
    try:
        for sid in SOURCES:
            if sid not in selected:continue
            try:
                if sid=="ontario_investment_news":
                    rows=parse_ontario_rss(_get(session,RSS_URL,1_000_000))
                    scope="LATEST_RSS_WINDOW_NOT_COMPLETE_ARCHIVE"
                else:
                    rows=parse_canadabuys_csv(_get(session,TENDERS_URL,25_000_000))
                    scope="CURRENT_FEDERAL_OPEN_TENDER_EXPORT"
                status=save_source(db,sid,rows,stamp)
                statuses.append(dict(source_id=sid,status="SUCCESS",
                    fetched=len(rows),source_scope=scope,
                    date_coverage=sum(bool(x["source_date"]) for x in rows),
                    warning="NOT_VERIFIED_GTA_OR_BUYER_OF_PRIVATE_DEVELOPMENT",
                    error="",**status))
            except (RuntimeError,ValueError,requests.RequestException,sqlite3.Error) as exc:
                db.rollback()
                statuses.append(dict(source_id=sid,status="FAILED",
                    fetched=0,new=0,updated=0,baseline="NO",
                    source_scope="UNVERIFIED",date_coverage=0,
                    warning="FAILED_SOURCE_NOT_ZERO",error=str(exc)[:240]))
        good={r["source_id"] for r in statuses if r["status"]=="SUCCESS"}
        candidates=[]
        for sid,rid,first,last,body in db.execute(
              "SELECT source_id,record_id,first_seen_at,last_seen_at,content FROM snapshots"):
            if sid not in SOURCES:continue
            item=json.loads(body)
            if item["commercial_fit"]!="REVIEW":continue
            candidates.append(dict(item,first_seen_at=first,last_seen_at=last,
              current_snapshot_status="SOURCE_FAILED" if sid not in good else
                "OBSERVED_LATEST" if last==stamp else "HISTORICAL_OR_NOT_IN_CURRENT_WINDOW"))
        changes=[dict(json.loads(body),observed_at=t,source_id=s,record_id=i,change_type=k)
             for t,s,i,k,body in db.execute(
             "SELECT observed_at,source_id,record_id,change_type,content FROM changes WHERE observed_at=?",
             (stamp,))]
        _write_csv(out_dir/"EARLY_INVESTMENT_TENDERS_STATUS.csv",STATUS,statuses)
        _write_csv(out_dir/"EARLY_INVESTMENT_TENDERS_RESEARCH.csv",FIELDS,candidates)
        _write_csv(out_dir/"EARLY_INVESTMENT_TENDERS_CHANGES.csv",CHANGE,changes)
        for s in statuses:print(s["source_id"],s["status"],s["fetched"],
                      "postbaseline",s["new"]+s["updated"],flush=True)
        print("No DeepSeek; V8 isolated; no new on initial baseline")
        return 1 if any(s["status"]=="FAILED" for s in statuses) else 0
    finally:db.close()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir",default="data")
    p.add_argument("--output-dir",default="GTA_RADAR_RESULTS")
    p.add_argument("--source",choices=SOURCES,action="append")
    args=p.parse_args(argv)
    return run(args.data_dir,args.output_dir,args.source)


if __name__=="__main__":
    raise SystemExit(main())
