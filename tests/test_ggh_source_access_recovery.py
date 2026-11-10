import csv
import datetime as dt
import json
from gta_ggh_source_access_recovery import run,CSV,MARKDOWN,STATUS,CONTACTS


def _status(tmp_path,name,records):
    (tmp_path/name).write_text(json.dumps({"source_status":records}),encoding="utf-8")


def test_six_verified_contact_routes_and_no_outreach(tmp_path):
    assert set(CONTACTS)=={"Richmond Hill","Newmarket","Innisfil","New Tecumseth","Vaughan","Kitchener"}
    report=run(tmp_path,today=dt.date(2026,11,4))
    assert report["ready_to_send_requests"]==6
    assert report["emails_sent"]==0
    assert report["municipal_replies_received"]==0
    assert report["source_status_read"]=={
        "GTA_RADAR_GGH_OFFICIAL_GIS_STATUS.json":False,
        "GTA_RADAR_GGH_EXPANSION_SOURCE_STATUS.json":False,
        "GTA_RADAR_OFFICIAL_CSV_IMPORT_STATUS.json":False,
        "GTA_RADAR_ADDITIONAL_CITY_GIS_STATUS.json":False,
        "GTA_RADAR_FIVE_CITY_RECOVERY_STATUS.json":False,
    }
    with (tmp_path/CSV).open(encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==6
    assert {r["recipient"] for r in rows}=={
        "planning@richmondhill.ca","planning@newmarket.ca",
        "planningservices@innisfil.ca","planning@newtecumseth.ca",
        "developmentplanning@vaughan.ca","gis@kitchener.ca"}
    assert all("publicly disclosable" in r["email_body"] for r in rows)
    assert all("NO_LIVE_STATUS" in r["automated_status"] for r in rows)
    text=(tmp_path/MARKDOWN).read_text(encoding="utf-8")
    assert "unsent" in text
    assert "New Tecumseth" in text
    assert json.loads((tmp_path/STATUS).read_text())["emails_sent"]==0


def test_only_exact_official_source_statuses_determine_next_action(tmp_path):
    _status(tmp_path,"GTA_RADAR_GGH_OFFICIAL_GIS_STATUS.json",[
        {"city":"Richmond Hill","state":"FAILED","application_id_rows":0,
         "error":"ROBOTS_BLOCKED:ROBOTS_ACCESS_DENIED"},
        {"city":"Newmarket","state":"COLLECTED","application_id_rows":5}])
    _status(tmp_path,"GTA_RADAR_GGH_EXPANSION_SOURCE_STATUS.json",[
        {"city":"Innisfil","state":"NO_APPLICATION_ID_ROWS","application_id_rows":0},
        {"city":"New Tecumseth","state":"NO_APPLICATION_ID_ROWS","application_id_rows":0}])
    _status(tmp_path,"GTA_RADAR_OFFICIAL_CSV_IMPORT_STATUS.json",[
        {"city":"Richmond Hill","status":"ASSISTED_EXPORT_BASELINED"},
        {"city":"New Tecumseth","status":"MISSING_AUTHORIZED_EXPORT"}])
    report=run(tmp_path)
    with (tmp_path/CSV).open(encoding="utf-8-sig",newline="") as f:
        rows={r["municipality"]:r for r in csv.DictReader(f)}
    assert rows["Richmond Hill"]["action"]=="VALIDATE_PUBLISHER_PROVENANCE_AND_REQUEST_RECURRING_FEED"
    assert rows["Newmarket"]["action"]=="VERIFY_COVERAGE_AND_FIRST_PUBLICATION_DATES"
    assert rows["Innisfil"]["action"]=="REVIEW_SOURCE_ACCESS_AND_REQUEST_PERMITTED_EXPORT"
    assert rows["New Tecumseth"]["action"]=="REVIEW_SOURCE_ACCESS_AND_REQUEST_PERMITTED_EXPORT"
    assert "5" in rows["Newmarket"]["automated_status"]
    assert report["emails_sent"]==0


def test_corrupt_diagnostics_still_produce_actionable_request(tmp_path):
    (tmp_path/"GTA_RADAR_GGH_OFFICIAL_GIS_STATUS.json").write_text("{")
    assert run(tmp_path)["ready_to_send_requests"]==6
