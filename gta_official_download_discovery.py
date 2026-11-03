"""Policy-safe municipal CSV alternative discovery, never an access bypass.

Official ArcGIS Hub catalogs for Mississauga site plan / rezoning and St.
Catharines permits expose an export API, but the export URL is on the same
service host that blocks our collector. Respect *both* robots policies.
Produces source-access evidence and refreshes weekly; no records collected,
no claims about city coverage, and no paid AI.
"""
from __future__ import annotations
import datetime as dt
import json
import socket
from pathlib import Path
from urllib.parse import urlparse
import requests
from robots_policy import evaluate
from toronto_pdf_download import public_dns

AGENT="GTARadarOfficialDownloadAccessAudit/1.0"
SOURCES={
 "mississauga_site_plan_applications":{
   "city":"Mississauga","item":"85536f145719436ebde8d31f36d11d83",
   "owner":"MississaugaData","title":"Site Plan Applications"},
 "mississauga_rezoning_applications":{
   "city":"Mississauga","item":"9b25caf083d54593a7db21ea056cfb3d",
   "owner":"MississaugaData","title":"Rezoning Applications"},
 "st_catharines_building_permits":{
   "city":"St. Catharines","item":"83f3b80be17a4fd29c58529dc945f371",
   "owner":"ncolangeloAGOL87","title":"Building Permits Public"}
}
STATUS="GTA_RADAR_OFFICIAL_DOWNLOAD_ACCESS_STATUS.json"
CACHE="GTA_RADAR_OFFICIAL_DOWNLOAD_ACCESS_LEDGER.json"
MAX_BYTES=300000

def _get(session,url):
    p=urlparse(url)
    if (p.scheme!="https" or not p.hostname or p.username or p.password
       or p.port not in (None,443) or p.fragment
       or not public_dns(p.hostname,socket.getaddrinfo)):
        raise ValueError("INVALID_OR_NONPUBLIC_CATALOG_URL")
    yes,why=evaluate(session,url,AGENT,timeout=5)
    if not yes:raise ValueError("CATALOG_ACCESS_DENIED:"+str(why))
    with session.get(url,timeout=(5,13),stream=True,allow_redirects=False) as r:
        if r.status_code!=200 or urlparse(r.url).hostname!=p.hostname:
            raise ValueError("CATALOG_HTTP_"+str(r.status_code))
        body=bytearray()
        for part in r.iter_content(65536):
            body.extend(part)
            if len(body)>MAX_BYTES:raise ValueError("CATALOG_RESPONSE_TOO_LARGE")
        obj=json.loads(body)
        if not isinstance(obj,dict):raise ValueError("NOT_JSON_OBJECT")
        return obj

def _allowed(session,url):
    p=urlparse(url)
    if p.scheme!="https" or not p.hostname or p.port not in (None,443):
        return False,"INVALID_EXPORT_TARGET"
    if p.username or p.password or p.fragment:
        return False,"INVALID_EXPORT_TARGET"
    try:
        if not public_dns(p.hostname,socket.getaddrinfo):
            return False,"NONPUBLIC_EXPORT_TARGET"
        return evaluate(session,url,AGENT,timeout=5)
    except Exception as e:
        return False,"EXPORT_POLICY_CHECK_FAILED:"+type(e).__name__

def probe(id,config,session,getter=_get,policy=_allowed):
    item=config["item"]
    meta_url="https://www.arcgis.com/sharing/rest/content/items/"+item+"?f=json"
    export_url="https://hub.arcgis.com/api/download/v1/items/"+item+"/csv?redirect=false&layers=0"
    row={"source_id":id,"city":config["city"],"title":config["title"],
         "item_id":item,"status":"FAILED","application_records":0,
         "official_catalog_url":meta_url,"hub_export_url":export_url,
         "sales_lead_publication":False}
    try:
        meta=getter(session,meta_url)
        if (meta.get("id")!=item or meta.get("owner")!=config["owner"]
            or meta.get("title")!=config["title"]):
            raise ValueError("PUBLISHER_OR_DATASET_IDENTITY_MISMATCH")
        row["published_service_url"]=meta.get("url","")
        export=getter(session,export_url)
        target=export.get("resultUrl","")
        if export.get("status")!="Completed" or not target:
            row.update(status="EXPORT_NOT_READY",export_status=export.get("status"))
            return row
        p=urlparse(target)
        expected=urlparse(meta.get("url","")).hostname
        if (p.scheme!="https" or p.hostname!=expected or
            "/replicafilescache/" not in p.path or not p.path.endswith(".csv")):
            raise ValueError("EXPORT_TARGET_NOT_OFFICIAL_SERVICE")
        # This is a POLICY CHECK ONLY, not a data request; never relay a
        # restricted ArcGIS CSV via the Hub, proxies or browser automation.
        allowed,reason=policy(session,target)
        row.update(export_target_host=p.hostname,export_target_allowed=bool(allowed),
                   export_policy_reason=reason,
                   status="EXPORT_ACCESS_PERMITTED_NEEDS_COLLECTION_QA" if allowed
                     else "EXPORT_TARGET_ACCESS_RESTRICTED")
    except Exception as e:
        row["error"]=type(e).__name__+":"+str(e)[:200]
        row["status"]="FAILED"
    return row

def run(results,*,today=None,scanner=probe,force=False):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    today=(today or dt.date.today()).isoformat()
    ledger=root/CACHE
    previous=json.loads(ledger.read_text(encoding="utf-8")) if ledger.exists() else None
    if previous and not force and previous.get("checked_date","")[:7]==today[:7]:
        return {"status":"CACHED_MONTHLY","sources":previous["sources"],
                "paid_ai_calls":0,"application_records":0}
    session=requests.Session();session.trust_env=False
    session.headers["User-Agent"]=AGENT
    try:
        records=[scanner(id,config,session) for id,config in SOURCES.items()]
    finally:session.close()
    result={"status":"ACCESS_AUDIT_COMPLETE","checked_date":today,
            "sources":records,"paid_ai_calls":0,"application_records":0,
            "access_restricted":sum(r["status"]=="EXPORT_TARGET_ACCESS_RESTRICTED" for r in records),
            "warning":"Hub export metadata is not an application export. No download of robots-restricted service data."}
    (root/STATUS).write_text(json.dumps(result,indent=2),encoding="utf-8")
    temp=ledger.with_suffix(".tmp")
    temp.write_text(json.dumps(result,indent=2),encoding="utf-8")
    temp.replace(ledger)
    return result

if __name__=="__main__":
 import argparse
 parser=argparse.ArgumentParser()
 parser.add_argument("--output",required=True)
 parser.add_argument("--force",action="store_true")
 args=parser.parse_args()
 print("OFFICIAL_EXPORT_ACCEPTANCE",json.dumps(run(args.output,force=args.force)))
