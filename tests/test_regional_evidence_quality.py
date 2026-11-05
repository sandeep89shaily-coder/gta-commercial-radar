"""Regression tests for separation of regional discovery and application evidence."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from gta_regional_early_intelligence import _candidate, run


class RegionalEvidenceQualityTests(unittest.TestCase):
    def test_generic_project_link_is_not_application(self):
        base = "https://example.gov/construction"
        row = _candidate("York", "INFRASTRUCTURE_INDEX", base,
                         "Watermain expansion project", "https://example.gov/projects/watermain")
        self.assertIsNotNone(row)
        self.assertEqual(row["application_id"], "")
        self.assertEqual(row["evidence_class"], "PROJECT_INDEX_SIGNAL")
        self.assertEqual(row["published_date"], "")

    def test_policy_reference_is_not_project_application(self):
        base = "https://example.gov/studies"
        row = _candidate("Niagara", "MASTER_SERVICING_POLICY", base,
                         "Water and wastewater master servicing plan",
                         "https://example.gov/studies/master-plan")
        self.assertEqual(row["evidence_class"], "POLICY_REFERENCE")
        self.assertFalse(row["application_id"])

    def test_report_separates_successful_index_from_applications(self):
        sources = {"York": {"url": "https://example.gov/projects", "kind": "INFRASTRUCTURE_INDEX"}}
        html = '<main><a href="/projects/road-improvement">Road improvement construction project</a></main>'
        with tempfile.TemporaryDirectory() as temp:
            report = run(temp, sources=sources, fetcher=lambda url: html, today=__import__("datetime").date(2026, 11, 4))
            self.assertEqual(report["authorities_with_records"], 1)
            self.assertEqual(report["application_id_records"], 0)
            self.assertEqual(report["project_index_signals"], 1)
            with (Path(temp) / "GTA_RADAR_REGIONAL_EARLY_RECORDS.csv").open(encoding="utf-8-sig") as fp:
                records = list(csv.DictReader(fp))
            self.assertEqual(records[0]["evidence_class"], "PROJECT_INDEX_SIGNAL")


if __name__ == "__main__":
    unittest.main()
