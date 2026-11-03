"""City of Toronto open-data CSV application collection (CKAN).

Uses the published municipal Development Applications dataset rather than an
ArcGIS AIC endpoint. Honors robots, DNS and resource restrictions. An
incomplete/unparseable CSV cannot establish or overwrite a source baseline.
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

from robots_policy import evaluate
from toronto_pdf_download import public_dns

PACKAGE_URL=("https://ckan0.cf.opendata.inter.prod-toronto.ca/"
             "api/3/action/package_show?id=development-applications")
LANDING="https://open.toronto.ca/dataset/development-applications/"
STATE="GTA_RADAR_TORONTO_OPEN_DATA_SEEN.json"
ALL="GTA_RADAR_TORONTO_OPEN_DATA_APPLICATIONS.csv"
CHANGES="GTA_RADAR_TORONTO_OPEN_DATA_CHANGES.csv"
STATUS="GTA_RADAR_TORONTO_OPEN_DATA_STATUS.json"
FIELDS=("project_id","city","application_id","address","description",
        "application_type","current_status","source_record_date",
        "date_basis","record_source_url","record_source_url_basis",
        "source_dataset_url","commercial_screen","first_seen_local",
        "observation","verification_required")
AGENT="GTARadarTorontoOpenData/1.0"
MAX_CSV_BYTES=125_000_000
MAX_ROWS=150_000
MAX_METADATA_BYTES=2_000_000
COMMERCIAL=re.compile(r"\b(?:commercial|industrial|office|hotel|restaurant|"
    r"warehouse|retail|logistics|manufactur\w*|distribution|mixed.use|"
    r"medical|clinic|hospital|business.park|data.cent(?:er|re)|"
    r"shopping|storage|employment)\b",re.I)

def _host_allowed(url):
    p=urlparse(url)
    return (p.scheme=="https" and p.port in (None,443) and
            p.username is None and p.password is None and
            p.fragment=="" and p.hostname and
            (p.hostname=="toronto.ca" or p.hostname.endswith(".toronto.ca")))

def _get(url, limit):
    if not _host_allowed(url):raise ValueError("NON_OFFICIAL_TORONTO_RESOURCE")
    host=urlparse(url).hostname
    if not public_dns(host,socket.getaddrinfo):
        raise ValueError("NON_PUBLIC_DNS")
    session=requests.Session()
    session.trust_env=False
    session.headers.update({"User-Agent":AGENT,"Accept":"application/json,text/csv"})
    ok,why=evaluate(session,url,AGENT,timeout=10)
    if not ok:raise ValueError("ROBOTS_POLICY:"+str(why))
    with session.get(url,timeout=(8,50),stream=True,allow_redirects=False) as response:
        if response.status_code!=200 or urlparse(response.url).hostname!=host:
            raise ValueError("DOWNLOAD_HTTP_"+str(response.status_code)+"_OR_REDIRECT")
        body=bytearray()
        for chunk in response.iter_content(65536):
            body.extend(chunk)
            if len(body)>limit:raise ValueError("OFFICIAL_DATASET_EXCEEDS_BOUND")
        return bytes(body)

def _resource(meta):
    if not isinstance(meta,dict) or not meta.get("success"):
        raise ValueError("CKAN_PACKAGE_QUERY_FAILED")
    package=meta.get("result",{})
    resources=package.get("resources",[])
    candidates=[r for r in resources if isinstance(r,dict)
                and "csv" in str(r.get("format","")).lower()
                and _host_allowed(str(r.get("url","")))]
    if not candidates:raise ValueError("NO_PERMITTED_OFFICIAL_CSV_RESOURCE")
    candidates.sort(key=lambda r:(
        "development applications" not in str(r.get("name","")).lower(),
        "csv" not in str(r.get("name","")).lower()))
    return candidates[0]["url"]

def _decode(data):
    for codec in ("utf-8-sig","utf-16","cp1252"):
        try:
            value=data.decode(codec)
            if value and "\x00" not in value[:400]:return value
        except UnicodeError:pass
    raise ValueError("UNSUPPORTED_CSV_TEXT_ENCODING")

def _norm(k):
    return re.sub(r"[^A-Z0-9]","",str(k).upper())

def _pick(row,*names):
    lookup={_norm(k):v for k,v in row.items()}
    for name in names:
        val=lookup.get(_norm(name),"")
        if val is not None and str(val).strip():
            return re.sub(r"\s+"," ",str(val)).strip()
    return ""

def _date(value):
    s=str(value or "").strip()
    for pattern in ("%Y-%m-%d","%Y-%m-%d %H:%M:%S",
                    "%m/%d/%Y","%d/%m/%Y","%Y/%m/%d"):
        try:return dt.datetime.strptime(s[:19],pattern).date()
        except ValueError:continue
    return None

def _parse_csv(data,today):
    decoded=_decode(data)
    reader=csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:raise ValueError("NO_CSV_HEADERS")
    columns={_norm(k) for k in reader.fieldnames}
    ids={"APPLICATIONNUMBER","APPLICATIONNO","APPLICATIONNUM",
         "APPLICATIONID","APPLICATION","FILENUMBER","REFERENCEFILE"}
    if not columns.intersection(ids):raise ValueError("CSV_HAS_NO_APPLICATION_IDENTIFIER")
    scope_columns={"DESCRIPTION","FOLDERDESCRIPTION","PROJECTDESCRIPTION",
                   "PROPOSALDESCRIPTION","PROPOSEDUSE","WORKDESCRIPTION","FOLDERNAME"}
    if not columns.intersection(scope_columns):
        raise ValueError("CSV_HAS_NO_PROJECT_SCOPE_FIELD")
    rows={}
    scanned=0
    cutoff=today-dt.timedelta(days=540)
    for record in reader:
        scanned+=1
        if scanned>MAX_ROWS:raise ValueError("CSV_ROW_BOUND_EXCEEDED")
        if not isinstance(record,dict):continue
        ident=_pick(record,"APPLICATION_NUMBER","APPLICATION_NO",
              "APPLICATION_NUM","APPLICATION_ID","APPLICATION","FILE_NUMBER","REFERENCE_FILE")
        if not ident or len(ident)>95:continue
        desc=_pick(record,"DESCRIPTION","FOLDERDESCRIPTION",
              "PROJECT_DESCRIPTION","PROPOSAL_DESCRIPTION","PROPOSED_USE",
              "WORK_DESCRIPTION","FOLDERNAME")
        typ=_pick(record,"APPLICATION_TYPE","TYPE","FOLDERTYPE_DESC")
        status=_pick(record,"STATUS_DESC","STATUS","CURRENT_STATUS",
              "STATUS_DESCRIPTION")
        filing=_pick(record,"SUBMIT_DATE","DATE_SUBMITTED",
              "APPLICATION_DATE","DATE_RECEIVED","IN_DATE","SUBMITTED_DATE")
        date=_date(filing)
        # Screen commercial candidates, not every minor residential variance.
        if not COMMERCIAL.search(desc):continue
        if re.search(r"(?i)\b(?:closed|cancelled|withdrawn|refused)\b",status):
            continue
        # Keep old still-active applications; the filing date is not the first
        # public posting date, and an old pending file can remain important.
        address=_pick(record,"FULL_ADDRESS","STREET_ADDRESS","ADDRESS",
                      "PROPERTY_ADDRESS","LOCATION")
        if not address:
            address=" ".join(filter(None,(_pick(record,"STREET_NUM","STREET_NUMBER"),
                _pick(record,"STREET_NAME"),_pick(record,"STREET_TYPE"))))
        key="OFFICIAL_CKAN:TORONTO:"+re.sub(r"\s+","",ident.upper())
        item={"project_id":key,"city":"Toronto","application_id":ident,
              "address":address,"description":desc[:900],
              "application_type":typ,"current_status":status,
              "source_record_date":date.isoformat() if date else "",
              "date_basis":"OFFICIAL_FILING_DATE_NOT_PUBLICATION" if date else "UNKNOWN",
              "record_source_url":"",
              "record_source_url_basis":"CITY_DATASET_NOT_DIRECT_APPLICATION_RECORD",
              "source_dataset_url":LANDING,
              "commercial_screen":"COMMERCIAL_TEXT_MATCH_NEEDS_VERIFICATION",
              "verification_required":"Verify filed application, proposed use, owner, stage and purchasing opportunity"}
        prior=rows.get(key)
        if prior is None or len(item["description"])>len(prior["description"]):
            rows[key]=item
    if scanned==0:raise ValueError("EMPTY_OFFICIAL_CSV_CANNOT_BASELINE")
    return rows,scanned

def _write(path,rows):
    with Path(path).open("w",encoding="utf-8-sig",newline="") as handle:
        w=csv.DictWriter(handle,fieldnames=FIELDS)
        w.writeheader();w.writerows(rows)

def run(results,*,today=None,metadata=None,csv_data=None):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    today=today or dt.date.today()
    status={"source":"TORONTO_CKAN_DEVELOPMENT_APPLICATIONS",
            "city":"Toronto","source_dataset_url":LANDING,
            "paid_ai_calls":0}
    path=root/STATE
    previous=json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if previous is not None and previous.get("schema")!=1:
        raise ValueError("UNRECOGNIZED_TORONTO_CKAN_STATE")
    allrows=[];changes=[]
    try:
        info=metadata if metadata is not None else json.loads(_get(PACKAGE_URL,MAX_METADATA_BYTES))
        url=_resource(info)
        dataset=csv_data if csv_data is not None else _get(url,MAX_CSV_BYTES)
        rows,scanned=_parse_csv(dataset,today)
        prior=previous.get("seen",{}) if previous else {}
        after=dict(prior)
        for key,row in sorted(rows.items()):
            digest=hashlib.sha256(json.dumps(
                {k:row[k] for k in ("address","description","current_status","application_type")},
                sort_keys=True).encode()).hexdigest()
            old=prior.get(key)
            observation=("INITIAL_BASELINE" if previous is None else
                         "FIRST_OBSERVED" if old is None else
                         "RECORD_CHANGED" if old["digest"]!=digest else "UNCHANGED")
            row["first_seen_local"]=old.get("first_seen_local",today.isoformat()) if old else today.isoformat()
            row["observation"]=observation
            allrows.append(row)
            if observation in ("FIRST_OBSERVED","RECORD_CHANGED"):changes.append(row)
            after[key]={"digest":digest,"first_seen_local":row["first_seen_local"]}
        state={"schema":1,"baseline_date":previous.get("baseline_date",today.isoformat())
               if previous else today.isoformat(),"seen":after}
        temp=path.with_suffix(".tmp")
        temp.write_text(json.dumps(state,indent=2),encoding="utf-8")
        temp.replace(path)
        status.update(status="BASELINED" if previous is None else "COLLECTED",
                      scanned_rows=scanned,commercial_candidates=len(rows),
                      new_or_changed=len(changes),csv_resource=url)
    except Exception as exc:
        status.update(status="FAILED",commercial_candidates=0,
                      new_or_changed=0,error=type(exc).__name__+":"+str(exc)[:180],
                      baseline_preserved=True)
    _write(root/ALL,allrows)
    _write(root/CHANGES,changes)
    (root/STATUS).write_text(json.dumps(status,indent=2),encoding="utf-8")
    return status
