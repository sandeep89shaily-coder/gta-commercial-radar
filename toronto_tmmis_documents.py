"""Toronto TMMIS public agenda attachment discovery (review-only).

Use official saved agenda HTML for deterministic parsing. Downloads are a
separate explicit decision subject to host policy and reuse review.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

AGENDA_HOST="secure.toronto.ca"
PDF_HOST="www.toronto.ca"
ATTACHMENT=re.compile(r"^/legdocs/mmis/20\d\d/[a-z0-9]+/bgrd/backgroundfile-\d+\.pdf$",re.I)
MEETING=re.compile(r"^/council/report\.do\?meeting=20\d\d\.[A-Z0-9]+&type=agenda$",re.I)
FIELDS=["meeting_url","attachment_url","attachment_id","sha256_url","source_type","publication_date_status","retrieval_status"]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag.lower()!="a":
            return
        val=dict(attrs).get("href")
        if val:
            self.links.append(val)


def agenda_url(url):
    p=urlparse(url)
    return p.scheme=="https" and p.hostname==AGENDA_HOST and p.username is None and p.password is None and p.port in (None,443) and bool(MEETING.fullmatch(p.path+"?"+p.query))


def parse_agenda(html_text, meeting_url):
    if not agenda_url(meeting_url):
        raise ValueError("Expected a Toronto public TMMIS agenda URL")
    parser=Links()
    parser.feed(html_text)
    out=[]
    seen=set()
    for ref in parser.links:
        url=urljoin(meeting_url,ref)
        p=urlparse(url)
        if p.scheme!="https" or p.hostname!=PDF_HOST or p.port not in (None,443) or not ATTACHMENT.fullmatch(p.path) or p.query or p.fragment or url in seen:
            continue
        seen.add(url)
        name=p.path.rsplit("/",1)[-1]
        out.append(dict(meeting_url=meeting_url,attachment_url=url,attachment_id=name,
                        sha256_url=hashlib.sha256(url.encode()).hexdigest(),
                        source_type="TORONTO_TMMIS_BACKGROUND_REPORT",
                        publication_date_status="UNVERIFIED",
                        retrieval_status="DISCOVERED_NOT_FETCHED"))
    return out


def build(agenda_html, meeting_url, output):
    records=parse_agenda(Path(agenda_html).read_text(encoding="utf-8"),meeting_url)
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(records)
    return {"documents_discovered":len(records),"documents_downloaded":0,
            "publisher_dates_verified":0,"paid_ai_calls":0,"file":str(output)}


def extract_local_pdf(pdf_path, max_pages=100, max_bytes=15_000_000):
    """Extract from an already-local digital PDF; never invokes OCR/network."""
    pdf_path=Path(pdf_path)
    if pdf_path.stat().st_size>max_bytes:
        raise ValueError("PDF exceeds bounded size")
    from pypdf import PdfReader
    reader=PdfReader(str(pdf_path),strict=True)
    if reader.is_encrypted:
        raise ValueError("Encrypted PDF is not supported")
    if len(reader.pages)>max_pages:
        raise ValueError("PDF exceeds page cap")
    pages=[]
    for i,page in enumerate(reader.pages,1):
        text=(page.extract_text() or "").strip()
        pages.append({"page":i,"text":text[:40000],"text_present":bool(text)})
    return {"sha256":hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
            "pages":pages,"requires_ocr_review":not any(p["text_present"] for p in pages),
            "verification_status":"TEXT_ONLY_UNVERIFIED"}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--agenda-html",type=Path,required=True)
    p.add_argument("--meeting-url",required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(build(a.agenda_html,a.meeting_url,a.out),indent=2))


if __name__=="__main__":
    main()
