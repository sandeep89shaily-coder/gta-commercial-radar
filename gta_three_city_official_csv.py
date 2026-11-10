"""Evidence-preserving official CSV intake for Kitchener, Vaughan, Richmond Hill, Newmarket.

When automated ArcGIS access is denied by publisher policy, a user may obtain
the publisher's official CSV export through its ordinary download UI and place
it in GTA_RADAR_RESULTS/official_exports. No proxy, redirect trick or scraping.
Imported files are provisional until independently source-verified; never
implicitly promote these as live collectors or new contracts.
"""
from __future__ import annotations

import argparse,csv,datetime as dt,hashlib,json,re
from pathlib import Path

FILES={
 "Kitchener":"KITCHENER_PLANNING_ACTIVE_OFFICIAL.csv",
 "Vaughan":"YORK_REGION_ACTIVE_DEVELOPMENT_OFFICIAL.csv",
 "Richmond Hill":"RICHMOND_HILL_ACTIVE_APPLICATIONS_OFFICIAL.csv",
 "Newmarket":"NEWMARKET_ACTIVE_DEVELOPMENTS_OFFICIAL.csv",
}
SOURCE={
 "Kitchener":"https://www.arcgis.com/home/item.html?id=b7e2f8feda7340eaa5f4dd7b9c4d5ac0",
 "Vaughan":"https://www.arcgis.com/home/item.html?id=d599fcc0898f42ad8b58fd376bcdbf54",
 "Richmond Hill":"https://services5.arcgis.com/cu2HFDk7AqvG7e31/ArcGIS/rest/services/Development_Applications_view_-_Active_Applications/FeatureServer/0",
 "Newmarket":"https://services3.arcgis.com/tSwsWwbYRimLwcCZ/ArcGIS/rest/services/OpenNewmarket_Developments/FeatureServer/23",
}
FIELDS=("project_id","city","application_id","address","description","application_type",
        "current_status","source_record_date","source_record_date_basis","source_url",
        "first_seen_local","observation","changed_fields","commercial_fit",
        "provenance","verification_required","applicant_name_unverified",
        "property_owner_unverified","planning_reviewer_unverified",
        "role_source_fields")
STATUS="GTA_RADAR_OFFICIAL_CSV_IMPORT_STATUS.json"
ALL="GTA_RADAR_OFFICIAL_CSV_IMPORT_APPLICATIONS.csv"
NEW="GTA_RADAR_OFFICIAL_CSV_IMPORT_NEW_OR_CHANGED.csv"
LEDGER="GTA_RADAR_OFFICIAL_CSV_IMPORT_LEDGER.json"
COMMERCIAL=re.compile(r"\b(?:industrial|commercial|warehouse|storage|factory|manufactur\w*|employment|distribution|retail|office|medical|hospital|hotel|mixed.use|institutional|data.cent(?:er|re)|logistics)\b",re.I)
MAX_BYTES=15_000_000
MAX_ROWS=25_000
def _norm(s):
 return re.sub(r"\s+"," ",str(s or "")).strip()
def _upper(d):
 return {str(k or "").strip().upper():_norm(v) for k,v in d.items() if k is not None}
def _csvsafe(s):
 s=_norm(s)
 return "'"+s if s.startswith(("=","+","-","@","\t","\r")) else s
def _load(path):
 if path.stat().st_size>MAX_BYTES:raise ValueError("EXPORT_TOO_LARGE")
 with path.open("r",encoding="utf-8-sig",newline="") as f:
  rd=csv.DictReader(f)
  if not rd.fieldnames:raise ValueError("MISSING_CSV_HEADER")
  headers={x.upper().strip() for x in rd.fieldnames if x}
  rows=[]
  for row in rd:
   if len(rows)>=MAX_ROWS:raise ValueError("EXPORT_ROW_LIMIT")
   rows.append(_upper(row))
 return headers,rows
def _pick(row,*names):
 return next((row[k] for k in names if row.get(k)), "")
