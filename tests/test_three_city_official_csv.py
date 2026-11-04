import csv,json
from gta_three_city_official_csv import run

def put(folder,name,head,rows):
 path=folder/"official_exports"/name
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=head);w.writeheader();w.writerows(rows)

def test_import_vaughan_and_kitchener_baseline_and_repeat(tmp_path):
 put(tmp_path,"KITCHENER_PLANNING_ACTIVE_OFFICIAL.csv",["APPLICATION_NO","DESCRIPTION","ADDRESS","STATUS"],
   [{"APPLICATION_NO":"ZBA-26-018","DESCRIPTION":"New industrial warehouse","ADDRESS":"100 Test Street","STATUS":"Under review"}])
 put(tmp_path,"YORK_REGION_ACTIVE_DEVELOPMENT_OFFICIAL.csv",["MUN_NAME","REG_FILE_NUM","APPL_DESC","ADDRESS","APPL_STATUS"],
   [{"MUN_NAME":"Vaughan","REG_FILE_NUM":"19-OP-2026-009","APPL_DESC":"Logistics distribution project","ADDRESS":"12 Test Road","APPL_STATUS":"Submitted"},
    {"MUN_NAME":"Markham","REG_FILE_NUM":"19-OP-2026-010","APPL_DESC":"Retail store","ADDRESS":"12 Test Street","APPL_STATUS":"Submitted"}])
 result=run(tmp_path,today=__import__("datetime").date(2026,11,3))
 assert result["application_id_rows"]==2
 assert result["new_or_changed"]==0
 assert result["automated_source_recovered"]==0
 again=run(tmp_path,today=__import__("datetime").date(2026,11,4))
 assert again["application_id_rows"]==2 and again["new_or_changed"]==0
 put(tmp_path,"YORK_REGION_ACTIVE_DEVELOPMENT_OFFICIAL.csv",["MUN_NAME","REG_FILE_NUM","APPL_DESC","ADDRESS","APPL_STATUS"],
   [{"MUN_NAME":"Vaughan","REG_FILE_NUM":"19-OP-2026-009","APPL_DESC":"Logistics distribution project","ADDRESS":"12 Test Road","APPL_STATUS":"Under review"}])
 third=run(tmp_path,today=__import__("datetime").date(2026,11,5))
 assert third["new_or_changed"]==1
 assert third["source_authenticity_verified"] is False

def test_reject_wrong_schema_and_no_fabricated_ids(tmp_path):
 put(tmp_path,"KITCHENER_PLANNING_ACTIVE_OFFICIAL.csv",["OBJECTID","DESCRIPTION"],
   [{"OBJECTID":"99","DESCRIPTION":"New warehouse"}])
 result=run(tmp_path)
 assert result["source_status"][0]["status"]=="REJECTED"
 assert result["application_id_rows"]==0

def test_filter_unrelated_york_municipality(tmp_path):
 put(tmp_path,"YORK_REGION_ACTIVE_DEVELOPMENT_OFFICIAL.csv",["MUN_NAME","REG_FILE_NUM","APPL_DESC"],
   [{"MUN_NAME":"Richmond Hill","REG_FILE_NUM":"19-OP-2026-009","APPL_DESC":"Office tower"}])
 result=run(tmp_path)
 assert result["source_status"][1]["status"]=="REJECTED"
 assert result["application_id_rows"]==0
