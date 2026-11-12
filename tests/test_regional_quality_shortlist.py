"""Regional shortlist regression: don't let Toronto drown out official Peel data."""
from __future__ import annotations

import csv
import datetime as dt
from collections import Counter
from gta_opportunity_lanes import (
    run, PRIVATE_TOP, PRIVATE_ALL, STATUS, _site,
)


def _write(root, name, rows):
    with (root / name).open("w", encoding="utf-8", newline="") as f:
        fields = list(rows[0])
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _read(root, name):
    with (root / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _qualified(city, address, ident, text="Proposed industrial warehouse building",
               status="Active", source="mississauga_site_plan_applications"):
    return dict(city=city, address=address, source_id=source,
                project_id=source+":"+ident, official_permit_id=ident,
                qualification_scope=text, description=text,
                source_record_date="2026-10-10", official_status=status,
                official_record_url=("https://services6.arcgis.com/municipal/"
                                     "FeatureServer/0/query?where=ID"),
                observation="", sale_ready="YES",
                operator="AI INFERRED OWNER", related_company="UNVERIFIED INC.",
                contact="not-a-verified-email@example.com")


def _toronto(i):
    return dict(city="Toronto", record_kind="APPLICATION_ID",
                application_id=f"26 2000{i:02d} STE 01 SA",
                address=f"{100+i} TEST INDUSTRIAL RD",
                description="Proposed two-storey industrial manufacturing warehouse",
                current_status="Under Review", application_year_hint="2026",
                evidence_urls="https://open.toronto.ca/dataset/development-applications/",
                first_seen_local="2026-11-11", observation="UNCHANGED")


def test_qualified_source_projects_reach_private_queue_without_buyer_claims(tmp_path):
    x = _qualified("Peel", "238 Glidden Rd, Brampton, ON, L6W 1H8",
                   "26-185633-000-00", "Addition Shell F2: Industrial",
                   status="Applied", source="brampton_building_permits")
    y = _qualified("Mississauga", "8 Falconer Drive", "SP 26/30 W11",
                   "Site plan for two industrial buildings")
    _write(tmp_path, "GTA_RADAR_QUALIFIED_OPPORTUNITY_SHORTLIST.csv", [x, y])
    result = run(tmp_path, today=dt.date(2026, 11, 11))
    rows = _read(tmp_path, PRIVATE_ALL)
    assert result["input_rows"]["private_qualified"] == 2
    assert {x["city"] for x in rows} == {"Brampton", "Mississauga"}
    assert all(x["company_name"] == "" for x in rows)
    assert all(x["email"] == "" and x["phone"] == "" for x in rows)
    assert all(x["procurement_status"] == "UNKNOWN_NOT_VERIFIED_UNAWARDED"
               for x in rows)
    assert result["private_verified_recent_publications"] == 0
    brampton = next(x for x in rows if x["city"] == "Brampton")
    assert brampton["project_stage"] == "Permit Applied"
    assert brampton["date_basis"] == ""
    assert "26-185633-000-00" in brampton["application_ids"]


def test_region_balancing_uses_real_evidence_and_keeps_toronto_cap(tmp_path):
    _write(tmp_path, "GTA_RADAR_COLLECTION_MASTER.csv",
           [_toronto(i) for i in range(1, 13)])
    records = [
        _qualified("Peel", "238 Glidden Rd, Brampton, ON", "26-185633-000-00",
                   source="brampton_building_permits", status="Applied"),
        _qualified("Brampton", "8050 Heritage Rd, Brampton, ON", "26-144459-000-00",
                   source="brampton_building_permits", status="Applied"),
        _qualified("Mississauga", "8 Falconer Drive", "SP 26/30 W11"),
        _qualified("Mississauga", "5990 Indian Line", "SP 26/25 W5",
                   "Proposed 16-storey hotel"),
        _qualified("Waterloo", "187 King St S", "26-5555-WL",
                   "Office building interior renovation"),
        _qualified("Cambridge", "210 Royal Oak Rd", "R02/26",
                   "Proposed industrial steel parts storage warehouse"),
        _qualified("Burlington", "3110 South Service Rd", "520-11/26",
                   "Proposed 20 MW data centre"),
        _qualified("Guelph", "175 Industrial Rd", "2026-155",
                   "Proposed industrial manufacturing building"),
        _qualified("Markham", "215 Enterprise Blvd", "2026-116",
                   "Proposed logistics warehouse and office"),
    ]
    _write(tmp_path, "GTA_RADAR_QUALIFIED_OPPORTUNITY_SHORTLIST.csv", records)
    result = run(tmp_path, today=dt.date(2026, 11, 11))
    top = _read(tmp_path, PRIVATE_TOP)
    assert len(top) == 10
    assert [x["rank"] for x in top] == [str(i) for i in range(1, 11)]
    cities = Counter(x["city"] for x in top)
    assert cities["Toronto"] <= 3
    assert any(x["city"] == "Brampton" for x in top)
    assert any(x["city"] == "Mississauga" for x in top)
    assert len(result["private_top_region_distribution"]) >= 4
    assert len({x["opportunity_id"] for x in top}) == 10


def test_qualified_records_do_not_force_residential_to_top(tmp_path):
    _write(tmp_path, "GTA_RADAR_QUALIFIED_OPPORTUNITY_SHORTLIST.csv", [
        _qualified("Waterloo", "494 Kingscourt Dr", "2026-001",
                   "Two-storey addition to a single detached dwelling, basement rec room"),
        _qualified("Mississauga", "8 Falconer Drive", "SP 26/30 W11",
                   "Industrial warehouse and manufacturing building"),
    ])
    run(tmp_path, today=dt.date(2026, 11, 11))
    rows = _read(tmp_path, PRIVATE_TOP)
    assert len(rows) == 1
    assert rows[0]["city"] == "Mississauga"


def test_site_dedupes_postal_suffixed_brampton_but_not_multisite():
    assert _site("8050 Heritage Rd, Brampton, ON, L6Y") == _site("8050 Heritage Road")
    assert _site("1 Rosetta Street, 6 & 8 Saint Michaels Street") != _site("1 Rosetta Street")


def test_single_city_fills_remainder_without_fake_regions(tmp_path):
    _write(tmp_path, "GTA_RADAR_COLLECTION_MASTER.csv",
           [_toronto(i) for i in range(1, 13)])
    result = run(tmp_path, today=dt.date(2026, 11, 11))
    top = _read(tmp_path, PRIVATE_TOP)
    assert len(top) == 10
    assert result["private_top_city_distribution"] == {"Toronto": 10}
    assert result["private_top_region_distribution"] == {"Toronto": 10}
