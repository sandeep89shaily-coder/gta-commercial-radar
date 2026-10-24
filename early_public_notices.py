"""Official Milton/Pickering development notices and ERO proposal-stage REVIEW pilot.

Entirely additive: separate SQLite, no V8/scheduler/paid AI. First collection is a
historical baseline. Notice "posted" dates are preserved only when source displays
them. Publisher can remove rows without implying a project is cancelled.
"""
from __future__ import annotations
import argparse
import csv
import json
import re
import sqlite3
import hashlib
from datetime import datetime, date, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from early_cue_watch import db_setup, save_source, _write_csv

MILTON = "https://www.milton.ca/news/development-notices/"
PICKERING = "https://www.pickering.ca/business-building-development/planning-and-development/current-development-proposals/"
ERO = "https://ero.ontario.ca/search"
SOURCES = ("milton_notices", "pickering_proposals", "ero_proposal_watch")
FIELDS = ("source_id","record_id","title","site","company","company_role","stage",
          "signal_type","source_date","date_basis","first_seen_at","last_seen_at",
          "current_snapshot_status","source_url","commercial_fit","geographic_confidence",
          "description","procurement_status","verification","not_sale_ready_reason")
STATS = ("source_id","status","fetched","new","updated","baseline","scope",
         "published_dates","potential_commercial","warning","error")
CHANGES = ("observed_at","source_id","record_id","change_type","title","site",
           "source_date","source_url","commercial_fit","procurement_status")
HOSTS = {"www.milton.ca","milton.ca","www.pickering.ca","pickering.ca","ero.ontario.ca"}
NON_RES = re.compile(
    r"\b(?:industrial|warehouse|manufactur\w*|logistic\w*|factory|cold[- ]?storage|"
    r"commercial|retail|office|hotel|institutional|medical clinic|"
    r"loading docks?|distribution cent(?:er|re)|industrial addition|"
    r"dealership|auto dealership|energy[- ]from[- ]waste|waste processing|"
    r"data cent(?:er|re)|plant expansion|business park)\b",re.I)
HOME = re.compile(r"\b(?:townhouse|residential|dwelling|apartments?|condominium|"
                  r"single.detached|homes|housing)\b",re.I)
MUNICIPAL = re.compile(r"\b(?:Brampton|Mississauga|Toronto|Burlington|Milton|"
   r"Oakville|Vaughan|Markham|Richmond Hill|Pickering|Ajax|Whitby|Oshawa|"
   r"Durham|Peel|Halton|Hamilton|York Region)\b",re.I)
DATE_FORMATS = ("%B %d, %Y","%b %d, %Y","%B %d %Y","%Y-%m-%d",
                "%b. %d, %Y","%B %d %Y")
DATE_RE = re.compile(r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
                     r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
                     r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{1,2},?\s+20\d{2}\b"
                     r"|\b20\d{2}-\d{2}-\d{2}\b",re.I)
LIMIT = 30


def text(node):
    return " ".join(node.stripped_strings) if node else ""


def date_from(value):
    match=DATE_RE.search(str(value or ""))
    if not match:return ""
    raw=match.group(0).strip().replace("Sept ","Sep ")
    for fmt in DATE_FORMATS:
        try:
            parsed=datetime.strptime(raw,fmt).date()
            if date(2010,1,1)<=parsed<=date.today()+timedelta(days=365):
                return parsed.isoformat()
        except ValueError:pass
    return ""


def safe_url(base,href,allow_hosts=HOSTS):
    target=urljoin(base,href)
    p=urlparse(target)
    if p.scheme!="https" or p.hostname not in allow_hosts:
        raise ValueError("Refusing external/non-HTTPS source link")
    return target.split("#",1)[0]


