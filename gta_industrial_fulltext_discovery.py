"""Official full-article industrial discovery (FedDev fallback + manufacturer news).

Read-only public HTML/Atom with bounded fetching, durable URL ledger and
source-specific diagnostics. Publisher-reported dates are separate from Radar
first-seen; no assumption of an open equipment order or purchasing contact.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin,urlsplit,urlunsplit
from urllib.request import Request,urlopen

from gta_freshness import _date
from gta_official_industrial_announcement_monitor import (
    _entries, SECTOR, ACTION, MACHINES, _clean, FEDDEV_ARCHIVE,
)

# Government-wide Atom is an explicit fallback: only FedDev release URLs qualify.
# This corrects the agency-specific feed that returned zero items on Nov 21.
GOVERNMENT_ATOM=("https://api.io.canada.ca/io-server/gc/news/en/v2?"
                 "type=newsreleases&sort=publishedDate&orderBy=desc&"
                 "publishedDate%3E=2021-10-25&pick=100&format=atom&"
                 "atomtitle=news%20releases")
INDEXES={
    "FEDDEV_GOVERNMENT_WIDE_ATOM":GOVERNMENT_ATOM,
    # The HTML archive is JS-rendered. Its official linked API is the actual
    # source of news items; parsing the HTML shell returns zero links.
    "FEDDEV_OFFICIAL_2026_ARCHIVE": FEDDEV_ARCHIVE,
    "INVEST_ONTARIO":"https://www.investontario.ca/press-room",
    "LINAMAR":"https://www.linamar.com/news-listings/",
    "MARTINREA":"https://www.martinrea.com/category/news-release/",
}
HOSTS={"api.io.canada.ca","www.canada.ca","canada.ca",
       "feddev-ontario.canada.ca","investontario.ca","www.investontario.ca",
       "www.linamar.com","linamar.com",
       "www.martinrea.com","martinrea.com"}
FILES={
    "ledger":"GTA_RADAR_FULLTEXT_INDUSTRIAL_LEDGER.json",
    "fresh":"GTA_RADAR_FULLTEXT_EQUIPMENT_FRESH_RESEARCH.csv",
    "watch":"GTA_RADAR_FULLTEXT_INDUSTRIAL_WATCHLIST.csv",
    "status":"GTA_RADAR_FULLTEXT_INDUSTRIAL_STATUS.json",
}
FIELDS=("source","source_url","title","publisher_reported_date",
        "publisher_date_basis","first_seen_by_radar","last_seen_by_radar",
        "observation","city_mentioned","company_source_claim_unverified",
        "industrial_scope_quote","specific_machinery_explicit",
        "procurement_stage","opportunity_class","publication_independently_verified",
        "buyer_verified","open_supplier_package_verified","verification_action")
CITY_NAMES=("Brampton","Mississauga","Toronto","Oakville","Burlington",
            "Vaughan","Guelph","Cambridge","Kitchener","Waterloo",
            "Hamilton","London","Sarnia","Windsor","Chatham-Kent",
            "Barrie","Woodbridge","Markham","Newmarket","Brantford",
            "Stevensville","Milton","Peterborough","Niagara Falls")
FUTURE=re.compile(r"\b(?:plans? to|propos(?:es|ed)|will (?:build|invest|install|"
    r"expand|purchase|construct|add|retool)|to be (?:built|installed)|"
    r"construction (?:is )?expected|planned investment|"
    r"expects? to (?:begin|start|install))\b",re.I)
COMPLETE=re.compile(r"\b(?:retooling (?:is |was |has been )?complet(?:e|ed)|"
    r"plant (?:is |was )?now operational|already operational|"
    r"now operating|has (?:begun|started) production|"
    r"production (?:has )?(?:begun|started)|"
    r"began production|is in operation|facility opened)\b",re.I)
SUPPLIER=re.compile(r"\b(?:supplier(?:s)? (?:already )?selected|"
    r"awarded (?:the )?(?:equipment|machinery) contract|"
    r"equipment (?:has been )?installed|installation completed)\b",re.I)
DATE_MONTH=re.compile(r"\b(January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+(\d{1,2}),?\s+(20\d{2})\b",re.I)
ISO_DATE=re.compile(r"\b20\d{2}-[01]\d-[0-3]\d\b")
MAX_INDEX_BYTES=1_500_000
MAX_ARTICLE_BYTES=1_200_000
MAX_ARTICLES=18

def _allowed(url):
    p=urlsplit(str(url or ""))
    return p.scheme=="https" and p.hostname in HOSTS and not p.username and not p.password

def _fetch(url):
    if not _allowed(url):
        raise ValueError("UNAUTHORIZED_SOURCE_URL")
    req=Request(url,headers={"User-Agent":"GTA-Radar-Industrial-Evidence/1.0",
                              "Accept":"text/html,application/atom+xml,application/rss+xml"})
    with urlopen(req,timeout=16) as response:
        if not _allowed(response.geturl()):raise ValueError("UNAUTHORIZED_REDIRECT")
        # Bound memory for both index and article. No PDF scraping.
        data=response.read(MAX_INDEX_BYTES+1)
        if len(data)>MAX_INDEX_BYTES:raise ValueError("OVERSIZE_RESPONSE")
        return data

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links=[];self.parts=[];self.meta={};self.anchor=None
        self.hidden=0;self.heading="";self.in_h1=False
        self.article_parts=[];self.main_parts=[]
        self.article_depth=0;self.main_depth=0
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=="article":self.article_depth+=1
        if tag=="main":self.main_depth+=1
        if tag in ("script","style","nav","footer"):
            self.hidden+=1
        if tag=="a":self.anchor={"url":d.get("href",""),"parts":[]}
        if tag=="h1":self.in_h1=True
        if tag=="meta":
            key=str(d.get("property") or d.get("name") or "").lower()
            val=d.get("content","")
            if key and val:self.meta[key]=val
        if tag=="time" and d.get("datetime"):
            self.meta.setdefault("time_datetime",d["datetime"])
    def handle_endtag(self,tag):
        if tag=="article":self.article_depth=max(0,self.article_depth-1)
        if tag=="main":self.main_depth=max(0,self.main_depth-1)
        if tag=="a" and self.anchor:
            self.links.append((self.anchor["url"],_clean(" ".join(self.anchor["parts"]))))
            self.anchor=None
        if tag=="h1":self.in_h1=False
        if tag in ("script","style","nav","footer"):
            self.hidden=max(0,self.hidden-1)
    def handle_data(self,data):
        if self.hidden:return
        cleaned=" ".join(data.split())
        if not cleaned:return
        if self.anchor is not None:self.anchor["parts"].append(cleaned)
        if self.in_h1:self.heading+=" "+cleaned
        self.parts.append(cleaned)
        if self.article_depth:self.article_parts.append(cleaned)
        if self.main_depth:self.main_parts.append(cleaned)
    @property
    def text(self):
        return " ".join(self.parts)[:35000]
    @property
    def article_text(self):
        # Prefer the authored article region; never use footer/forms to
        # establish manufacturing scope if an article region exists.
        if sum(map(len,self.article_parts))>=100:
            return " ".join(self.article_parts)[:30000]
        if sum(map(len,self.main_parts))>=100:
            return " ".join(self.main_parts)[:30000]
        return self.text

def _page(data):
    page=Page()
    page.feed(data.decode("utf-8",errors="replace"))
    return page

def _date_from_article(p):
    for name in ("article:published_time","datepublished","date",
                 "dc.date.issued","time_datetime"):
        if name in p.meta:
            d=_date(p.meta[name])
            if d:return d, "ARTICLE_PUBLISHER_METADATA_"+name.upper()
    # Fall back only to a clearly printed date very near the article title.
    intro=p.text[:1400]
    m=DATE_MONTH.search(intro)
    if m:
        try:
            date=dt.datetime.strptime(" ".join(m.groups()),"%B %d %Y").date()
            return date,"VISIBLE_ARTICLE_DATE"
        except ValueError:pass
    m=ISO_DATE.search(intro)
    if m:
        d=_date(m.group())
        if d:return d,"VISIBLE_ARTICLE_DATE"
    return None,"DATE_NOT_FOUND_ON_ARTICLE"

def _canonical(url):
    p=urlsplit(url)
    return urlunsplit((p.scheme,p.netloc.lower(),p.path.rstrip("/"),"",""))

def _feddev_item(item):
    # Agency identity is determined from the canonical federal path, never
    # merely from a text mention of FedDev in a different department's release.
    p=urlsplit(item["url"])
    path=p.path.lower()
    return ((p.hostname in ("www.canada.ca","canada.ca") and
             "/en/economic-development-southern-ontario/news/" in path)
            or (p.hostname=="feddev-ontario.canada.ca" and
                "/en/media-room/" in path))

def _federal_atom_entries(content):
    """Read real Atom links even when <published> is omitted.

    <updated> means the feed entry changed; it MUST NOT be relabeled as
    first publication. The linked original article has to establish a date
    before the research record can be admitted.
    """
    root=ET.fromstring(content)
    entries=[]
    for node in root.iter():
        if node.tag.rsplit("}",1)[-1]!="entry":
            continue
        title="";published="";url=""
        for child in node:
            name=child.tag.rsplit("}",1)[-1]
            if name=="title":
                title=_clean(" ".join(child.itertext()))
            elif name=="published" and child.text:
                published=child.text.strip()
            elif name=="link" and child.attrib.get("rel","alternate")=="alternate":
                url=child.attrib.get("href") or (child.text or "").strip()
        if not url:
            # Some government Atom entries use an <id> URL as their
            # canonical reference rather than an alternate link.
            for child in node:
                if child.tag.rsplit("}",1)[-1]=="id" and child.text:
                    value=child.text.strip()
                    if _allowed(value):
                        url=value
                        break
        if not title or not _allowed(url):
            continue
        published_date=_date(published) if published else None
        entries.append((url,title,published_date.isoformat() if published_date else ""))
    return entries

def _candidate_links(source,index,content):
    if source in ("FEDDEV_GOVERNMENT_WIDE_ATOM",
                  "FEDDEV_OFFICIAL_2026_ARCHIVE"):
        # Both feeds provide Atom entries. The agency-specific archive
        # endpoint itself is authoritative for FedDev affiliation, but
        # a linked article must still be hosted on official FedDev/Canada.ca.
        return [(url,title,feed_date) for url,title,feed_date
                in _federal_atom_entries(content)
                if _feddev_item({"url":url})]
    page=_page(content)
    seen=set();out=[]
    for relative,text in page.links:
        url=urljoin(index,relative)
        if not _allowed(url):continue
        path=urlsplit(url).path.lower()
        if source=="FEDDEV_OFFICIAL_2026_ARCHIVE":
            if not (path.startswith("/en/economic-development-southern-ontario/news/")
                    or path.startswith("/en/media-room/news-releases/")):
                continue
        if source=="LINAMAR" and not re.match(r"^/news/[^/]+/?$",path):
            continue
        if source=="MARTINREA" and not re.match(
                r"^/(?:news-release|news)/[^/]+/?$",path):
            continue
        if source=="INVEST_ONTARIO":
            if path.rstrip("/") in ("/press-room","/news","/"):continue
            if not re.search(r"(?:news|press|investment|media|announcement)",path):
                continue
        if (url in seen or len(text)>250 or
                (len(text)<15 and not
                 (source=="MARTINREA" and text.casefold()=="read more"))):
            continue
        seen.add(url)
        out.append((url,text,""))
    return out

def _excerpt(text):
    # Capture a directly checkable text segment around the first machinery/
    # production-expansion statement, not the whole publisher article.
    for pattern in (MACHINES,FUTURE,SECTOR):
        m=pattern.search(text)
        if m:return _clean(text[max(0,m.start()-150):m.start()+950])
    return _clean(text[:1100])

def _stage(text):
    completed=bool(COMPLETE.search(text))
    future=bool(FUTURE.search(text))
    if SUPPLIER.search(text):
        return "SUPPLIER_OR_EQUIPMENT_ALREADY_AWARDED_RECHECK"
    if completed:
        return "COMPLETED_OR_OPERATIONAL_NOT_UPCOMING_ORDER"
    if future:
        return "FUTURE_EXPANSION_RESEARCH_NOT_OPEN_PROCUREMENT"
    return "TIMING_UNKNOWN_REQUIRES_VERIFICATION"

def _load(path):
    if not path.is_file():return {}
    if path.is_symlink() or path.stat().st_size>20_000_000:
        raise ValueError("UNSAFE_FULLTEXT_LEDGER")
    obj=json.loads(path.read_text(encoding="utf-8"))
    if obj.get("schema")!=1 or not isinstance(obj.get("records"),dict):
        raise ValueError("UNRECOGNIZED_FULLTEXT_LEDGER")
    return obj["records"]

def _write_csv(path,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader()
        for row in rows:
            w.writerow({k:("'"+str(row.get(k,"")) if str(row.get(k,"")).lstrip().startswith(
                ("=","+","-","@")) else row.get(k,"")) for k in FIELDS})

def run(results,*,today=None,fetcher=None,indexes=None,max_articles=MAX_ARTICLES):
    root=Path(results)
    if not root.is_dir():raise FileNotFoundError("RESULTS_FOLDER_REQUIRED")
    day=_date(today) or dt.date.today()
    if not 1<=max_articles<=MAX_ARTICLES:raise ValueError("ARTICLES_LIMIT_EXCEEDED")
    fetch=fetcher or _fetch
    feeds=indexes if indexes is not None else INDEXES
    ledger=_load(root/FILES["ledger"])
    pending=[];health={};all_rows=[];visited=set()
    for source,index_url in feeds.items():
        try:
            if not _allowed(index_url):raise ValueError("UNAUTHORIZED_SOURCE_INDEX")
            payload=fetch(index_url)
            candidates=_candidate_links(source,index_url,payload)
            health[source]={"status":"INDEX_READ","candidate_links":len(candidates),
                            "articles_ok":0,"articles_failed":0,
                            "publisher_dated":0,"industrial":0}
            if source in ("FEDDEV_GOVERNMENT_WIDE_ATOM",
                          "FEDDEV_OFFICIAL_2026_ARCHIVE"):
                raw_items=_federal_atom_entries(payload)
                # Audit entry parsing before agency-path filtering. These
                # counts show whether the XML, URLs, or article stage is
                # responsible for a zero result; no content is discarded.
                root_xml=ET.fromstring(payload)
                health[source].update({
                    "atom_raw_entry_nodes":sum(
                        x.tag.rsplit("}",1)[-1]=="entry"
                        for x in root_xml.iter()),
                    "atom_valid_https_links":len(raw_items),
                    "atom_links_without_published":sum(
                        not item[2] for item in raw_items),
                    "atom_agency_url_matches":len(candidates),
                    "atom_example_hosts":sorted(set(
                        urlsplit(item[0]).hostname or "" for item in raw_items
                    ))[:8],
                })
            if not candidates:
                health[source]["status"]="NO_CANDIDATES_CHECK_INDEX_PARSER"
            for url,title,feed_date in candidates[:35]:
                canonical=_canonical(url)
                if canonical in visited:continue
                visited.add(canonical);pending.append((source,url,title,feed_date))
        except (OSError,ValueError,TypeError,ET.ParseError) as exc:
            health[source]={"status":"INDEX_FAILED","error_type":type(exc).__name__,
                            "candidate_links":0,"articles_ok":0,"articles_failed":0,
                            "publisher_dated":0,"industrial":0}
    # Give each accessible publisher a chance before the large FedDev archives
    # consume the bounded article budget. The dedicated FedDev all-40 collector
    # already handles that archive. Keep one article per source in the first
    # pass, then fill remaining slots in original within-source order.
    priority=("INVEST_ONTARIO","LINAMAR","MARTINREA",
              "FEDDEV_OFFICIAL_2026_ARCHIVE","FEDDEV_GOVERNMENT_WIDE_ATOM")
    by_source={name:[] for name in priority}
    for item in pending:
        by_source.setdefault(item[0],[]).append(item)
    selected=[]
    order=[name for name in priority if by_source.get(name)]
    order += [name for name in by_source if name not in order and by_source[name]]
    while len(selected)<max_articles and any(by_source.get(name) for name in order):
        for name in order:
            if by_source.get(name) and len(selected)<max_articles:
                selected.append(by_source[name].pop(0))
    # Bound total requests; no extra URLs or source-policy bypasses.
    for source,url,index_title,feed_date in selected:
        diag=health[source]
        try:
            page=_page(fetch(url))
            title=_clean(page.heading or page.meta.get("og:title") or index_title)
            date,basis=_date_from_article(page)
            if not date and feed_date:
                date=_date(feed_date);basis="PUBLISHER_ATOM_DATE_NOT_ARTICLE_CONFIRMED"
            if not date or date>day:
                diag["articles_failed"]+=1
                continue
            diag["articles_ok"]+=1;diag["publisher_dated"]+=1
            body=page.article_text
            combined=title+" "+body
            # The original implementation classified manufacturer articles
            # from site-wide newsletter/footer boilerplate. Qualify against
            # substantive article text, not a stray site navigation keyword.
            if (len(body)<100 or not SECTOR.search(body)
                    or not ACTION.search(body)):
                diag.setdefault("not_equipment_evidence",0)
                diag["not_equipment_evidence"]+=1
                continue
                continue
            if source=="FEDDEV_GOVERNMENT_WIDE_ATOM" and not _feddev_item({"url":url}):
                continue
            diag["industrial"]+=1
            key=hashlib.sha256(_canonical(url).encode()).hexdigest()
            digest=hashlib.sha256(combined.encode()).hexdigest()
            old=ledger.get(key)
            first=(old or {}).get("first_seen_by_radar") or day.isoformat()
            earliest=(old or {}).get("first_publisher_reported_date") or date.isoformat()
            earliest_date=_date(earliest)
            if earliest_date and earliest_date<date:date=earliest_date
            obs=("INITIAL_BASELINE" if old is None else
                 "ARTICLE_CHANGED" if digest!=old.get("digest") else "UNCHANGED")
            ledger[key]={"source":source,"url":url,"title":title,
                "first_seen_by_radar":first,"last_seen_by_radar":day.isoformat(),
                "first_publisher_reported_date":earliest,
                "date_basis":basis,"digest":digest,
                "content_excerpt":_excerpt(body)[:1200]}
            location=next((city for city in CITY_NAMES if re.search(
                r"(?<!\w)"+re.escape(city)+r"(?!\w)",combined,re.I)),"")
            stage=_stage(combined)
            is_recent=(day-date).days<=7
            classification=("RECENT_DATED_RESEARCH" if is_recent else
                            "HISTORICAL_WATCHLIST")
            # Completed work remains a dated announcement but is not
            # eligible for upcoming-equipment outreach without new proof.
            all_rows.append({
                "source":source,"source_url":url,"title":title,
                "publisher_reported_date":date.isoformat(),
                "publisher_date_basis":basis,
                "first_seen_by_radar":first,"last_seen_by_radar":day.isoformat(),
                "observation":obs,"city_mentioned":location,
                "company_source_claim_unverified":(
                    "Linamar" if source=="LINAMAR" else
                    "Martinrea International" if source=="MARTINREA" else ""),
                "industrial_scope_quote":_excerpt(body),
                "specific_machinery_explicit":str(bool(MACHINES.search(_excerpt(body)))),
                "procurement_stage":stage,"opportunity_class":classification,
                "publication_independently_verified":"False",
                "buyer_verified":"False","open_supplier_package_verified":"False",
                "verification_action":"Check article's original date, actual Ontario site, machinery need, purchaser, vendor award and tender status.",
            })
        except (OSError,ValueError,TypeError) as exc:
            diag["articles_failed"]+=1
            diag.setdefault("article_errors",[]).append(type(exc).__name__)
    # Keep durable prior first-seen evidence through temporary source outages.
    temp=(root/FILES["ledger"]).with_suffix(".tmp")
    temp.write_text(json.dumps({"schema":1,"records":ledger},indent=2),
                    encoding="utf-8")
    temp.replace(root/FILES["ledger"])
    recent=[r for r in all_rows if r["opportunity_class"]=="RECENT_DATED_RESEARCH"]
    history=[r for r in all_rows if r["opportunity_class"]!="RECENT_DATED_RESEARCH"]
    recent.sort(key=lambda r:r["publisher_reported_date"],reverse=True)
    _write_csv(root/FILES["fresh"],recent)
    _write_csv(root/FILES["watch"],history)
    feddev=health.get("FEDDEV_GOVERNMENT_WIDE_ATOM",{})
    feddev_archive=health.get("FEDDEV_OFFICIAL_2026_ARCHIVE",{})
    report={"status":"FULLTEXT_SOURCE_RESEARCH_WITH_GAPS"
               if any(v.get("status")!="INDEX_READ" or not v.get("publisher_dated")
                      for v in health.values()) else "FULLTEXT_SOURCES_RETRIEVED",
        "date":day.isoformat(),"sources":health,
        "federal_fallback_observed_feddev_articles":(
            feddev.get("publisher_dated",0)+feddev_archive.get("publisher_dated",0)),
        "articles_requested":len(selected),
        "publisher_round_robin_retrieval":True,
        "recent_dated_research":len(recent),"older_watchlist":len(history),
        "ledger_total_urls":len(ledger),
        "verified_open_orders":0,"verified_buyers":0,
        "publication_independently_verified":0,
        "outreach_authorized":False,"paid_ai_requests":0,
        "warning":"An announcement is not an open RFQ. Feed publication dates are publisher claims, not independently verified first-publication dates; company site may describe worldwide operations.",
        "outputs":FILES}
    (root/FILES["status"]).write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--results",required=True)
    p.add_argument("--as-of")
    a=p.parse_args()
    print(json.dumps(run(a.results,today=a.as_of),indent=2))
if __name__=="__main__":main()
