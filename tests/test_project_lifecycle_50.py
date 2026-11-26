import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import gta_project_lifecycle_50 as lc


class LifecycleTest(unittest.TestCase):
    def test_seed_count_and_preview_no_calls(self):
        self.assertEqual(len(lc.load_seeds()), 50)
        with tempfile.TemporaryDirectory() as root:
            with patch.object(lc.native, "request", side_effect=AssertionError("No paid call")):
                result = lc.run(root, today=dt.date(2026,11,26))
            self.assertEqual(result["watchlist_count"], 50)
            self.assertEqual(result["ai_reviewed_today"], 0)
            with (Path(root) / lc.CSV).open(encoding="utf-8-sig", newline="") as fp:
                self.assertEqual(len(list(csv.DictReader(fp))), 50)

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
            result = lc.run(root, paid=True, key="", today=dt.date(2026,11,26))
            self.assertEqual(result["counts"], {"MISSING_API_KEY": 50})

    def test_query_source_rotation(self):
        p = lc.load_seeds()[0]
        self.assertNotEqual(lc.queries(p, "2026-11-26")[1], lc.queries(p, "2026-11-27")[1])


if __name__ == "__main__":
    unittest.main()