def fetch(session,url,params=None):
    p=urlparse(url)
    if p.scheme!="https" or p.hostname not in HOSTS:
        raise ValueError("Untrusted official-source URL")
    r=session.get(url,params=params,headers={"User-Agent":"GTA-Radar-Public-Cue-Pilot/0.2"},timeout=(10,45))
    r.raise_for_status()
    html=r.text
    if "<html" not in html[:5000].lower() or len(html)<250:
        raise RuntimeError("Official source did not return an HTML document")
    return html


def classify(description):
    positive=bool(NON_RES.search(description))
    residential=bool(HOME.search(description))
    if positive and residential:return "MIXED_USE_REVIEW"
    if positive:return "POSSIBLE_COMMERCIAL"
    if residential:return "RESIDENTIAL_LIKELY"
    return "USE_UNKNOWN"


def as_record(source_id,record_id,title,url,*,municipality,posted="",site="",
              company="",description="",stage="",date_basis="NOT_PUBLISHED",
              signal_type="PUBLIC_NOTICE",extra=None):
    content=" ".join((title,description))
    return dict(source_id=source_id,record_id=record_id,title=title,site=site,
       company=company,company_role="PUBLISHED_APPLICANT_NOT_VERIFIED_BUYER" if company
       else "COMPANY_NOT_VERIFIED",stage=stage,signal_type=signal_type,
       source_date=posted,date_basis=date_basis if posted else "MISSING_OR_NOT_OBSERVED",
       source_url=url,commercial_fit=classify(content),
       geographic_confidence=municipality,description=description[:1100],
       procurement_status="UNKNOWN",verification="PUBLIC_CUE_NOT_PROCUREMENT",
       attributes=extra or {})


def card_date(anchor):
    # News listing places a posting date beside the official news-card link.
    for depth,container in enumerate([anchor.parent,anchor.parent.parent,
                                        anchor.parent.parent.parent]):
        if not container:continue
        raw=text(container)
        if len(raw)<450:
            d=date_from(raw)
            if d:return d
    return ""


def parse_milton(html):
    soup=BeautifulSoup(html,"html.parser")
    if "Development Notices" not in text(soup):
        raise RuntimeError("Milton news-list heading missing")
    rows={}
    for a in soup.find_all("a",href=True):
        title=text(a)
        href=a.get("href") or ""
        if not title or not re.search(r"(?:notice|public meeting|application for temporary|environmental assessment)",title,re.I):
            continue
        url=urljoin(MILTON,href)
        p=urlparse(url)
        if p.hostname not in {"www.milton.ca","milton.ca"} or "/news/posts/" not in p.path:
            continue
        rid=p.path.rstrip("/").split("/")[-1].lower()
        if not rid or rid in rows:continue
        published=card_date(a)
        rows[rid]=as_record("milton_notices",rid,title,url,municipality="MILTON",
             posted=published,date_basis="MILTON_NEWS_LIST_DATE",
             stage="PUBLIC_NOTICE",signal_type="PLANNING_NOTICE")
    if not rows:
        raise RuntimeError("Milton development notices not found (possible dynamic feed)")
    return list(rows.values()),("FIRST_LISTING_PAGE_ONLY;NOT_FULL_HISTORY"+
       (";SOME_DATES_MISSING" if any(not x["source_date"] for x in rows.values()) else ""))


