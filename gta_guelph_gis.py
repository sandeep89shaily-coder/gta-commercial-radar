"""Official Guelph active-development GIS collector. No paid AI or policy bypass.

Layer URL comes from the City of Guelph's public Active Development
Applications ArcGIS Experience web map. Only identified application files
with relevant commercial text are candidates. A first successful source
read is a baseline, never a new project announcement.
"""
from __future__ import annotations
import csv
import datetime as dt
import hashlib
import json
import re
import socket
from pathlib import Path
from urllib.parse import urlparse
import requests

from robots_policy import evaluate
from toronto_pdf_download import public_dns

LAYER=("https://gismaps.guelph.ca/hosting/rest/services/External/"
       "ActiveDevelopmentApplications/FeatureServer/0")
MAP="https://experience.arcgis.com/experience/e66bd026b90e4faaae2d81b7319a0ad6"
STATE="GTA_RADAR_GUELPH_GIS_SEEN.json"
ALL="GTA_RADAR_GUELPH_GIS_APPLICATIONS.csv"
NEW="GTA_RADAR_GUELPH_GIS_NEW_OR_CHANGED.csv"
AUDIT="GTA_RADAR_GUELPH_GIS_STATUS.json"
FIELDS=("project_id","city","application_id","address","description",
 "application_type","current_status","source_record_date",
 "source_record_date_basis","source_url","source_layer_url",
 "commercial_screen","first_seen_local","observation","verification_required")
AGENT="GTARadarGuelphPublicGIS/1.0"
PAGE=500
MAX_PAGES=20
MAX_BYTES=6_000_000
COMMERCIAL=re.compile(r"\b(?:commercial|industrial|warehouse|logistics|"
    r"manufactur\w*|office|retail|restaurant|hotel|clinic|medical|veterinary|"
    r"hospital|business|employment|mixed.use|self.storage|distribution|"
    r"gas.bar|shopping|data.cent(?:er|re)|storage.facility|pharma\w*)\b",re.I)
CLOSED=re.compile(r"\b(?:cancelled|withdrawn|closed|refused)\b",re.I)
REQUIRED={"REFERENCEFILE","FOLDERDESCRIPTION","ADDRESS","OBJECTID"}
def _clean(x):
    return re.sub(r"\s+"," ",str(x or "")).strip()

def _http(url,params):
    p=urlparse(url)
    if (p.scheme!="https" or p.hostname!="gismaps.guelph.ca" or
        p.port not in (None,443) or p.username or p.password or
        not public_dns(p.hostname,socket.getaddrinfo)):
        raise ValueError("UNSAFE_OFFICIAL_GUELPH_ENDPOINT")
    ss=requests.Session();ss.trust_env=False
    ss.headers.update({"User-Agent":AGENT,"Accept":"application/json"})
    ok,why=evaluate(ss,url,AGENT,timeout=8)
    if not ok:raise ValueError("SOURCE_POLICY_BLOCKED:"+str(why))
    with ss.get(url,params=params,timeout=(6,18),allow_redirects=False,
                stream=True) as resp:
        if resp.status_code!=200 or urlparse(resp.url).hostname!=p.hostname:
            raise ValueError("GIS_HTTP_"+str(resp.status_code)+"_OR_REDIRECT")
        if "json" not in resp.headers.get("Content-Type","").lower():
            raise ValueError("NON_JSON_GIS_RESPONSE")
        content=bytearray()
        for part in resp.iter_content(65536):
            content.extend(part)
            if len(content)>MAX_BYTES:raise ValueError("GIS_RESPONSE_TOO_LARGE")
        result=json.loads(content)
        if not isinstance(result,dict) or result.get("error"):
            raise ValueError("GIS_API_ERROR:"+str(result.get("error","invalid"))[:130])
        return result

def _collect(fetch):
    meta=fetch(LAYER,{"f":"json"})
    fields={x.get("name") for x in meta.get("fields",[])
            if isinstance(x,dict)}
    if not REQUIRED.issubset(fields):raise ValueError("MISSING_REQUIRED_APPLICATION_FIELDS")
    rows=[];offset=0;complete=False
    for _ in range(MAX_PAGES):
        payload=fetch(LAYER+"/query",{"f":"json","where":"1=1",
            "outFields":"REFERENCEFILE,FOLDERDESCRIPTION,ADDRESS,FOLDERDESC,"
                         "FOLDERNAME,SUBDESC,INDATE,url,OBJECTID",
            "returnGeometry":"false","orderByFields":"OBJECTID ASC",
            "resultOffset":str(offset),"resultRecordCount":str(PAGE)})
        features=payload.get("features")
        if not isinstance(features,list):raise ValueError("GIS_FEATURE_LIST_MISSING")
        for f in features:
            attr=f.get("attributes") if isinstance(f,dict) else None
            if isinstance(attr,dict):rows.append(attr)
        if len(features)<PAGE:
            complete=True;break
        offset+=len(features)
    if not complete:raise ValueError("GIS_PAGINATION_INCOMPLETE")
    return rows

