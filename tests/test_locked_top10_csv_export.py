"""Windows/Excel locked CSV regression: no paid rerun or stale report masquerading."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gta_commercial_qualification_review import (
    CLIENT, TOP_OUT, REPORT, run as qualification_run,
)
from gta_ai_project_intelligence_refresh import run as refresh_run


class LockedCsvFallbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.old_top = self.root / TOP_OUT
        self.old_top.write_text("OLD_CURRENTLY_OPEN_IN_EXCEL", encoding="utf-8")
        data = {
            "opportunity_id": "NEW_ID",
            "application_ids": "NEW_FILING_2026",
            "city": "Brampton",
            "address": "123 Industrial Road, Brampton",
            "nature_of_work": "Industrial manufacturing warehouse expansion",
            "source_event_date": "2026-11-13",
            "source_event_date_basis": "OFFICIAL_FILING_DATE_NOT_PUBLICATION",
            "stage_gate": "Under Review",
            "source_url": "https://www.brampton.ca/current-project/NEW_FILING_2026",
        }
        with (self.root / CLIENT).open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=data.keys())
            writer.writeheader()
            writer.writerow(data)

    def locked_replace(self):
        original_replace = Path.replace
        def call(path, target):
            if Path(target).name == TOP_OUT and path.name.endswith(".csv.tmp"):
                raise PermissionError(13, "File is in use by Excel", str(target))
            return original_replace(path, target)
        return call

    def test_closed_csv_still_uses_canonical_output(self):
        result = qualification_run(self.root)
        self.assertEqual(result["top10_export_status"], "CANONICAL_UPDATED")
        self.assertTrue(result["canonical_top10_updated"])
        self.assertEqual(Path(result["outputs"]["top10_analyst_csv"]), self.old_top)
        self.assertIn("NEW_ID", self.old_top.read_text(encoding="utf-8-sig"))
        self.assertEqual(result["paid_ai_calls"], 0)

    def test_excel_locked_canonical_keeps_original_and_writes_new_report(self):
        with patch.object(Path, "replace", autospec=True, side_effect=self.locked_replace()):
            result = qualification_run(self.root)
        self.assertEqual(result["top10_export_status"],
                         "CANONICAL_LOCKED_UPDATED_ALTERNATE_WRITTEN")
        self.assertFalse(result["canonical_top10_updated"])
        self.assertEqual(self.old_top.read_text(encoding="utf-8"),
                         "OLD_CURRENTLY_OPEN_IN_EXCEL")
        actual = Path(result["outputs"]["top10_analyst_csv"])
        self.assertTrue(actual.is_file())
        self.assertNotEqual(actual, self.old_top)
        self.assertTrue(actual.name.startswith(
            "GTA_RADAR_COMMERCIAL_TOP10_ANALYST_REVIEW_UPDATED_"))
        with actual.open("r", newline="", encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["record_id"], "NEW_ID")
        self.assertIn("locked", result["warning_if_locked"].lower())
        self.assertFalse((self.root / (TOP_OUT + ".tmp")).exists())
        summary = json.loads((self.root / REPORT).read_text(encoding="utf-8"))
        self.assertEqual(summary["outputs"]["top10_analyst_csv"], str(actual))
        self.assertFalse(summary["canonical_top10_updated"])
        self.assertEqual(summary["paid_ai_calls"], 0)

    def test_offline_refresh_uses_actual_fallback_path_not_stale_canonical(self):
        with patch.object(Path, "replace", autospec=True, side_effect=self.locked_replace()):
            status = refresh_run(self.root)
        self.assertEqual(status["top10_export_status"],
                         "CANONICAL_LOCKED_UPDATED_ALTERNATE_WRITTEN")
        self.assertFalse(status["canonical_top10_updated"])
        latest = Path(status["latest_top10_analyst_csv"])
        self.assertTrue(latest.is_file())
        self.assertNotEqual(latest, self.old_top)
        self.assertEqual(status["outputs"]["commercial_analyst_top10"], str(latest))
        self.assertEqual(status["new_paid_ai_calls"], 0)
        self.assertEqual(status["verified_buyers"], 0)
        self.assertEqual(status["qualified_sale_ready_leads"], 0)


if __name__ == "__main__":
    unittest.main()
