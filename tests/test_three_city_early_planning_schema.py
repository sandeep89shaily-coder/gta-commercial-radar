"""Official Kitchener metadata has APPLICATION_NO, not APPLICATION_NUMBER.

ObjectID changes after export and must never be used as a case ID.
"""
from gta_additional_city_gis import _parse
def test_kitchener_actual_official_application_number():
    row=_parse("Kitchener","https://services1.arcgis.com/qAo1OsXi67t7XgmS/arcgis/rest/services/Planning_Applications_Active/FeatureServer/0",{
        "OBJECTID":205,"APPLICATION_NO":"ZBA-26-018",
        "DESCRIPTION":"Commercial warehouse redevelopment",
        "ADDRESS":"100 Example Street","PUBLIC_STATUS_DESC":"Under review",
        "INDATE":1793654400000})
    assert row is not None
    assert row["application_id"]=="ZBA-26-018"
    assert row["source_record_date"]==""
    assert row["date_basis"]=="NO_VERIFIED_APPLICATION_POSTING_DATE"
def test_kitchener_objectid_never_becomes_application_number():
    row=_parse("Kitchener","https://example.ca/layer",{
       "OBJECTID":205,"DESCRIPTION":"Commercial warehouse"})
    assert row is None