def _parse(city,row):
 if city=="Kitchener":
  ident=_pick(row,"APPLICATION_NO")
  desc=_pick(row,"DESCRIPTION","FOLDERNAME","PROPOSED_LANDUSE")
  addr=_pick(row,"ADDRESS")
  kind=_pick(row,"FOLDERTYPE","SUBTYPE")
  state=_pick(row,"PUBLIC_STATUS_DESC","STATUS","AMANDA_STATUS_DESC")
  date=_pick(row,"INDATE")
 elif city=="Richmond Hill":
  ident=_pick(row,"FILENUMBER")
  desc=_pick(row,"DESCRIPTIONOFAPPLICATION")
  addr=_pick(row,"ADDRESS")
  kind=_pick(row,"APPLICATIONTYPE")
  state=_pick(row,"STATUS")
  date=_pick(row,"APPLICATIONRECEIVEDDATE")
 elif city=="Newmarket":
  ident=_pick(row,"FILE_NUM")
  desc=_pick(row,"DESCRIPTION")
  addr=_pick(row,"LOCATION")
  kind=_pick(row,"APP_TYPE","PROPOSE_LAND_USE")
  state=_pick(row,"APP_STATUS")
  date=""
 else:
  if _pick(row,"MUN_NAME").casefold() not in ("vaughan","city of vaughan"):
   return None
  ident=_pick(row,"REG_FILE_NUM","EXT_REF_NUM")
  desc=_pick(row,"APPL_DESC","APPL_NAME","APPLICATION_NAME__C")
  addr=_pick(row,"ADDRESS","LOCATION")
  kind=_pick(row,"APPL_TYPE","APPLICATION_TYPE__C")
  state=_pick(row,"APPL_STATUS","APPL_STAGE","APPLICATION_STATUS__C")
  date=_pick(row,"DATE_RECVD","DATE_RECEIVED__C")
 if not ident or len(ident)>120 or not re.search(r"\d",ident):return None
 if not (desc or addr):return None
 if not (re.search(r"[A-Za-z]",ident) or re.search(r"[/.-]",ident)):
  return None
 # Explicit roles from *public source fields* in a manually supplied export.
 # Never conflate a Kitchener applicant/owner or York Region review lead with
 # the buyer or a contractor for a specific supplier package.
 applicant=_pick(row,"APPLICANT")[:250] if city=="Kitchener" else ""
 owner=_pick(row,"PROPERTY_OWNER")[:250] if city=="Kitchener" else ""
 if city=="Kitchener":
  reviewer=_pick(row,"ISSUED_BY")[:250]
  role_fields="KITCHENER:APPLICANT|PROPERTY_OWNER|ISSUED_BY"
 elif city=="Vaughan":
  local=_pick(row,"LOCALLEAD")[:120]
  regional=_pick(row,"REGIONALLEAD")[:120]
  reviewer="; ".join(x for x in (
      "Local review lead: "+local if local else "",
      "Regional review lead: "+regional if regional else "") if x)
  role_fields="YORK_REGION:LOCALLEAD|REGIONALLEAD_NOT_PROJECT_BUYERS"
 else:
  reviewer=""
  role_fields="NO_ROLE_FIELDS_EXTRACTED"
 proj="OFFICIAL_EXPORT:"+city.upper()+":"+re.sub(r"\s+","",ident.upper())
 return dict(project_id=proj,city=city,application_id=ident,address=addr,
  description=desc[:1000],application_type=kind,current_status=state,
  source_record_date=date,
  source_record_date_basis=("OFFICIAL_APPLICATION_INTAKE_DATE_NOT_FIRST_PUBLICATION" if date else "UNAVAILABLE"),
  source_url=SOURCE[city],
  commercial_fit=("COMMERCIAL_TEXT_MATCH_REVIEW" if COMMERCIAL.search(desc+" "+kind) else "UNCLASSIFIED_REVIEW"),
  provenance="USER_SUPPLIED_OFFICIAL_EXPORT_NOT_INDEPENDENTLY_AUTHENTICATED",
  verification_required="Confirm export origin, exact file ID, named roles, current stage and original publication date; no purchasing authority verified",
  applicant_name_unverified=applicant,property_owner_unverified=owner,
  planning_reviewer_unverified=reviewer,role_source_fields=role_fields)
def _write(path,rows):
 with path.open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=FIELDS,extrasaction="ignore")
  w.writeheader()
  for row in rows:w.writerow({k:_csvsafe(row.get(k,"")) for k in FIELDS})
