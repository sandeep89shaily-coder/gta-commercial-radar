"""Offline acceptance for fresh-first client-facing research quality gates."""
from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

from gta_client_freshness import (
    run, CLIENT_TOP, CLIENT_STATUS, CLIENT_EXCLUDED, CLIENT_HTML,
)


TODAY=dt.date(2026,11,12)


def _write(root, filename, rows):
    with (root / filename).open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _read(root, filename):
    with (root / filename).open(encoding="utf-8-sig",newline="") as handle:
        return list(csv.DictReader(handle))


def _candidate(city,address,scope,*,stage="PLANNING_OR_SITE_PLAN_REVIEW",
               identified="PRIVATE:example",first_seen="2026-11-12"):
    return {
        "city":city,"address":address,"opportunity_id":identified,
        "project_name":address,"nature_of_work":scope,
        "stage_gate":stage,"project_stage":"Under Review",
        "score":"140","first_seen_local":first_seen,
        "freshness_class":"FIRST_OBSERVED_IN_RADAR_NOT_NEW_PUBLICATION",
        "source_urls":"https://www.toronto.ca/example/project",
        "contact_status":"NO_PROJECT_ASSIGNED_CONTACT_VERIFIED",
        "company_name":"UNVERIFIED TENANT LTD",
        "procurement_status":"UNKNOWN_NOT_VERIFIED_UNAWARDED",
        "source_date":"",
        "date_basis":"",
        "estimated_value":"",
    }


def _event(city,address,date,*,changed="description",
           observation="FIRST_OBSERVED",source="toronto_active_building_permits"):
    return {"city":city,"address":address,"observation":observation,
            "source_record_date":date,"changed_fields":changed,
            "source_id":source,
            "date_basis":"SOURCE EVENT DATE — NOT VERIFIED ISSUANCE/OPENING",
            "freshness_date_basis":"SOURCE_RECORD_DATE_NOT_PUBLICATION_PROOF"}


def test_november_reported_sites_suppressed_across_days_and_postal_suffix(tmp_path):
    _write(tmp_path,"GTA_RADAR_PRIVATE_DEVELOPMENT_REVIEW.csv",[
        _candidate("Toronto","2 NORELCO DR M9M","19,267 m² warehouse",identified="a"),
        _candidate("Brampton","238 Glidden Rd, Brampton, ON","Industrial shell addition",identified="b"),
        _candidate("Toronto","568 Passmore Avenue","Industrial tenant fit-out",identified="c"),
        _candidate("Toronto","999 NEWINDUSTRIAL RD","Warehouse site servicing",identified="d"),
    ])
    _write(tmp_path,"GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv",[
        _event("Toronto","2 Norelco Drive","2026-11-06"),
        _event("Brampton","238 Glidden Road","2026-11-10"),
        _event("Toronto","568 Passmore Avenue","2026-11-10"),
        _event("Toronto","999 Newindustrial Road","2026-11-12"),
    ])
    summary=run(tmp_path,today=TODAY)
    assert summary["top_count"]==1
    assert summary["projects_excluded_previously_reported"]==3
    top=_read(tmp_path,CLIENT_TOP)
    assert top[0]["address"]=="999 NEWINDUSTRIAL RD"
    assert top[0]["source_event_date_basis"]=="SOURCE_RECORD_DATE_NOT_PUBLICATION_PROOF"
    assert summary["verified_original_publications"]==0
    assert all(row["procurement_status"]=="UNKNOWN_NOT_VERIFIED_UNAWARDED" for row in top)
    assert all("PROJECT_ASSIGNED" not in row["contact_status"] for row in top)
    assert len(_read(tmp_path,CLIENT_EXCLUDED))==3
    assert "Non-repeating" not in (tmp_path/CLIENT_HTML).read_text()  # no false claim of newly published


def test_fresh_modest_project_beats_huge_old_investment(tmp_path):
    _write(tmp_path,"GTA_RADAR_PRIVATE_DEVELOPMENT_REVIEW.csv",[
        _candidate("Toronto","998 New Industrial Road",
                   "Proposed 150,000 m² $75 million manufacturing facility",identified="older"),
        _candidate("Toronto","997 New Industrial Road",
                   "Interior alteration new industrial office kitchenette",identified="recent"),
    ])
    _write(tmp_path,"GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv",[
        _event("Toronto","998 New Industrial Rd","2026-09-10"),
        _event("Toronto","997 New Industrial Rd","2026-11-11"),
    ])
    summary=run(tmp_path,today=TODAY)
    assert summary["top_count"]==2
    top=_read(tmp_path,CLIENT_TOP)
    assert top[0]["opportunity_id"]=="recent"
    assert top[1]["opportunity_id"]=="older"
    assert int(top[1]["project_size_score_25"]) > int(top[0]["project_size_score_25"])
    assert int(top[0]["freshness_priority"]) < int(top[1]["freshness_priority"])
    assert top[0]["freshness_label"]=="SOURCE_EVENT_LAST_7_DAYS_NOT_PUBLICATION_PROOF"


def test_observation_alone_is_not_event_and_no_padded_fake_top_ten(tmp_path):
    _write(tmp_path,"GTA_RADAR_PRIVATE_DEVELOPMENT_REVIEW.csv",[
        _candidate("Toronto","887 Simcoe Road","Industrial warehouse 35,000 m²",
                   identified="first_seen",first_seen="2026-11-12"),
    ])
    result=run(tmp_path,today=TODAY)
    assert result["top_count"]==0
    assert result["rejected_by_reason"]["NO_RECENT_DOCUMENTED_SOURCE_EVENT"]==1
    assert _read(tmp_path,CLIENT_TOP)==[]


def test_repeat_ledger_is_not_automatically_updated(tmp_path):
    _write(tmp_path,"GTA_RADAR_PRIVATE_DEVELOPMENT_REVIEW.csv",[
        _candidate("Mississauga","101 Brand New Road","Proposed warehouse",identified="new"),
    ])
    _write(tmp_path,"GTA_RADAR_QUALIFIED_OPPORTUNITY_SHORTLIST.csv",[
        _event("Mississauga","101 Brand New Road","2026-11-10",source="mississauga_site_plan_applications"),
    ])
    before=(tmp_path/"GTA_RADAR_CLIENT_REPORT_HISTORY.csv")
    first=run(tmp_path,today=TODAY)
    second=run(tmp_path,today=TODAY)
    assert first["top_count"]==second["top_count"]==1
    assert not before.exists()
    _write(tmp_path,before.name,[{
        "report_date":"2026-11-12","city":"Mississauga",
        "address":"101 Brand New Road","report_name":"Actual owner-approved client report"
    }])
    after=run(tmp_path,today=TODAY)
    assert after["top_count"]==0
    assert after["projects_excluded_previously_reported"]==1
    assert _read(tmp_path,CLIENT_EXCLUDED)[0]["report_name"]=="Actual owner-approved client report"


def test_unverified_owner_and_contact_never_promoted(tmp_path):
    _write(tmp_path,"GTA_RADAR_PRIVATE_DEVELOPMENT_REVIEW.csv",[
        _candidate("Toronto","776 New Test Avenue","Hotel mechanical expansion",
                   identified="maybe_buyer"),
    ])
    _write(tmp_path,"GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv",[
        _event("Toronto","776 New Test Ave","2026-11-09"),
    ])
    s=run(tmp_path,today=TODAY)
    row=_read(tmp_path,CLIENT_TOP)[0]
    assert s["buyer_verified_by_this_stage"] is False
    assert row["verified_contact_score_10"]=="0"
    assert row["named_company_role_unverified"]=="UNVERIFIED TENANT LTD"
    assert row["source_event_date_basis"]!="OFFICIAL_FIRST_PUBLICATION_VERIFIED"
    assert "UNKNOWN" in row["procurement_status"]


def test_closed_project_excluded_even_with_very_recent_source_event(tmp_path):
    _write(tmp_path,"GTA_RADAR_PRIVATE_DEVELOPMENT_REVIEW.csv",[
        _candidate("Toronto","999 Island Road","Industrial building",
                   stage="CLOSED_EXCLUDE",identified="completed"),
        _candidate("Toronto","998 Island Road","Industrial building",
                   stage="APPEALED_OR_ON_HOLD",identified="paused"),
    ])
    _write(tmp_path,"GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv",[
        _event("Toronto","999 Island Road","2026-11-12"),
        _event("Toronto","998 Island Road","2026-11-12"),
    ])
    result=run(tmp_path,today=TODAY)
    assert result["top_count"]==0
    assert result["rejected_by_reason"]["INACTIVE_OR_PAUSED"]==2


def test_future_date_does_not_manufacture_fresh_project(tmp_path):
    _write(tmp_path,"GTA_RADAR_PRIVATE_DEVELOPMENT_REVIEW.csv",[
        _candidate("Toronto","999 Future Road","Hotel project",identified="fake_date"),
    ])
    _write(tmp_path,"GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv",[
        _event("Toronto","999 Future Road","2027-01-01"),
    ])
    result=run(tmp_path,today=TODAY)
    assert result["top_count"]==0
    assert json.loads((tmp_path/CLIENT_STATUS).read_text())["verified_original_publications"]==0