def parse_pickering(html):
    soup=BeautifulSoup(html,"html.parser")
    if "Current Development Proposals" not in text(soup):
        raise RuntimeError("Pickering application-list heading missing")
    out={}
    ward=""
    for element in soup.find_all(["h2","h3","table"]):
        if element.name in ("h2","h3"):
            m=re.search(r"(All Wards|Ward\s+\d+)",text(element),re.I)
            if m:ward=m.group(1)
            continue
        table=element
        if not all(s in text(table.find("tr")).lower() for s in ("applicant","date posted")) if table.find("tr") else True:
            continue
        for tr in table.find_all("tr"):
            cells=tr.find_all("td",recursive=False)
            if len(cells)<3:continue
            company=text(cells[0]).strip()
            address=text(cells[1]).replace("Location Map","").strip()
            posted=date_from(text(cells[2]))
            link=cells[0].find("a",href=True)
            if not company or not address or not link:continue
            try:url=safe_url(PICKERING,link["href"],{"www.pickering.ca","pickering.ca"})
            except ValueError:continue
            rid=urlparse(url).path.rstrip("/").lower()
            if rid in out:continue
            out[rid]=as_record("pickering_proposals",rid,company,url,
                municipality="PICKERING",posted=posted,
                date_basis="PICKERING_OFFICIAL_DATE_POSTED",
                site=address,company=company,stage="ACTIVE_APPLICATION_INDEX",
                signal_type="PLANNING_APPLICATION_POSTED",extra={"ward":ward})
    if not out:
        raise RuntimeError("Pickering applicant/address/date table not found")
    return list(out.values()),("ACTIVE_PLANNING_INDEX;NO_SITE_PLAN_EXHAUSTIVENESS"+
            (";SOME_DATES_MISSING" if any(not x["source_date"] for x in out.values()) else ""))


def detail_extract(html,kind):
    soup=BeautifulSoup(html,"html.parser")
    content=soup.find("main") or soup.find("article") or soup
    for heading in content.find_all(re.compile("^h[1-6]$")):
        label=text(heading).lower().replace("’","'")
        keywords=("applicant's proposal","proposal") if kind=="milton" else ("proposal",)
        if not any(label==x for x in keywords):continue
        found=[]
        for sibling in heading.next_siblings:
            if getattr(sibling,"name",None) and re.fullmatch(r"h[1-6]",sibling.name):break
            words=text(sibling) if hasattr(sibling,"stripped_strings") else str(sibling).strip()
            if words:found.append(words)
            if len(" ".join(found))>1100:break
        result=" ".join(found).strip()
        if result:return result[:1100]
    return ""


def enrich_recent(items,session,kind,limit=12):
    # Fetch only a small bounded set of newest official project detail pages.
    ordered=sorted(items,key=lambda x:x.get("source_date") or "",reverse=True)
    warnings=[]
    for item in ordered[:limit]:
        try:
            details=detail_extract(fetch(session,item["source_url"]),kind)
            if details:
                item["description"]=details
                item["commercial_fit"]=classify(item["title"]+" "+details)
                item["attributes"]["detail_checked"]="YES"
            else:
                item["attributes"]["detail_checked"]="NO_PROPOSAL_SECTION"
        except (ValueError,RuntimeError,requests.RequestException) as exc:
            item["attributes"]["detail_checked"]="FETCH_FAILED"
            warnings.append(item["record_id"]+": "+type(exc).__name__)
    return items, warnings


def parse_ero_proposals(html):
    # Reuse V8's existing parser without editing or invoking V8's collector.
    from radar import _parse_ero_search_cards
    raw=_parse_ero_search_cards(html)
    if not raw:
        raise RuntimeError("No parsed ERO notice cards: fail rather than assert zero")
    records=[]
    for item in raw:
        if not re.search(r"\bproposal\b",str(item.get("NOTICE_STAGE","")),re.I):
            continue
        title=str(item.get("TITLE") or "")
        scope=" ".join(str(item.get(k) or "") for k in
                       ("INSTRUMENT_TYPE","TITLE","SUMMARY"))
        if not any(term in scope.upper() for term in
                ("ENVIRONMENTAL COMPLIANCE APPROVAL","AIR AND NOISE","AIR & NOISE",
                 "SEWAGE","WASTE","PERMIT TO TAKE WATER","INDUSTRIAL","FACTORY",
                 "MANUFACTURING","DATA CENTRE","DATA CENTER")):
            continue
        city="GTA_CITY_MENTIONED_REVIEW" if MUNICIPAL.search(scope) else "ONTARIO_LOCATION_UNVERIFIED"
        rid=str(item.get("ERO_NUMBER") or "")
        if not re.fullmatch(r"\d{3}-\d{4,}",rid):
            continue
        posted=date_from(str(item.get("PROPOSAL_POSTED") or ""))
        records.append(as_record("ero_proposal_watch",rid,title,
            str(item.get("NOTICE_URL") or ""),municipality=city,posted=posted,
            date_basis="ERO_PROPOSAL_POSTED",company=str(item.get("ENTITY_NAME") or ""),
            description=scope[:1100],stage="PROPOSAL",signal_type="INDUSTRIAL_ENVIRONMENTAL_PROPOSAL",
            extra={"notice_stage":item.get("NOTICE_STAGE",""),"instrument":item.get("INSTRUMENT_TYPE","")}))
    return records, len(raw)


