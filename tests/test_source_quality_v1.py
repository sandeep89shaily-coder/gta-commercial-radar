"""Regression tests for conservative source quality scorecard."""
from pathlib import Path
import csv
import tempfile
import unittest

from gta_source_quality_v1 import build, run, OUTPUT


class SourceQualityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, records):
        with (self.root / "GTA_RADAR_COLLECTION_HEALTH.csv").open(
                "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=[
                "city", "application_files", "official_sources_with_records",
                "source_failures", "access_failures", "quality_status", "source_notes"])
            w.writeheader()
            w.writerows(records)

    def test_missing_input_does_not_claim_coverage(self):
        result = build(self.root)
        self.assertEqual(result["citywide_verified"], 0)
        self.assertEqual(result["status"], "NO_CURRENT_HEALTH_CSV")

    def test_partial_cities_never_become_citywide_or_buyers(self):
        self.write([
            {"city": "Toronto", "application_files": "1261",
             "official_sources_with_records": "1", "source_failures": "1",
             "access_failures": "1", "quality_status": "EXTRACTED",
             "source_notes": "robots blocked"},
            {"city": "Mississauga", "application_files": "30",
             "official_sources_with_records": "1", "source_failures": "0",
             "access_failures": "0", "quality_status": "EXTRACTED",
             "source_notes": ""},
        ])
        report = run(self.root)
        self.assertEqual(report["municipalities_targeted"], 16)
        self.assertEqual(report["municipalities_with_records"], 2)
        self.assertEqual(report["municipalities_with_source_access_failures"], 1)
        self.assertEqual(report["citywide_verified"], 0)
        self.assertEqual(report["buyer_leads_verified"], 0)
        self.assertFalse(report["cities"][0]["citywide_complete"])
        self.assertFalse(report["cities"][0]["source_freshness_verified"])
        self.assertEqual(report["cities"][1]["city"], "Brampton")
        self.assertTrue((self.root / OUTPUT).is_file())

    def test_duplicate_or_unknown_city_refused(self):
        record = {"city": "Toronto", "application_files": "1",
                  "official_sources_with_records": "1", "source_failures": "0",
                  "access_failures": "0", "quality_status": "x",
                  "source_notes": ""}
        self.write([record, record])
        with self.assertRaisesRegex(ValueError, "DUPLICATE_OR_UNKNOWN_CITY"):
            build(self.root)

    def test_bad_counts_refused(self):
        self.write([{"city": "Toronto", "application_files": "-1",
                     "official_sources_with_records": "1", "source_failures": "0",
                     "access_failures": "0", "quality_status": "x",
                     "source_notes": ""}])
        with self.assertRaisesRegex(ValueError, "NEGATIVE_SOURCE_COUNT"):
            build(self.root)


if __name__ == "__main__":
    unittest.main()