def _parse(a):
    ident=_clean(a.get("REFERENCEFILE"))
    description=_clean(a.get("FOLDERDESCRIPTION") or a.get("FOLDERNAME"))
    if not ident or len(ident)>110 or not description or not COMMERCIAL.search(description):
        return None
    kind=_clean(a.get("SUBDESC") or a.get("FOLDERDESC"))
    if CLOSED.search(kind):return None
    rawdate=a.get("INDATE")
    date=""
    if isinstance(rawdate,(float,int)) and rawdate>0:
        try:date=dt.datetime.fromtimestamp(rawdate/1000,dt.timezone.utc).date().isoformat()
        except (ValueError,OverflowError,OSError):pass
    link=_clean(a.get("url"))
    if not (link.startswith("https://") and
            urlparse(link).hostname in ("guelph.ca","www.guelph.ca")):
        link=""
    return {"project_id":"OFFICIAL_GIS:GUELPH:"+re.sub(r"[^A-Z0-9]","",ident.upper()),
      "city":"Guelph","application_id":ident,"address":_clean(a.get("ADDRESS")),
      "description":description[:900],"application_type":kind,"current_status":"",
      "source_record_date":date,
      "source_record_date_basis":"OFFICIAL_GIS_INDATE_NOT_FIRST_PUBLICATION" if date else "UNKNOWN",
      "source_url":link or MAP,"source_layer_url":LAYER,
      "commercial_screen":"COMMERCIAL_DESCRIPTION_MATCH_NEEDS_MANUAL_VERIFICATION",
      "verification_required":"Verify file, commercial scope, current stage, owner and procurement before outreach"}

def _write(path,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS)
        writer.writeheader();writer.writerows(rows)

def run(results,*,today=None,fetcher=None):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    day=(today or dt.date.today()).isoformat()
    path=root/STATE
    existing=json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    if existing and existing.get("schema")!=1:
        raise ValueError("UNKNOWN_GUELPH_GIS_STATE")
    rows=[];changes=[]
    audit={"source":"GUELPH_ACTIVE_DEVELOPMENT_GIS","city":"Guelph",
           "status":"FAILED","commercial_candidates":0,"new_or_changed":0,
           "baseline_preserved":True,"paid_ai_calls":0}
    try:
        attrs=_collect(fetcher or _http)
        parsed={}
        for attr in attrs:
            item=_parse(attr)
            if item:
                old=parsed.get(item["project_id"])
                if old is None or len(item["description"])>len(old["description"]):
                    parsed[item["project_id"]]=item
        prior=existing.get("seen",{}) if existing else {}
        seen=dict(prior)
        for pid,item in sorted(parsed.items()):
            digest=hashlib.sha256(json.dumps({
                k:item[k] for k in ("address","description","application_type",
                                   "source_record_date")},sort_keys=True).encode()).hexdigest()
            before=prior.get(pid)
            obs=("INITIAL_BASELINE" if existing is None else
                 "FIRST_OBSERVED" if before is None else
                 "RECORD_CHANGED" if digest!=before["digest"] else "UNCHANGED")
            item.update(first_seen_local=before.get("first_seen_local",day) if before else day,
                        observation=obs)
            rows.append(item)
            if obs in ("FIRST_OBSERVED","RECORD_CHANGED"):changes.append(item)
            seen[pid]={"digest":digest,"first_seen_local":item["first_seen_local"]}
        state={"schema":1,"seen":seen,"baseline_date":
               existing.get("baseline_date",day) if existing else day}
        temp=path.with_suffix(".tmp")
        temp.write_text(json.dumps(state,indent=2),encoding="utf-8")
        temp.replace(path)
        audit.update(status="BASELINE_COMPLETE" if existing is None else "COLLECTED",
                     source_rows_scanned=len(attrs),commercial_candidates=len(rows),
                     new_or_changed=len(changes),baseline_preserved=False)
    except Exception as exc:
        audit["error"]=type(exc).__name__+":"+str(exc)[:180]
    _write(root/ALL,rows)
    _write(root/NEW,changes)
    (root/AUDIT).write_text(json.dumps(audit,indent=2),encoding="utf-8")
    return {"source_status":[audit],"commercial_candidates":len(rows),
            "new_or_changed":len(changes),"paid_ai_calls":0}