def _all_urls_valid(rows):
    if not rows or len({r["record_id"] for r in rows})!=len(rows):
        raise RuntimeError("Empty or duplicate official source identity set")
    for row in rows:
        safe_url(row["source_url"],row["source_url"])


def run(data_dir="data",output_dir="GTA_RADAR_RESULTS",sources=None,session=None,
        now=None,detail_limit=12,ero_pages=3):
    chosen=set(sources or SOURCES)
    if not chosen or chosen-set(SOURCES):
        raise ValueError("Unknown public-notice source")
    session=session or requests.Session()
    now=now or datetime.now(timezone.utc).isoformat(timespec="seconds")
    data_dir=Path(data_dir); data_dir.mkdir(parents=True,exist_ok=True)
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(data_dir/"early_public_notices_review.sqlite")
    db_setup(conn)
    statuses=[]
    try:
        for source in SOURCES:
            if source not in chosen:continue
            try:
                if source=="milton_notices":
                    records,warning=parse_milton(fetch(session,MILTON))
                    records,problems=enrich_recent(records,session,"milton",detail_limit)
                    scope="VISIBLE_NEWS_LIST_PAGE"
                elif source=="pickering_proposals":
                    records,warning=parse_pickering(fetch(session,PICKERING))
                    records,problems=enrich_recent(records,session,"pickering",detail_limit)
                    scope="PUBLISHED_ACTIVE_APPLICATION_TABLE"
                else:
                    records=[];seen=set();raw_total=0;problems=[]
                    low=(date.today()-timedelta(days=120)).isoformat()
                    for page in range(ero_pages):
                        html=fetch_ero(session,{"date[min]":low,"date[max]":date.today().isoformat(),
                                                "search":"","page":page})
                        fresh,raw_count=parse_ero_proposals(html)
                        raw_total+=raw_count
                        for item in fresh:
                            if item["record_id"] not in seen:
                                records.append(item); seen.add(item["record_id"])
                        if raw_count < 20:break
                    warning="PROPOSAL_STAGE_ONLY;LIMITED_SEARCH_PAGES;ONTARIO_LOCATION_NOT_ALWAYS_KNOWN"
                    scope="RECENT_ERO_PROPOSAL_SEARCH"
                if not records and source=="ero_proposal_watch":
                    # Live source may genuinely have zero proposal-stage relevant
                    # notices in the bounded window. Never erase history.
                    statuses.append(dict(source_id=source,status="NO_MATCHES_REVIEW",
                       fetched=0,new=0,updated=0,baseline="NO",scope=scope,
                       published_dates=0,potential_commercial=0,warning=warning,
                       error="No eligible proposal-stage notices in searched pages"))
                    continue
                _all_urls_valid(records)
                saved=save_source(conn,source,records,now)
                statuses.append(dict(source_id=source,status="SUCCESS",fetched=len(records),
                     scope=scope,published_dates=sum(bool(r["source_date"]) for r in records),
                     potential_commercial=sum(r["commercial_fit"] in
                          ("POSSIBLE_COMMERCIAL","MIXED_USE_REVIEW") for r in records),
                     warning=(warning+(";DETAIL_FAILURES="+str(len(problems)) if problems else "")),
                     error="",**saved))
            except (requests.RequestException,ValueError,RuntimeError,sqlite3.DatabaseError) as exc:
                conn.rollback()
                statuses.append(dict(source_id=source,status="FAILED",fetched=0,
                    new=0,updated=0,baseline="NO",scope="NOT_VALIDATED",
                    published_dates=0,potential_commercial=0,warning="",error=str(exc)[:250]))
        valid={s["source_id"] for s in statuses if s["status"]=="SUCCESS"}
        queue=[]
        for source,rid,first,last,raw in conn.execute(
             "SELECT source_id,record_id,first_seen_at,last_seen_at,content FROM snapshots"):
            if source not in SOURCES:continue
            item=json.loads(raw)
            if item["commercial_fit"] not in ("POSSIBLE_COMMERCIAL","MIXED_USE_REVIEW"):continue
            state=("UNKNOWN_FAILED_SOURCE" if source not in valid else
                   "OBSERVED_THIS_RUN" if last==now else "NOT_IN_LATEST_VISIBLE_WINDOW")
            queue.append(dict(**item,first_seen_at=first,last_seen_at=last,
                 current_snapshot_status=state,
                 not_sale_ready_reason="BUYER_ROLE_UNVERIFIED;CONTRACT_UNVERIFIED;VENDOR_AVAILABILITY_UNKNOWN"))
        queue.sort(key=lambda x:(x.get("source_date") or "",x["source_id"]),reverse=True)
        changes=[]
        for observed,sid,rid,typ,raw in conn.execute(
              "SELECT observed_at,source_id,record_id,change_type,content "
              "FROM changes WHERE observed_at=?",(now,)):
            changes.append(dict(json.loads(raw),observed_at=observed,
                                source_id=sid,record_id=rid,change_type=typ))
        _write_csv(output_dir/"EARLY_PUBLIC_NOTICES_SOURCE_STATUS.csv",STATS,statuses)
        _write_csv(output_dir/"EARLY_PUBLIC_NOTICES_RESEARCH_QUEUE.csv",FIELDS,queue)
        _write_csv(output_dir/"EARLY_PUBLIC_NOTICES_CHANGES_REVIEW_ONLY.csv",CHANGES,changes)
        for x in statuses:print(x["source_id"],x["status"],"rows",x["fetched"],
                               "post-baseline",x["new"]+x["updated"],flush=True)
        print("Public-notice research candidates:",len(queue),
              "| historical baseline is not new | DeepSeek: $0")
        return 1 if any(x["status"]=="FAILED" for x in statuses) else 0
    finally:conn.close()


def fetch_ero(session,params):
    # Avoid joining filtered pages into an apparently complete snapshot.
    p=urlparse(ERO)
    if p.hostname not in HOSTS:raise ValueError("Invalid ERO host")
    response=session.get(ERO,params=params,headers={"User-Agent":"GTA-Radar-Public-Cue-Pilot/0.2"},
                         timeout=(10,45))
    response.raise_for_status()
    if "<html" not in response.text[:5000].lower():
        raise RuntimeError("ERO returned non-HTML")
    return response.text


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",choices=SOURCES,action="append")
    p.add_argument("--data-dir",default="data")
    p.add_argument("--output-dir",default="GTA_RADAR_RESULTS")
    p.add_argument("--detail-limit",type=int,default=12)
    p.add_argument("--ero-pages",type=int,default=3)
    a=p.parse_args(argv)
    if a.detail_limit<0 or a.detail_limit>25 or a.ero_pages<1 or a.ero_pages>5:
        p.error("Detail limit 0..25, ERO pages 1..5")
    return run(a.data_dir,a.output_dir,a.source,detail_limit=a.detail_limit,ero_pages=a.ero_pages)


if __name__=="__main__":
    raise SystemExit(main())
