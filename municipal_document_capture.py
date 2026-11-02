"""Policy-checked, bounded municipal PDF intake from official council pages.

The eight-city meeting-index stage supplies city-identified, observed agenda
links. For non-Toronto cities this adapter checks official-host pages and exact
same-host PDF links only. Third-party eSCRIBE/Portal/Laserfiche destinations
need a separately validated adapter, not a permissive hostname suffix.

No paid AI, no first-publication claims, no video/caption downloads.
"""
from __future__ import annotations

import csv
import hashlib
import io
import ipaddress
import json
import os
import re
import socket
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from pypdf import PdfReader

import robots_policy
from municipal_meeting_capture import AGENDAS
from toronto_pdf_download import AGENT, MAX_BYTES, TIMEOUT, public_dns

MAX_HTML_BYTES = 1_500_000
MAX_AGENDA_PAGES_PER_CITY = 2
MAX_PDFS_PER_CITY = 2
MAX_TOTAL_PDFS = 12
CITY_PAGES = {city:uri for city,uri in AGENDAS.items() if city!="Toronto"}
FIELDS = ("city","source_page","url","status","reason","http_status","bytes",
          "sha256","saved_path","publisher_date_verified","document_type")


def _valid_city_url(city, url, *, pdf=False):
    """Pin PDF and agenda requests to the city's configured official hostname."""
    trusted = CITY_PAGES.get(city)
    if not trusted:
        return False
    try:
        parsed = urlparse(str(url or ""))
        official = urlparse(trusted)
        if (parsed.scheme!="https" or parsed.hostname!=official.hostname or
                parsed.port not in (None,443) or parsed.username or parsed.password or
                parsed.fragment):
            return False
        if pdf:
            return parsed.path.lower().endswith(".pdf")
        # Do not fetch indexes of other site sections, APIs, or arbitrary pages
        # returned by public text; links must be on same-host official pages.
        return bool(parsed.path.startswith("/"))
    except ValueError:
        return False


class Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_link=False
        self.href=None
        self.text=[]
        self.links=[]

    def handle_starttag(self, tag, attrs):
        if tag=="a":
            self.in_link=True
            self.href=dict(attrs).get("href")
            self.text=[]

    def handle_data(self, data):
        if self.in_link:self.text.append(data)

    def handle_endtag(self, tag):
        if tag=="a" and self.in_link:
            if self.href:self.links.append((self.href," ".join(self.text).strip()))
            self.in_link=False
            self.href=None
            self.text=[]


def _guard(session,city,url,resolver,policy_reader):
    if not _valid_city_url(city,url):
        return "NOT_OFFICIAL_CITY_HOST"
    host=urlparse(url).hostname
    if not public_dns(host,resolver):
        return "NONPUBLIC_OR_UNAVAILABLE_DNS"
    allowed,reason=robots_policy.evaluate(
        session,url,AGENT,timeout=TIMEOUT,policy_reader=policy_reader)
    if not allowed:return reason
    return ""


def _read_html(session,city,url,resolver,policy_reader):
    reason=_guard(session,city,url,resolver,policy_reader)
    if reason:return {"status":"BLOCKED","reason":reason,"pdf_links":[]}
    try:
        with session.get(url,timeout=TIMEOUT,allow_redirects=False,stream=True) as res:
            if res.status_code!=200 or res.url!=url:
                return {"status":"FAILED","reason":"HTTP_OR_REDIRECT_"+str(res.status_code),"pdf_links":[]}
            mime=res.headers.get("Content-Type","").split(";",1)[0].lower()
            if mime not in ("text/html","application/xhtml+xml"):
                return {"status":"FAILED","reason":"NOT_HTML","pdf_links":[]}
            buf=bytearray()
            for part in res.iter_content(chunk_size=65536):
                buf.extend(part)
                if len(buf)>MAX_HTML_BYTES:
                    return {"status":"FAILED","reason":"HTML_TOO_LARGE","pdf_links":[]}
            links=Anchors()
            links.feed(buf.decode("utf-8","replace"))
            found=[]
            for href,title in links.links:
                target=urljoin(url,href)
                if _valid_city_url(city,target,pdf=True):
                    found.append({"url":target,"title":title[:180]})
            return {"status":"FETCHED","reason":"OK","pdf_links":found}
    except requests.RequestException as exc:
        return {"status":"FAILED","reason":"NETWORK_"+type(exc).__name__,"pdf_links":[]}


