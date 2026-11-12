"""Real producer regression: the source report must say Brampton, not Peel."""
import csv
import json
import sqlite3
import datetime as dt

from opportunity_engine import municipal_city, collect, export


def test_region_to_city_requires_source_or_explicit_address():
    assert municipal_city("Peel", "brampton_building_permits", "238 Glidden Road") == "Brampton"
    assert municipal_city("Peel", "unknown", "238 Glidden Rd, Brampton, ON") == "Brampton"
    assert municipal_city("Peel", "unknown", "Industrial project") == "Peel"
    assert municipal_city("York", "unknown", "Industrial project") == "York"
    assert municipal_city("Peel Region", "peel_flow_projects", "Road widening") == "Peel Region"
    assert municipal_city("Waterloo", "waterloo_city_building_permits", "187 King St") == "Waterloo"
    assert municipal_city("Halton", "oakville_site_plans", "100 Main Street") == "Oakville"


def test_real_daily_export_locality_and_source_dates_not_changed(tmp_path):
    today = dt.date.today().isoformat()
    with sqlite3.connect(tmp_path / "radar.sqlite") as db:
        db.execute("CREATE TABLE records_current (source_id TEXT,record_key TEXT,source_date TEXT,normalized_json TEXT,active INTEGER)")
        db.execute("INSERT INTO records_current VALUES (?,?,?,?,?)", (
            "brampton_building_permits", "26-185633-000-00", today,
            json.dumps({"region":"Peel",
                        "address":"238 Glidden Rd, Brampton, ON, L6W 1H8",
                        "description":"Industrial shell addition",
                        "commercial_relevance":"HIGH"}),1))
    rows, _, _ = collect(tmp_path, today=dt.date.today())
    assert len(rows) == 1
    assert rows[0]["city"] == "Brampton"
    assert rows[0]["event_date"] == today
    assert rows[0]["review_status"] == "UNVERIFIED_NOT_FOR_SALE"
    export(tmp_path, today=dt.date.today())
    with (tmp_path / "opportunities_ALL_REVIEW_ONLY.csv").open(
            encoding="utf-8-sig", newline="") as f:
        output = list(csv.DictReader(f))
    assert output[0]["city"] == "Brampton"
    assert output[0]["source_id"] == "brampton_building_permits"


def test_updated_source_change_uses_same_city_conversion(tmp_path):
    today = dt.datetime.now(dt.timezone.utc).isoformat()
    with sqlite3.connect(tmp_path / "radar.sqlite") as db:
        db.execute("CREATE TABLE records_current (source_id TEXT,record_key TEXT,source_date TEXT,normalized_json TEXT,active INTEGER)")
        db.execute("CREATE TABLE changes (source_id TEXT,record_key TEXT,observed_at TEXT,normalized_json TEXT,change_type TEXT)")
        db.execute("INSERT INTO changes VALUES (?,?,?,?,?)", (
            "brampton_building_permits", "26-185633-000-00", today,
            json.dumps({"region":"Peel","address":"238 Glidden Rd",
                        "description":"Industrial warehouse addition"}),"UPDATED"))
    rows, _, _ = collect(tmp_path, today=dt.date.today())
    changed = [r for r in rows if r["source_group"] == "MUNICIPAL_CHANGE"]
    assert len(changed) == 1
    assert changed[0]["city"] == "Brampton"
    assert changed[0]["event_date_basis"] == "CHANGE_DETECTED_NOT_PERMIT_ISSUED"
