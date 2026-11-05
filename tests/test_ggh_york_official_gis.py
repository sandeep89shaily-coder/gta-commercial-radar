import csv
import datetime as dt
from gta_ggh_york_official_gis import SOURCES,_row,_collect,run,OUTPUT,CHANGES


def _metadata(source):
    mandatory=(source["id"],source["address"],source["description"],
               source["owner"],source["kind"],source["status"],"OBJECTID")
    return {"objectIdField":"OBJECTID","fields":[{"name":v} for v in mandatory]}


def _fixture(city):
    if city=="Richmond Hill":
        return {"OBJECTID":919,"FILENUMBER":"D02-26012",
                "ADDRESS":"125 Test Drive","DESCRIPTIONOFAPPLICATION":"New industrial warehouse",
                "OWNER":"Real Applicant Corp","APPLICATIONTYPE":"Zoning Amendment",
                "STATUS":"In Process","APPLICATIONRECEIVEDDATE":"2026-09-01"}
    return {"OBJECTID":333,"FILE_NUM":"D14-NP-26-03",
            "LOCATION":"200 Example Street","DESCRIPTION":"New manufacturing facility and logistics warehouse",
            "OWNER":"Sample Applicant Inc","APP_TYPE":"Site Plan",
            "APP_STATUS":"Pre-Application Submission",
            "PROPOSE_LAND_USE":"Industrial"}


def _fetch(city):
    def fetch(url,params):
        if not url.endswith("/query"):return _metadata(SOURCES[city])
        return {"features":[{"attributes":_fixture(city)}]}
    return fetch


def test_official_number_only_not_object_id():
    city="Richmond Hill";src=SOURCES[city]
    assert _row(city,src,{"OBJECTID":32,"ADDRESS":"123 Main St",
          "DESCRIPTIONOFAPPLICATION":"Industrial warehouse"}) is None
    row=_row(city,src,_fixture(city))
    assert row["application_id"]=="D02-26012"
    assert row["source_record_date"]==""
    assert row["date_basis"]=="NO_VERIFIED_PUBLICATION_DATE"
    assert row["applicant"]=="Real Applicant Corp"


def test_newmarket_prep_application_not_fresh_publication():
    city="Newmarket";row=_row(city,SOURCES[city],_fixture(city))
    assert row["commercial_fit"]=="COMMERCIAL_TEXT_MATCH_REVIEW"
    assert row["current_status"]=="Pre-Application Submission"
    assert row["first_seen_local"] if "first_seen_local" in row else True


def test_pagination_schema_gate():
    city="Newmarket"
    assert len(_collect(SOURCES[city],_fetch(city)))==1
    import pytest
    with pytest.raises(ValueError,match="UNVERIFIED_CITY_GIS_SCHEMA"):
        _collect(SOURCES[city],lambda url,params:{"fields":[],"objectIdField":"OBJECTID"})


def test_baseline_repeat_changes_two_cities(tmp_path):
    def fetch(url,params):
        city="Newmarket" if "OpenNewmarket" in url else "Richmond Hill"
        return _fetch(city)(url,params)
    first=run(tmp_path,today=dt.date(2026,11,4),fetcher=fetch)
    assert first["cities_with_application_ids"]==2
    assert first["application_id_rows"]==2
    assert first["new_or_changed"]==0
    second=run(tmp_path,today=dt.date(2026,11,5),fetcher=fetch)
    assert second["new_or_changed"]==0
    def changed(url,params):
        city="Newmarket" if "OpenNewmarket" in url else "Richmond Hill"
        if not url.endswith("/query"):return _metadata(SOURCES[city])
        attrs=_fixture(city)
        if city=="Newmarket":attrs["DESCRIPTION"]="New manufacturing facility and additional logistics warehouse"
        return {"features":[{"attributes":attrs}]}
    third=run(tmp_path,today=dt.date(2026,11,6),fetcher=changed)
    assert third["new_or_changed"]==1
    with (tmp_path/CHANGES).open(encoding="utf-8-sig") as f:items=list(csv.DictReader(f))
    assert items[0]["city"]=="Newmarket"
    assert items[0]["first_seen_local"]=="2026-11-04"


def test_failed_city_does_not_destroy_other_city(tmp_path):
    def fetch(url,params):
        if "OpenNewmarket" in url:raise ValueError("ROBOTS_BLOCKED")
        return _fetch("Richmond Hill")(url,params)
    result=run(tmp_path,fetcher=fetch)
    assert result["application_id_rows"]==1
    assert result["cities_with_application_ids"]==1
    assert next(x for x in result["source_status"] if x["city"]=="Newmarket")["state"]=="FAILED"


def test_missing_all_no_false_coverage(tmp_path):
    result=run(tmp_path,fetcher=lambda url,params:{"error":"server refused"})
    assert result["application_id_rows"]==0
    assert result["cities_with_application_ids"]==0
    assert result["verified_citywide_coverage"]==0
