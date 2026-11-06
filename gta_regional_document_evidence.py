"""Bounded official regional PDF evidence stage, following reviewed HTML detail links.

The input consists exclusively of same-host PDF references emitted by
gta_regional_project_details. No bypasses, OCR, inferred dates or paid AI.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import re
import socket
from pathlib import Path
from urllib.parse import urlparse

import requests
from pypdf import PdfReader

from gta_regional_early_intelligence import _safe_url
from gta_regional_project_details import _approved_document_url
from robots_policy import evaluate
from toronto_pdf_download import public_dns

INPUT = "GTA_RADAR_REGIONAL_PROJECT_DETAILS.csv"
OUTPUT = "GTA_RADAR_REGIONAL_DOCUMENT_EVIDENCE.csv"
CHANGES = "GTA_RADAR_REGIONAL_DOCUMENT_EVIDENCE_NEW_OR_CHANGED.csv"
STATUS = "GTA_RADAR_REGIONAL_DOCUMENT_EVIDENCE_STATUS.json"
LEDGER = "GTA_RADAR_REGIONAL_DOCUMENT_EVIDENCE_SEEN.json"
COLUMNS = (
    "document_id", "authority", "project_id", "project_title", "project_url",
    "document_url", "evidence_excerpt", "budget_evidence", "stage_evidence",
    "text_pages", "first_seen_local", "observation", "source_date_basis",
    "source_verification", "commercial_status", "verification_required",
)
MAX_DOCUMENTS = 12
MAX_PER_PROJECT = 2
MAX_BYTES = 4_500_000
MAX_PAGES = 35
MAX_TEXT_CHARS = 80_000
AGENT = "GTARadarRegionalOfficialPDF/1.0"
MATCH = re.compile(
    r"\b(?:reservoir|pumping|wastewater|watermain|treatment plant|"
    r"construction|capital project|cost estimate|estimated cost|"
    r"preliminary design|detailed design|expansion|budget|"
    r"environmental assessment|rehabilitation|tender|procurement|bridge)\b", re.I,
)
COST = re.compile(r"(?:\$\s*\d[\d,.]*\s*(?:million|billion|M|B)?|"
                  r"\b\d[\d,.]*\s*(?:million|billion)\s+dollars\b)", re.I)
STAGES = (
    ("CONSTRUCTION", re.compile(r"\b(?:construction underway|under construction|construction started)\b", re.I)),
    ("DESIGN_OR_TENDER", re.compile(r"\b(?:preliminary design|detailed design|tendering|request for proposals)\b", re.I)),
    ("ASSESSMENT", re.compile(r"\b(?:environmental assessment|feasibility study)\b", re.I)),
)


def _fetch_pdf(url):
    parsed = urlparse(url)
    if not (parsed.scheme == "https" and parsed.hostname and parsed.port in (None, 443)
            and not parsed.username and not parsed.password and not parsed.fragment):
        raise ValueError("INVALID_PDF_SOURCE")
    if not public_dns(parsed.hostname, socket.getaddrinfo):
        raise ValueError("UNSAFE_PDF_DNS")
    with requests.Session() as session:
        session.trust_env = False
        session.headers.update({"User-Agent":AGENT,"Accept":"application/pdf"})
        allowed, reason = evaluate(session, url, AGENT, timeout=8)
        if not allowed:
            raise ValueError("PDF_POLICY_DENIED:"+str(reason))
        with session.get(url,timeout=(6,18),stream=True,allow_redirects=False) as response:
            if response.status_code != 200 or response.url != url:
                raise ValueError("PDF_HTTP_OR_REDIRECT_"+str(response.status_code))
            ctype = response.headers.get("Content-Type", "").split(";",1)[0].lower().strip()
            if ctype not in ("application/pdf", "application/octet-stream"):
                raise ValueError("INVALID_PDF_CONTENT_TYPE")
            chunks = bytearray()
            for chunk in response.iter_content(65536):
                chunks.extend(chunk)
                if len(chunks) > MAX_BYTES:
                    raise ValueError("REGIONAL_PDF_TOO_LARGE")
            if not chunks.startswith(b"%PDF-"):
                raise ValueError("PDF_SIGNATURE_MISSING")
            return bytes(chunks)


def _evidence(pdf_bytes):
    if len(pdf_bytes)>MAX_BYTES or not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("INVALID_BOUNDED_PDF")
    reader=PdfReader(io.BytesIO(pdf_bytes), strict=False)
    if reader.is_encrypted:
        raise ValueError("ENCRYPTED_REGIONAL_PDF")
    count=len(reader.pages)
    if count==0 or count>MAX_PAGES:
        raise ValueError("PDF_PAGE_LIMIT_EXCEEDED")
    passages=[]
    text_size=0
    readable_pages=0
    for page in reader.pages:
        text=" ".join((page.extract_text() or "").split())
        text_size+=len(text)
        if text_size>MAX_TEXT_CHARS:
            raise ValueError("PDF_EXTRACTED_TEXT_TOO_LONG")
        if len(text)>80:
            readable_pages+=1
        # Bound evidence to page-local snippets; never extrapolate a value from
        # a different paragraph or present a file modification time as a date.
        for clause in re.split(r"(?<=[.!?])\s+|\n+",text):
            value=clause.strip()
            if 30 <= len(value) <= 550 and MATCH.search(value):
                passages.append(value)
                if len(passages)>=24:
                    break
        if len(passages)>=24:
            break
    if readable_pages==0:
        raise ValueError("NO_EXTRACTABLE_PDF_TEXT_SCANNED_OR_EMPTY")
    if not passages:
        raise ValueError("NO_REGIONAL_PROJECT_EVIDENCE_IN_PDF")
    budget=next((p[:450] for p in passages if COST.search(p) and
       re.search(r"\b(?:budget|cost|capital|funding|investment|estimate)\b",p,re.I)),"")
    stage=next((label for label,pattern in STAGES if any(pattern.search(p) for p in passages)),
               "STAGE_NOT_VERIFIED")
    return {"evidence_excerpt":" ".join(passages[:4])[:1500],
            "budget_evidence":budget,"stage_evidence":stage,
            "text_pages":readable_pages}


def _read(path):
    if not path.is_file():return []
    with path.open(encoding="utf-8-sig",newline="") as handle:
        return list(csv.DictReader(handle))


def _write(path,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=COLUMNS,extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k:("'"+v if isinstance(v,str) and v.startswith(("=","+","-","@")) else v)
                             for k,v in row.items() if k in COLUMNS})


def _candidates(rows):
    selected=[]
    seen=set()
    for row in rows:
        parent=row.get("project_url","")
        authority=row.get("authority","")
        if authority not in ("York","Peel","Waterloo") or not parent:
            continue
        try:
            urls=json.loads(row.get("official_pdf_urls_json","[]"))
        except (TypeError, ValueError):
            continue
        if not isinstance(urls,list):
            continue
        for url in urls[:MAX_PER_PROJECT]:
            if not isinstance(url,str) or not urlparse(url).path.lower().endswith(".pdf"):
                continue
            if not _approved_document_url(url,parent,authority) or url in seen:
                continue
            selected.append((row,url))
            seen.add(url)
            if len(selected)>=MAX_DOCUMENTS:
                return selected
    return selected


def run(results, *, today=None, fetcher=None):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    day=(today or dt.date.today()).isoformat()
    ledger=root/LEDGER
    prior=json.loads(ledger.read_text(encoding="utf-8")) if ledger.exists() else {"schema":1,"seen":{}}
    if prior.get("schema")!=1 or not isinstance(prior.get("seen"),dict):
        raise ValueError("INVALID_REGIONAL_DOCUMENT_LEDGER")
    old=prior["seen"];updated=dict(old)
    records=[];changes=[];failures=[]
    selected=_candidates(_read(root/INPUT))
    for row,url in selected:
        try:
            evidence=_evidence((fetcher or _fetch_pdf)(url))
            did="REGIONAL_PDF:"+hashlib.sha256(url.encode()).hexdigest()[:24]
            record={"document_id":did,"authority":row["authority"],
                    "project_id":row.get("project_id",""),
                    "project_title":row.get("project_title",""),
                    "project_url":row["project_url"],"document_url":url,
                    **evidence,"source_date_basis":"PDF_TEXT_NO_VERIFIED_FIRST_PUBLICATION",
                    "source_verification":("OFFICIAL_PAGE_LINKED_WATERLOO_CDN_PDF_TEXT_EXTRACTED"
                        if urlparse(url).hostname!=urlparse(row["project_url"]).hostname
                        else "OFFICIAL_SAME_HOST_PDF_TEXT_EXTRACTED"),
                    "commercial_status":"DOCUMENT_EVIDENCE_NOT_OPEN_PROCUREMENT",
                    "verification_required":"Verify exact project, source date, budget applicability, contractor and unawarded work"}
            digest=hashlib.sha256(json.dumps({k:record[k] for k in
                ("evidence_excerpt","budget_evidence","stage_evidence","text_pages")},sort_keys=True).encode()).hexdigest()
            previous=old.get(did)
            baseline=not any(k.startswith("REGIONAL_PDF:") for k in old)
            observation="INITIAL_BASELINE" if baseline else (
                "FIRST_OBSERVED" if previous is None else
                "RECORD_CHANGED" if previous["digest"]!=digest else "UNCHANGED")
            record.update(observation=observation,
                          first_seen_local=previous["first_seen_local"] if previous else day)
            records.append(record)
            if observation in ("FIRST_OBSERVED","RECORD_CHANGED"):
                changes.append(record)
            updated[did]={"digest":digest,"first_seen_local":record["first_seen_local"]}
        except Exception as err:
            failures.append({"authority":row.get("authority"),"document_url":url,
                             "error":type(err).__name__+":"+str(err)[:160]})
    _write(root/OUTPUT,records)
    _write(root/CHANGES,changes)
    if updated!=old:
        tmp=ledger.with_suffix(".tmp")
        tmp.write_text(json.dumps({"schema":1,"seen":updated},indent=2),encoding="utf-8")
        tmp.replace(ledger)
    summary={"status":"EXTRACTED" if records else "NO_VERIFIED_PDF_EVIDENCE",
             "selected_pdf_links":len(selected),"documents_with_text":len(records),
             "new_or_changed":len(changes),"failed_documents":len(failures),
             "failures":failures,"paid_ai_calls":0,
             "verified_procurement_opportunities":0,
             "warning":"Official same-host PDFs and explicitly approved Waterloo publisher-linked CDN documents only; robots, public DNS, no redirects, file/page limits apply. Extracted passages are not proof of first publication or open work."}
    (root/STATUS).write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary
