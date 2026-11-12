"""Measured municipal coverage acceptance; no configured index counts as lead."""
from __future__ import annotations

import csv
import json

from gta_municipal_recovery_scorecard import build, OUTPUT, STATUS
from gta_early_applications import SOURCES


def _json(root, filename, payload):
    (root / filename).write_text(json.dumps(payload), encoding="utf-8")


def _csv(root, filename, rows):
    with (root / filename).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _rows(root):
    with (root / OUTPUT).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_scorecard_explicitly_marks_access_failures_and_buyer_unknown(tmp_path):
    _json(tmp_path, "GTA_RADAR_COLLECTION_ACCEPTANCE.json", {
        "per_city": [
            {"city": "Toronto", "application_files": 1261,
             "project_only_signals": 0, "source_failures": 1,
             "source_notes": "TORONTO_AIC:ROBOTS_REDIRECT_LOOP"},
            {"city": "Brampton", "application_files": 2,
             "project_only_signals": 0, "source_failures": 2,
             "source_notes": "BRAMPTON_OPA_ZBA:ROBOTS_ACCESS_DENIED"},
            {"city": "Vaughan", "application_files": 0,
             "project_only_signals": 0, "source_failures": 1,
             "source_notes": "HTTP_403_OR_REDIRECT"},
            {"city": "Mississauga", "application_files": 30,
             "project_only_signals": 0, "source_failures": 0},
        ],
    })
    _json(tmp_path, "GTA_RADAR_CITY_COVERAGE_STATUS.json", {
        "city_status": [
            {"city": "Toronto", "measured_source_state": "APPLICATION_CANDIDATES_EXTRACTED_NOT_CITYWIDE_COMPLETE"},
            {"city": "Brampton", "measured_source_state": "APPLICATION_CANDIDATES_EXTRACTED_NOT_CITYWIDE_COMPLETE"},
        ],
    })
    _csv(tmp_path, "GTA_RADAR_QUALIFIED_OPPORTUNITY_SHORTLIST.csv", [
        {"city": "Peel", "address": "238 Glidden Rd, Brampton, ON", "sale_ready": "YES"},
        {"city": "Mississauga", "address": "8 Falconer Dr", "sale_ready": "NO"},
    ])
    _csv(tmp_path, "GTA_RADAR_PRIVATE_TOP_10.csv", [
        {"city": "Brampton", "address": "238 Glidden Rd, Brampton, ON"},
        {"city": "Toronto", "address": "135 Vanderhoof Ave"},
    ])
    _csv(tmp_path, "GTA_RADAR_PRIVATE_DEVELOPMENT_REVIEW.csv", [
        {"city": "Brampton", "address": "238 Glidden Rd, Brampton, ON"},
        {"city": "Mississauga", "address": "8 Falconer Dr"},
    ])
    _json(tmp_path, "GTA_RADAR_NEXT_FOUR_MUNICIPALITIES_STATUS.json", {
        "source_status": [
            {"city": "Ajax", "status": "INDEX_ONLY_NO_PROJECT_APPLICATION_RECORDS",
             "application_id_rows": 0},
            {"city": "Whitby", "status": "FAILED",
             "error": "ROBOTS_DENIED", "application_id_rows": 0},
        ],
    })
    data = build(tmp_path)
    rows = _rows(tmp_path)
    assert len(rows) == len(SOURCES) + 2
    toronto = next(x for x in rows if x["municipality"] == "Toronto")
    brampton = next(x for x in rows if x["municipality"] == "Brampton")
    vaughan = next(x for x in rows if x["municipality"] == "Vaughan")
    ajax = next(x for x in rows if x["municipality"] == "Ajax")
    whitby = next(x for x in rows if x["municipality"] == "Whitby")
    assert toronto["municipality_readiness"] == "PARTIAL_RECORDS_WITH_SOURCE_FAILURES"
    assert brampton["private_research_candidates"] == "1"
    assert brampton["top_ten_investigations"] == "1"
    assert brampton["region"] == "Peel"
    assert vaughan["municipality_readiness"] == "BLOCKED_OR_FAILED_APPLICATION_SOURCES"
    assert "Wait" not in vaughan["recommended_next_action"]  # preserve explicit action
    assert ajax["municipality_readiness"] == "PILOT_INDEX_ONLY_NOT_COVERAGE"
    assert whitby["municipality_readiness"] == "PILOT_SOURCE_FAILED_HOLD"
    assert all(x["buyer_contacts_verified"] == "0" for x in rows)
    assert data["main_municipalities_configured"] == 16
    assert data["main_municipalities_with_application_records"] == 3
    assert data["main_municipalities_with_failed_sources"] == 3
    assert data["citywide_coverage_verified"] == 0


def test_absent_owner_evidence_stays_unverified(tmp_path):
    result = build(tmp_path)
    assert result["main_municipalities_with_application_records"] == 0
    assert result["citywide_coverage_verified"] == 0
    rows = _rows(tmp_path)
    assert len(rows) == 16
    assert all(row["municipality_readiness"] == "NO_CURRENT_OWNER_RUN_EVIDENCE"
               for row in rows)
    assert json.loads((tmp_path / STATUS).read_text())["paid_ai_calls"] == 0


def test_pilot_city_registered_twice_does_not_inflate_main_count(tmp_path):
    _json(tmp_path, "GTA_RADAR_GGH_EXPANSION_SOURCE_STATUS.json", {
        "source_status": [
            {"city": "Richmond Hill", "state": "BASELINE_COMPLETE",
             "application_id_rows": 4},
            {"city": "Innisfil", "state": "NO_APPLICATION_ID_ROWS",
             "application_id_rows": 0},
        ],
    })
    state = build(tmp_path)
    assert state["main_municipalities_with_application_records"] == 0
    assert state["experimental_city_source_rows_not_added_to_main"] == 2
    assert all(r["scope"] == "EXPERIMENTAL_GGH_12"
               for r in _rows(tmp_path) if r["municipality"] in ("Richmond Hill", "Innisfil"))
