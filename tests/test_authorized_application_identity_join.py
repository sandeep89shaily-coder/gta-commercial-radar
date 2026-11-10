"""Unit regressions for the manual-only authorized application ID role join."""
from __future__ import annotations

import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

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


class AuthorizedApplicationIdentityTests(unittest.TestCase):
    def test_exact_city_id_and_site_is_only_unverified_review(self):
        matches, holds, stats = join.reconcile(
            [export()], {"additional_official_gis": [other()]})
        self.assertEqual(len(matches), 1)
        self.assertEqual(holds, [])
        m = matches[0]
        self.assertEqual(m["match_basis"], "EXACT_CITY_ID_AND_CIVIC_SITE_REVIEW_ONLY")
        self.assertEqual(m["applicant_unverified"], "Factory Planning Ltd")
        self.assertEqual(m["property_owner_unverified"], "Factory Holdings Ltd")
        self.assertEqual(m["planning_reviewer_unverified"], "Municipal Planner")
        for f in ("same_application_verified", "organization_role_verified",
                  "buyer_verified", "procurement_verified", "first_publication_verified"):
            self.assertEqual(m[f], "NO")
        self.assertEqual(stats["match_rows_review_only"], 1)

    def test_id_normalization_only_ignores_case_and_space(self):
        self.assertEqual(join.application_key(" zba - 26 - 018 "), "ZBA-26-018")
        self.assertNotEqual(join.application_key("ZBA-26-018"),
                            join.application_key("ZBA-26-18"))
        self.assertNotEqual(join.application_key("ZBA-26-018"),
                            join.application_key("ZBA/26/018"))
        self.assertEqual(join.application_key("99"), "")

    def test_conflicting_city_id_address_and_unit_never_join(self):
        cases = (
            (other(city="Vaughan"), "NO_EXACT_CITY_AND_APPLICATION_ID_IN_OTHER_SOURCE"),
            (other(application_id="ZBA-26-019"), "NO_EXACT_CITY_AND_APPLICATION_ID_IN_OTHER_SOURCE"),
            (other(address="200 King Street Unit 3"), "CONFLICTING_CIVIC_SITE_FOR_EXACT_ID"),
            (other(address=""), "OTHER_SOURCE_LACKS_CIVIC_SITE"),
            (other(address="100 King St Unit 7"), "UNIT_CONFLICT_OR_UNSPECIFIED_UNIT"),
            (other(address="100 King St"), "UNIT_CONFLICT_OR_UNSPECIFIED_UNIT"),
        )
        for row, expected in cases:
            with self.subTest(reason=expected, row=row):
                matches, holds, _ = join.reconcile(
                    [export()], {"additional_official_gis": [row]})
                self.assertFalse(matches)
                self.assertEqual(len(holds), 1)
                self.assertEqual(holds[0]["reason"], expected)

    def test_strict_source_provenance_and_role_fields(self):
        for record in (
            export(provenance="OFFICIAL_VERIFIED"),
            export(city="Toronto"),
            export(application_id="123"),
            export(applicant_name_unverified="", property_owner_unverified="",
                   planning_reviewer_unverified=""),
        ):
            with self.subTest(record=record):
                matches, holds, _ = join.reconcile(
                    [record], {"additional_official_gis": [other()]})
                self.assertFalse(matches)
                self.assertTrue(holds)

    def test_conflicting_sites_across_sources_block_every_match(self):
        matches, holds, _ = join.reconcile([export()], {
            "additional_official_gis": [other()],
            "five_city_official": [other(address="100 Queen Street Unit 3")],
        })
        self.assertFalse(matches)
        self.assertEqual(holds[0]["reason"],
                         "CONFLICTING_CIVIC_SITE_FOR_EXACT_ID")

    def test_two_exact_sources_are_two_independent_review_candidates(self):
        matches, holds, _ = join.reconcile([export()], {
            "additional_official_gis": [other()],
            "planning_master": [other("planning_master",
                                      source_url="https://kitchener.ca/planning")],
        })
        self.assertEqual(len(matches), 2)
        self.assertFalse(holds)
        self.assertEqual({r["comparison_source"] for r in matches},
                         {"planning_master", "additional_official_gis"})
        self.assertTrue(all(r["buyer_verified"] == "NO" for r in matches))

    def test_non_application_master_record_and_missing_id_cannot_join(self):
        for master in (other("planning_master", record_kind="NEWS"),
                       other("planning_master", application_id="")):
            with self.subTest(master=master):
                matches, holds, _ = join.reconcile(
                    [export()], {"planning_master": [master]})
                self.assertFalse(matches)
                self.assertEqual(holds[0]["reason"],
                                 "NO_EXACT_CITY_AND_APPLICATION_ID_IN_OTHER_SOURCE")

    def test_terminal_and_duplicate_assisted_export_ids_are_held(self):
        matches, holds, _ = join.reconcile(
            [export(current_status="Withdrawn")],
            {"additional_official_gis": [other()]})
        self.assertFalse(matches)
        self.assertEqual(holds[0]["reason"],
                         "HISTORICAL_OR_TERMINAL_APPLICATION_STATUS")
        rec = export()
        matches, holds, _ = join.reconcile([rec, dict(rec)],
                                           {"additional_official_gis": [other()]})
        self.assertFalse(matches)
        self.assertEqual(len(holds), 2)
        self.assertTrue(all(h["reason"] ==
                            "DUPLICATE_ASSISTED_EXPORT_APPLICATION_ID_REVIEW"
                            for h in holds))

    def test_missing_export_emits_no_false_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result=join.run(root)
            self.assertEqual(result["status"], "ASSISTED_OFFICIAL_EXPORT_MISSING")
            self.assertEqual(result["verified_buyers"], 0)
            self.assertFalse((root/"FACILITY_DOSSIER_PILOT").exists())

    def test_offline_report_and_sources_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            incoming = [export(), export(application_id="ZBA-26-019",
                                        project_id="B", address="200 King St")]
            src = root/join.EXPORT
            cmp_file = root/"GTA_RADAR_ADDITIONAL_CITY_GIS_APPLICATIONS.csv"
            put(src, incoming)
            put(cmp_file, [other()])
            old = {str(p):p.read_bytes() for p in (src, cmp_file)}
            report=join.run(root,today=dt.date(2026,11,10))
            self.assertEqual(report["candidate_role_links"], 1)
            self.assertEqual(report["held_records"], 1)
            self.assertEqual(report["distinct_import_applications_with_matches"], 1)
            self.assertFalse(report["official_source_independently_authenticated"])
            self.assertEqual(report["verified_buyers"], 0)
            self.assertEqual(report["open_supplier_contracts_verified"], 0)
            self.assertTrue(report["no_source_files_modified"])
            for p in (src,cmp_file):
                self.assertEqual(p.read_bytes(),old[str(p)])
            out=root/"FACILITY_DOSSIER_PILOT"
            with (out/join.MATCHES).open(encoding="utf-8-sig",newline="") as fp:
                row=next(csv.DictReader(fp))
            self.assertEqual(row["same_application_verified"],"NO")
            with (out/join.HOLDS).open(encoding="utf-8-sig",newline="") as fp:
                holds=list(csv.DictReader(fp))
            self.assertEqual(holds[0]["reason"],
                             "NO_EXACT_CITY_AND_APPLICATION_ID_IN_OTHER_SOURCE")
            status=json.loads((out/join.STATUS).read_text())
            self.assertEqual(status["candidate_role_links"],1)

    def test_wrong_export_schema_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            put(root/join.EXPORT,[{"city":"Kitchener",
                                  "application_id":"ZBA-26-018",
                                  "address":"100 King St"}])
            with self.assertRaisesRegex(ValueError,"INVALID_SOURCE_SCHEMA"):
                join.run(root)
            self.assertFalse((root/"FACILITY_DOSSIER_PILOT").exists())

    def test_csv_formula_injection_escaped(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            put(root/join.EXPORT,[export(applicant_name_unverified="=HYPERLINK(1)")])
            put(root/"GTA_RADAR_ADDITIONAL_CITY_GIS_APPLICATIONS.csv",[other()])
            join.run(root)
            with (root/"FACILITY_DOSSIER_PILOT"/join.MATCHES).open(
                    encoding="utf-8-sig",newline="") as fp:
                result=next(csv.DictReader(fp))
            self.assertTrue(result["applicant_unverified"].startswith("'=HYPERLINK"))


if __name__ == "__main__":
    unittest.main()
