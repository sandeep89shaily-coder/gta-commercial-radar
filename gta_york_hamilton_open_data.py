"""Four municipal recovery lanes from TWO published open-data services.

York Region active applications -> Vaughan / Markham / Richmond Hill.
Hamilton official development applications -> Hamilton.

No scraping a blocked local GIS site, no proxy/login bypass. Officially
published open-data layer and licence are separate from restricted municipal
map-viewer URLs. Site records are partial *regional review*, not a complete
list of local planning files, and source dates never equal first disclosure.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

YORK="https://services1.arcgis.com/GzvOwaQBbX7KLiuG/ArcGIS/rest/services/Hosted_Active_Development_Application/FeatureServer/0"
HAMILTON="https://services.arcgis.com/rYz782eMbySr2srL/arcgis/rest/services/Development_Applications/FeatureServer/2"
BRANTFORD="https://services.arcgis.com/aji2lCmjXt0KpGzI/ArcGIS/rest/services/Planning_Application_Open_Data_view/FeatureServer/0"
YORK_CITIES=("Vaughan","Markham","Richmond Hill")
ALL_CITIES=(*YORK_CITIES,"Hamilton","Brantford")
MAX_BYTES=2500000
MAX_PAGES=5
PAGE=200
OUTPUT="GTA_RADAR_ADDITIONAL_OFFICIAL_OPEN_DATA.csv"
STATUS="GTA_RADAR_ADDITIONAL_OFFICIAL_OPEN_DATA_STATUS.json"
FIELDS=("city","application_id","address","scope","applicant","stage","category",
        "date","date_basis","source_url","source_lane",
        "source_permission","publication_verified","buyer_verified",
        "open_supplier_package_verified")

def clean(v,cap=1200):
    return " ".join(str(v or "").split())[:cap]

def date(v):
    if isinstance(v,(int,float)) and 1e12<v<1e14:
        try:
            return dt.datetime.fromtimestamp(v/1000,dt.timezone.utc).date().isoformat()
        except (OverflowError,ValueError,OSError):
            return ""
    return ""

def robots_ok(url,*,parser_factory=RobotFileParser):
    parsed=urlsplit(url)
    if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    bot=parser_factory()
    bot.set_url("https://"+parsed.netloc+"/robots.txt")
    try:
        bot.read()
        return bool(bot.can_fetch("GTA-Radar-open-data/1.0",url))
    except (ValueError,OSError):
        return False

def fetch_json(url,*,check_robots=True,opener=urlopen):
    u=urlsplit(url)
    if (u.scheme!="https" or u.hostname not in ("services1.arcgis.com","services.arcgis.com")
            or u.username or u.password):
        raise ValueError("UNAUTHORIZED_OR_NON_OFFICIAL_URL")
    if check_robots and not robots_ok(url):
        raise PermissionError("OPEN_DATA_ENDPOINT_ROBOTS_DENIED")
    request=Request(url,headers={"User-Agent":"GTA-Radar-open-data/1.0"})
    with opener(request,timeout=20) as resp:
        redirect=urlsplit(resp.geturl())
        if redirect.hostname!=u.hostname or redirect.scheme!="https":
            raise PermissionError("CROSS_HOST_REDIRECT_DENIED")
        blob=resp.read(MAX_BYTES+1)
    if len(blob)>MAX_BYTES:raise ValueError("SOURCE_TOO_LARGE")
    data=json.loads(blob.decode("utf-8"))
    if not isinstance(data,dict) or data.get("error"):
        raise ValueError("OFFICIAL_ARCGIS_ERROR")
    return data

def pull(layer,*,getter=fetch_json,check_robots=True,max_pages=MAX_PAGES):
    if layer not in (YORK,HAMILTON,BRANTFORD) or not 1<=max_pages<=MAX_PAGES:
        raise ValueError("UNSUPPORTED_LAYER_OR_CAP")
    seen=set()
    features=[]
    total=0
    complete=False
    for index in range(max_pages):
        params={"f":"json","where":"1=1","outFields":"*",
                "returnGeometry":"false","orderByFields":(
                    "ESRI_OID ASC" if layer==YORK else "OBJECTID ASC"),
                "resultOffset":index*PAGE,"resultRecordCount":PAGE}
        url=layer+"/query?"+urlencode(params)
        result=getter(url,check_robots=check_robots)
        batch=result.get("features")
        if not isinstance(batch,list) or len(batch)>PAGE:
            raise ValueError("MALFORMED_ARCGIS_PAGE")
        for feature in batch:
            attrs=feature.get("attributes") if isinstance(feature,dict) else None
            if not isinstance(attrs,dict):raise ValueError("MALFORMED_ARCGIS_FEATURE")
            oid=attrs.get("ESRI_OID") if layer==YORK else attrs.get("OBJECTID")
            if oid is None:
                # York may supply OBJECTID but unique id is ESRI_OID.
                raise ValueError("NO_OBJECT_ID")
            if oid in seen:raise ValueError("DUPLICATED_PAGINATED_OBJECT_ID")
            seen.add(oid)
            features.append(attrs)
        total+=len(batch)
        if len(batch)<PAGE:
            complete=True
            break
    return features,{"features_examined":total,"pagination_complete":complete,
                     "row_cap":PAGE*max_pages}

def parse_york(attributes):
    rows=[]
    for a in attributes:
        mun=clean(a.get("MUN_NAME"),90).casefold()
        city=next((c for c in YORK_CITIES if c.casefold() in mun),None)
        if city is None:continue
        # Regional file number is a true planning file; GIS record IDs aren't.
        ident=clean(a.get("REG_FILE_NUM") or a.get("EXT_REF_NUM"),120)
        addr=clean(a.get("ADDRESS") or a.get("LOCATION"),230)
        scope=clean(a.get("APPL_DESC") or a.get("APPL_NAME"),1400)
        if not all((ident,addr,scope)):continue
        rows.append({"city":city,"application_id":ident,"address":addr,
          "scope":scope,"applicant":clean(a.get("OWNERSHIP"),220),
          "stage":clean(a.get("APPL_STATUS") or a.get("APPL_STAGE"),120),
          "category":clean(a.get("APPL_TYPE"),120),
          "date":date(a.get("DATE_RECVD")),
          "date_basis":"REGIONAL_RECEIPT_NOT_PUBLICATION",
          "source_url":YORK,
          "source_lane":"YORK_REGION_ACTIVE_APPLICATIONS_OPEN_DATA",
          "source_permission":"YORK_REGION_OPEN_DATA_LICENCE",
          "publication_verified":"False","buyer_verified":"False",
          "open_supplier_package_verified":"False"})
    return rows

def parse_hamilton(attributes):
    rows=[]
    for a in attributes:
        ident=clean(a.get("FILE_NUM"),120)
        addr=clean(a.get("ADDRESS"),230)
        scope=clean(a.get("DESCRIP") or a.get("FILE_TYPE"),1400)
        if not all((ident,addr,scope)):continue
        year=a.get("FILE_YEAR")
        # FILE_YEAR is an application year, not notice date. Never claim
        # the 2026 field means a November 2026 new investment.
        rows.append({"city":"Hamilton","application_id":ident,"address":addr,
          "scope":scope,"applicant":"","stage":"STATUS_NOT_IN_DATASET",
          "category":clean(a.get("FILE_TYPE"),100),"date":"",
          "date_basis":"FILE_YEAR_ONLY_NOT_PUBLICATION",
          "source_url":HAMILTON,
          "source_lane":"HAMILTON_OPEN_DATA_DEVELOPMENT_APPLICATIONS",
          "source_permission":"HAMILTON_OPEN_DATA_COMMERCIAL_LICENCE",
          "publication_verified":"False","buyer_verified":"False",
          "open_supplier_package_verified":"False"})
    return rows

def parse_brantford(attributes):
    rows=[]
    for a in attributes:
        # This is Brantford's *published Open Data view*, not the old
        # CollectorData GIS/editor service. ApplicationNum is the file number;
        # GlobalID and OBJECTID are technical keys, never a substitute.
        ident=clean(a.get("ApplicationNum") or a.get("ApplicationID"),120)
        address=clean(a.get("Address"),230)
        scope=clean(a.get("Description") or a.get("Proposed_use"),1200)
        if not all((ident,address,scope)):continue
        rows.append({"city":"Brantford","application_id":ident,
            "address":address,"scope":scope,
            "applicant":clean(a.get("Applicant"),220),
            "stage":clean(a.get("Status"),120),
            "category":clean(a.get("Category") or a.get("Proposed_use"),120),
            "date":date(a.get("Submitted_date")),
            "date_basis":"APPLICATION_SUBMITTED_NOT_FIRST_NOTICE",
            "source_url":BRANTFORD,
            "source_lane":"BRANTFORD_OFFICIAL_OPEN_DATA_VIEW",
            "source_permission":"BRANTFORD_OPEN_DATA_COMMERCIAL_LICENCE",
            "publication_verified":"False","buyer_verified":"False",
            "open_supplier_package_verified":"False"})
    return rows

def run(results,*,getter=fetch_json):
    root=Path(results)
    root.mkdir(parents=True,exist_ok=True)
    states={}
    rows=[]
    for name,layer in (("York Region",YORK),("Hamilton",HAMILTON),
                       ("Brantford",BRANTFORD)):
        try:
            attrs,diag=pull(layer,getter=getter)
            data=(parse_york(attrs) if layer==YORK else
                  parse_hamilton(attrs) if layer==HAMILTON else
                  parse_brantford(attrs))
            rows.extend(data)
            states[name]={"status":("LIVE_APPLICATION_FILES_RETRIEVED" if data
                      else "FETCHED_WITHOUT_VALID_APPLICATION_FILES"),
                      "validated_file_rows":len(data),**diag}
        except (OSError,PermissionError,ValueError,TypeError,UnicodeError) as exc:
            states[name]={"status":"BLOCKED_OR_FAILED",
                          "validated_file_rows":0,
                          "failure":type(exc).__name__+":"+str(exc)[:180]}
    dedup={}
    for row in rows:
        key=(row["city"].casefold(),row["application_id"].casefold())
        dedup.setdefault(key,row)
    with (root/OUTPUT).open("w",encoding="utf-8-sig",newline="") as fp:
        writer=csv.DictWriter(fp,fieldnames=FIELDS)
        writer.writeheader()
        for row in dedup.values():
            writer.writerow({k:("'" + clean(row.get(k),1500) if clean(row.get(k),1500).startswith(
                 ("=","+","-","@","\\t","\\r")) else clean(row.get(k),1500))
                for k in FIELDS})
    by_city={c:sum(r["city"]==c for r in dedup.values()) for c in ALL_CITIES}
    result={"status":"PUBLISHED_OPEN_DATA_RECOVERY_PARTIAL_UNTIL_LIVE_VERIFIED",
            "source_status":states,"records_by_city":by_city,
            "total_valid_application_files":len(dedup),
            "complete_citywide_application_inventory_verified":False,
            "verified_buyers":0,"verified_first_publications":0,
            "source_caveat":"York Region reviews only applications within regional mandate, not every Vaughan/Markham/Richmond Hill file",
            "csv":OUTPUT}
    (root/STATUS).write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result

if __name__=="__main__":
    arg=argparse.ArgumentParser()
    arg.add_argument("--results",required=True)
    print(json.dumps(run(arg.parse_args().results),indent=2))
