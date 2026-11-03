"""Official Burlington quarterly application activity.

Downloads the City's public summary ZIP and reads bounded PDF text. Tables
contain aggregate counts, NOT application identities. This feed is entirely
separate from application/lead records. No paid AI or access workarounds.
"""
from __future__ import annotations
import csv
import datetime as dt
import hashlib
import io
import json
import re
import socket
import zipfile
from pathlib import Path
from urllib.parse import urlparse
import requests
from pypdf import PdfReader
from robots_policy import evaluate
from toronto_pdf_download import public_dns

URL="https://mapping.burlington.ca/docs/Burlington%20Development%20Application%20Summary%20Tables.zip"
STATE="GTA_RADAR_BURLINGTON_QUARTERLY_SEEN.json"
CSV="GTA_RADAR_BURLINGTON_QUARTERLY_ACTIVITY.csv"
STATUS="GTA_RADAR_BURLINGTON_QUARTERLY_STATUS.json"
COLUMNS=("city","period","active_applications","new_applications",
         "decided_applications","appealed_applications",
         "withdrawn_applications","source_url","observation","first_seen_local",
         "record_kind","verification_required")
AGENT="GTARadarBurlingtonQuarterly/1.0"
MAX_ZIP=5_000_000
MAX_MEMBERS=20
MAX_PDF=1_000_000
MAX_PAGES=7
PATTERN=re.compile(r"Q([1-4])[\s_-]*(20\d{2})",re.I)
METRICS={
 "active_applications":r"\bTotal number of active applications\s+(\d+)\b",
 "new_applications":r"\bTotal number of new applications\s+(\d+)\b",
 "decided_applications":r"\bTotal number of applications decided\s+(\d+)\b",
 "appealed_applications":r"\bTotal number of applications appealed\s+(\d+)\b",
 "withdrawn_applications":r"\bTotal number of applications withdrawn\s+(\d+)\b",
}
def _download():
    parsed=urlparse(URL)
    if parsed.scheme!="https" or parsed.hostname!="mapping.burlington.ca" or not public_dns(parsed.hostname,socket.getaddrinfo):
        raise ValueError("UNSAFE_SOURCE")
    ss=requests.Session();ss.trust_env=False
    ss.headers["User-Agent"]=AGENT
    ok,reason=evaluate(ss,URL,AGENT,timeout=8)
    if not ok:raise ValueError("SOURCE_POLICY_BLOCKED:"+reason)
    with ss.get(URL,timeout=(7,22),stream=True,allow_redirects=False) as response:
        if response.status_code!=200 or urlparse(response.url).hostname!=parsed.hostname:
            raise ValueError("SOURCE_HTTP_OR_REDIRECT_"+str(response.status_code))
        raw=bytearray()
        for chunk in response.iter_content(65536):
            raw.extend(chunk)
            if len(raw)>MAX_ZIP:raise ValueError("SOURCE_ZIP_TOO_LARGE")
        return bytes(raw)

def _extract(archive):
    if len(archive)>MAX_ZIP or not zipfile.is_zipfile(io.BytesIO(archive)):
        raise ValueError("INVALID_BURLINGTON_OFFICIAL_ZIP")
    records={}
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        files=z.infolist()
        if len(files)>MAX_MEMBERS:raise ValueError("TOO_MANY_PDF_DOCUMENTS")
        for item in files:
            if not item.filename.lower().endswith(".pdf"):continue
            if item.file_size>MAX_PDF or ".." in item.filename or item.filename.startswith("/"):
                raise ValueError("UNSAFE_PDF_ENTRY")
            match=PATTERN.search(item.filename)
            if not match:continue
            period=f"{match.group(2)}-Q{match.group(1)}"
            reader=PdfReader(io.BytesIO(z.read(item)))
            if len(reader.pages)>MAX_PAGES:raise ValueError("PDF_PAGE_LIMIT_EXCEEDED")
            text=" ".join((page.extract_text() or "") for page in reader.pages)
            text=re.sub(r"\s+"," ",text)
            counts={}
            for field,regex in METRICS.items():
                m=re.search(regex,text,re.I)
                counts[field]=int(m.group(1)) if m else None
            if counts["new_applications"] is None or counts["active_applications"] is None:
                raise ValueError("OFFICIAL_REPORT_MISSING_REQUIRED_TOTALS:"+period)
            if period in records:raise ValueError("DUPLICATE_QUARTER")
            records[period]={"city":"Burlington","period":period,**counts,
                "source_url":URL,"record_kind":"AGGREGATE_ACTIVITY_NOT_APPLICATION_FILES",
                "verification_required":"Aggregate counts only. Do not treat as individual projects or fresh leads"}
    if not records:raise ValueError("NO_VERIFIABLE_QUARTERLY_REPORTS")
    return records

def run(results,*,today=None,fetcher=None):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    date=(today or dt.date.today()).isoformat()
    statepath=root/STATE
    previous=json.loads(statepath.read_text(encoding="utf-8")) if statepath.exists() else None
    if previous and previous.get("schema")!=1:raise ValueError("UNKNOWN_QUARTERLY_STATE")
    status={"status":"FAILED","source":URL,"report_quarters":0,
            "application_id_rows":0,"paid_ai_calls":0,"baseline_preserved":True}
    rows=[]
    try:
        records=_extract((fetcher or _download)())
        before=previous.get("seen",{}) if previous else {}
        after=dict(before)
        for period,row in sorted(records.items()):
            digest=hashlib.sha256(json.dumps({k:row[k] for k in METRICS},
                 sort_keys=True).encode()).hexdigest()
            old=before.get(period)
            obs=("INITIAL_BASELINE" if previous is None else
                 "FIRST_OBSERVED" if old is None else
                 "RECORD_CHANGED" if old["digest"]!=digest else "UNCHANGED")
            row["observation"]=obs
            row["first_seen_local"]=old["first_seen_local"] if old else date
            rows.append(row)
            after[period]={"digest":digest,"first_seen_local":row["first_seen_local"]}
        tmp=statepath.with_suffix(".tmp")
        tmp.write_text(json.dumps({"schema":1,"seen":after},indent=2),encoding="utf-8")
        tmp.replace(statepath)
        status.update(status="BASELINED" if previous is None else "COLLECTED",
                      report_quarters=len(rows),baseline_preserved=False,
                      latest_period=max(records),
                      latest_new_applications=records[max(records)]["new_applications"])
    except Exception as exc:
        status["error"]=type(exc).__name__+":"+str(exc)[:200]
    with (root/CSV).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=COLUMNS)
        w.writeheader();w.writerows(rows)
    (root/STATUS).write_text(json.dumps(status,indent=2),encoding="utf-8")
    return status
