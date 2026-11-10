"""Source-role enrichment and permitted-source recovery checks; no live access."""
from __future__ import annotations
import csv
import datetime as dt
import json

from gta_three_city_official_csv import run as import_csv, ALL, STATUS
from gta_ggh_source_access_recovery import run as requests, CSV as REQUESTS


def write_csv(root, name, fields, values):
    folder=root/"official_exports"
    folder.mkdir(parents=True, exist_ok=True)
    with (folder/name).open("w", encoding="utf-8", newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields)
        writer.writeheader()
        writer.writerows(values)


def test_kitchener_named_applicant_owner_and_planner_are_provisional(tmp_path):
    write_csv(tmp_path,"KITCHENER_PLANNING_ACTIVE_OFFICIAL.csv",
        ["APPLICATION_NO","DESCRIPTION","ADDRESS","STATUS","APPLICANT","PROPERTY_OWNER","ISSUED_BY"],
        [{"APPLICATION_NO":"ZBA-26-018","DESCRIPTION":"New industrial warehouse",
          "ADDRESS":"100 Example Street","STATUS":"Under review",
          "APPLICANT":"Industrial Planning Applicant Ltd",
          "PROPERTY_OWNER":"Factory Holdings Ltd",
          "ISSUED_BY":"City Planner One"}])
    result=import_csv(tmp_path,today=dt.date(2026,11,10))
    status=next(x for x in result["source_status"] if x["city"]=="Kitchener")
    assert status["rows_with_named_applicant"]==1
    assert status["rows_with_named_property_owner"]==1
    assert status["rows_with_planning_reviewer"]==1
    assert status["purchaser_verified"]==0
    assert result["automated_source_recovered"]==0
    assert not result["source_authenticity_verified"]
    with (tmp_path/ALL).open(encoding="utf-8-sig",newline="") as fh:
        rows=list(csv.DictReader(fh))
    assert len(rows)==1
    row=rows[0]
    assert row["applicant_name_unverified"]=="Industrial Planning Applicant Ltd"
    assert row["property_owner_unverified"]=="Factory Holdings Ltd"
    assert row["planning_reviewer_unverified"]=="City Planner One"
    assert row["observation"]=="INITIAL_BASELINE"
    assert "NOT_INDEPENDENTLY_AUTHENTICATED" in row["provenance"]
    assert "KITCHENER" in row["role_source_fields"]
    # Missing file or blocked source does not silently produce a verified buyer.
    assert result["purchasing_authorities_verified"]==0


def test_york_region_review_leads_are_not_developers_or_buyers(tmp_path):
    write_csv(tmp_path,"YORK_REGION_ACTIVE_DEVELOPMENT_OFFICIAL.csv",
        ["MUN_NAME","REG_FILE_NUM","APPL_DESC","ADDRESS","LOCALLEAD","REGIONALLEAD","OWNERSHIP"],
        [{"MUN_NAME":"Vaughan","REG_FILE_NUM":"19-OP-2026-009",
          "APPL_DESC":"Commercial factory","ADDRESS":"12 Sample Rd",
          "LOCALLEAD":"Local Planner","REGIONALLEAD":"Regional Planner",
          "OWNERSHIP":"Private"}])
    result=import_csv(tmp_path,today=dt.date(2026,11,10))
    assert result["application_id_rows"]==1
    with (tmp_path/ALL).open(encoding="utf-8-sig",newline="") as fh:
        row=list(csv.DictReader(fh))[0]
    assert row["applicant_name_unverified"]==""
    assert row["property_owner_unverified"]==""
    assert "Local Planner" in row["planning_reviewer_unverified"]
    assert "Regional Planner" in row["planning_reviewer_unverified"]
    assert "NOT_PROJECT_BUYERS" in row["role_source_fields"]


def test_public_source_access_requests_show_blocker_without_auto_promotion(tmp_path):
    (tmp_path/"GTA_RADAR_ADDITIONAL_CITY_GIS_STATUS.json").write_text(json.dumps({
        "source_status":[{"city":"Kitchener","status":"FAILED_OR_INCOMPLETE",
            "commercial_candidates":99,"error":"ROBOTS_BLOCKED"}]}),encoding="utf-8")
    (tmp_path/"GTA_RADAR_FIVE_CITY_RECOVERY_STATUS.json").write_text(json.dumps({
        "source_status":[{"city":"Vaughan","status":"SOURCE_ACCESS_OR_PARSE_BLOCKED",
            "application_id_rows_this_stage":70,
            "automated_source_recovered_this_stage":False}]}),encoding="utf-8")
    (tmp_path/STATUS).write_text(json.dumps({"source_status":[
        {"city":"Kitchener","status":"ASSISTED_EXPORT_BASELINED","application_id_rows":15},
        {"city":"Vaughan","status":"ASSISTED_EXPORT_BASELINED","application_id_rows":18}
    ]}),encoding="utf-8")
    report=requests(tmp_path,today=dt.date(2026,11,10))
    assert report["emails_sent"]==0
    assert report["ready_to_send_requests"]==6
    with (tmp_path/REQUESTS).open(encoding="utf-8-sig",newline="") as fh:
        rows={r["municipality"]:r for r in csv.DictReader(fh)}
    for city in ("Kitchener","Vaughan"):
        assert rows[city]["automated_status"].endswith("extracted_application_ids=0")
        assert rows[city]["action"]=="VALIDATE_PUBLISHER_PROVENANCE_AND_REQUEST_RECURRING_FEED"
        assert "publicly disclosable" in rows[city]["email_body"]
    assert rows["Kitchener"]["recipient"]=="gis@kitchener.ca"
    assert rows["Vaughan"]["recipient"]=="developmentplanning@vaughan.ca"


def test_permitted_live_source_is_still_not_citywide_coverage(tmp_path):
    (tmp_path/"GTA_RADAR_ADDITIONAL_CITY_GIS_STATUS.json").write_text(json.dumps({
        "source_status":[{"city":"Kitchener","status":"COLLECTED",
            "commercial_candidates":2}]}),encoding="utf-8")
    (tmp_path/"GTA_RADAR_FIVE_CITY_RECOVERY_STATUS.json").write_text(json.dumps({
        "source_status":[{"city":"Vaughan","status":"OFFICIAL_NOTICE_COLLECTION",
            "application_id_rows_this_stage":1,
            "automated_source_recovered_this_stage":True}]}),encoding="utf-8")
    requests(tmp_path)
    with (tmp_path/REQUESTS).open(encoding="utf-8-sig",newline="") as fh:
        rows={r["municipality"]:r for r in csv.DictReader(fh)}
    assert "extracted_application_ids=2" in rows["Kitchener"]["automated_status"]
    assert "extracted_application_ids=1" in rows["Vaughan"]["automated_status"]
    assert rows["Kitchener"]["action"]=="VERIFY_COVERAGE_AND_FIRST_PUBLICATION_DATES"
    assert rows["Vaughan"]["action"]=="VERIFY_COVERAGE_AND_FIRST_PUBLICATION_DATES"