def _fetch_pdf(session,city,source_page,url,destination,resolver,policy_reader):
    record=dict(city=city,source_page=source_page,url=url,status="FAILED",reason="",
                http_status="",bytes=0,sha256="",saved_path="",
                publisher_date_verified=False,document_type="PDF")
    if not _valid_city_url(city,url,pdf=True):
        record["reason"]="NOT_APPROVED_DIRECT_PDF";return record
    issue=_guard(session,city,url,resolver,policy_reader)
    if issue:
        record["reason"]=issue;return record
    temp=None
    try:
        with session.get(url,timeout=TIMEOUT,allow_redirects=False,stream=True) as res:
            record["http_status"]=res.status_code
            if res.status_code!=200 or res.url!=url:
                record["reason"]="HTTP_OR_REDIRECT_"+str(res.status_code);return record
            mime=res.headers.get("Content-Type","").split(";",1)[0].strip().lower()
            if mime not in ("application/pdf","application/octet-stream"):
                record["reason"]="NOT_PDF_CONTENT_TYPE";return record
            length=res.headers.get("Content-Length")
            try:
                if length and int(length)>MAX_BYTES:
                    record["reason"]="PDF_TOO_LARGE";return record
            except ValueError:
                record["reason"]="INVALID_CONTENT_LENGTH";return record
            payload=bytearray()
            for part in res.iter_content(chunk_size=65536):
                payload.extend(part)
                if len(payload)>MAX_BYTES:
                    record["reason"]="PDF_TOO_LARGE";return record
            if len(payload)<100 or not payload.startswith(b"%PDF-"):
                record["reason"]="INVALID_PDF_SIGNATURE";return record
            try:
                pdf=PdfReader(io.BytesIO(payload),strict=False)
                if pdf.is_encrypted or len(pdf.pages)<1:
                    raise ValueError("Encrypted or empty PDF")
            except Exception:
                record["reason"]="INVALID_OR_ENCRYPTED_PDF";return record
            sha=hashlib.sha256(payload).hexdigest()
            dest=Path(destination)
            dest.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=dest.parent,suffix=".part",delete=False) as handle:
                temp=Path(handle.name)
                handle.write(payload)
            os.replace(temp,dest)
            temp=None
            record.update(status="CAPTURED",reason="OK",bytes=len(payload),
                          sha256=sha,saved_path=str(dest.resolve()))
            return record
    except (requests.RequestException,OSError) as exc:
        record["reason"]="FETCH_OR_WRITE_"+type(exc).__name__
        return record
    finally:
        if temp is not None:temp.unlink(missing_ok=True)


