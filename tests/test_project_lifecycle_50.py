import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from gta_lifecycle_baseline import PROJECT_IDS, WORKBOOK, install_baseline

import gta_project_lifecycle_50 as lc


class LifecycleTest(unittest.TestCase):
    def test_seed_count_and_preview_no_calls(self):
        self.assertEqual(len(lc.load_seeds()), 50)
        with tempfile.TemporaryDirectory() as root:
            with patch.object(lc.native, "request", side_effect=AssertionError("No paid call")):
                result = lc.run(root, baseline_path=None, today=dt.date(2026,11,26))
            self.assertEqual(result["watchlist_count"], 50)
            self.assertEqual(result["ai_reviewed_today"], 0)
            with (Path(root) / lc.CSV).open(encoding="utf-8-sig", newline="") as fp:
                self.assertEqual(len(list(csv.DictReader(fp))), 50)

    def test_private_baseline_import_preserves_ids_and_no_cost_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "source.zip"
            rows = [{"project_id": pid, "name": f"Company {pid}", "search_name": f"Company {pid}",
                     "location": "Oakville", "scope_hint": "Machinery upgrade",
                     "lifecycle": "Historical evidence", "equipment": "Forming press",
                     "timing": "Unknown"} for pid in sorted(PROJECT_IDS)]
            with ZipFile(archive_path, "w") as archive:
                for path in (WORKBOOK, "investigation_tables.json", "START_HERE.md", "DeepSeek_Method.md"):
                    archive.writestr(path, "test fixture")
                for pid in PROJECT_IDS:
                    archive.writestr(f"reports/{pid}.md", "test report")
                archive.writestr("baseline.json", json.dumps({
                    "schema": 1, "reviewed_on": "2026-11-26", "projects": rows}))
            active = root / "data/lifecycle/baseline.zip"
            imported = install_baseline(archive_path, active)
            self.assertEqual(install_baseline(archive_path, active), imported)
            self.assertEqual(Path(imported["snapshot_file"]).read_bytes(), archive_path.read_bytes())
            with patch.object(lc.native, "request", side_effect=AssertionError("No paid call")):
                result = lc.run(root, baseline_path=active, today=dt.date(2026, 11, 27))
                routine = lc.run(root, baseline_path=active, paid=True, key="", today=dt.date(2026, 11, 27))
            self.assertEqual(result["watchlist_count"], 100)
            self.assertEqual(result["ai_reviewed_today"], 0)
            self.assertEqual(routine["counts"], {"BASELINE_IMPORTED_REVIEW_PENDING": 50, "MISSING_API_KEY": 50})
            with (root / lc.CSV).open(encoding="utf-8-sig", newline="") as handle:
                output = list(csv.DictReader(handle))
            self.assertEqual({row["project_id"] for row in output}, PROJECT_IDS)
            self.assertEqual(output[0]["project"], "Ford Canada")
            self.assertEqual(output[-1]["baseline_date"], "2026-11-26")
            self.assertEqual(output[-1]["baseline_equipment"], "Forming press")
            self.assertEqual(output[-1]["verified_open_contract"], "False")

    def test_unsupported_quote_and_identity_cannot_promote(self):
        pages = [{"id": 1, "text": "Company opened a facility."}]
        raw = {"identity": {"status": "MATCHED", "evidence_ids": [999]},
               "stage": "PROCUREMENT", "stage_evidence_ids": [1],
               "change_status": "NEW_EVIDENCE",
               "packages": [{"scope": "HVAC", "evidence_ids": [1], "quote": "Open tender"}]}
        result = lc.verified_review(raw, pages)
        self.assertEqual(result["stage"], "UNKNOWN")
        self.assertEqual(result["packages"], [])
        self.assertEqual(result["change_status"], "INSUFFICIENT_EVIDENCE")

    def test_documented_package_stays_review_only(self):
        pages = [{"id": 1, "text": "Company announced an equipment tender."}]
        raw = {"identity": {"status": "MATCHED", "evidence_ids": [1]},
               "stage": "PROCUREMENT", "stage_evidence_ids": [1],
               "packages": [{"scope": "equipment", "basis": "DOCUMENTED",
                             "status": "TENDER_PUBLISHED", "evidence_ids": [1],
                             "quote": "equipment tender"}]}
        result = lc.verified_review(raw, pages)
        self.assertEqual(result["packages"][0]["status"], "UNKNOWN")
        self.assertFalse(result["packages"][0]["open_contract_verified"])

    def test_missing_key_preserves_all_projects(self):
        with tempfile.TemporaryDirectory() as root:
            result = lc.run(root, baseline_path=None, paid=True, key="", today=dt.date(2026,11,26))
            self.assertEqual(result["counts"], {"MISSING_API_KEY": 50})

    def test_query_source_rotation(self):
        p = lc.load_seeds()[0]
        self.assertNotEqual(lc.queries(p, "2026-11-26")[1], lc.queries(p, "2026-11-27")[1])


if __name__ == "__main__":
    unittest.main()
