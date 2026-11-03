"""Official Hamilton and Kitchener public planning GIS intake, review only.

This adds genuine application-level sources rather than counting an accessible
landing page as coverage. It does not claim that either live ArcGIS query has
succeeded until an actual successful production fetch appears in the audit.
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
from toronto_pdf_download import public_dns
from robots_policy import evaluate
from gta_early_applications import COMMERCIAL, RESIDENTIAL, ID_PATTERN

SOURCES={
    "HAMILTON_DEVELOPMENT_APPLICATIONS":{
        "city":"Hamilton",
        "url":"https://services.arcgis.com/rYz782eMbySr2srL/arcgis/rest/services/Development_Applications/FeatureServer/2",
        "reference":"City of Hamilton public Development Applications, up to last five years"},
    "KITCHENER_ACTIVE_PLANNING":{
        "city":"Kitchener",
        "url":"https://services1.arcgis.com/qAo1OsXi67t7XgmS/arcgis/rest/services/Planning_Applications_Active/FeatureServer/0",
        "reference":"City of Kitchener Planning Applications Active, advertised hourly update"},
}
STATE="GTA_RADAR_ADDITIONAL_GIS_SEEN.json"
ALL="GTA_RADAR_ADDITIONAL_CITY_GIS_APPLICATIONS.csv"
NEW="GTA_RADAR_ADDITIONAL_CITY_GIS_NEW_OR_CHANGED.csv"
AUDIT="GTA_RADAR_ADDITIONAL_CITY_GIS_STATUS.json"
FIELDS=("project_id","city","application_id","address","description","application_type",
        "current_status","source_url","source_record_date","date_basis",
        "official_record_link","official_record_link_basis","commercial_fit",
        "first_seen_local","observation","changed_fields","verification_required")
PAGE=750
MAX_PAGES=20
MAX_BYTES=5_000_000
AGENT="GTARadarPublicGIS/1.0"
CLOSED=re.compile(r"\b(?:closed|cancelled|withdrawn|refused)\b",re.I)

def _read_json(url,params):
    parsed=urlparse(url)
    if (parsed.scheme!="https" or parsed.port not in (None,443) or
            parsed.username or parsed.password or parsed.fragment or
            not parsed.hostname or not public_dns(parsed.hostname,socket.getaddrinfo)):
        raise ValueError("INVALID_PUBLIC_ARCGIS_URL_OR_DNS")
    session=requests.Session();session.trust_env=False
    session.headers.update({"User-Agent":AGENT,"Accept":"application/json"})
    permitted,reason=evaluate(session,url,AGENT,timeout=8)
    if not permitted:raise ValueError("ROBOTS_BLOCKED:"+str(reason))
    with session.get(url,params=params,stream=True,allow_redirects=False,
                     timeout=(6,16)) as resp:
        if resp.status_code!=200 or urlparse(resp.url).hostname!=parsed.hostname:
            raise ValueError("HTTP_"+str(resp.status_code)+"_OR_REDIRECT")
        if "json" not in resp.headers.get("Content-Type","").lower():
            raise ValueError("NOT_A_JSON_API_RESPONSE")
        data=bytearray()
        for chunk in resp.iter_content(65536):
            data.extend(chunk)
            if len(data)>MAX_BYTES:raise ValueError("GIS_RESPONSE_TOO_LARGE")
        result=json.loads(data)
        if not isinstance(result,dict) or result.get("error"):
            raise ValueError("ARCGIS_ERROR:"+str(result.get("error","unknown"))[:120])
        return result

def _clean(v):
    return re.sub(r"\s+"," ",str(v or "")).strip()

def _pick(attrs,parts):
    for token in parts:
        for key,val in attrs.items():
            key_l=key.casefold().replace("_","")
            if key_l==token or key_l.startswith(token):
                if isinstance(val,str) and _clean(val):return _clean(val)
    return ""

def _parse(city,url,attrs):
    # Source schemas differ. Prefer official file-number fields; never use
    # ArcGIS OBJECTID or a street address as an alleged application number.
    ident=_pick(attrs,("applicationnumber","applicationnum","appnumber",
        "appnum","filenumber","fileno","filename","fileid","planningfile",
        "applicno","applicationid"))
    if not ident:
        for key,val in attrs.items():
            if isinstance(val,str) and ID_PATTERN.fullmatch(_clean(val)):
                ident=_clean(val);break
    if not ident or len(ident)>130:return None
    desc=_pick(attrs,("description","filedescription","proposeddevelopment",
        "developmentdescription","proposal","projectdescription",
        "workdescription","developmenttype","landuse"))
    if not desc or not COMMERCIAL.search(desc) or CLOSED.search(
        _pick(attrs,("applicationstatus","filestatus","status"))):
        return None
    cls="MIXED_USE_NEEDS_REVIEW" if RESIDENTIAL.search(desc) else "COMMERCIAL_TEXT_MATCH_NEEDS_REVIEW"
    addr=_pick(attrs,("fulladdress","municipaladdress","propertyaddress",
        "siteaddress","address","location","streetaddress","filelocation"))
    kind=_pick(attrs,("filetype","applicationtype","apptype","type"))
    current=_pick(attrs,("applicationstatus","filestatus","status"))
    # The source's year/last-update timestamp is not proof of first publication.
    return {"project_id":"OFFICIAL_GIS:"+city.upper()+":"+
                 re.sub(r"\s+","",ident.upper()),
        "city":city,"application_id":ident,"address":addr,
        "description":desc[:800],"application_type":kind,
        "current_status":current,"source_url":url,
        "source_record_date":"","date_basis":"NO_VERIFIED_APPLICATION_POSTING_DATE",
        "official_record_link":"","official_record_link_basis":"GIS_LAYER_ONLY_NOT_APPLICATION_DEEP_LINK",
        "commercial_fit":cls,
        "verification_required":"Verify ID, property, proposal, original filing/revision date and contract stage"}

def _get_source(src,fetch,max_pages):
    meta=fetch(src["url"],{"f":"json"})
    fields=meta.get("fields")
    oid=meta.get("objectIdField") or meta.get("objectIdFieldName")
    if not oid or not isinstance(fields,list):
        raise ValueError("GIS_LAYER_METADATA_MISSING")
    names={x.get("name") for x in fields if isinstance(x,dict)}
    if oid not in names:raise ValueError("GIS_OBJECT_ID_NOT_IN_METADATA")
    rows=[];offset=0;complete=False
    for page in range(max_pages):
        query=fetch(src["url"]+"/query",{
            "f":"json","where":"1=1","outFields":"*",
            "returnGeometry":"false","orderByFields":oid+" ASC",
            "resultRecordOffset":str(offset),
            "resultOffset":str(offset),
            "resultRecordCount":str(PAGE)})
        features=query.get("features")
        if not isinstance(features,list):raise ValueError("GIS_NO_FEATURE_LIST")
        for element in features:
            attrs=element.get("attributes") if isinstance(element,dict) else None
            if isinstance(attrs,dict):rows.append(attrs)
        if len(features)<PAGE:
            complete=True
            break
        offset+=len(features)
    if not complete:raise ValueError("INCOMPLETE_GIS_PAGINATION_NO_BASELINE")
    return rows

def _write(path,rows):
    with Path(path).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS,extrasaction="ignore")
        w.writeheader();w.writerows(rows)

def run(results,*,today=None,sources=None,fetcher=None,max_pages=MAX_PAGES):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    day=(today or dt.date.today()).isoformat()
    path=root/STATE
    if path.is_file():
        state=json.loads(path.read_text(encoding="utf-8"))
        if state.get("schema")!=1:raise ValueError("UNKNOWN_ADDITIONAL_GIS_SCHEMA")
    else:state={"schema":1,"sources":{}}
    changes=[];allrows=[];city_status=[]
    for key,src in (sources or SOURCES).items():
        oldstate=state["sources"].get(key)
        try:
            attrs=_get_source(src,fetcher or _read_json,max_pages)
            matched={}
            for a in attrs:
                row=_parse(src["city"],src["url"],a)
                if row:
                    existing=matched.get(row["project_id"])
                    if existing is None or len(row["description"])>len(existing["description"]):
                        matched[row["project_id"]]=row
            # If the schema has no verifiable application ID and/or description
            # field, do NOT mark an empty layer as complete coverage.
            field_names={str(k).lower() for a in attrs[:4] for k in a}
            has_id=any(("file" in k or "application" in k or "appnum" in k) and
                       not k.endswith("date") for k in field_names)
            has_scope=any(any(t in k for t in ("desc","proposal","development","landuse"))
                          for k in field_names)
            if attrs and not (has_id and has_scope):
                raise ValueError("SCHEMA_LACKS_APPLICATION_ID_OR_DESCRIPTION")
            before=oldstate.get("seen",{}) if oldstate else {}
            after=dict(before)
            for pid,row in sorted(matched.items()):
                digest=hashlib.sha256(json.dumps(
                    {k:row.get(k) for k in ("address","description","application_type","current_status")},
                    sort_keys=True).encode()).hexdigest()
                prev=before.get(pid)
                label=("INITIAL_BASELINE" if not oldstate and prev is None else
                       "FIRST_OBSERVED" if prev is None else
                       "RECORD_CHANGED" if prev.get("digest")!=digest else "UNCHANGED")
                row.update(first_seen_local=prev.get("first_seen_local",day) if prev else day,
                           observation=label,
                           changed_fields="REVIEW_SOURCE_RECORD_CHANGE" if label=="RECORD_CHANGED" else "")
                after[pid]={"digest":digest,"first_seen_local":row["first_seen_local"]}
                allrows.append(row)
                if label in ("FIRST_OBSERVED","RECORD_CHANGED"):changes.append(row)
            state["sources"][key]={"seen":after,"baseline_date":
                  oldstate.get("baseline_date",day) if oldstate else day}
            city_status.append({"city":src["city"],"source":key,
                "status":"BASELINE_COMPLETE" if oldstate is None else "COLLECTED",
                "source_rows_scanned":len(attrs),"commercial_candidates":len(matched),
                "new_or_changed":sum(r["city"]==src["city"] for r in changes)})
        except Exception as e:
            city_status.append({"city":src["city"],"source":key,
                "status":"FAILED_OR_INCOMPLETE","error":type(e).__name__+":"+str(e)[:170],
                "commercial_candidates":0,"baseline_preserved":True})
    _write(root/ALL,allrows);_write(root/NEW,changes)
    temp=path.with_name(path.name+".tmp")
    temp.write_text(json.dumps(state,indent=2),encoding="utf-8")
    temp.replace(path)
    output={"sources_configured":len(city_status),
            "sources_successful":sum(v["status"] in ("BASELINE_COMPLETE","COLLECTED") for v in city_status),
            "source_status":city_status,"commercial_candidates":len(allrows),
            "new_or_changed":len(changes),"all_csv":str(root/ALL),
            "new_csv":str(root/NEW),
            "warning":"Only bounded, complete ArcGIS queries count. Scope text is a screening match. No verified public posting, contractor or buyer implied."}
    (root/AUDIT).write_text(json.dumps(output,indent=2),encoding="utf-8")
    return output
