"""Evidence-first municipal document discovery and commercial verification.

Network discovery is bounded to configured official index pages; robots failures
fail closed. Buyer/supplier and lead-time claims require explicit dated evidence.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,json,re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin,urlparse
from urllib.robotparser import RobotFileParser
from collections import Counter
import requests
from toronto_pdf_download import AGENT, valid_url, fetch_one

MAX_HTML=2_000_000
INDEX_FIELDS=("city","index_url","document_url","document_id","discovered_at","status","reason")
BUYER_FIELDS=("project_id","organization","role","source_url","exact_quote","contact_url","buyer_authority","supplier_status","award_reference","verification")
class Anchors(HTMLParser):
    def __init__(self):super().__init__();self.hrefs=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            value=dict(attrs).get("href")
            if value:self.hrefs.append(value)

def robots_allowed(session,url):
    parsed=urlparse(url)
    robots=parsed.scheme+"://"+parsed.netloc+"/robots.txt"
    try:
        r=session.get(robots,timeout=12,allow_redirects=False)
        if r.status_code!=200 or r.url!=robots or len(r.content)>500_000:return False,"ROBOTS_UNAVAILABLE"
        p=RobotFileParser();p.parse(r.text.splitlines())
        return (True,"ALLOWED") if p.can_fetch(AGENT,url) else (False,"ROBOTS_DISALLOWED")
    except requests.RequestException:return False,"ROBOTS_NETWORK_ERROR"

def discover(indexes,out,*,session=None,max_indexes=12,max_documents=30):
    """Discover official Toronto report URLs; no manual PDF seed is required."""
    session=session or requests.Session()
    session.trust_env=False
    session.headers["User-Agent"]=AGENT
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    found={};checks=[]
    for item in list(indexes)[:max_indexes]:
        city=item.get("city","")
        url=item.get("index_url","")
        p=urlparse(url)
        if city!="Toronto" or p.scheme!="https" or p.hostname not in ("www.toronto.ca","secure.toronto.ca") or p.username or p.password:
            checks.append({"city":city,"url":url,"status":"INVALID_INDEX"});continue
        allowed,reason=robots_allowed(session,url)
        if not allowed:
            checks.append({"city":city,"url":url,"status":reason});continue
        try:
            response=session.get(url,timeout=20,allow_redirects=False)
            if response.status_code!=200 or response.url!=url or len(response.content)>MAX_HTML or "html" not in response.headers.get("Content-Type","").lower():
                checks.append({"city":city,"url":url,"status":"HTTP_OR_CONTENT_REJECTED"});continue
            parser=Anchors();parser.feed(response.text)
            count=0
            for raw in parser.hrefs:
                link=urljoin(url,raw)
                if not valid_url(link):continue
                if link in found:continue
                found[link]={"city":city,"index_url":url,"document_url":link,
                             "document_id":link.rsplit("/",1)[-1],
                             "discovered_at":dt.datetime.now(dt.timezone.utc).isoformat(),
                             "status":"DISCOVERED_NOT_FETCHED","reason":""}
                count+=1
                if len(found)>=max_documents:break
            checks.append({"city":city,"url":url,"status":"FETCHED","new_pdf_links":count})
            if len(found)>=max_documents:break
        except (requests.RequestException,ValueError) as error:
            checks.append({"city":city,"url":url,"status":"REQUEST_FAILED","reason":type(error).__name__})
    dest=out/"AUTOMATIC_DOCUMENT_DISCOVERY.csv"
    with dest.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=INDEX_FIELDS);w.writeheader();w.writerows(found.values())
    result={"indexes_checked":len(checks),"documents_discovered":len(found),
            "source_audit":checks,"discovered_csv":str(dest),"automatic_discovery":True,
            "documents_captured":0}
    (out/"AUTOMATIC_DOCUMENT_DISCOVERY.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result

def fetch_discovered(csv_path,out,*,limit=6,downloader=fetch_one):
    """Download only URLs discovered from permitted official indexes."""
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    with Path(csv_path).open(encoding="utf-8-sig",newline="") as h:
        items=list(csv.DictReader(h))
    records=[]
    for item in items[:max(0,min(limit,20))]:
        url=item.get("document_url","")
        if not valid_url(url):
            continue
        filename=hashlib.sha256(url.encode()).hexdigest()[:24]+".pdf"
        data=downloader(url,out/"pdfs"/filename)
        records.append({"url":url,**{key:data.get(key,"") for key in
                            ("status","reason","http_status","bytes","sha256","saved_path")}})
    target=out/"AUTOMATIC_PDF_FETCH_AUDIT.csv"
    fields=("url","status","reason","http_status","bytes","sha256","saved_path")
    with target.open("w",encoding="utf-8-sig",newline="") as h:
        w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows(records)
    return {"attempted":len(records),"captured":sum(x["status"]=="CAPTURED" for x in records)}

def classify_buyer(item):
    """AI observations are candidates; authority/awards only from explicit sourced statements."""
    role=str(item.get("role") or "").lower()
    exact=str(item.get("exact_quote") or "")
    source=str(item.get("source_url") or "")
    authority=str(item.get("buyer_authority_evidence") or "")
    award=str(item.get("award_evidence") or "")
    buyer=(role in ("purchasing_organization","procurement_contact") and
           bool(authority) and authority in exact and source.startswith("https://"))
    supplier="UNKNOWN"
    if award and award in exact and source.startswith("https://"):
        if re.search(r"\\b(?:awarded to|contract awarded|successful bidder)\\b",award,re.I):
            supplier="AWARDED_CLAIM_REQUIRES_CORROBORATION"
        elif re.search(r"\\b(?:request for proposals|invitation to tender|bids close)\\b",award,re.I):
            supplier="TENDER_PUBLISHED_STATUS_REQUIRES_LIVE_CHECK"
    return {"buyer_authority": "SOURCE_SUPPORTED_REVIEW_REQUIRED" if buyer else "NOT_VERIFIED",
            "supplier_status":supplier,"verification":"MANUAL_OR_INDEPENDENT_SOURCE_REVIEW_REQUIRED"}

def evaluate_worklist(observations,out):
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    records=[]
    for r in observations:
        record={**r,**classify_buyer(r)}
        records.append(record)
    out.write_text(json.dumps({"relationships":records,"verified_private_buyers":0,
                               "verified_unawarded_packages":0},indent=2),encoding="utf-8")
    return records

def lead_pair(early,later):
    """Compare genuinely dated public events with a reviewed stable identity."""
    from gta_lead_time_proof import validate
    if early.get("official_project_id")!=later.get("official_project_id") or not early.get("official_project_id"):
        return {"status":"PROJECT_IDENTITY_NOT_VERIFIED"}
    obj={"official_project_id":early["official_project_id"],
         "first_public_url":early.get("source_url"),"first_public_at":early.get("published_at"),
         "radar_first_seen_at":early.get("radar_first_seen_at"),
         "later_permit_url":later.get("source_url"),"later_permit_public_at":later.get("published_at"),
         "same_project_match_reviewed":early.get("identity_reviewed") is True and later.get("identity_reviewed") is True}
    return validate(obj)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--indexes",required=True);p.add_argument("--out",required=True)
    p.add_argument("--fetch",action="store_true")
    a=p.parse_args()
    with open(a.indexes,encoding="utf-8-sig",newline="") as h:
        indexes=list(csv.DictReader(h))
    result=discover(indexes,a.out)\n    if a.fetch:\n        result["downloads"]=fetch_discovered(result["discovered_csv"],a.out)\n    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
