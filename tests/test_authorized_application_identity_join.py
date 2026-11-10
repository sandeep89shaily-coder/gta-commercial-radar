"""Safety gates for authorized-role cross-source application reconciliation."""
from __future__ import annotations

import csv
import datetime as dt
import json

import pytest

import gta_authorized_application_identity_join as join


def put(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def export(**kwargs):
    source = {
        "city": "Kitchener", "application_id": "ZBA-26-018",
        "project_id": "OFFICIAL_EXPORT:KITCHENER:ZBA-26-018",
        "address": "100 King Street Unit 3",
        "source_url": "https://www.arcgis.com/home/item.html?id=example",
        "provenance": join.EXPECTED_PROVENANCE,
        "applicant_name_unverified": "Factory Planning Ltd",
        "property_owner_unverified": "Factory Holdings Ltd",
        "planning_reviewer_unverified": "Municipal Planner",
        "role_source_fields": "KITCHENER:APPLICANT|PROPERTY_OWNER|ISSUED_BY",
    }
    source.update(kwargs)
    return source


def other(family="additional_official_gis", **kwargs):
    record = {
        "city": "Kitchener", "application_id": "ZBA-26-018",
        "address": "100 King St Unit 3",
        "project_id": "OFFICIAL_GIS:KITCHENER:ZBA-26-018",
        "source_url": "https://services1.arcgis.com/example/FeatureServer/0",
    }
    if family == "planning_master":
        record.update({
            "canonical_id": "KITCHENER:ZBA-26-018",
            "record_kind": "APPLICATION_ID",
        })
    record.update(kwargs)
    return record


def test_same_city_exact_application_id_and_site_yields_unverified_review():
    matches, holds, stats = join.reconcile(
        [export()], {"additional_official_gis": [other()]})
    assert len(matches) == 1
    assert holds == []
    m = matches[0]
    assert m["match_basis"] == "EXACT_CITY_ID_AND_CIVIC_SITE_REVIEW_ONLY"
    assert m["applicant_unverified"] == "Factory Planning Ltd"
    assert m["property_owner_unverified"] == "Factory Holdings Ltd"
    assert m["planning_reviewer_unverified"] == "Municipal Planner"
    assert m["same_application_verified"] == "NO"
    assert m["organization_role_verified"] == "NO"
    assert m["buyer_verified"] == "NO"
    assert m["procurement_verified"] == "NO"
    assert m["first_publication_verified"] == "NO"
    assert stats["match_rows_review_only"] == 1


def test_id_normalization_only_ignores_whitespace_and_case():
    assert join.application_key(" zba - 26 - 018 ") == "ZBA-26-018"
    assert join.application_key("ZBA-26-018") != join.application_key("ZBA-26-18")
    assert join.application_key("ZBA-26-018") != join.application_key("ZBA/26/018")
    assert not join.application_key("99")


@pytest.mark.parametrize("other_row,expected", [
    (other(city="Vaughan"), "NO_EXACT_CITY_AND_APPLICATION_ID_IN_OTHER_SOURCE"),
    (other(application_id="ZBA-26-019"), "NO_EXACT_CITY_AND_APPLICATION_ID_IN_OTHER_SOURCE"),
    (other(address="200 King Street Unit 3"), "CONFLICTING_CIVIC_SITE_FOR_EXACT_ID"),
    (other(address=""), "OTHER_SOURCE_LACKS_CIVIC_SITE"),
    (other(address="100 King St Unit 7"), "UNIT_CONFLICT_OR_UNSPECIFIED_UNIT"),
    (other(address="100 King St"), "UNIT_CONFLICT_OR_UNSPECIFIED_UNIT"),
])
def test_false_cross_source_join_is_held(other_row, expected):
    matches, holds, _ = join.reconcile(
        [export()], {"additional_official_gis": [other_row]})
    assert not matches
    assert len(holds) == 1
    assert holds[0]["reason"] == expected


def test_strict_provenance_and_export_scope_prevent_join():
    for changed in (
        export(provenance="OFFICIAL_VERIFIED"),
        export(city="Toronto"),
        export(application_id="123"),
        export(applicant_name_unverified="", property_owner_unverified="",
               planning_reviewer_unverified=""),
    ):
        matches, holds, _ = join.reconcile([changed], {
            "additional_official_gis": [other()]})
        assert not matches
        assert holds


def test_site_conflict_across_multiple_sources_blocks_even_one_exact_match():
    matches, holds, stats = join.reconcile([export()], {
        "additional_official_gis": [other()],
        "five_city_official": [other(address="100 Queen Street Unit 3")],
    })
    assert not matches
    assert holds[0]["reason"] == "CONFLICTING_CIVIC_SITE_FOR_EXACT_ID"


def test_multiple_exact_sources_are_independent_review_candidates():
    matches, holds, _ = join.reconcile([export()], {
        "additional_official_gis": [other()],
        "planning_master": [other("planning_master",
                                  source_url="https://kitchener.ca/planning")],
    })
    assert len(matches) == 2
    assert not holds
    assert {r["comparison_source"] for r in matches} == {
        "planning_master", "additional_official_gis"}
    assert all(r["buyer_verified"] == "NO" for r in matches)


def test_no_link_to_generic_master_rows_and_independent_id_required():
    matches, holds, _ = join.reconcile([export()], {
        "planning_master": [other("planning_master", record_kind="NEWS")]
    })
    assert not matches
    assert holds[0]["reason"] == "NO_EXACT_CITY_AND_APPLICATION_ID_IN_OTHER_SOURCE"


def test_missing_role_export_emits_no_false_success_or_files(tmp_path):
    result=join.run(tmp_path)
    assert result["status"] == "ASSISTED_OFFICIAL_EXPORT_MISSING"
    assert result["verified_buyers"] == 0
    assert not (tmp_path/"FACILITY_DOSSIER_PILOT").exists()


def test_end_to_end_holds_and_matches_do_not_change_source_data(tmp_path):
    export_rows = [export(),
                   export(application_id="ZBA-26-019", project_id="B",
                          address="200 King St", applicant_name_unverified="=BAD()")]
    comparison_rows = [other()]
    export_path=tmp_path/join.EXPORT
    gis_path=tmp_path/"GTA_RADAR_ADDITIONAL_CITY_GIS_APPLICATIONS.csv"
    put(export_path, export_rows)
    put(gis_path, comparison_rows)
    before={str(p):p.read_bytes() for p in (export_path,gis_path)}
    report=join.run(tmp_path, today=dt.date(2026,11,10))
    assert report["candidate_role_links"] == 1
    assert report["held_records"] == 1
    assert report["distinct_import_applications_with_matches"] == 1
    assert report["official_source_independently_authenticated"] is False
    assert report["verified_buyers"] == 0
    assert report["open_supplier_contracts_verified"] == 0
    assert report["no_source_files_modified"] is True
    for p in (export_path,gis_path):
        assert p.read_bytes() == before[str(p)]
    out=tmp_path/"FACILITY_DOSSIER_PILOT"
    with (out/join.MATCHES).open(encoding="utf-8-sig",newline="") as fp:
        row=next(csv.DictReader(fp))
    assert row["same_application_verified"] == "NO"
    with (out/join.HOLDS).open(encoding="utf-8-sig",newline="") as fp:
        holds=list(csv.DictReader(fp))
    assert holds[0]["reason"] == "NO_EXACT_CITY_AND_APPLICATION_ID_IN_OTHER_SOURCE"
    status=json.loads((out/join.STATUS).read_text())
    assert status["candidate_role_links"] == 1


def test_wrong_schema_fails_closed_and_does_not_write_reports(tmp_path):
    put(tmp_path/join.EXPORT,[{"city":"Kitchener","application_id":"ZBA-26-018",
                                "address":"100 King St"}])
    with pytest.raises(ValueError, match="INVALID_SOURCE_SCHEMA"):
        join.run(tmp_path)
    assert not (tmp_path/"FACILITY_DOSSIER_PILOT").exists()


def test_source_csv_formula_injection_cannot_execute_in_report(tmp_path):
    put(tmp_path/join.EXPORT,[export(applicant_name_unverified="=HYPERLINK(1)")])
    put(tmp_path/"GTA_RADAR_ADDITIONAL_CITY_GIS_APPLICATIONS.csv",[other()])
    join.run(tmp_path)
    with (tmp_path/"FACILITY_DOSSIER_PILOT"/join.MATCHES).open(
            encoding="utf-8-sig",newline="") as fp:
        result=next(csv.DictReader(fp))
    assert result["applicant_unverified"].startswith("'=HYPERLINK")