def run(results,*,today=None):
 root=Path(results);root.mkdir(parents=True,exist_ok=True)
 folder=root/"official_exports";folder.mkdir(parents=True,exist_ok=True)
 today=(today or dt.date.today()).isoformat()
 ledger_path=root/LEDGER
 state=json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {"schema":1,"seen":{}}
 if state.get("schema")!=1:raise ValueError("UNKNOWN_CSV_IMPORT_LEDGER")
 original=state["seen"]
 modified=dict(original)
 allrows=[];changed=[];stats=[]
 for city,name in FILES.items():
  path=folder/name
  status=dict(city=city,source_file=str(path),status="MISSING_AUTHORIZED_EXPORT",
              application_id_rows=0,new_or_changed=0)
  if not path.is_file():
   stats.append(status);continue
  try:
   headers,rows=_load(path)
   required=({"APPLICATION_NO","DESCRIPTION"} if city=="Kitchener" else
       {"FILENUMBER","ADDRESS","DESCRIPTIONOFAPPLICATION"} if city=="Richmond Hill" else
       {"FILE_NUM","LOCATION","DESCRIPTION"} if city=="Newmarket" else
       {"MUN_NAME","REG_FILE_NUM","APPL_DESC"})
   if not required.issubset(headers):
    raise ValueError("WRONG_EXPORT_SCHEMA_OR_MISSING_REQUIRED_FIELDS")
   parsed={}
   for raw in rows:
    obj=_parse(city,raw)
    if obj is not None:
     pid=obj["project_id"]
     if pid in parsed and parsed[pid]!=obj:
      raise ValueError("DUPLICATE_APPLICATION_ID_CONFLICT:"+pid[:60])
     parsed[pid]=obj
   if not parsed:raise ValueError("NO_VALID_APPLICATION_IDS_FOR_CITY")
   for pid,obj in sorted(parsed.items()):
    digest=hashlib.sha256(json.dumps({k:obj[k] for k in
     ("application_id","address","description","application_type","current_status","source_record_date")},
      sort_keys=True).encode()).hexdigest()
    prior=original.get(pid)
    observation=("INITIAL_BASELINE" if not any(k.startswith("OFFICIAL_EXPORT:"+city.upper()+":") for k in original)
      else "FIRST_OBSERVED" if prior is None
      else "RECORD_CHANGED" if prior["digest"]!=digest else "UNCHANGED")
    obj["first_seen_local"]=prior["first_seen_local"] if prior else today
    obj["observation"]=observation
    obj["changed_fields"]="SNAPSHOT_CHANGED_DETAILS_UNVERIFIED" if observation=="RECORD_CHANGED" else ""
    allrows.append(obj)
    if observation in ("FIRST_OBSERVED","RECORD_CHANGED"):changed.append(obj)
    modified[pid]={"digest":digest,"first_seen_local":obj["first_seen_local"]}
   status.update(status="ASSISTED_EXPORT_BASELINED" if not any(k.startswith("OFFICIAL_EXPORT:"+city.upper()+":") for k in original)
                 else "ASSISTED_EXPORT_COLLECTED",
                 source_rows_scanned=len(rows),application_id_rows=len(parsed),
                 new_or_changed=sum(x["city"]==city for x in changed),
                 file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                 rows_with_named_applicant=sum(bool(x.get("applicant_name_unverified"))
                     for x in parsed.values()),
                 rows_with_named_property_owner=sum(bool(x.get("property_owner_unverified"))
                     for x in parsed.values()),
                 rows_with_planning_reviewer=sum(bool(x.get("planning_reviewer_unverified"))
                     for x in parsed.values()),
                 purchaser_verified=0,original_publication_dates_verified=0)
  except (ValueError,UnicodeError,OSError,csv.Error) as err:
   status["status"]="REJECTED"
   status["error"]=type(err).__name__+":"+str(err)[:130]
  stats.append(status)
 _write(root/ALL,allrows)
 _write(root/NEW,changed)
 report={"source_status":stats,"application_id_rows":len(allrows),
    "new_or_changed":len(changed),"automated_source_recovered":0,
    "source_authenticity_verified":False,
    "purchasing_authorities_verified":0,"publication_dates_verified":0,
    "warning":"Official-labelled CSVs placed manually in official_exports; source-role fields are provisional and publisher provenance is not authenticated. No review staff/applicant becomes a purchaser; no city is promoted to verified automatic coverage."}
 (root/STATUS).write_text(json.dumps(report,indent=2),encoding="utf-8")
 if modified!=original:
  temp=ledger_path.with_suffix(".tmp")
  temp.write_text(json.dumps({"schema":1,"seen":modified},indent=2),encoding="utf-8")
  temp.replace(ledger_path)
 return report
if __name__=="__main__":
 parser=argparse.ArgumentParser();parser.add_argument("--output",default="GTA_RADAR_RESULTS")
 args=parser.parse_args();print(json.dumps(run(args.output),indent=2))
