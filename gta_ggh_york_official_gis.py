"""Official ArcGIS applications: Richmond Hill and Newmarket, not generic indexes.

Explicit file number fields only. No ArcGIS object IDs as case IDs, no invented
publication dates, no network bypass or citywide-coverage claims. Daily GGH add-on.
"""
from __future__ import annotations
import csv,datetime as dt,hashlib,json,re
from pathlib import Path
from gta_additional_city_gis import _read_json

SOURCES={
 "Richmond Hill":{"url":"https://services5.arcgis.com/cu2HFDk7AqvG7e31/ArcGIS/rest/services/Development_Applications_view_-_Active_Applications/FeatureServer/0",
    "id":"FILENUMBER","address":"ADDRESS","description":"DESCRIPTIONOFAPPLICATION",
    "owner":"OWNER","kind":"APPLICATIONTYPE","status":"STATUS","date":"APPLICATIONRECEIVEDDATE"},
 "Newmarket":{"url":"https://services3.arcgis.com/tSwsWwbYRimLwcCZ/ArcGIS/rest/services/OpenNewmarket_Developments/FeatureServer/23",
    "id":"FILE_NUM","address":"LOCATION","description":"DESCRIPTION",
    "owner":"OWNER","kind":"APP_TYPE","status":"APP_STATUS","land_use":"PROPOSE_LAND_USE"},
}
OUTPUT="GTA_RADAR_GGH_OFFICIAL_GIS_APPLICATIONS.csv"
CHANGES="GTA_RADAR_GGH_OFFICIAL_GIS_NEW_OR_CHANGED.csv"
STATUS="GTA_RADAR_GGH_OFFICIAL_GIS_STATUS.json"
LEDGER="GTA_RADAR_GGH_OFFICIAL_GIS_SEEN.json"
FIELDS=("project_id","city","application_id","address","description","applicant",
        "application_type","current_status","proposed_land_use","commercial_fit",
        "official_layer_url","source_record_date","date_basis","observation",
        "first_seen_local","verification_required")
COMMERCIAL=re.compile(r"\b(?:commercial|industrial|manufactur\w*|warehouse|retail|office|"
                     r"medical|institutional|mixed.use|hotel|distribution|logistics|"
                     r"employment|business|data.cent(?:er|re)|storage)\b",re.I)
PAGE=500
MAX_PAGES=12

def _clean(x):return re.sub(r"\s+"," ",str(x or "")).strip()

def _row(city,src,attributes):
    if not isinstance(attributes,dict):return None
    number=_clean(attributes.get(src["id"]))
    # Require a genuine published application identifier. Never use OBJECTID
    # or building address, and avoid treating an empty/preapplication status as a case.
    if not number or len(number)>130 or not any(c.isdigit() for c in number):
        return None
    address=_clean(attributes.get(src["address"]))[:240]
    description=_clean(attributes.get(src["description"]))[:850]
    owner=_clean(attributes.get(src["owner"]))[:180]
    kind=_clean(attributes.get(src["kind"]))[:140]
    status=_clean(attributes.get(src["status"]))[:140]
    land_use=_clean(attributes.get(src.get("land_use","")))[:140]
    if not address and not description:return None
    identity="GGH_GIS:"+city.upper().replace(" ","_")+":"+re.sub(r"\s+","",number.upper())
    fit="COMMERCIAL_TEXT_MATCH_REVIEW" if COMMERCIAL.search(" ".join((description,kind,land_use))) else "UNCLASSIFIED_REVIEW"
    return {"project_id":identity,"city":city,"application_id":number,
            "address":address,"description":description,"applicant":owner,
            "application_type":kind,"current_status":status,
            "proposed_land_use":land_use,"commercial_fit":fit,
            "official_layer_url":src["url"],"source_record_date":"",
            "date_basis":"NO_VERIFIED_PUBLICATION_DATE",
            "verification_required":"Confirm official application number, proposal details, first publication, project stage, buyer and packages"}

