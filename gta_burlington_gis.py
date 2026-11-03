"""Official Burlington development GIS project feed (no invented file numbers).

The City's public ArcGIS MapServer publishes named development projects,
locations and official project URLs but DOES NOT publish application IDs.
Output is therefore PROJECT_INDEX_SIGNAL only, never confirmed applications.
"""
from __future__ import annotations
import csv
import datetime as dt
import hashlib
import json
import socket
from pathlib import Path
from urllib.parse import urlparse
import requests
from robots_policy import evaluate
from toronto_pdf_download import public_dns

LAYER=("https://mapping.burlington.ca/arcgisweb/rest/services/COB/"
       "Development_Apps/MapServer/0")
STATE="GTA_RADAR_BURLINGTON_GIS_SEEN.json"
ALL="GTA_RADAR_BURLINGTON_GIS_PROJECTS.csv"
NEW="GTA_RADAR_BURLINGTON_GIS_NEW_OR_CHANGED.csv"
AUDIT="GTA_RADAR_BURLINGTON_GIS_STATUS.json"
FIELDS=("project_id","city","application_id","project_title","address",
        "description","source_url","source_type","record_kind",
        "commercial_screen","first_seen_local","observation","verification_required")
AGENT="GTARadarBurlingtonOfficialGIS/1.0"
PAGE=400
MAX_PAGES=10
MAX_BYTES=4500000
REQUIRED={"OBJECTID","NAME","PROJECTWEBSITE","LOCATION","WARD"}

def _fetch(url,params):
    p=urlparse(url)
    if (p.scheme!="https" or p.hostname!="mapping.burlington.ca" or
        p.port not in (None,443) or p.username or p.password or p.fragment or
        not public_dns(p.hostname,socket.getaddrinfo)):
        raise ValueError("INVALID_BURLINGTON_GIS_SOURCE")
    ss=requests.Session();ss.trust_env=False
    ss.headers.update({"User-Agent":AGENT,"Accept":"application/json"})
    yes,reason=evaluate(ss,url,AGENT,timeout=8)
    if not yes:raise ValueError("POLICY_DENIED:"+reason)
    with ss.get(url,params=params,timeout=(6,18),stream=True,allow_redirects=False) as r:
        if r.status_code!=200 or urlparse(r.url).hostname!=p.hostname:
            raise ValueError("GIS_HTTP_"+str(r.status_code))
        if "json" not in r.headers.get("Content-Type","").lower():
            raise ValueError("NON_JSON_BURLINGTON_GIS")
        body=bytearray()
        for chunk in r.iter_content(65536):
            body.extend(chunk)
            if len(body)>MAX_BYTES:raise ValueError("GIS_TOO_LARGE")
        result=json.loads(body)
        if not isinstance(result,dict) or result.get("error"):
            raise ValueError("INVALID_GIS_JSON:"+str(result.get("error"))[:90])
        return result

def _collect(fetcher):
    meta=fetcher(LAYER,{"f":"json"})
    fields={r.get("name") for r in meta.get("fields",[]) if isinstance(r,dict)}
    if not REQUIRED.issubset(fields):
        raise ValueError("UNVERIFIED_BURLINGTON_GIS_SCHEMA")
    rows=[];offset=0;complete=False
    for _ in range(MAX_PAGES):
        result=fetcher(LAYER+"/query",{"f":"json","where":"1=1",
           "returnGeometry":"false",
           "outFields":"OBJECTID,NAME,PROJECTWEBSITE,LOCATION,WARD",
           "orderByFields":"OBJECTID ASC","resultOffset":str(offset),
           "resultRecordCount":str(PAGE)})
        features=result.get("features")
        if not isinstance(features,list):raise ValueError("GIS_FEATURE_LIST_MISSING")
        rows.extend(f.get("attributes",{}) for f in features if isinstance(f,dict))
        if len(features)<PAGE:
            complete=True;break
        offset+=len(features)
    if not complete:raise ValueError("INCOMPLETE_BURLINGTON_GIS_PAGINATION")
    return rows

def _record(r):
    title=" ".join(str(r.get("NAME") or "").split())[:250]
    address=" ".join(str(r.get("LOCATION") or "").split())[:240]
    oid=r.get("OBJECTID")
    if not title or oid is None:return None
    link=str(r.get("PROJECTWEBSITE") or "")
    p=urlparse(link)
    if (p.scheme!="https" or p.hostname not in
        ("www.burlington.ca","burlington.ca")):
        link=LAYER
    identity="BURLINGTON:GIS:"+str(oid)
    return {"project_id":identity,"city":"Burlington","application_id":"",
            "project_title":title,"address":address,
            "description":title+" — "+address,"source_url":link,
            "source_type":"BURLINGTON_OFFICIAL_GIS","record_kind":"PROJECT_INDEX_SIGNAL",
            "commercial_screen":"PROJECT_SCOPE_REQUIRES_REVIEW",
            "verification_required":"Official map contains no application ID, scope or filing date. Verify exact application, commercial use, stage and owner manually"}

def _write(path,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS)
        w.writeheader();w.writerows(rows)

def run(results,*,today=None,fetcher=None):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    day=(today or dt.date.today()).isoformat()
    path=root/STATE
    prior=json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if prior and prior.get("schema")!=1:raise ValueError("UNKNOWN_GIS_STATE")
    allrows=[];changed=[]
    status={"city":"Burlington","source":"BURLINGTON_DEVELOPMENT_GIS",
            "status":"FAILED","project_only_signals":0,
            "application_id_rows":0,"new_or_changed":0,"paid_ai_calls":0,
            "baseline_preserved":True}
    try:
        source=_collect(fetcher or _fetch)
        rows={v["project_id"]:v for raw in source if (v:=_record(raw))}
        previous=prior.get("seen",{}) if prior else {}
        seen=dict(previous)
        for pid,row in sorted(rows.items()):
            digest=hashlib.sha256((row["project_title"]+"|"+row["address"]).encode()).hexdigest()
            old=previous.get(pid)
            obs="INITIAL_BASELINE" if prior is None else (
                "FIRST_OBSERVED" if old is None else
                "RECORD_CHANGED" if digest!=old["digest"] else "UNCHANGED")
            row.update(first_seen_local=old["first_seen_local"] if old else day,
                       observation=obs)
            allrows.append(row)
            if obs in ("FIRST_OBSERVED","RECORD_CHANGED"):changed.append(row)
            seen[pid]={"digest":digest,"first_seen_local":row["first_seen_local"]}
        update={"schema":1,"seen":seen,"baseline_date":prior.get("baseline_date",day) if prior else day}
        tmp=path.with_suffix(".tmp")
        tmp.write_text(json.dumps(update,indent=2),encoding="utf-8")
        tmp.replace(path)
        status.update(status="BASELINE_COMPLETE" if prior is None else "COLLECTED",
                      project_only_signals=len(allrows),
                      source_rows_scanned=len(source),new_or_changed=len(changed),
                      baseline_preserved=False)
    except Exception as err:
        status["error"]=type(err).__name__+":"+str(err)[:180]
    _write(root/ALL,allrows);_write(root/NEW,changed)
    (root/AUDIT).write_text(json.dumps(status,indent=2),encoding="utf-8")
    return status
