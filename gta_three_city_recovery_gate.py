"""P0 early-planning readiness for Burlington Vaughan Kitchener only.

Consumes city coverage output rather than incorrectly counting project-only
signals or metadata/landing pages as application-level collection success.
"""
from __future__ import annotations
import csv,json
from pathlib import Path

CITIES=("Burlington","Vaughan","Kitchener")
STATUS="GTA_RADAR_THREE_CITY_EARLY_PLANNING_GAPS.json"
CSV="GTA_RADAR_THREE_CITY_EARLY_PLANNING_GAPS.csv"
FIELDS=("city","application_id_candidates","project_only_signals","gis_project_only_signals",
        "source_state","assisted_application_id_rows","assisted_source_status","acceptance","next_action")
ACTIONS={
 "Burlington":"Exact application number must come from an authorized official notice or file-level export; both public COB Development_Apps GIS layers lack application-ID fields",
 "Vaughan":"Request a permitted public-notice feed / structured PLANit extract; public-notice HTML collection is robots-restricted",
 "Kitchener":"Request a permitted CSV or API export containing APPLICATION_NO; source metadata alone is not an application feed"
}
def build(results,coverage=None):
 root=Path(results);root.mkdir(parents=True,exist_ok=True)
 if coverage is None:
  file=root/"GTA_RADAR_CITY_COVERAGE_AUDIT.csv"
  with file.open(encoding="utf-8-sig",newline="") as f:
   coverage=list(csv.DictReader(f))
 seen={r.get("city"):r for r in coverage}
 records=[]
 for city in CITIES:
  row=seen.get(city,{})
  count=int(row.get("total_source_candidate_rows_not_deduplicated",0) or 0)
  signals=int(row.get("project_only_signals",0) or 0)
  gis_signals=0
  if city=="Burlington":
   status_path=root/"GTA_RADAR_BURLINGTON_GIS_STATUS.json"
   if status_path.is_file():
    try:
     status=json.loads(status_path.read_text(encoding="utf-8"))
     if status.get("status") in ("BASELINE_COMPLETE","COLLECTED"):
      gis_signals=int(status.get("project_only_signals",0) or 0)
    except (ValueError,OSError,TypeError):
     gis_signals=0
  assisted=0
  assisted_states=[]
  # Assisted snapshots are not evidence of permitted live retrieval. Show
  # them alongside the strict automatic coverage gate, never inside it.
  assisted_paths={
   "Burlington":["GTA_RADAR_BURLINGTON_OFFICIAL_PAGES_STATUS.json"],
   "Vaughan":["GTA_RADAR_VAUGHAN_OFFICIAL_NOTICES_STATUS.json"],
   "Kitchener":[],
  }
  for name in assisted_paths[city]:
   p=root/name
   if not p.is_file():
    assisted_states.append("NOT_IMPORTED")
    continue
   try:
    data=json.loads(p.read_text(encoding="utf-8"))
    assisted+=int(data.get("application_id_rows",0) or 0) if data.get("status") not in ("REJECTED","MISSING_SAVED_OFFICIAL_PAGES","MISSING_SAVED_PUBLIC_NOTICES") else 0
    assisted_states.append(str(data.get("status","UNKNOWN")))
   except (ValueError,OSError,TypeError):
    assisted_states.append("INVALID_STATUS")
  if city in ("Kitchener","Vaughan"):
   p=root/"GTA_RADAR_OFFICIAL_CSV_IMPORT_STATUS.json"
   if p.is_file():
    try:
     data=json.loads(p.read_text(encoding="utf-8"))
     for entry in data.get("source_status",[]):
      if entry.get("city")==city:
       assisted_states.append("CSV:"+str(entry.get("status","UNKNOWN")))
       if str(entry.get("status","")).startswith("ASSISTED_EXPORT"):
        assisted+=int(entry.get("application_id_rows",0) or 0)
    except (ValueError,OSError,TypeError):
     assisted_states.append("INVALID_CSV_STATUS")
  assisted_label=" | ".join(assisted_states) if assisted_states else "NOT_IMPORTED"
  records.append({"city":city,"application_id_candidates":count,
    "project_only_signals":signals+gis_signals,"gis_project_only_signals":gis_signals,
    "source_state":row.get("measured_source_state","NOT_YET_MEASURED"),
    "assisted_application_id_rows":assisted,"assisted_source_status":assisted_label,
    "acceptance":"APPLICATION_CANDIDATES_PRESENT_VERIFY_REPEAT" if count else
                 "BLOCKED_NO_APPLICATION_ID_EXTRACTED",
    "next_action":ACTIONS[city]})
 report={"cities_targeted":3,"cities_with_application_candidates":sum(
     r["application_id_candidates"]>0 for r in records),
   "cities_without_application_candidates":sum(
     r["application_id_candidates"]==0 for r in records),
   "cities_verified_citywide_complete":0,
   "assisted_application_id_rows_not_automatic":sum(r["assisted_application_id_rows"] for r in records),
   "records":records,
   "warning":"A city with extracted application candidates still needs a live repeat test, source dates and coverage verification; assisted imports are separate from automatic coverage; no project-only signal becomes an application."}
 (root/STATUS).write_text(json.dumps(report,indent=2),encoding="utf-8")
 with (root/CSV).open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(records)
 return report
