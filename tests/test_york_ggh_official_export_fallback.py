import csv
from gta_three_city_official_csv import run

def write(root,name,fields,rows):
    path=root/"official_exports"/name
    path.parent.mkdir(exist_ok=True)
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)

def test_official_csv_fallback_for_two_york_municipalities(tmp_path):
    write(tmp_path,"RICHMOND_HILL_ACTIVE_APPLICATIONS_OFFICIAL.csv",
          ["FILENUMBER","ADDRESS","DESCRIPTIONOFAPPLICATION","OWNER","APPLICATIONTYPE","STATUS","APPLICATIONRECEIVEDDATE"],
          [{"FILENUMBER":"D02-26012","ADDRESS":"123 Test Street",
            "DESCRIPTIONOFAPPLICATION":"Industrial warehouse expansion",
            "OWNER":"ABC","APPLICATIONTYPE":"ZBA","STATUS":"In Process",
            "APPLICATIONRECEIVEDDATE":"2026-06-03"}])
    write(tmp_path,"NEWMARKET_ACTIVE_DEVELOPMENTS_OFFICIAL.csv",
          ["FILE_NUM","LOCATION","DESCRIPTION","OWNER","APP_TYPE","APP_STATUS","PROPOSE_LAND_USE"],
          [{"FILE_NUM":"D14-NP-26-03","LOCATION":"300 Test Blvd",
            "DESCRIPTION":"Manufacturing expansion and logistics warehouse",
            "OWNER":"Company","APP_TYPE":"SPA","APP_STATUS":"Submitted",
            "PROPOSE_LAND_USE":"Industrial"}])
    first=run(tmp_path)
    assert first["application_id_rows"]==2
    assert first["automated_source_recovered"]==0
    assert first["source_authenticity_verified"] is False
    assert first["new_or_changed"]==0
    second=run(tmp_path)
    assert second["new_or_changed"]==0
    by_city={x["city"]:x for x in first["source_status"]}
    assert by_city["Newmarket"]["status"]=="ASSISTED_EXPORT_BASELINED"
    assert by_city["Richmond Hill"]["status"]=="ASSISTED_EXPORT_BASELINED"

def test_wrong_official_export_schema_rejected(tmp_path):
    write(tmp_path,"NEWMARKET_ACTIVE_DEVELOPMENTS_OFFICIAL.csv",
          ["OBJECTID","DESCRIPTION"],[{"OBJECTID":"1000","DESCRIPTION":"Industrial building"}])
    result=run(tmp_path)
    assert result["application_id_rows"]==0
    assert next(x for x in result["source_status"] if x["city"]=="Newmarket")["status"]=="REJECTED"
