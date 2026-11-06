import json
from gta_five_city_recovery_status import run,OUTPUT

def test_five_city_source_and_assisted_are_not_conflated(tmp_path):
 (tmp_path/"GTA_RADAR_MUNICIPAL_OFFICIAL_APPLICATIONS_STATUS.json").write_text(json.dumps({
  "source_status":[{"city":"Burlington","status":"FAILED","application_id_rows":0},
    {"city":"Vaughan","status":"COLLECTED","application_id_rows":3}]}))
 (tmp_path/"GTA_RADAR_GGH_OFFICIAL_GIS_STATUS.json").write_text(json.dumps({
  "source_status":[{"city":"Richmond Hill","state":"FAILED","application_id_rows":0},
    {"city":"Newmarket","state":"FAILED","application_id_rows":0}]}))
 (tmp_path/"GTA_RADAR_OFFICIAL_CSV_IMPORT_STATUS.json").write_text(json.dumps({
  "source_status":[{"city":"Kitchener","status":"ASSISTED_EXPORT_BASELINED","application_id_rows":9},
   {"city":"Newmarket","status":"ASSISTED_EXPORT_BASELINED","application_id_rows":8}]}))
 summary=run(tmp_path)
 assert summary["cities_targeted"]==5
 assert summary["cities_with_automated_application_candidates"]==1
 assert summary["cities_with_only_assisted_records"]==2
 assert summary["verified_citywide_complete"]==0
 records={r["city"]:r for r in summary["source_status"]}
 assert records["Kitchener"]["automated_application_ids"]==0
 assert records["Kitchener"]["assisted_application_ids"]==9
 assert records["Newmarket"]["assisted_application_ids"]==8
 assert records["Vaughan"]["automated_application_ids"]==3
 assert (tmp_path/OUTPUT).is_file()

def test_five_city_malformed_statuses_fail_closed(tmp_path):
 (tmp_path/"GTA_RADAR_GGH_OFFICIAL_GIS_STATUS.json").write_text("{")
 r=run(tmp_path)
 assert r["cities_with_automated_application_candidates"]==0
 assert r["verified_new_publications"]==0
