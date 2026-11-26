"""Official Brampton and Mississauga planning source recovery.

Brampton: published Planning Land Use Development layers 9/10/11.
Mississauga: public Site Plan Applications FeatureServer/0.
Each source is independently robot/policy-gated and its licence status is
reported; the Mississauga custom licence is NOT assumed commercial.
Supports only first-party hosted ArcGIS data or explicitly supplied offline
approved export files, without proxying a denied route or login bypass.

No claims of new publications, open supplier packages, citywide completeness,
or developer/agent purchasing authority.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlsplit, urlencode
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from gta_brampton_public_planning import LANE as BRAMPTON_PORTAL, LICENCE as PORTAL_LICENCE
from gta_brampton_public_planning import collect as collect_brampton_portal

BRAMPTON_BASE=("https://services3.arcgis.com/rl7ACuZkiFsmDA2g/arcgis/rest/"
              "services/Planning_Land_Use_Development/FeatureServer")
MISSISSAUGA=("https://services6.arcgis.com/hM5ymMLbxIyWTjn2/ArcGIS/rest/"
             "services/Site_Plan_Applications/FeatureServer/0")
SOURCES={"Brampton_OPA_ZBA":BRAMPTON_BASE+"/9",
         "Brampton_Preconsultation":BRAMPTON_BASE+"/10",
         "Brampton_Site_Plan":BRAMPTON_BASE+"/11",
         "Mississauga_Site_Plan":MISSISSAUGA}
LICENSE={"Brampton_OPA_ZBA":"REVIEW_DATASET_SPECIFIC_REUSE",
         "Brampton_Preconsultation":"CC_BY_4_0_PUBLISHED_DATASET",
         "Brampton_Site_Plan":"CC_BY_4_0_PUBLISHED_DATASET",
         "Mississauga_Site_Plan":"CUSTOM_LICENSE_NOT_VERIFIED"}
OUTPUT="GTA_RADAR_BR_MISS_OPEN_PLANNING_APPLICATIONS.csv"
STATUS="GTA_RADAR_BR_MISS_OPEN_PLANNING_STATUS.json"
PAGE=200
MAX_PAGES=10
MAX_BYTES=3_000_000
FIELDS=("city","application_id","address","scope","project_title","applicant",
        "agent","stage","category","source_date","source_date_basis",
        "source_url","source_lane","licence_status",
        "non_res_gfa","industrial_gfa","office_gfa","retail_gfa",
        "first_publication_verified","buyer_verified","procurement_verified")

def clean(x,limit=1500):
    return " ".join(str(x or "").split())[:limit]

def iso_date(value):
    if isinstance(value,(float,int)) and 10**11<value<10**14:
        try:return dt.datetime.fromtimestamp(value/1000,dt.timezone.utc).date().isoformat()
        except (OSError,OverflowError,ValueError):pass
    return ""

def robots_permit(url):
    p=urlsplit(url)
    if p.scheme!="https" or p.hostname not in ("services3.arcgis.com","services6.arcgis.com"):
        return False
    bot=RobotFileParser()
    bot.set_url("https://"+p.netloc+"/robots.txt")
    try:
        bot.read()
        return bool(bot.can_fetch("GTA-Radar-OfficialOpenData/1.0",url))
    except (OSError,ValueError,UnicodeError):
        return False

def request_json(url,*,check_robots=True,opener=urlopen):
    p=urlsplit(url)
    if p.scheme!="https" or p.hostname not in ("services3.arcgis.com","services6.arcgis.com"):
        raise PermissionError("NON_OFFICIAL_ARCGIS_ORIGIN")
    if p.username or p.password:raise PermissionError("EMBEDDED_CREDENTIALS_REJECTED")
    if check_robots and not robots_permit(url):
        raise PermissionError("SOURCE_ROBOTS_DENIED_OR_UNVERIFIED")
    req=Request(url,headers={"User-Agent":"GTA-Radar-OfficialOpenData/1.0"})
    with opener(req,timeout=18) as resp:
        end=urlsplit(resp.geturl())
        if end.hostname!=p.hostname or end.scheme!="https":
            raise PermissionError("CROSS_HOST_REDIRECT_REJECTED")
        raw=resp.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError("ARCGIS_RESPONSE_TOO_LARGE")
    data=json.loads(raw.decode("utf-8"))
    if not isinstance(data,dict) or data.get("error"):
        raise ValueError("ARCGIS_ERROR_OR_INVALID_JSON")
    return data

def query_lane(lane,*,getter=request_json,max_pages=MAX_PAGES):
    if lane not in SOURCES or not 1<=max_pages<=MAX_PAGES:
        raise ValueError("UNSUPPORTED_SOURCE_OR_PAGE_CAP")
    source=SOURCES[lane]
    meta=getter(source+"?f=json")
    oid=meta.get("objectIdField")
    names={f.get("name") for f in meta.get("fields",[]) if isinstance(f,dict)}
    if not isinstance(oid,str) or oid not in names:
        raise ValueError("NO_VALID_PUBLISHER_OBJECTID_FIELD")
    seen=set()
    records=[]
    complete=False
    for index in range(max_pages):
        query=source+"/query?"+urlencode({"f":"json","where":"1=1",
            "outFields":"*","returnGeometry":"false",
            "orderByFields":oid+" ASC",
            "resultOffset":index*PAGE,"resultRecordCount":PAGE})
        payload=getter(query)
        batch=payload.get("features")
        if not isinstance(batch,list) or len(batch)>PAGE:
            raise ValueError("ARCGIS_INVALID_FEATURE_PAGE")
        for feature in batch:
            attrs=feature.get("attributes") if isinstance(feature,dict) else None
            if not isinstance(attrs,dict) or attrs.get(oid) is None:
                raise ValueError("ARCGIS_MISSING_ID")
            if attrs[oid] in seen:raise ValueError("ARCGIS_DUPLICATE_OBJECTID")
            seen.add(attrs[oid])
            record=normalize(lane,attrs)
            if record is not None:records.append(record)
        if len(batch)<PAGE:
            complete=True
            break
    return records,{"features_examined":len(seen),
                    "valid_files":len(records),
                    "pagination_complete":complete,
                    "row_cap":PAGE*max_pages,
                    "schema_objectid":oid}

def normalize(lane,a):
    if lane not in SOURCES:raise ValueError("INVALID_LANE")
    br=lane.startswith("Brampton")
    if br:
        ident=clean(a.get("FILE_NUMBER"),120)
        address=clean(a.get("LOCATION"),260)
        scope=clean(a.get("PROPOSAL_DESCRIPTION") or a.get("DESCRIPTION"),1500)
        title=clean(a.get("APPLICATION_TITLE"),250)
        applicant=clean(a.get("APPLICANT_COMPANY"),220)
        agent=clean(a.get("AGENT_COMPANY"),220)
        stage=clean(a.get("STATUS"),160)
        category=clean(a.get("APPLICATION_TYPE"),130)
        received=iso_date(a.get("DATE_RECEIVED"))
        date_basis="APPLICATION_RECEIVED_NOT_FIRST_PUBLICATION"
        areas=("","","","")
    else:
        ident=clean(a.get("APP_FILE_NO"),120)
        address=clean(a.get("SITE_ADDRESS") or a.get("GENERAL_LOCATION"),260)
        scope=clean(a.get("DESCRIPTION") or a.get("TYPE_DESC"),1500)
        title=clean(a.get("TYPE_DESC"),250)
        applicant=clean(a.get("APPLICANT"),220)
        agent=""
        stage=clean(a.get("SIMPLE_STATUS") or a.get("STATUS"),160)
        category=clean(a.get("CATEGORY_DESC"),130)
        received=iso_date(a.get("APPLICATION_DATE"))
        date_basis="APPLICATION_DATE_NOT_FIRST_PUBLICATION"
        areas=tuple(clean(a.get(key),40) for key in
            ("TOTAL_NON_RES_GFA","ICI_INDUST","ICI_OFFICE","ICI_RETAIL"))
    if not ident or not address or not (scope or title):
        return None
    return {"city":"Brampton" if br else "Mississauga",
        "application_id":ident,"address":address,"scope":scope or title,
        "project_title":title,"applicant":applicant,"agent":agent,
        "stage":stage,"category":category,"source_date":received,
        "source_date_basis":date_basis,"source_url":SOURCES[lane],
        "source_lane":lane,"licence_status":LICENSE[lane],
        "non_res_gfa":areas[0],"industrial_gfa":areas[1],
        "office_gfa":areas[2],"retail_gfa":areas[3],
        "first_publication_verified":"False","buyer_verified":"False",
        "procurement_verified":"False"}

def run(results, *, getter=request_json, portal_collector=None):
    root=Path(results)
    root.mkdir(parents=True,exist_ok=True)
    states={};records=[]
    for lane in SOURCES:
        try:
            rows,detail=query_lane(lane,getter=getter)
            states[lane]={"status":"LIVE_VALID_APPLICATION_FILES_PARTIAL" if rows
                else "FETCHED_ZERO_VALID_APPLICATION_FILES",**detail,
                "licence_status":LICENSE[lane]}
            records.extend(rows)
        except (OSError,PermissionError,ValueError,TypeError,KeyError,UnicodeError) as exc:
            states[lane]={"status":"BLOCKED_OR_FAILED","valid_files":0,
                "licence_status":LICENSE[lane],
                "failure":type(exc).__name__+":"+str(exc)[:170]}
    if portal_collector is None and getter is request_json:
        portal_collector = collect_brampton_portal
    if portal_collector is not None:
        try:
            rows, detail = portal_collector()
            records.extend(rows)
            states[BRAMPTON_PORTAL] = {
                "status": ("LIVE_VALID_APPLICATION_FILES_PARTIAL" if rows
                           else "FETCHED_ZERO_VALID_APPLICATION_FILES"),
                "valid_files": len(rows), "licence_status": PORTAL_LICENCE, **detail,
            }
        except (OSError, ValueError) as exc:
            states[BRAMPTON_PORTAL] = {
                "status": "BLOCKED_OR_FAILED", "valid_files": 0,
                "licence_status": PORTAL_LICENCE,
                "failure": f"{type(exc).__name__}:{exc}"[:190],
            }
    # Multiple Brampton land-use layers may carry identical FILE_NUMBER.
    # Keep the richer record; retain individual lane coverage in the manifest.
    unique={}
    for row in records:
        key=(row["city"].casefold(),"".join(c for c in row["application_id"].upper() if c.isalnum()))
        if not key[1]:continue
        old=unique.get(key)
        if old is None or len(row["scope"])>len(old["scope"]):
            unique[key]=row
    with (root/OUTPUT).open("w",encoding="utf-8-sig",newline="") as fp:
        writer=csv.DictWriter(fp,fieldnames=FIELDS)
        writer.writeheader()
        for row in unique.values():
            writer.writerow({key:("'"+str(row.get(key) or "")
                if str(row.get(key) or "").lstrip().startswith(("=","+","-","@","\t","\r"))
                else str(row.get(key) or "")) for key in FIELDS})
    result={"status":"BRAMPTON_MISSISSAUGA_OFFICIAL_DATA_ATTEMPT_AUDITED",
        "source_status":states,
        "unique_application_files":len(unique),
        "by_city":{city:sum(x["city"]==city for x in unique.values())
                   for city in ("Brampton","Mississauga")},
        "source_count":len(states),"citywide_coverage_verified":False,
        "mississauga_custom_licence_reuse_authorized":False,
        "qualified_buyers":0,"verified_new_publications":0,
        "supplier_contracts_verified":0,"paid_ai_calls":0,
        "output_csv":OUTPUT}
    (root/STATUS).write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--results",required=True)
    print(json.dumps(run(p.parse_args().results),indent=2))