def run(meeting_results, out, *, session=None, resolver=socket.getaddrinfo,
        policy_reader=None, per_city=MAX_AGENDA_PAGES_PER_CITY,
        per_city_pdfs=MAX_PDFS_PER_CITY, total_pdfs=MAX_TOTAL_PDFS):
    """Discover and capture direct official PDF links; report all access failures.

    meeting_results contains outputs of eight-city meeting index stage.
    Injection of session/resolver/policy_reader supports hermetic CI.
    """
    target=Path(out)
    target.mkdir(parents=True,exist_ok=True)
    session=session or requests.Session()
    session.trust_env=False
    session.headers.update({"User-Agent":AGENT,"Accept":"text/html,application/pdf"})
    records=[];audit=[];seen_pdf=set()
    remaining=max(0,min(int(total_pdfs),MAX_TOTAL_PDFS))
    max_pages=max(0,min(int(per_city),MAX_AGENDA_PAGES_PER_CITY))
    max_per_city=max(0,min(int(per_city_pdfs),MAX_PDFS_PER_CITY))
    for city,index in CITY_PAGES.items():
        stage=meeting_results.get(city,{})
        file=stage.get("meeting_index") if isinstance(stage,dict) else ""
        try:
            data=json.loads(Path(file).read_text(encoding="utf-8")) if file else {}
        except (OSError,ValueError):
            data={}
        # Only index and already-observed official-host agenda pages. No
        # recursive crawling, no speculative PDF URLs, no third-party access.
        possibilities=[index]
        for item in data.get("agenda_candidates",[]):
            page=item.get("url") if isinstance(item,dict) else ""
            if page and page not in possibilities:
                possibilities.append(page)
        count=0;checked=0;found=0;failures=[]
        for page in possibilities:
            if checked>=max_pages:break
            if not _valid_city_url(city,page):
                failures.append({"url":page,"reason":"EXTERNAL_CALENDAR_DOCUMENT_HOST_NOT_APPROVED"})
                continue
            checked+=1
            response=_read_html(session,city,page,resolver,policy_reader)
            if response["status"]!="FETCHED":
                failures.append({"url":page,"reason":response["reason"]})
                continue
            for item in response["pdf_links"]:
                pdf=item["url"]
                if pdf in seen_pdf:continue
                seen_pdf.add(pdf);found+=1
                if count>=max_per_city or remaining<=0:continue
                name=hashlib.sha256(pdf.encode()).hexdigest()[:24]+".pdf"
                rec=_fetch_pdf(session,city,page,pdf,target/"pdfs"/name,
                               resolver,policy_reader)
                records.append(rec);count+=1;remaining-=1
        audit.append({"city":city,"official_index":index,
                      "meeting_index_present":bool(data),
                      "pages_checked":checked,"pdf_links_seen":found,
                      "pdf_attempted":count,
                      "pdf_captured":sum(x["status"]=="CAPTURED" for x in records if x["city"]==city),
                      "access_failures":failures,
                      "status":"PDF_CAPTURED" if any(x["status"]=="CAPTURED" and x["city"]==city for x in records)
                        else "INDEX_CHECKED_NO_DIRECT_PDF" if checked and not failures
                        else "PARTIAL_OR_BLOCKED",
                      "third_party_calendar_requires_adapter":True,
                      "document_publication_verified":False})
    report=target/"MULTICITY_PDF_FETCH_AUDIT.csv"
    with report.open("w",encoding="utf-8-sig",newline="") as stream:
        w=csv.DictWriter(stream,fieldnames=FIELDS);w.writeheader();w.writerows(records)
    outcome={"cities_configured":len(CITY_PAGES),"cities_attempted":len(audit),
             "direct_pdf_attempted":len(records),
             "direct_pdf_captured":sum(x["status"]=="CAPTURED" for x in records),
             "successful_document_cities":sorted({x["city"] for x in records if x["status"]=="CAPTURED"}),
             "city_audit":audit,"audit_csv":str(report),
             "ai_calls":0,"buyer_roles_verified":0,"publisher_dates_verified":0,
             "coverage_warning":"Direct same-host PDFs only; dynamic/eSCRIBE/Laserfiche documents need validated adapters. An empty capture is NOT no municipal developments."}
    (target/"MULTICITY_DOCUMENT_STATUS.json").write_text(
        json.dumps(outcome,indent=2),encoding="utf-8")
    return outcome


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--results",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    review=Path(a.results)/"DAILY_INTEGRATED_REVIEW"/"MEETINGS"
    meetings={city:{"meeting_index":str(review/city/(city.upper()+"_MEETINGS.json"))}
              for city in CITY_PAGES}
    print(json.dumps(run(meetings,a.out),indent=2))
