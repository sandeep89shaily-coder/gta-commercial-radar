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
FIELDS=("city","application_id_candidates","project_only_signals",
        "source_state","acceptance","next_action")
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
  records.append({"city":city,"application_id_candidates":count,
    "project_only_signals":signals,
    "source_state":row.get("measured_source_state","NOT_YET_MEASURED"),
    "acceptance":"APPLICATION_CANDIDATES_PRESENT_VERIFY_REPEAT" if count else
                 "BLOCKED_NO_APPLICATION_ID_EXTRACTED",
    "next_action":ACTIONS[city]})
 report={"cities_targeted":3,"cities_with_application_candidates":sum(
     r["application_id_candidates"]>0 for r in records),
   "cities_without_application_candidates":sum(
     r["application_id_candidates"]==0 for r in records),
   "cities_verified_citywide_complete":0,
   "records":records,
   "warning":"A city with extracted application candidates still needs a live repeat test, source dates and coverage verification; no project-only signal becomes an application."}
 (root/STATUS).write_text(json.dumps(report,indent=2),encoding="utf-8")
 with (root/CSV).open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(records)
 return report
