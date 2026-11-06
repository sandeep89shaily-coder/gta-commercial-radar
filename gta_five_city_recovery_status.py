"""Five-city application coverage readiness: automated vs assisted, never conflated."""
import csv
import json
from pathlib import Path

CITIES=("Burlington","Vaughan","Kitchener","Richmond Hill","Newmarket")
OUTPUT="GTA_RADAR_FIVE_CITY_APPLICATION_RECOVERY.csv"
STATUS="GTA_RADAR_FIVE_CITY_APPLICATION_RECOVERY_STATUS.json"
FIELDS=("city","automated_application_ids","assisted_application_ids",
        "automatic_access_status","assisted_import_status","coverage_claim",
        "verified_first_publication","verified_citywide_complete",
        "next_permitted_action")
ACTIONS={
 "Burlington":"Official city project pages or authorized saved city pages with file number; do not bypass blocked HTTP access",
 "Vaughan":"Official public notices/authorized saved notices or city-approved structured planning export",
 "Kitchener":"Official Planning_Applications_Active GIS if permitted; alternatively published APPLICATION_NO CSV from GeoHub export",
 "Richmond Hill":"Publisher-approved Active Development Applications CSV with FILENUMBER from city portal",
 "Newmarket":"Publisher-approved OpenNewmarket development CSV with FILE_NUM from town portal",
}
def _read(p):
 try:
  data=json.loads(p.read_text(encoding="utf-8"))
  return data if isinstance(data,dict) else {}
 except (OSError,ValueError):return {}
def _record(report,city):
 return next((r for r in report.get("source_status",[]) if r.get("city")==city),{})
def run(results):
 root=Path(results);root.mkdir(parents=True,exist_ok=True)
 public=_read(root/"GTA_RADAR_MUNICIPAL_OFFICIAL_APPLICATIONS_STATUS.json")
 york=_read(root/"GTA_RADAR_GGH_OFFICIAL_GIS_STATUS.json")
 other=_read(root/"GTA_RADAR_ADDITIONAL_CITY_GIS_STATUS.json")
 assisted=_read(root/"GTA_RADAR_OFFICIAL_CSV_IMPORT_STATUS.json")
 saved_b=_read(root/"GTA_RADAR_BURLINGTON_OFFICIAL_PAGES_STATUS.json")
 saved_v=_read(root/"GTA_RADAR_VAUGHAN_OFFICIAL_NOTICES_STATUS.json")
 diagnostics=[]
 for city in CITIES:
  if city in ("Burlington","Vaughan"):
   auto=_record(public,city)
  elif city in ("Richmond Hill","Newmarket"):
   auto=_record(york,city)
  else:
   # Kitchener resides in the existing Hamilton/Kitchener GIS collector.
   auto=next((r for r in other.get("source_status",[]) if
      r.get("city")=="Kitchener"),{})
  count=int(auto.get("application_id_rows",auto.get("application_candidates",
         auto.get("commercial_candidates",0))) or 0)
  assisted_record=_record(assisted,city)
  saved=saved_b if city=="Burlington" else saved_v if city=="Vaughan" else {}
  extra=int(saved.get("application_id_rows",0) or 0)
  if str(assisted_record.get("status","")).startswith("ASSISTED_EXPORT"):
   extra+=int(assisted_record.get("application_id_rows",0) or 0)
  state=str(auto.get("status",auto.get("state","NOT_YET_MEASURED")))
  # No status counts as citywide completeness, even after extraction succeeds.
  diagnostics.append(dict(city=city,automated_application_ids=count,
    assisted_application_ids=extra,automatic_access_status=state,
    assisted_import_status=str(assisted_record.get("status",saved.get("status","NO_ASSISTED_EXPORT"))),
    coverage_claim="PARTIAL_OFFICIAL_RECORD_CANDIDATES_ONLY" if count else "NOT_RECOVERED_AUTOMATICALLY",
    verified_first_publication=False,verified_citywide_complete=False,
    next_permitted_action=ACTIONS[city]))
 with (root/OUTPUT).open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(diagnostics)
 summary={"cities_targeted":len(CITIES),
          "cities_with_automated_application_candidates":sum(x["automated_application_ids"]>0 for x in diagnostics),
          "cities_with_only_assisted_records":sum(x["assisted_application_ids"]>0 and x["automated_application_ids"]==0 for x in diagnostics),
          "verified_citywide_complete":0,"verified_new_publications":0,
          "source_status":diagnostics,
          "warning":"Publisher-level HTTP access restrictions are not bypassed. Manual exports and officially displayed numbers are different from validated automatic, complete or newly published municipal coverage."}
 (root/STATUS).write_text(json.dumps(summary,indent=2),encoding="utf-8")
 return summary
