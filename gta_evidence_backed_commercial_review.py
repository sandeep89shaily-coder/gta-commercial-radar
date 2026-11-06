"""Source-backed regional opportunity review; never equate first-observed with published."""
import csv
import datetime as dt
import json
import re
from pathlib import Path

INPUTS={
 "REGIONAL_PROJECT":"GTA_RADAR_REGIONAL_PROJECT_DETAILS.csv",
 "REGIONAL_DOCUMENT":"GTA_RADAR_REGIONAL_DOCUMENT_EVIDENCE.csv",
 "CAPITAL_PIPELINE":"GTA_RADAR_TORONTO_CAPITAL_PIPELINE.csv",
 "MUNICIPAL_APPLICATION":"GTA_RADAR_MUNICIPAL_OFFICIAL_APPLICATIONS.csv"}
OUTPUT="GTA_RADAR_EVIDENCE_BACKED_COMMERCIAL_REVIEW.csv"
WATCH="GTA_RADAR_EVIDENCE_BACKED_PROJECT_WATCHLIST.csv"
STATUS="GTA_RADAR_EVIDENCE_BACKED_REVIEW_STATUS.json"
FIELDS=("classification","source_type","project_id","city_or_region","project_name",
 "work_scope","owner_or_division","stage","budget_hint","target_sourcing_year",
 "source_date","date_basis","observation","source_url","document_url",
 "review_reason","required_checks")
CLOSED=re.compile(r"\b(?:awarded|tender awarded|contract awarded|completed|cancelled|withdrawn|refused|closed)\b",re.I)
CONSTRUCTION=re.compile(r"\b(?:under construction|construction (?:begins|began|started)|work (?:has )?begun)\b",re.I)
def _read(p):
 if not p.is_file():return []
 with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def _write(p,rows):
 with p.open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=FIELDS,extrasaction="ignore");w.writeheader()
  for r in rows:
   w.writerow({k:("'"+v if isinstance(v,str) and v.startswith(("=","+","-","@"))
               else v) for k,v in r.items() if k in FIELDS})
def _value(row,*fields):
 return next((row[k] for k in fields if row.get(k)),"")
def _to_row(kind,r):
 if kind=="CAPITAL_PIPELINE":
  return dict(source_type=kind,project_id=r.get("project_id",""),
    city_or_region="Toronto",project_name=r.get("project_name_contract",""),
    work_scope=r.get("scope_of_work",""),owner_or_division=r.get("project_owner_division",""),
    stage=r.get("procurement_status",""),budget_hint=r.get("estimated_range",""),
    target_sourcing_year=r.get("target_sourcing_year",""),
    source_date=r.get("source_publication_date",""),date_basis=r.get("source_date_basis",""),
    source_url=r.get("source_document_url",""),document_url=r.get("source_document_url",""),
    observation=r.get("observation",""),required_checks=r.get("verification_required",""))
 if kind=="MUNICIPAL_APPLICATION":
  return dict(source_type=kind,project_id=r.get("project_id",""),
    city_or_region=r.get("city",""),project_name=r.get("project_title",""),
    work_scope=r.get("scope_of_work",""),owner_or_division=r.get("owner_or_applicant",""),
    stage=r.get("current_status",""),source_url=r.get("source_url",""),
    source_date=r.get("source_publication_date",""),date_basis=r.get("source_date_basis",""),
    observation=r.get("observation",""),required_checks=r.get("verification_required",""))
 return dict(source_type=kind,project_id=_value(r,"document_id","project_id"),
    city_or_region=r.get("authority",""),project_name=r.get("project_title",""),
    work_scope=r.get("evidence_excerpt",""),owner_or_division=r.get("authority","")+" Region",
    stage=r.get("stage_evidence",""),budget_hint=r.get("budget_evidence",""),
    source_date=r.get("explicit_source_date","") if kind=="REGIONAL_PROJECT" else "",
    date_basis=r.get("source_date_basis",""),source_url=r.get("project_url",""),
    document_url=r.get("document_url",""),
    observation=r.get("observation",""),required_checks=r.get("verification_required",""))
def _classify(row,today):
 stage=row.get("stage","")
 text=stage+" "+row.get("work_scope","")[:600]
 if CLOSED.search(stage) or re.search(r"\b(?:contract (?:was )?awarded|tender (?:was )?awarded|(?:project|construction|work) (?:was |has been )?completed)\b",text,re.I):
  return "EXCLUDED_REVIEW","Source record explicitly indicates completed, awarded or closed"
 if CONSTRUCTION.search(text):
  return "WATCH_CONSTRUCTION","Construction already underway; remaining subcontracts unverified"
 if row["source_type"]=="CAPITAL_PIPELINE":
  try:
   if int(row.get("target_sourcing_year",0))<today.year:
    return "WATCH_HISTORICAL","Target sourcing year has passed; current award status unverified"
  except ValueError:pass
  return "WATCH_PLANNED","Planned procurement is not an open tender"
 if row.get("observation")=="INITIAL_BASELINE":
  return "WATCH_BASELINE","Initial observed snapshot, not confirmed first publication"
 if row.get("observation")=="UNCHANGED":
  return "WATCH_UNCHANGED","No detected change since previous collection"
 if row.get("observation") in ("FIRST_OBSERVED","RECORD_CHANGED"):
  return "REVIEW_UNVERIFIED_CHANGE","Official record newly observed or changed, not confirmed new publication"
 return "WATCH_UNVERIFIED","Insufficient change, stage or source evidence"
def run(results,*,today=None):
 root=Path(results);root.mkdir(parents=True,exist_ok=True)
 day=today or dt.date.today()
 candidates=[_to_row(kind,r) for kind,name in INPUTS.items() for r in _read(root/name)]
 review=[];watch=[];excluded=0;seen=set()
 for row in candidates:
  key=(row["source_type"],row.get("project_id",""))
  if not key[1] or key in seen:continue
  seen.add(key)
  classification,reason=_classify(row,day)
  row.update(classification=classification,review_reason=reason)
  if classification=="EXCLUDED_REVIEW":excluded+=1
  elif classification.startswith("REVIEW_"):review.append(row)
  else:watch.append(row)
 key=lambda r:(r.get("city_or_region",""),r.get("project_name",""))
 review.sort(key=key);watch.sort(key=key)
 _write(root/OUTPUT,review);_write(root/WATCH,watch)
 result={"source_records":len(candidates),"review_candidates":len(review),
   "watchlist_records":len(watch),"excluded_source_explicit":excluded,
   "verified_open_tenders":0,"verified_new_publications":0,
   "warning":"Planned, baseline, under-construction and past-target-year records are separate watchlist items. Award and new-publication verification requires current primary tender evidence."}
 (root/STATUS).write_text(json.dumps(result,indent=2),encoding="utf-8")
 return result