def _collect(src,fetch):
    url=src["url"]
    metadata=fetch(url,{"f":"json"})
    names={str(x.get("name")) for x in metadata.get("fields",[]) if isinstance(x,dict)}
    oid=metadata.get("objectIdField") or metadata.get("objectIdFieldName")
    required={src["id"],src["address"],src["description"],src["owner"],
              src["status"],src["kind"]}
    if not required.issubset(names) or not oid or oid not in names:
        raise ValueError("UNVERIFIED_CITY_GIS_SCHEMA:"+",".join(sorted(required-names)))
    rows=[];offset=0;complete=False
    for _ in range(MAX_PAGES):
        data=fetch(url+"/query",{"f":"json","where":"1=1","returnGeometry":"false",
              "outFields":"*","orderByFields":oid+" ASC",
              "resultOffset":str(offset),"resultRecordCount":str(PAGE)})
        features=data.get("features")
        if not isinstance(features,list) or data.get("error"):
            raise ValueError("CITY_GIS_QUERY_FAILED")
        rows.extend(x.get("attributes",{}) for x in features if isinstance(x,dict))
        if len(features)<PAGE:
            complete=True;break
        offset+=len(features)
    if not complete:raise ValueError("INCOMPLETE_CITY_GIS_PAGINATION")
    return rows

def _write(path,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS,extrasaction="ignore");w.writeheader()
        for row in rows:
            w.writerow({k:("'"+v if isinstance(v,str) and v.startswith(("=","+","-","@")) else v)
                        for k,v in row.items() if k in FIELDS})

def run(results,*,today=None,fetcher=None,sources=None):
    root=Path(results);root.mkdir(parents=True,exist_ok=True)
    day=(today or dt.date.today()).isoformat()
    catalog=sources if sources is not None else SOURCES
    state_path=root/LEDGER
    state=json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"schema":1,"seen":{}}
    if state.get("schema")!=1 or not isinstance(state.get("seen"),dict):
        raise ValueError("UNSUPPORTED_GGH_GIS_LEDGER")
    old=state["seen"];updated=dict(old)
    all_rows=[];changes=[];statuses=[]
    for city,src in catalog.items():
        audit={"city":city,"source_url":src["url"],"state":"FAILED",
               "source_features":0,"application_id_rows":0,"commercial_text_matches":0,
               "new_or_changed":0,"source_publication_dates_verified":0}
        try:
            raw=_collect(src,fetcher or _read_json)
            rows={}
            for attributes in raw:
                candidate=_row(city,src,attributes)
                if candidate:rows[candidate["project_id"]]=candidate
            baseline=not any(key.startswith("GGH_GIS:"+city.upper().replace(" ","_")+":") for key in old)
            for candidate in sorted(rows.values(),key=lambda x:x["project_id"]):
                key=candidate["project_id"]
                digest=hashlib.sha256(json.dumps({k:candidate[k] for k in
                    ("address","description","applicant","application_type",
                     "current_status","proposed_land_use")},sort_keys=True).encode()).hexdigest()
                previous=old.get(key)
                observation=("INITIAL_BASELINE" if baseline else
                    "FIRST_OBSERVED" if previous is None else
                    "RECORD_CHANGED" if previous["digest"]!=digest else "UNCHANGED")
                candidate.update(observation=observation,
                                 first_seen_local=previous["first_seen_local"] if previous else day)
                all_rows.append(candidate)
                if observation in ("FIRST_OBSERVED","RECORD_CHANGED"):changes.append(candidate)
                updated[key]={"digest":digest,"first_seen_local":candidate["first_seen_local"]}
            audit.update(state="BASELINE_COMPLETE" if baseline and rows else
                "COLLECTED" if rows else "NO_APPLICATION_ID_ROWS",
                source_features=len(raw),application_id_rows=len(rows),
                commercial_text_matches=sum(r["commercial_fit"]=="COMMERCIAL_TEXT_MATCH_REVIEW"
                       for r in rows.values()),
                new_or_changed=sum(r["city"]==city for r in changes))
        except Exception as exc:
            audit["error"]=type(exc).__name__+":"+str(exc)[:180]
        statuses.append(audit)
    _write(root/OUTPUT,all_rows);_write(root/CHANGES,changes)
    if updated!=old:
        temp=state_path.with_suffix(".tmp")
        temp.write_text(json.dumps({"schema":1,"seen":updated},indent=2),encoding="utf-8")
        temp.replace(state_path)
    result={"cities_configured":len(catalog),
            "cities_with_application_ids":sum(x["application_id_rows"]>0 for x in statuses),
            "application_id_rows":len(all_rows),"new_or_changed":len(changes),
            "verified_fresh_commercial_leads":0,
            "verified_citywide_coverage":0,
            "source_status":statuses,
            "warning":"GIS official case IDs are review candidates; source last-edit or application-received dates are NOT verified publication dates. Initial baseline is historical, not fresh."}
    (root/STATUS).write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result
