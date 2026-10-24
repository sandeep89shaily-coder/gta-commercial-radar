"""Town of Ajax official ArcGIS Apps_Dev planning layers, manual pilot only.

Layer 0: pre-consultation; layer 1: active development applications.
Layer 3 repeats active applications in a second map presentation, so omitted.
The Town's old HTML /bootrest/planningapps/property.html index no longer
contains its former application rows. Direct ArcGIS JSON is publisher-hosted.
"""
from __future__ import annotations
import datetime as dt
import re
from urllib.parse import urlparse

import requests

BASE="https://ajaxmaps.ajax.ca/gisernie/rest/services/Planning/Apps_Dev/MapServer"
LAYERS=(0,1)
NEEDED={"OBJECTID","REF_ID","ADDRESS","DESCRIPTION","STATUS","APPLICANT","SUBMISSION_DATE"}
COMMERCIAL=re.compile(r"\b(?:industrial|warehous\w*|manufactur\w*|hotel|office|retail|"
 r"commercial|factory|logistic\w*|employment|data cent(?:er|re)|distribution)\b",re.I)
RESIDENTIAL=re.compile(r"\b(?:residential|condo|apartments?|townhouses?|dwellings?)\b",re.I)

def get_json(session,url,params=None,post=False):
    if urlparse(url).scheme!="https" or urlparse(url).hostname!="ajaxmaps.ajax.ca":
        raise ValueError("Non-official Ajax ArcGIS host")
    req_kwargs={"timeout":(10,50),"headers":{"User-Agent":"GTA-Radar-Public-AjaxPlanningReview/0.2"}}
    if post:
        result=session.post(url,data=params,**req_kwargs)
    else:
        result=session.get(url,params=params,**req_kwargs)
    result.raise_for_status()
    obj=result.json()
    if not isinstance(obj,dict) or "error" in obj:
        raise RuntimeError("Ajax GIS endpoint refused request or returned invalid JSON")
    return obj

def get_batch(session,layer,ids):
    url=f"{BASE}/{layer}/query"
    params={"objectIds":",".join(map(str,ids)),"outFields":"*",
            "returnGeometry":"false","f":"json"}
    if hasattr(session,"post"):
        try:
            result=get_json(session,url,params,post=True)
            if isinstance(result.get("features"),list) and len(result["features"])==len(ids):
                return result["features"]
        except (requests.RequestException,RuntimeError,ValueError):
            pass
    # GET fallback is deliberately small to avoid 414 URI Too Long errors.
    out=[]
    for start in range(0,len(ids),25):
        chunk=ids[start:start+25]
        data=get_json(session,url,dict(params,objectIds=",".join(map(str,chunk))))
        got=data.get("features")
        if not isinstance(got,list) or len(got)!=len(chunk):
            raise RuntimeError("Ajax ArcGIS incomplete batch; preserve previous snapshot")
        out+=got
    return out

def _date(raw):
    if raw is None or raw=="":
        return ""
    try:
        if isinstance(raw,(float,int)) and raw>10**10:
            parsed=dt.datetime.fromtimestamp(raw/1000,tz=dt.timezone.utc).date()
            if dt.date(1990,1,1)<=parsed<=dt.datetime.now(dt.timezone.utc).date():
                return parsed.isoformat()
        if isinstance(raw,str) and re.fullmatch(r"20\d{2}-[01]\d-[0-3]\d",raw):
            return dt.date.fromisoformat(raw).isoformat()
    except (ValueError,OverflowError,OSError):
        pass
    return ""

def parse_features(layer,features):
    out=[]
    for feature in features:
        a=feature.get("attributes")
        if not isinstance(a,dict):raise RuntimeError("Ajax GIS missing feature attributes")
        if not isinstance(a.get("OBJECTID"),int):
            raise RuntimeError("Ajax GIS feature missing integer OBJECTID")
        oid=a["OBJECTID"]
        title=str(a.get("DESCRIPTION") or a.get("TYPE") or "").strip()[:400]
        address=str(a.get("ADDRESS") or a.get("LOCATION") or "").strip()[:240]
        applicant=str(a.get("APPLICANT") or "").strip()[:200]
        raw_type=str(a.get("TYPE") or "").strip()
        status=str(a.get("STATUS") or "").strip()
        file_id=str(a.get("REF_ID") or a.get("ARN") or "").strip()[:110]
        date=_date(a.get("SUBMISSION_DATE"))
        nonres=a.get("TOTAL_NONRES_SQ")
        if nonres is None:nonres=a.get("SP_NONRES_SQ")
        try:floor=float(nonres or 0)
        except (TypeError,ValueError):floor=0
        both=title+" "+raw_type
        pos=bool(COMMERCIAL.search(both) or floor>0)
        home=bool(RESIDENTIAL.search(both))
        commercial=("MIXED_USE_REVIEW" if pos and home else
                    "POSSIBLE_COMMERCIAL" if pos else
                    "RESIDENTIAL_LIKELY" if home else "USE_UNKNOWN")
        out.append(dict(
            source_id="ajax_planning_properties",
            record_id=f"AJAX-{layer}-{oid}",
            title=(title or "Ajax published planning record")[:400],
            site=address,company=applicant,
            company_role="PUBLISHED_APPLICANT_NOT_VERIFIED_PURCHASER",
            stage=("PRECONSULTATION" if layer==0 else
                   "ACTIVE_PLANNING_APPLICATION")+"_"+(status or "STATUS_UNKNOWN"),
            source_application_date=date,source_date="",
            date_basis="GIS_SUBMISSION_DATE_NOT_PUBLIC_POST_DATE",
            source_url=f"{BASE}/{layer}",
            commercial_fit=commercial,procurement_status="UNKNOWN",
            verification="AJAX_OFFICIAL_GIS_RECORD_NOT_OPEN_TRADE_PROCUREMENT",
            attributes={"layer":layer,"file_number":file_id,
                        "published_status":status,"nonres_floor_area_m2":floor,
                        "raw_use_type":raw_type,
                        "submission_date_is_not_public_posted_date":True}
        ))
    return out

def collect(session,batch_size=400,max_ids=25000):
    records=[]
    ids_by_layer={}
    for layer in LAYERS:
        meta=get_json(session,f"{BASE}/{layer}",{"f":"json"})
        fields={x.get("name") for x in meta.get("fields",[])}
        if not NEEDED.issubset(fields):
            raise RuntimeError(f"Ajax layer {layer} published schema changed")
        result=get_json(session,f"{BASE}/{layer}/query",{
            "where":"1=1","returnIdsOnly":"true","f":"json"})
        original=result.get("objectIds")
        if not isinstance(original,list) or not original:
            raise RuntimeError(f"Ajax layer {layer} returned no ID list; not zero projects")
        ids=[int(x) for x in original]
        if len(ids)!=len(set(ids)) or len(ids)>max_ids:
            raise RuntimeError("Ajax returned duplicated/unbounded OBJECTIDs")
        ids_by_layer[layer]=len(ids)
        for start in range(0,len(ids),batch_size):
            selected=ids[start:start+batch_size]
            batch=get_batch(session,layer,selected)
            if len(batch)!=len(selected):
                raise RuntimeError("Ajax batch incomplete; no state mutation")
            got={v.get("attributes",{}).get("OBJECTID") for v in batch}
            if got!=set(selected):raise RuntimeError("Ajax batch identity mismatch")
            records.extend(parse_features(layer,batch))
    if len(records)!=sum(ids_by_layer.values()):
        raise RuntimeError("Ajax dataset incomplete across source layers")
    return records,ids_by_layer
