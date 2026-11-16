"""Regression checks for evidence-only application reconciliation."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from gta_project_document_reconciliation import review, normalize_id, procurement_gate

def write_rows(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)

class ProjectDocumentReconciliationTests(unittest.TestCase):
    def test_normalized_ids_ignore_punctuation(self):
        self.assertEqual(normalize_id("OZS-2025-0038"), "OZS20250038")

    def test_exact_city_join_only_and_no_buyer_inference(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_rows(root / "GTA_RADAR_PRIVATE_DEVELOPMENT_REVIEW.csv", [
                {"city":"Toronto", "application_ids":"26 185171 NNY 17 OZ",
                 "opportunity_id":"T1", "address":"Example"},
                {"city":"Brampton", "application_ids":"OZS-2025-0048",
                 "opportunity_id":"B1", "address":"Example"}])
            target = (root / "COUNCIL_INTELLIGENCE_REVIEW" /
                      "TORONTO_OFFICIAL_PLANNING_NOTICES" /
                      "TORONTO_CURRENT_PLANNING_NOTICES_REVIEW.csv")
            write_rows(target, [
                {"city":"Toronto", "application_id":"26-185171-NNY-17-OZ",
                 "official_notice_url":"https://secure.toronto.ca/notice/123"},
                {"city":"Toronto", "application_id":"OZS-2025-0048",
                 "official_notice_url":"https://secure.toronto.ca/notice/124"}])
            result = review(root)
            self.assertEqual(result["exact_official_application_id_joins_for_review"], 1)
            self.assertEqual(result["unmatched_official_application_records"], 1)
            self.assertEqual(result["verified_procurement_buyers"], 0)
            self.assertEqual(result["verified_open_supplier_packages"], 0)
            details = json.loads((root / "PROJECT_DOCUMENT_RECONCILIATION" /
                                  "APPLICATION_JOIN_REVIEW.json").read_text())
            self.assertEqual(details[0]["matched_opportunity_ids"], ["T1"])
            self.assertEqual(details[1]["matched_opportunity_ids"], [])

    def test_ambiguous_id_cannot_be_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_rows(root / "GTA_RADAR_PRIVATE_DEVELOPMENT_REVIEW.csv", [
                {"city":"Brampton", "application_ids":"OZS-2025-0038",
                 "opportunity_id":"B1"},
                {"city":"Brampton", "application_ids":"OZS20250038",
                 "opportunity_id":"B2"}])
            source = root / "COUNCIL_INTELLIGENCE_REVIEW/BRAMPTON_FEATURED_PDC/BRAMPTON_PDC_FEATURED_APPLICATIONS_REVIEW.csv"
            write_rows(source,[{"city":"Brampton", "application_id":"OZS-2025-0038",
                                "source_url":"https://letsconnect.brampton.ca/yourcityplans"}])
            result = review(root)
            self.assertEqual(result["ambiguous_joins"], 1)
            self.assertEqual(result["exact_official_application_id_joins_for_review"], 0)

    def test_complete_procurement_evidence_still_requires_manual_review(self):
        row = dict.fromkeys(("project_source_url", "purchaser_name", "purchaser_role",
             "purchaser_source_url", "open_package_description",
             "open_package_source_url", "open_package_asof"), "source")
        for key in ("project_source_url", "purchaser_source_url", "open_package_source_url"):
            row[key] = "https://example.org/official"
        self.assertEqual(procurement_gate(row), (False, "HUMAN_VERIFICATION_REQUIRED"))
        row["open_package_source_url"] = ""
        self.assertFalse(procurement_gate(row)[0])

if __name__ == "__main__":
    unittest.main()
