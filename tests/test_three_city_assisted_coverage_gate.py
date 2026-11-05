"""Assisted city recovery must not inflate automated municipal coverage."""
import csv
import json
from gta_three_city_recovery_gate import build


def test_assisted_ids_do_not_change_automatic_coverage(tmp_path):
    rows=[{"city":city,"total_source_candidate_rows_not_deduplicated":"0",
           "project_only_signals":"0","measured_source_state":"SOURCE_FETCH_FAILED"}
          for city in ("Burlington","Vaughan","Kitchener")]
    (tmp_path/"GTA_RADAR_BURLINGTON_OFFICIAL_PAGES_STATUS.json").write_text(json.dumps({
        "status":"ASSISTED_PAGES_PROCESSED","application_id_rows":3}),encoding="utf-8")
    (tmp_path/"GTA_RADAR_VAUGHAN_OFFICIAL_NOTICES_STATUS.json").write_text(json.dumps({
        "status":"ASSISTED_OFFICIAL_NOTICE_BASELINED","application_id_rows":2}),encoding="utf-8")
    (tmp_path/"GTA_RADAR_OFFICIAL_CSV_IMPORT_STATUS.json").write_text(json.dumps({
        "source_status":[
            {"city":"Kitchener","status":"ASSISTED_EXPORT_BASELINED","application_id_rows":9},
            {"city":"Vaughan","status":"REJECTED","application_id_rows":100}]}),encoding="utf-8")
    result=build(tmp_path,coverage=rows)
    assert result["cities_with_application_candidates"]==0
    assert result["cities_without_application_candidates"]==3
    assert result["assisted_application_id_rows_not_automatic"]==14
    assert result["cities_verified_citywide_complete"]==0
    by_city={r["city"]:r for r in result["records"]}
    assert by_city["Burlington"]["assisted_application_id_rows"]==3
    assert by_city["Vaughan"]["assisted_application_id_rows"]==2
    assert by_city["Kitchener"]["assisted_application_id_rows"]==9
    with (tmp_path/"GTA_RADAR_THREE_CITY_EARLY_PLANNING_GAPS.csv").open(encoding="utf-8-sig") as fp:
        items=list(csv.DictReader(fp))
    assert len(items)==3
    assert items[0]["assisted_application_id_rows"]=="3"


def test_no_assisted_files_is_not_success(tmp_path):
    rows=[{"city":city,"total_source_candidate_rows_not_deduplicated":"0",
           "project_only_signals":"0"} for city in ("Burlington","Vaughan","Kitchener")]
    result=build(tmp_path,coverage=rows)
    assert result["assisted_application_id_rows_not_automatic"]==0
    assert all(row["acceptance"]=="BLOCKED_NO_APPLICATION_ID_EXTRACTED"
               for row in result["records"])
