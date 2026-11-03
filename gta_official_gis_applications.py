"""Official structured planning application intake for Toronto and Brampton.

Read-only, bounded ArcGIS public application layers. Unlike municipality landing
pages, these contain actual application IDs. No new lead is published from the
first successful source-specific baseline, a failed/incomplete fetch, or a
submission date alone. All applicant names are role-unverified.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import socket
from pathlib import Path
from urllib.parse import urlparse, unquote

import requests

from toronto_pdf_download import public_dns
from robots_policy import evaluate as robots_evaluate

SOURCES = {
    "TORONTO_AIC": {
        "city": "Toronto",
        "url": "https://gis.toronto.ca/arcgis/rest/services/cot_geospatial11/MapServer/60",
        "date": "SUBMIT_DATE",
        "oid": "OBJECTID",
        "fields": ("OBJECTID","APPLICATION_NUMBER","FULL_ADDRESS",
                   "FOLDERDESCRIPTION","FOLDERNAME","APPLICATION_TYPE",
                   "FOLDERTYPE_DESC","SUBMIT_DATE","STATUS_DESC",
                   "AIC_URL","LAST_MODIFIED_DATE"),
    },
    "BRAMPTON_OPA_ZBA": {
        "city": "Brampton",
        "url": "https://services3.arcgis.com/rl7ACuZkiFsmDA2g/ArcGIS/rest/services/Planning_Land_Use_Development/FeatureServer/9",
        "date": "DATE_RECEIVED",
        "oid": "POLY_ID",
        "fields": ("POLY_ID","FILE_NUMBER","LOCATION","DATE_RECEIVED",
                   "APPLICATION_TYPE","APPLICATION_TITLE","DESCRIPTION",
                   "PROPOSAL_DESCRIPTION","STATUS","APPLICANT_COMPANY","AGENT_COMPANY"),
    },
    "BRAMPTON_SITE_PLAN": {
        "city": "Brampton",
        "url": "https://services3.arcgis.com/rl7ACuZkiFsmDA2g/ArcGIS/rest/services/Planning_Land_Use_Development/FeatureServer/11",
        "date": "DATE_RECEIVED",
        "oid": "POLY_ID",
        "fields": ("POLY_ID","FILE_NUMBER","LOCATION","DATE_RECEIVED",
                   "APPLICATION_TYPE","APPLICATION_TITLE","DESCRIPTION",
                   "PROPOSAL_DESCRIPTION","STATUS","APPLICANT_COMPANY","AGENT_COMPANY"),
    },
}
STATE="GTA_RADAR_STRUCTURED_PLANNING_APPLICATION_SEEN.json"
ALL="GTA_RADAR_STRUCTURED_APPLICATIONS_TORONTO_BRAMPTON.csv"
CHANGES="GTA_RADAR_STRUCTURED_APPLICATION_CHANGES.csv"
AUDIT="GTA_RADAR_STRUCTURED_APPLICATION_SOURCE_STATUS.json"
FIELDS=("project_id","city","application_id","address","description",
        "application_type","current_status","applicant_company_unverified",
        "source_record_date","source_record_date_basis","record_source_url",
        "record_source_url_basis","source_layer","source_layer_url","commercial_fit",
        "first_seen_local","observation","changed_fields","verification_required")
COMMERCIAL=re.compile(
    r"\b(?:industrial|warehouse|logistics|distribution.cent(?:er|re)|"
    r"manufactur\w*|factory|commercial|retail|shopping|supermarket|grocery|"
    r"restaurant|office|hotel|hospital|clinic|medical|data.cent(?:er|re)|"
    r"employment.land|employment.block|business.park|self.storage|"
    r"storage.facility|laborator\w*|pharma\w*|research.facility)\b",re.I)
RESIDENTIAL=re.compile(r"\b(?:residential|condominium|apartments?|dwellings?|"
                       r"townhous\w*|townhom\w*|single.family)\b",re.I)
CLOSED=re.compile(r"\b(?:closed|withdrawn|cancelled|refused|rejected)\b",re.I)
AGENT="GTARadarStructuredPlanning/1.0"
PAGE=750
MAX_PAGES=20
MAX_BYTES=6_000_000

def _clean(val):
    return re.sub(r"\s+"," ",str(val or "")).strip()

def _date(val):
    if isinstance(val,(float,int)) and val>0:
        try:return dt.datetime.fromtimestamp(val/1000,dt.timezone.utc).date()
        except (OverflowError,ValueError,OSError):return None
    if isinstance(val,str) and len(val)>=10:
        try:return dt.date.fromisoformat(val[:10])
        except ValueError:pass
    return None

def _json_http(url,params):
    target=url+"/query"
    host=urlparse(url).hostname
    if urlparse(url).scheme!="https" or not host or not public_dns(host,socket.getaddrinfo):
        raise ValueError("INVALID_OFFICIAL_GIS_DNS_OR_SCHEME")
    session=requests.Session()
    session.trust_env=False
    session.headers.update({"User-Agent":AGENT,"Accept":"application/json"})
    allowed,reason=robots_evaluate(session,target,AGENT,timeout=8)
    if not allowed:raise ValueError("SOURCE_POLICY_BLOCKED:"+str(reason))
    with session.get(target,params=params,timeout=(6,16),
                     allow_redirects=False,stream=True) as resp:
        if resp.status_code!=200 or urlparse(resp.url).hostname!=host:
            raise ValueError("GIS_HTTP_"+str(resp.status_code)+"_OR_REDIRECT")
        if "json" not in resp.headers.get("Content-Type","").lower():
            raise ValueError("GIS_NON_JSON_RESPONSE")
        content=bytearray()
        for chunk in resp.iter_content(65536):
            content.extend(chunk)
            if len(content)>MAX_BYTES:raise ValueError("GIS_RESPONSE_TOO_LARGE")
        result=json.loads(content)
        if not isinstance(result,dict) or "error" in result:
            raise ValueError("GIS_API_ERROR:"+str(result.get("error","invalid JSON"))[:100])
        return result

def _fetch_layer(source,fetcher,cutoff,max_pages):
    offset=0
    recent=[]
    pages=0
    exhausted=False
    for _ in range(max_pages):
        args={
            "where":"1=1",
            "outFields":",".join(source["fields"]),
            "returnGeometry":"false",
            "orderByFields":source["date"]+" DESC,"+source["oid"]+" DESC",
            "resultRecordCount":str(PAGE),
            "resultOffset":str(offset),
            "f":"json",
        }
        data=fetcher(source["url"],args)
        features=data.get("features")
        if not isinstance(features,list):
            raise ValueError("GIS_FEATURES_NOT_RETURNED")
        pages+=1
        newer=0
        for item in features:
            attrs=item.get("attributes") if isinstance(item,dict) else None
            if not isinstance(attrs,dict):continue
            timestamp=_date(attrs.get(source["date"]))
            if timestamp and timestamp>=cutoff:
                recent.append(attrs);newer+=1
        # Dates are in descending order: stop when the first older
        # application appears, rather than paginate the whole city history.
        if len(features)<PAGE or newer<len(features):
            exhausted=True
            break
        offset+=len(features)
    if not exhausted:
        raise ValueError("GIS_PAGE_LIMIT_REACHED_NO_COMPLETE_RECENT_WINDOW")
    return recent,pages

def _parse(source_key,attrs):
    src=SOURCES[source_key]
    city=src["city"]
    if city=="Toronto":
        num=_clean(attrs.get("APPLICATION_NUMBER"))
        address=_clean(attrs.get("FULL_ADDRESS"))
        desc=_clean(attrs.get("FOLDERDESCRIPTION") or attrs.get("FOLDERNAME"))[:800]
        kind=_clean(attrs.get("FOLDERTYPE_DESC") or attrs.get("APPLICATION_TYPE"))
        status=_clean(attrs.get("STATUS_DESC"))
        link=_clean(attrs.get("AIC_URL"))
        # The official GIS AIC_URL field can point to a general search page.
        # Treat it as an exact record link only when it contains this file ID
        # in the actual URL. Do not invent record-level evidence from a portal.
        normalized_id=re.sub(r"[^A-Z0-9]","",num.upper())
        normalized_link=re.sub(r"[^A-Z0-9]","",unquote(link).upper())
        allow_link=(urlparse(link).scheme=="https" and
                    urlparse(link).hostname in (
                        "www.toronto.ca","toronto.ca","secure.toronto.ca") and
                    len(normalized_id)>=8 and normalized_id in normalized_link)
        direct=link if allow_link else ""
        applicant=""
    else:
        num=_clean(attrs.get("FILE_NUMBER"))
        address=_clean(attrs.get("LOCATION"))
        desc=_clean(attrs.get("PROPOSAL_DESCRIPTION") or attrs.get("DESCRIPTION")
                    or attrs.get("APPLICATION_TITLE"))[:800]
        kind=_clean(attrs.get("APPLICATION_TYPE"))
        status=_clean(attrs.get("STATUS"))
        applicant=_clean(attrs.get("APPLICANT_COMPANY"))[:180]
        direct=""
    if not num or not _date(attrs.get(src["date"])) or CLOSED.search(status):
        return None
    if not COMMERCIAL.search(desc):
        return None
    cls=("MIXED_RESIDENTIAL_COMMERCIAL_NEEDS_REVIEW" if RESIDENTIAL.search(desc)
         else "COMMERCIAL_INDUSTRIAL_TEXT_MATCH_NEEDS_VERIFICATION")
    pid="OFFICIAL_GIS:"+city.upper()+":"+re.sub(r"\s+","",num.upper())
    record_date=_date(attrs[src["date"]])
    return {
        "project_id":pid,"city":city,"application_id":num,"address":address,
        "description":desc,"application_type":kind,"current_status":status,
        "applicant_company_unverified":applicant,
        "source_record_date":record_date.isoformat(),
        "source_record_date_basis":"OFFICIAL_APPLICATION_SUBMISSION_DATE_NOT_FIRST_PUBLICATION",
        "record_source_url":direct,
        "record_source_url_basis":("TORONTO_AIC_RECORD_LINK_FROM_OFFICIAL_GIS"
            if direct else "NO_DIRECT_RECORD_LINK_GIS_LAYER_ONLY"),
        "source_layer":source_key,"source_layer_url":src["url"],
        "commercial_fit":cls,
        "verification_required":"Verify exact application, project scope, developer/owner role, construction stage and whether packages remain open",
    }

def _write(path,rows):
    with Path(path).open("w",encoding="utf-8-sig",newline="") as file:
        writer=csv.DictWriter(file,fieldnames=FIELDS,extrasaction="ignore")
        writer.writeheader();writer.writerows(rows)

def run(results,*,today=None,fetcher=None,sources=None,max_pages=MAX_PAGES):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    today=today or dt.date.today()
    cutoff=today-dt.timedelta(days=540)
    statepath=root/STATE
    state=json.loads(statepath.read_text(encoding="utf-8")) if statepath.is_file() else {
        "schema":1,"sources":{}}
    if state.get("schema")!=1:raise ValueError("UNKNOWN_STRUCTURED_GIS_SCHEMA")
    active_sources=sources or SOURCES
    output=[];changes=[];status=[]
    for source_key,src in active_sources.items():
        source_state=state["sources"].get(source_key)
        try:
            attrs,pages=_fetch_layer(src,fetcher or _json_http,cutoff,max_pages)
            # Stable city file ID is the identity; multiple parcels or layers
            # must not silently turn one file into different projects.
            rows={}
            for raw in attrs:
                item=_parse(source_key,raw)
                if item:
                    pid=item["project_id"]
                    prior=rows.get(pid)
                    if prior is None or len(item["description"])>len(prior["description"]):
                        rows[pid]=item
            old=source_state.get("seen",{}) if source_state else {}
            baseline=source_state is None
            newseen=dict(old)
            for pid,item in sorted(rows.items()):
                fields=("application_id","address","description","application_type",
                        "current_status","applicant_company_unverified","source_record_date")
                fingerprint=hashlib.sha256(json.dumps(
                    {k:item[k] for k in fields},sort_keys=True).encode()).hexdigest()
                previous=old.get(pid)
                if previous is None:obs="INITIAL_BASELINE" if baseline else "FIRST_OBSERVED"
                elif fingerprint!=previous["fingerprint"]:obs="RECORD_CHANGED"
                else:obs="UNCHANGED"
                item["first_seen_local"]=(previous.get("first_seen_local",today.isoformat())
                                          if previous else today.isoformat())
                item["observation"]=obs
                item["changed_fields"]=("REQUIRES_SNAPSHOT_COMPARISON" if obs=="RECORD_CHANGED" else "")
                newseen[pid]={"fingerprint":fingerprint,
                              "first_seen_local":item["first_seen_local"]}
                output.append(item)
                if obs in ("FIRST_OBSERVED","RECORD_CHANGED"):changes.append(item)
            state["sources"][source_key]={"seen":newseen,"baseline_date":
                source_state["baseline_date"] if source_state else today.isoformat()}
            status.append({"source":source_key,"city":src["city"],
                           "status":"OK_BASELINE" if baseline else "OK_MONITORED",
                           "rows_scanned_recent":len(attrs),
                           "commercial_candidates":len(rows),
                           "new_or_changed":sum(r["source_layer"]==source_key for r in changes),
                           "pages":pages,"cutoff":cutoff.isoformat()})
        except Exception as error:
            status.append({"source":source_key,"city":src["city"],"status":"FAILED",
                           "error":type(error).__name__+":"+str(error)[:150],
                           "commercial_candidates":0,
                           "baseline_preserved_for_retry":True})
    # Commit successful source baselines independently; blocked source must
    # not establish one. Write snapshots atomically after the full stage.
    _write(root/ALL,output)
    _write(root/CHANGES,changes)
    state_temp=statepath.with_name(statepath.name+".tmp")
    state_temp.write_text(json.dumps(state,indent=2),encoding="utf-8")
    state_temp.replace(statepath)
    summary={
        "status":"OK" if all(s["status"].startswith("OK_") for s in status)
                 else "PARTIAL_SOURCES_FAILED",
        "source_status":status,"sources_configured":len(active_sources),
        "sources_successful":sum(s["status"].startswith("OK_") for s in status),
        "application_candidates":len(output),"new_or_changed":len(changes),
        "date_cutoff":cutoff.isoformat(),"initial_successful_fetch_is_baseline":True,
        "paid_ai_calls":0,"canonical_project_auto_promotions":0,
        "all_csv":str(root/ALL),"new_csv":str(root/CHANGES),
        "note":"Commercial text matches unverified; dates are filing dates, not first public posting; historical records remain in local per-source first-seen ledger."}
    (root/AUDIT).write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary
