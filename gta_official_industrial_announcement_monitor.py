"""Low-cost official industrial announcement monitor with persistent source ledger.

RSS/Atom publisher dates are reported dates, NOT independently proven first
publications. A first Radar sighting is NEVER a new publication by itself.
Does not infer vendors, purchasers, procurement, or open orders; no DeepSeek,
outreach, municipal access workaround or deletion of older records.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import email.utils
import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from gta_freshness import _date

FEEDS = {
    "ONTARIO_NEWSROOM": "https://news.ontario.ca/newsroom/en/rss/allnews.rss",
    "FEDDEV_ONTARIO": (
        "https://api.io.canada.ca/io-server/gc/news/en/v2?"
        "atomtitle=Federal+Economic+Development+Agency+for+Southern+Ontario"
        "&dept=economicdevelopmentsouthernontario&format=atom&orderBy=desc"
        "&pick=50&publishedDate%3E=2021-07-23&sort=publishedDate"
    ),
}
ALLOWED_HOST = {"news.ontario.ca", "api.io.canada.ca"}
LEDGER = "GTA_RADAR_INDUSTRIAL_ANNOUNCEMENT_LEDGER.json"
FRESH = "GTA_RADAR_FRESH_INDUSTRIAL_ANNOUNCEMENTS.csv"
HISTORY = "GTA_RADAR_INDUSTRIAL_ANNOUNCEMENT_WATCHLIST.csv"
STATUS = "GTA_RADAR_INDUSTRIAL_ANNOUNCEMENT_STATUS.json"
CSV_FIELDS = (
    "source","source_url","title","publisher_reported_date",
    "publisher_date_basis","first_seen_by_radar","last_seen_by_radar",
    "observation","company_source_claim_unverified","city_mentioned",
    "industrial_scope_quote","equipment_explicit_in_excerpt",
    "equipment_inference_only","classification","project_stage","buyer_verified",
    "open_supplier_package_verified","publication_independently_verified",
    "next_check",
)
# Expand sources cautiously. Business awards, policy briefs and workforce
# programmes alone are not machinery purchase opportunities.
SECTOR = re.compile(r"\b(?:manufactur\w*|production|factory|plant|"
    r"industrial|machinery|machine|retool\w*|assembly line|"
    r"processing facility|fabricat\w*|automotive|steelmaking|"
    r"food processing|robotic\w*|equipment)\b",re.I)
ACTION = re.compile(r"\b(?:invest\w*|expand\w*|expansion|new|build\w*|"
    r"construct\w*|moderniz\w*|upgrade|retool\w*|install\w*|"
    r"launch\w*|production line|acquir\w*|purchase\w*|"
    r"automat\w*|capacity)\b",re.I)
COMPLETED = re.compile(r"\b(?:retooling (?:is |was |has been )?complete|"
    r"retooling of the plant now complete|already operational|"
    r"now operational|has begun production|began production|"
    r"production (?:has )?started|opened (?:last |in )?20\d\d)\b",re.I)
MACHINES = re.compile(r"\b(?:CNC|machine(?:ry)?|equipment|robot\w*|"
    r"production line|automation|press(?:es)?|packaging line|"
    r"furnace|kiln|boiler|extruder|stamping|milling|"
    r"laser cutter|dust collector|scrubber|cooling tower)\b",re.I)
CITIES = ("Toronto","Brampton","Mississauga","Burlington","Oakville",
    "Vaughan","Kitchener","Cambridge","Waterloo","Guelph","Hamilton",
    "London","Sarnia","Windsor","Chatham-Kent","Barrie","Brantford",
    "St. Catharines","Niagara Falls","Ajax","Pickering","Whitby",
    "Markham","Oshawa","Newmarket","Milton","Caledon","Peterborough",
    "Woodbridge","Stevensville","Alliston")
MAX_FEED = 2_000_000
MAX_ITEMS_PER_SOURCE = 90

def _clean(text):
    value=html.unescape(re.sub(r"<[^>]*>"," ",str(text or "")))
    return " ".join(value.split())[:2200]

def _first_child_text(node,*names):
    for child in node:
        if child.tag.rsplit("}",1)[-1] in names:
            if child.text and child.text.strip():
                return child.text.strip()
    return ""

def _when(raw):
    val=str(raw or "").strip()
    if not val:return None
    try:
        stamp=email.utils.parsedate_to_datetime(val)
        if stamp:
            return stamp.date()
    except (TypeError,ValueError,OverflowError):
        pass
    return _date(val)

def _http(url):
    """Fixed official feed endpoints only; reject cross-domain redirects."""
    p=urlsplit(url)
    if p.scheme!="https" or p.hostname not in ALLOWED_HOST:
        raise ValueError("UNAUTHORIZED_FEED_HOST")
    req=Request(url,headers={"User-Agent":"GTA-Radar-Source-Monitor/1.0",
        "Accept":"application/rss+xml,application/atom+xml,application/xml,text/xml"})
    with urlopen(req,timeout=16) as resp:
        final=urlsplit(resp.geturl())
        if final.scheme!="https" or final.hostname not in ALLOWED_HOST:
            raise ValueError("UNAUTHORIZED_FEED_REDIRECT")
        data=resp.read(MAX_FEED+1)
    if len(data)>MAX_FEED:
        raise ValueError("FEED_TOO_LARGE")
    return data

def _entries(data):
    root=ET.fromstring(data)
    nodes=[x for x in root.iter() if x.tag.rsplit("}",1)[-1] in ("item","entry")]
    result=[]
    for node in nodes[:MAX_ITEMS_PER_SOURCE]:
        title=_clean(_first_child_text(node,"title"))
        body=_clean(_first_child_text(node,"description","summary","content"))
        published=_first_child_text(node,"pubDate","published","issued")
        date=_when(published)
        link=_first_child_text(node,"link")
        if not link:
            for child in node:
                if child.tag.rsplit("}",1)[-1]=="link" and (
                    child.attrib.get("rel","alternate")=="alternate"):
                    link=child.attrib.get("href","")
                    break
        parsed=urlsplit(link)
        if parsed.scheme!="https" or not parsed.hostname:
            continue
        if not title or not published or not date:
            # Atom updated and a crawler observation are NOT publication.
            continue
        result.append({"title":title,"body":body,"url":link[:1100],
                       "publisher_date":date.isoformat()})
    return result

def _write(path,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k:("'"+str(r.get(k,"")) if str(r.get(k,"")).lstrip().startswith(
                ("=","+","-","@")) else r.get(k,"")) for k in CSV_FIELDS})

def _load(path):
    if not path.is_file():return {}
    if path.is_symlink() or path.stat().st_size>20_000_000:
        raise ValueError("UNSAFE_ANNOUNCEMENT_LEDGER")
    data=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data,dict) or data.get("schema")!=1 or not isinstance(data.get("records"),dict):
        raise ValueError("INVALID_ANNOUNCEMENT_LEDGER_SCHEMA")
    return data["records"]

def _save(path,records):
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"schema":1,"records":records},
        indent=2,ensure_ascii=False),encoding="utf-8")
    tmp.replace(path)

def run(results, *, today=None, fetcher=None, feeds=None):
    root=Path(results)
    if not root.is_dir():raise FileNotFoundError("EXISTING_RESULTS_REQUIRED")
    day=_date(today) or dt.date.today()
    records=_load(root/LEDGER)
    sources=feeds if feeds is not None else FEEDS
    outputs=[];feed_health={};seen_urls=set();success=0
    for source,url in sources.items():
        try:
            data=(fetcher or _http)(url)
            entries=_entries(data)
            if not entries:
                # HTTP 200 with an empty/mismatched feed is not coverage.
                feed_health[source]={"status":"EMPTY_OR_UNRECOGNIZED_FEED",
                                     "items":0,
                                     "warning":"No dated RSS/Atom entries parsed; source coverage not verified."}
                continue
            success+=1
            feed_health[source]={"status":"FETCHED_AND_PARSED","items":len(entries)}
        except (OSError,ValueError,ET.ParseError,TypeError) as exc:
            feed_health[source]={"status":"FAILED","error_type":type(exc).__name__,
                                "items":0}
            continue
        for entry in entries:
            title=entry["title"]; body=entry["body"];combined=title+" "+body
            if not (SECTOR.search(combined) and ACTION.search(combined)):
                continue
            date=_date(entry["publisher_date"])
            url=entry["url"]
            if date>day:continue
            # Only retain publisher-linked documents, never treat an index
            # page or generic source URL as a project-specific announcement.
            host=urlsplit(url).hostname or ""
            if host not in {"news.ontario.ca","feddev-ontario.canada.ca",
                            "www.canada.ca","canada.ca","www.investontario.ca",
                            "investontario.ca"}:
                continue
            norm_url=urlsplit(url)._replace(fragment="",query="").geturl().rstrip("/")
            if norm_url in seen_urls:continue
            seen_urls.add(norm_url)
            key=hashlib.sha256(norm_url.encode("utf-8")).hexdigest()
            digest=hashlib.sha256(combined.encode("utf-8")).hexdigest()
            old=records.get(key)
            first=(old or {}).get("first_seen_by_radar") or day.isoformat()
            obs=("INITIAL_BASELINE" if old is None else
                 "SOURCE_TEXT_CHANGED" if old.get("digest")!=digest else "UNCHANGED")
            # Never allow a new feed ingestion to overwrite stored first-seen
            # or an original reporter-published date without a change note.
            original_date=(old or {}).get("first_reported_date") or entry["publisher_date"]
            # If a publisher revises an existing item and changes pubDate,
            # preserve its earliest observed publisher date for freshness.
            # A revision is not automatically a new equipment announcement.
            original_day=_date(original_date)
            if original_day and original_day<date:
                date=original_day
            if not old or old.get("digest")!=digest:
                records[key]={"source":source,"url":url,"title":title,
                    "excerpt":body[:1500],"digest":digest,
                    "first_seen_by_radar":first,"last_seen_by_radar":day.isoformat(),
                    "first_reported_date":original_date,
                    "last_feed_reported_date":entry["publisher_date"]}
            else:
                old["last_seen_by_radar"]=day.isoformat()
            city=next((c for c in CITIES if re.search(
                r"(?<!\w)"+re.escape(c)+r"(?!\w)",combined,re.I)),"")
            explicit=bool(MACHINES.search(combined))
            age=(day-date).days
            fresh=age<=7
            # Initial discovery of an old announcement goes into history.
            classification=("RECENT_PUBLISHER_REPORTED_ANNOUNCEMENT_RESEARCH_ONLY"
                if fresh else "HISTORICAL_ANNOUNCEMENT_WATCHLIST")
            # Excerpt-only evidence may not describe procurement timing.
            # Explicitly completed work cannot be marketed as upcoming.
            project_stage=("COMPLETED_OR_OPERATIONAL_RECHECK_PROCUREMENT"
                           if COMPLETED.search(combined)
                           else "STAGE_NOT_VERIFIED_FROM_FEED_EXCERPT")
            outputs.append({"source":source,"source_url":url,
                "title":title,"publisher_reported_date":date.isoformat(),
                "publisher_date_basis":"RSS_ATOM_PUBLISHER_DATE_NOT_INDEPENDENTLY_VERIFIED",
                "first_seen_by_radar":first,"last_seen_by_radar":day.isoformat(),
                "observation":obs,"company_source_claim_unverified":"",
                "city_mentioned":city,
                "industrial_scope_quote":body[:1100],
                "equipment_explicit_in_excerpt":str(explicit),
                "equipment_inference_only":str(not explicit),
                "classification":classification,
                "project_stage":project_stage,
                "buyer_verified":"False","open_supplier_package_verified":"False",
                "publication_independently_verified":"False",
                "next_check":"Confirm named manufacturer, exact plant, original publication, equipment procurement and potential vendors."})
    # Ledger history is never reset just because a feed was unavailable today.
    if success:
        _save(root/LEDGER,records)
    fresh=[x for x in outputs if x["classification"].startswith("RECENT_")]
    historical=[x for x in outputs if x not in fresh]
    fresh.sort(key=lambda r:(r["publisher_reported_date"],
        r["equipment_explicit_in_excerpt"],r["title"]),reverse=True)
    historical.sort(key=lambda r:r["publisher_reported_date"],reverse=True)
    _write(root/FRESH,fresh)
    _write(root/HISTORY,historical)
    report={"status":("NO_OFFICIAL_FEEDS_WITH_ITEMS" if success==0
                      else "PARTIAL_OFFICIAL_FEED_COLLECTION" if success<len(sources)
                      else "OFFICIAL_FEEDS_COLLECTED"),
            "run_date":day.isoformat(),"source_health":feed_health,
            "source_count":len(sources),"sources_collected":success,
            "feed_items_relevant":len(outputs),"recent_publisher_dated_research":len(fresh),
            "historical_observed":len(historical),
            "ledger_unique_urls":len(records),
            "verified_first_publications":0,"verified_buyers":0,
            "verified_open_supplier_packages":0,
            "newly_seen_not_publication_proof":True,
            "paid_ai_calls":0,"outreach_authorized":False,
            "outputs":[FRESH,HISTORY,LEDGER,STATUS]}
    (root/STATUS).write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results",required=True)
    p.add_argument("--as-of",default=None)
    a=p.parse_args()
    print(json.dumps(run(a.results,today=a.as_of),indent=2))
if __name__=="__main__":main()
