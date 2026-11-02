"""Structured, review-only Markham circulation applications from captured official PDFs.

The Markham circulated-applications PDFs give an application number, site,
use and *circulation* date. A circulation date is not a proven first public
publication date, and applicant fragments from line-wrapped PDF tables must
never be presented as verified developer/owner names. Baseline on first run.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from pypdf import PdfReader

STATE="GTA_RADAR_MARKHAM_CIRCULATION_SEEN.json"
ALL="GTA_RADAR_MARKHAM_CIRCULATED_APPLICATIONS.csv"
CHANGES="GTA_RADAR_MARKHAM_CIRCULATION_CHANGES.csv"
STATUS="GTA_RADAR_MARKHAM_CIRCULATION_STATUS.json"
FIELDS=("project_id","city","application_id","address","proposed_use",
        "circulation_date","date_basis","pdf_url","pdf_sha256",
        "first_seen_local","observation","changed_fields",
        "status","verified_first_publication","company_role_verified")
DATE=re.compile(r"^\d{1,2}-[A-Za-z]{3}-\d{2}$")
ID=re.compile(r"^(?:SPC\s+)?\d{2}-\d{5,8}$",re.I)
PRIMARY_USES={"industrial","commercial","institutional","parking lot","extension"}

def _read(path):
    if not Path(path).is_file():return []
    with Path(path).open(encoding="utf-8-sig",newline="") as file:
        return list(csv.DictReader(file))

def _write(path,records):
    with Path(path).open("w",encoding="utf-8-sig",newline="") as file:
        w=csv.DictWriter(file,fieldnames=FIELDS,extrasaction="ignore")
        w.writeheader()
        w.writerows(records)

def extract(text,pdf_url,digest):
    """Parse only aligned, complete table rows; reject ambiguous identifiers."""
    records={}
    lines=text.splitlines()
    for idx,line in enumerate(lines):
        chunks=[x.strip() for x in re.split(r"\s{2,}",line) if x.strip()]
        if len(chunks)<7:continue
        for j,val in enumerate(chunks):
            if j<1 or not DATE.fullmatch(val):continue
            if j+4>=len(chunks) or not DATE.fullmatch(chunks[j+1]):continue
            use=chunks[j+4].casefold()
            if use not in PRIMARY_USES:continue
            raw_id=chunks[j-1].upper().replace(" ","")
            if re.fullmatch(r"SPC\d{2}-",raw_id):
                # An official Markham table wraps the six-digit suffix onto
                # the next line. Never borrow the suffix from another record.
                next_line=lines[idx+1] if idx+1<len(lines) else ""
                if re.search(r"\b(?:SPC\s*\d{2}-|\d{1,2}-[A-Za-z]{3}-\d{2})\b",next_line):
                    continue
                candidates=re.findall(r"\b\d{5,8}\b",next_line)
                if len(candidates)!=1:continue
                raw_id=raw_id+candidates[0]
            if not re.fullmatch(r"(?:SPC)?\d{2}-\d{5,8}",raw_id):continue
            applicant=chunks[j-2] if j>=2 else ""
            # Avoid conflating a line-wrapped applicant hint with the owner.
            address=chunks[j+2].strip()
            if not re.search(r"\d",address) or len(address)>125:continue
            try:
                circulation=dt.datetime.strptime(val,"%d-%b-%y").date().isoformat()
            except ValueError:continue
            application_id=raw_id.replace("SPC","SPC ")
            pid="EARLY_APP:MARKHAM:"+raw_id
            records[pid]={
                "project_id":pid,"city":"Markham",
                "application_id":application_id,
                "address":address,"proposed_use":chunks[j+4],
                "circulation_date":circulation,
                "date_basis":"OFFICIAL_APPLICATION_CIRCULATION_DATE_NOT_PUBLICATION",
                "pdf_url":pdf_url,"pdf_sha256":digest,
                "status":"OFFICIAL_PDF_TABLE_PARSED_REVIEW_ONLY",
                "verified_first_publication":False,
                "company_role_verified":False,
            }
            break
    return list(records.values())

def run(pdf_union,results,*,today=None):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    day=(today or dt.date.today()).isoformat()
    statepath=root/STATE
    if statepath.exists():
        state=json.loads(statepath.read_text(encoding="utf-8"))
        if state.get("schema")!=1:raise ValueError("UNKNOWN_MARKHAM_STATE")
    else:state={"schema":1,"seen":{}}
    existing=state["seen"]
    baseline=not statepath.exists()
    selected={}
    skipped=0
    for item in _read(pdf_union):
        url=item.get("url","")
        parsed=urlparse(url)
        if (item.get("city")!="Markham" or item.get("status")!="CAPTURED"
                or parsed.scheme!="https" or parsed.hostname!="www.markham.ca"
                or not parsed.path.lower().endswith(".pdf")
                or "circulated" not in parsed.path.casefold()):
            continue
        local=Path(item.get("saved_path") or "")
        digest=item.get("sha256","")
        try:
            if not local.is_file() or local.stat().st_size>12_000_000:
                raise ValueError("MISSING_OR_OVERSIZED_PDF")
            if hashlib.sha256(local.read_bytes()).hexdigest()!=digest:
                raise ValueError("CHECKSUM_MISMATCH")
            pdf=PdfReader(str(local),strict=False)
            if pdf.is_encrypted or len(pdf.pages)>30:
                raise ValueError("PDF_NOT_SUPPORTED")
            first=pdf.pages[0].extract_text(extraction_mode="layout") or ""
            entries=extract(first,url,digest)
            for r in entries:
                prior=selected.get(r["project_id"])
                if prior is None or r["circulation_date"]>prior["circulation_date"]:
                    selected[r["project_id"]]=r
        except Exception:
            skipped+=1
    allrows=[];changed=[]
    for pid,r in sorted(selected.items()):
        digest=hashlib.sha256(json.dumps(
            {k:r[k] for k in ("application_id","address","proposed_use","circulation_date")},
            sort_keys=True).encode()).hexdigest()
        prev=existing.get(pid)
        if prev is None:obs="INITIAL_BASELINE" if baseline else "FIRST_OBSERVED"
        elif digest!=prev["digest"]:obs="RECORD_CHANGED"
        else:obs="UNCHANGED"
        r.update(first_seen_local=prev.get("first_seen_local",day) if prev else day,
                 observation=obs,changed_fields="APPLICATION_TABLE_CHANGE_UNRECONCILED" if obs=="RECORD_CHANGED" else "")
        allrows.append(r)
        if obs in ("FIRST_OBSERVED","RECORD_CHANGED"):changed.append(r)
        existing[pid]={"digest":digest,"first_seen_local":r["first_seen_local"]}
    _write(root/ALL,allrows)
    _write(root/CHANGES,changed)
    tmp=statepath.with_suffix(".tmp")
    tmp.write_text(json.dumps(state,indent=2),encoding="utf-8")
    tmp.replace(statepath)
    status={"status":"MARKHAM_CIRCULATION_REVIEW_ONLY",
            "source_pdfs_parsed":sum(1 for row in _read(pdf_union)
                                  if row.get("city")=="Markham" and row.get("status")=="CAPTURED"),
            "rows_extracted":len(allrows),"first_run_baseline":baseline,
            "new_or_changed":len(changed),"pdfs_unreadable_or_invalid":skipped,
            "not_auto_merged":True,"ai_calls":0,
            "first_publication_dates_verified":0,
            "applications_csv":str(root/ALL),"changes_csv":str(root/CHANGES),
            "warning":"Only complete table rows and official circulation dates; publication date and purchasing authority unverified."}
    (root/STATUS).write_text(json.dumps(status,indent=2),encoding="utf-8")
    return status
