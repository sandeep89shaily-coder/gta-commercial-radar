"""Cross-source Brampton GIS matches must be exact ID and current-source safe."""
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from gta_brampton_official_gis_planning import (
    ALL as GIS_CSV, STATUS as GIS_STATUS, COLUMNS as GIS_COLS, BASE
)
from gta_brampton_featured_pdc import CSV as FEATURED_CSV, STATUS as FEATURED_STATUS
from gta_brampton_gis_radar_reconciliation import run, OUT, STATUS

STAMP = "2026-11-13T18:35:00+00:00"


def csv_write(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def gis_fixture(root, *, partial=False, duplicate=False, stale=False):
    gis = root / "GIS"
    gis.mkdir()
    rows = [
        dict(city="Brampton", layer="OPA_ZBA_SUBDIVISION",
             application_id="OZS-2026-0038", location="110 Test Road",
             proposal_description="New industrial distribution warehouse",
             status="Under Review", date_received_utc="2026-11-01",
             date_received_basis="GIS_DATE_RECEIVED_NOT_FIRST_PUBLICATION",
             first_observed_utc=STAMP, last_observed_utc=STAMP,
             observation="BASELINE_EXISTING_NOT_NEW_PUBLICATION",
             source_layer_url=BASE+"/9",
             commercial_screen="COMMERCIAL_KEYWORD_REVIEW_ONLY",
             applicant_company_source_text="Applicant Test Inc",
             agent_company_source_text="Planning Agent Ltd"),
        dict(city="Brampton", layer="SITE_PLAN_APPROVAL",
             application_id="SP-2026-0123", location="200 Sample Road",
             description="Proposed commercial office building",
             status="Under Review", date_received_utc="2026-11-09",
             date_received_basis="GIS_DATE_RECEIVED_NOT_FIRST_PUBLICATION",
             first_observed_utc=STAMP,
             last_observed_utc="2026-11-12T18:35:00+00:00" if stale else STAMP,
             observation="BASELINE_EXISTING_NOT_NEW_PUBLICATION",
             source_layer_url=BASE+"/11",
             commercial_screen="COMMERCIAL_KEYWORD_REVIEW_ONLY",
             applicant_company_source_text="Another Owner Inc"),
    ]
    if duplicate:
        rows.append(dict(rows[0]))
    csv_write(gis / GIS_CSV, GIS_COLS, rows)
    layer_results = [
        {"layer": 9, "status": "COMPLETE_REVIEW_ONLY"},
        {"layer": 11, "status": "COMPLETE_REVIEW_ONLY"}
    ]
    (gis / GIS_STATUS).write_text(json.dumps({
        "status": ("PARTIAL_OFFICIAL_GIS_LAYERS_REVIEW_ONLY" if partial
                   else "ALL_THREE_LAYERS_REVIEW_ONLY"),
        "checked_utc": STAMP, "layers_complete": 2 if partial else 3,
        "layer_results": layer_results if partial else layer_results + [
            {"layer": 10, "status": "COMPLETE_REVIEW_ONLY"}]
    }), encoding="utf-8")
    return gis


def featured_fixture(root):
    folder = root / "FEATURED"
    folder.mkdir()
    (folder / FEATURED_STATUS).write_text(json.dumps({
        "status": "FEATURED_APPLICATIONS_REVIEW_ONLY",
        "checked_utc": STAMP
    }), encoding="utf-8")
    csv_write(folder / FEATURED_CSV,
              ("city", "application_id", "last_observed_utc"),
              [
                  {"city": "Brampton", "application_id": "OZS-2026-0038",
                   "last_observed_utc": STAMP},
                  {"city": "Brampton", "application_id": "OZS-2026-0308",
                   "last_observed_utc": STAMP}
              ])
    return folder


class BramptonGISReconciliationTests(unittest.TestCase):
    def test_exact_file_not_substring_and_saved_sources_never_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gis, featured = gis_fixture(root), featured_fixture(root)
            existing = root / "RESULTS"
            existing.mkdir()
            csv_write(existing / "GTA_RADAR_PRIVATE_DEVELOPMENT_REVIEW.csv",
                      ("city", "address", "application_ids"), [
                          {"city": "Brampton", "address": "110 Test Road",
                           "application_ids": "OZS 2026 0038; OZS-2026-00380"},
                          {"city": "Toronto", "address": "110 Test Road",
                           "application_ids": "SP-2026-0123"},
                      ])
            csv_write(existing / "GTA_RADAR_PRIVATE_TOP_10.csv",
                      ("city", "address", "application_ids"), [
                          {"city": "Brampton", "address": "Different place",
                           "application_ids": "OZS-2026-00380"}
                      ])
            result = run(gis, featured, existing, root / "OUT")
            self.assertEqual(result["status"], "AUDIT_READY_COMPLETE_GIS_LAYERS")
            self.assertEqual(result["gis_unique_file_numbers"], 2)
            self.assertEqual(result["exact_ids_in_saved_radar"], 1)
            self.assertEqual(result["exact_ids_in_private_investigation"], 1)
            self.assertEqual(result["exact_ids_in_private_top_ten"], 0)
            self.assertEqual(result["exact_ids_in_featured_pdc"], 1)
            self.assertEqual(result["cases_for_manual_audit"], 2)
            self.assertEqual(result["buyers_verified"], 0)
            self.assertEqual(result["paid_ai_calls"], 0)
            with (root/"OUT"/OUT).open(encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]["application_id"], "SP-2026-0123")
            self.assertEqual(rows[1]["application_id"], "OZS-2026-0038")
            self.assertEqual(rows[1]["featured_pdc_exact_file_match"], "True")
            self.assertEqual(rows[1]["previously_in_private_investigation"], "True")
            self.assertEqual(rows[0]["buyer_verified"], "False")
            self.assertEqual(rows[0]["municipal_file_receipt_is_not_publication"], "True")

    def test_stale_source_and_bad_duplicate_refuse_all_joins(self):
        for kind in ("stale", "duplicate", "failed"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                gis = gis_fixture(root, stale=kind == "stale",
                                  duplicate=kind == "duplicate")
                if kind == "failed":
                    (gis / GIS_STATUS).write_text(json.dumps({
                        "status": "ALL_OFFICIAL_GIS_LAYERS_HELD_NO_LEDGER_MUTATION",
                        "layers_complete": 0, "checked_utc": STAMP
                    }))
                result = run(gis, root / "not_present", root, root / "OUT")
                self.assertFalse(result["status"].startswith("AUDIT_READY"))
                self.assertEqual(result["cases_for_manual_audit"], 0)
                self.assertFalse((root / "OUT" / OUT).exists())
                self.assertTrue((root / "OUT" / STATUS).is_file())

    def test_missing_secondary_outputs_does_not_fabricate_project_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run(gis_fixture(root, partial=True),
                         root / "not_present", root, root / "OUT")
            self.assertEqual(result["status"], "AUDIT_READY_PARTIAL_GIS_LAYERS")
            self.assertEqual(result["exact_ids_in_saved_radar"], 0)
            self.assertEqual(result["exact_ids_in_featured_pdc"], 0)
            self.assertEqual(result["gis_current_rows"], 2)
            self.assertEqual(result["buyers_verified"], 0)
            self.assertEqual(result["publisher_first_publications_verified"], 0)

    def test_no_primary_db_or_external_network_needed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run(root/"absent", root/"absent", root, root/"OUT")
            self.assertEqual(result["status"], "NO_CURRENT_GIS_SOURCE_DATA_HOLD")
            self.assertEqual(list(root.glob("*.sqlite")), [])

if __name__ == "__main__":
    unittest.main()
