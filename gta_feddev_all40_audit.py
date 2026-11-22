"""Exhaustive, bounded FedDev 2026 Atom batch: audit ALL first 40 entries.

Every feed item receives a row, including failed, undated, non-industrial
and historic articles. Fetch each original once. Save full authored text for
evidence (local JSON, never publish or redistribute it). No DeepSeek,
unverified buyer claims, scraping bypass or outreach.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

from gta_freshness import _date
from gta_industrial_fulltext_discovery import (
    INDEXES, _fetch, _federal_atom_entries, _feddev_item, _page,
    _date_from_article, _excerpt, _stage, _canonical, CITY_NAMES,
    SECTOR, ACTION, MACHINES, FUTURE, COMPLETE, SUPPLIER
)

FEED_SOURCE="FEDDEV_OFFICIAL_2026_ARCHIVE"
REPORT="GTA_RADAR_FEDDEV_ALL40_EVIDENCE.csv"
EVIDENCE="GTA_RADAR_FEDDEV_ALL40_FULLTEXT_EVIDENCE.json"
STATUS="GTA_RADAR_FEDDEV_ALL40_STATUS.json"
LEDGER="GTA_RADAR_FEDDEV_ALL40_FIRST_SEEN_LEDGER.json"
MAX_ITEMS=40
FIELDS=(
    "feed_position","source_url","headline","feed_reported_date",
    "article_reported_date","date_basis","first_seen_by_radar",
    "last_checked","article_retrieval_status","article_length",
    "evidence_excerpt","city_mentioned_unverified","company_identified",
    "company_identification_status","equipment_explicit","equipment_evidence_quote",
    "manufacturing_expansion_explicit","procurement_stage",
    "published_in_last_7_days","freshness_classification",
    "public_business_contact_route","business_contact_role",
    "purchasing_contact_verified","supplier_selection_verified",
    "open_equipment_order_verified","review_reason"
)
CITY_SEARCH=[(re.compile(r"(?<!\w)"+re.escape(city)+r"(?!\w)",re.I),city)
             for city in CITY_NAMES]
COMPANY_PATTERNS=(
    re.compile(r"\b(?:investment (?:by|from)|funding (?:to|for)|"
               r"support (?:for|to)|investment in)\s+"
               r"([A-Z][\w&.'’\-]+(?:\s+[A-Z][\w&.'’\-]+){0,5})"),
    re.compile(r"\b(?:company|manufacturer|business)\s+"
               r"([A-Z][\w&.'’\-]+(?:\s+[A-Z][\w&.'’\-]+){0,5})"),
)
PROVEN_BAD={"Ontario","Canada","Southern Ontario","The Government",
            "Federal Economic Development","FedDev Ontario"}
EMAIL=re.compile(r"(?<![\w.])[\w.+-]+@(?:[\w-]+\.)+[A-Za-z]{2,}(?![\w.])")
MAX_SAVED_TEXT=30000

# Require a concrete equipment + industrial action passage. The broad MACHINES
# keyword includes "press", which incorrectly matched "Press Secretary" in
# government article footers; generic policy announcements are not purchases.
_SPECIFIC_MACHINE = re.compile(
    r"\b(?:cnc|machin(?:e|ery)|equipment|robot(?:s|ics|ic)?|automation|"
    r"production lines?|packaging lines?|industrial presses|stamping presses|"
    r"furnaces?|kilns?|boilers?|extruders?|stamping|milling|laser cutters?|"
    r"dust collectors?|scrubbers?|cooling towers?)\b", re.I)
_CONCRETE_ACTION = re.compile(
    r"\b(?:invest(?:ing|ment)?|moderniz\w*|upgrad\w*|retool\w*|"
    r"purchas\w*|acquir\w*|install\w*|add(?:ing)?|integrat\w*|"
    r"expan\w*|adopt\w*|replac\w*|new production)\b", re.I)
_SITE_CONTEXT = re.compile(
    r"\b(?:manufactur\w*|factory|plant|production|facilit\w*|"
    r"processing|fabricat\w*|industrial|steel|operations)\b", re.I)
_GENERIC_POLICY = re.compile(
    r"\b(?:businesses of all sizes|eligible businesses|"
    r"productivity mega deduction|funding applications|"
    r"businesses and organizations can apply|"
    r"government is helping canadian businesses|"
    r"sectors where canada has strong expertise|"
    r"industries support thousands of jobs|"
    r"defence ecosystem is dynamic|"
    r"government of canada is aiming to transform)\b", re.I)

def _specific_equipment_quote(text):
    """Extract an equipment/action/source passage; never infer a supplier bid."""
    # The footer on many Canada.ca releases contains "Press Secretary",
    # "Associated links", and named automation companies unrelated to a sale.
    main=re.split(r"\b(?:Associated links|Contacts|Media contacts)\b",
                  str(text or ""),maxsplit=1,flags=re.I)[0]
    for found in _SPECIFIC_MACHINE.finditer(main):
        excerpt=main[max(0,found.start()-230):found.end()+230]
        # A roster of recipient company names such as "Cravo Equipment" or
        # "Ascension Automation" does not itself describe an equipment order.
        if (excerpt.count(",") >= 4 and not re.search(
                r"\b(?:is receiving|will install|will purchase|is undertaking|"
                r"plans to install|plans to purchase)\b", excerpt, re.I)):
            continue
        if (_GENERIC_POLICY.search(excerpt)
                or not _CONCRETE_ACTION.search(excerpt)
                or not _SITE_CONTEXT.search(excerpt)):
            continue
        return " ".join(excerpt.split())[:650]
    return ""


def _company(text):
    """Conservative source-text *candidate*, never verified legal buyer."""
    for pattern in COMPANY_PATTERNS:
        for match in pattern.finditer(text[:14000]):
            name=" ".join(match.group(1).split()).strip(".,;:")
            if 5<=len(name)<=95 and name not in PROVEN_BAD and not name.startswith(
                    ("the ","The ","a ","A ")):
                return name,"REGEX_SOURCE_TEXT_CANDIDATE_NOT_VERIFIED"
    return "","NOT_IDENTIFIED_FROM_ARTICLE"

def _quote(text,pattern,limit=650):
    match=pattern.search(text)
    if not match:return ""
    a=max(0,match.start()-150)
    return " ".join(text[a:min(len(text),match.end()+limit)].split())[:900]

def _contact(text,page,company):
    """Link explicitly named company to outbound site only as review candidate.

    Other outbound publisher/news/agency links are not proof of a recipient
    business contact. A government media email is never the equipment buyer.
    """
    if company:
        words=[x.lower() for x in re.findall(r"[a-zA-Z]{4,}",company)
               if x.lower() not in ("incorporated","limited","company","industries",
                                    "canada","ontario","manufacturing")]
        for link,label in page.links:
            host=urlsplit(link).hostname or ""
            if (urlsplit(link).scheme=="https" and host and
                    not host.endswith(("canada.ca","gc.ca","ontario.ca")) and
                    not any(x in host for x in ("facebook.","linkedin.","youtube.",
                                               "twitter.","instagram.","x.com",
                                               "google.","bit.ly")) and
                    any(word in host.lower().replace("-","") for word in words)):
                return link[:700],"POSSIBLE_COMPANY_DOMAIN_FROM_SOURCE_LINK_NOT_BUYER"
    if EMAIL.search(text):
        return "","GOVERNMENT_MEDIA_OR_GENERAL_EMAIL_PRESENT_NOT_BUYER"
    return "","NO_PUBLIC_BUSINESS_CONTACT_ESTABLISHED"

def _read_ledger(path):
    if not path.is_file():return {}
    if path.is_symlink() or path.stat().st_size>10_000_000:
        raise ValueError("UNSAFE_FEDDEV_LEDGER")
    obj=json.loads(path.read_text(encoding="utf-8"))
    if obj.get("schema")!=1 or not isinstance(obj.get("first_seen"),dict):
        raise ValueError("UNRECOGNIZED_FEDDEV_LEDGER")
    return obj["first_seen"]

def _write_csv(path,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=FIELDS,extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            safe={}
            for key in FIELDS:
                value=str(row.get(key,""))
                safe[key]=("'"+value if value.lstrip().startswith(
                    ("=","+","-","@")) else value)
            writer.writerow(safe)

def run(results,*,today=None,fetcher=None,feed_url=None,limit=MAX_ITEMS):
    root=Path(results)
    if not root.is_dir():raise FileNotFoundError("EXISTING_RESULTS_FOLDER_REQUIRED")
    if not 1<=limit<=MAX_ITEMS:raise ValueError("LIMIT_MUST_BE_1_TO_40")
    day=_date(today) or dt.date.today()
    fetch=fetcher or _fetch
    url=feed_url or INDEXES[FEED_SOURCE]
    # Do not allow caller-supplied arbitrary untrusted destinations.
    if urlsplit(url).hostname!="api.io.canada.ca":
        raise ValueError("OFFICIAL_CANADA_ATOM_ONLY")
    ledger=_read_ledger(root/LEDGER)
    records=[];snapshots=[];source_error="";entries=[]
    try:
        entries=[(u,t,d) for u,t,d in _federal_atom_entries(fetch(url))
                 if _feddev_item({"url":u})]
    except Exception as exc:
        source_error=type(exc).__name__+":"+str(exc)[:120]
    for index,(article_url,title,feed_date) in enumerate(entries[:limit],1):
        key=hashlib.sha256(_canonical(article_url).encode()).hexdigest()
        first=ledger.setdefault(key,day.isoformat())
        row={name:"" for name in FIELDS}
        row.update(feed_position=index,source_url=article_url,headline=title,
                   feed_reported_date=feed_date,
                   first_seen_by_radar=first,last_checked=day.isoformat(),
                   article_retrieval_status="NOT_ATTEMPTED",
                   publishing_contact_verified="False",
                   purchasing_contact_verified="False",
                   supplier_selection_verified="False",
                   open_equipment_order_verified="False")
        try:
            page=_page(fetch(article_url))
            body=page.article_text
            date,basis=_date_from_article(page)
            if not date and feed_date:
                date=_date(feed_date)
                basis="ATOM_PUBLISHER_DATE_UNCONFIRMED_IN_ARTICLE"
            row["article_length"]=len(body)
            row["article_retrieval_status"]="FETCHED"
            row["article_reported_date"]=date.isoformat() if date else ""
            row["date_basis"]=basis
            recent=bool(date and 0<=(day-date).days<=7)
            row["published_in_last_7_days"]=str(recent)
            row["freshness_classification"]=(
                "RECENT_PUBLISHER_DATED_RESEARCH_NOT_VERIFIED_FIRST_PUBLICATION"
                if recent else
                "HISTORICAL_SOURCE_PUBLICATION" if date else
                "UNKNOWN_PUBLICATION_DATE_HOLD")
            row["city_mentioned_unverified"]=next(
                (city for matcher,city in CITY_SEARCH if matcher.search(body)),"")
            company,status=_company(page.heading+" "+body)
            row["company_identified"]=company
            row["company_identification_status"]=status
            equipment_quote=_specific_equipment_quote(body)
            row["equipment_explicit"]=str(bool(equipment_quote))
            row["equipment_evidence_quote"]=equipment_quote
            # The downstream equipment research shortlist must not elevate
            # generic workforce/funding programmes with boilerplate keywords.
            row["manufacturing_expansion_explicit"]=str(
                bool(equipment_quote and SECTOR.search(body)
                     and ACTION.search(body)))
            row["procurement_stage"]=_stage(body)
            row["evidence_excerpt"]=_excerpt(body)[:1100]
            contact,contact_role=_contact(body,page,company)
            row["public_business_contact_route"]=contact
            row["business_contact_role"]=contact_role
            if not date:
                row["review_reason"]="Original article lacks verifiable date"
            elif not SECTOR.search(body) or not ACTION.search(body):
                row["review_reason"]="No article-body manufacturing investment evidence"
            elif row["procurement_stage"] in (
                "COMPLETED_OR_OPERATIONAL_NOT_UPCOMING_ORDER",
                "SUPPLIER_OR_EQUIPMENT_ALREADY_AWARDED_RECHECK"):
                row["review_reason"]="Equipment stage completed or supplier already selected"
            elif not equipment_quote:
                row["review_reason"]="No concrete industrial equipment action in article body"
            else:
                row["review_reason"]="Research future equipment requirement and purchaser"
            snapshots.append({
                "position":index,"source_url":article_url,
                "headline":title,"publisher_date":row["article_reported_date"],
                "article_text":body[:MAX_SAVED_TEXT],
                "sha256":hashlib.sha256(body.encode("utf-8")).hexdigest(),
                "note":"Publisher text saved locally for evidence, not a redistribution license"
            })
        except Exception as exc:
            row["article_retrieval_status"]="FAILED_"+type(exc).__name__
            row["review_reason"]=str(exc)[:150]
            row["freshness_classification"]="RETRIEVAL_FAILED_NOT_FRESH"
            row["published_in_last_7_days"]="UNKNOWN"
            row["procurement_stage"]="UNKNOWN"
        records.append(row)
    _write_csv(root/REPORT,records)
    (root/EVIDENCE).write_text(json.dumps({"as_of":day.isoformat(),
        "source_url":url,"articles":snapshots},ensure_ascii=False,indent=2),
        encoding="utf-8")
    tmp=(root/LEDGER).with_suffix(".tmp")
    tmp.write_text(json.dumps({"schema":1,"first_seen":ledger},indent=2),
                   encoding="utf-8")
    tmp.replace(root/LEDGER)
    counts={
        "atom_agency_entries":len(entries),
        "selected_for_audit":min(limit,len(entries)),
        "rows_written":len(records),
        "full_articles_fetched":sum(r["article_retrieval_status"]=="FETCHED" for r in records),
        "fetch_failures":sum(r["article_retrieval_status"].startswith("FAILED_") for r in records),
        "recent_publisher_dated":sum(r["published_in_last_7_days"]=="True" for r in records),
        "historical_publisher_dated":sum(r["freshness_classification"]=="HISTORICAL_SOURCE_PUBLICATION" for r in records),
        "machinery_explicit_articles":sum(r["equipment_explicit"]=="True" for r in records),
        "future_expansion_research":sum(r["procurement_stage"]=="FUTURE_EXPANSION_RESEARCH_NOT_OPEN_PROCUREMENT" for r in records),
        "completed_or_awarded":sum(r["procurement_stage"] in (
            "COMPLETED_OR_OPERATIONAL_NOT_UPCOMING_ORDER",
            "SUPPLIER_OR_EQUIPMENT_ALREADY_AWARDED_RECHECK") for r in records),
        "source_text_company_candidates":sum(bool(r["company_identified"]) for r in records),
        "verified_equipment_buyers":0,"verified_open_orders":0,
    }
    result={"status":("FEDDEV_SOURCE_FAILED" if source_error else
                      "PARTIAL_FULLTEXT_RETRIEVAL" if counts["fetch_failures"] else
                      "ALL_REQUESTED_FEDDEV_ENTRIES_AUDITED"),
            "as_of":day.isoformat(),"feed":url,"feed_error":source_error,
            **counts,"limit":limit,"network_requests_max":limit+1,
            "paid_ai_calls":0,"outreach_authorized":False,
            "files":[REPORT,EVIDENCE,STATUS,LEDGER],
            "warning":"40 records are announcements, not verified machine orders. Company candidates, contacts and procurement stages are preliminary text evidence only."}
    (root/STATUS).write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results",required=True)
    ap.add_argument("--as-of",default=None)
    ap.add_argument("--limit",type=int,default=MAX_ITEMS)
    ap.add_argument("--zip",dest="zip_path",default=None,
                    help="Optional output ZIP for one-step Desktop upload")
    args=ap.parse_args()
    result=run(args.results,today=args.as_of,limit=args.limit)
    if args.zip_path:
        destination=Path(args.zip_path).expanduser()
        if not destination.parent.is_dir():
            raise FileNotFoundError("ZIP_DESTINATION_PARENT_NOT_FOUND")
        if destination.suffix.lower()!=".zip":
            raise ValueError("ZIP_DESTINATION_MUST_END_IN_ZIP")
        with zipfile.ZipFile(destination,"w",compression=zipfile.ZIP_DEFLATED) as archive:
            for name in (REPORT,EVIDENCE,STATUS,LEDGER):
                archive.write(Path(args.results)/name,arcname=name)
        result["upload_zip"]=str(destination)
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
