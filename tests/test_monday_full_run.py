"""Integrated launcher acceptance: source collection once, bounded pilots, honest holds."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import gta_monday_full_run as monday


class MondayIntegrationTests(unittest.TestCase):
    def test_stage_order_one_collection_no_second_paid_ai_or_unbounded_ero(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            stages = monday.stages(ws, ws / "GTA_RADAR_RESULTS")
            self.assertEqual([s[0] for s in stages], [
                "daily_radar", "industrial_equipment", "commercial_activation",
                "facility_evidence", "toronto_20_source_research",
                "ai_harness_free"])
            self.assertEqual(sum("gta_total_intelligence_run.py" in s[1]
                                 for s in stages), 1)
            self.assertEqual(sum("gta_agent_harness.py" in s[1]
                                 for s in stages), 1)
            industrial = stages[1][1]
            self.assertEqual(industrial[industrial.index("--limit") + 1], "10")
            self.assertNotIn("--paid", stages[-1][1])
            self.assertNotIn("--fetch", stages[-2][1])
            self.assertNotIn("--live-ckan", stages[-2][1])

    def test_complete_run_writes_six_stage_manifest_and_html(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            calls = []
            def fake_run(command, **kwargs):
                calls.append(command)
                return type("Result", (), {"returncode": 0})()
            with patch.object(monday, "find_workspace", return_value=ws):
                result = monday.execute(ws, runner=fake_run)
            self.assertEqual(result, 0)
            self.assertEqual(len(calls), 6)
            report = json.loads((ws / "GTA_RADAR_RESULTS" /
                "MONDAY_FULL_RADAR" / monday.REPORT).read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "ALL_STAGES_RAN_REVIEW_ONLY")
            self.assertTrue(report["fresh_collection_verified"])
            self.assertEqual(report["stage_successes"], 6)
            self.assertFalse(report["buyer_verified_by_integration"])
            self.assertFalse(report["open_supplier_contract_verified_by_integration"])
            self.assertFalse(report["outreach_performed"])
            self.assertTrue((ws / "GTA_RADAR_RESULTS" /
                             "MONDAY_FULL_RADAR" / monday.INDEX).is_file())

    def test_failures_are_visible_and_do_not_stop_remaining_review_stages(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            calls = []
            def fail_first(command, **kwargs):
                calls.append(command)
                return type("Result", (), {
                    "returncode": 2 if len(calls) in (1, 3) else 0
                })()
            with patch.object(monday, "find_workspace", return_value=ws):
                code = monday.execute(ws, runner=fail_first)
            self.assertEqual(code, 2)
            self.assertEqual(len(calls), 6)
            record = json.loads((ws / "GTA_RADAR_RESULTS" /
                "MONDAY_FULL_RADAR" / monday.REPORT).read_text(encoding="utf-8"))
            self.assertFalse(record["fresh_collection_verified"])
            self.assertEqual(record["failed_stages"],
                             ["daily_radar", "commercial_activation"])
            self.assertEqual(record["status"], "REVIEW_COMPLETED_WITH_FAILURES")

    def test_historical_only_mode_cannot_claim_new_collection(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            def fake_run(command, **kwargs):
                return type("Result", (), {"returncode": 0})()
            with patch.object(monday, "find_workspace", return_value=ws):
                self.assertEqual(monday.execute(ws, skip_collection=True,
                                                runner=fake_run), 0)
            report = json.loads((ws / "GTA_RADAR_RESULTS" /
                "MONDAY_FULL_RADAR" / monday.REPORT).read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "SAVED_DATA_REVIEW_ONLY_NO_NEW_COLLECTION")
            self.assertFalse(report["collection_performed"])
            self.assertFalse(report["fresh_collection_verified"])
            self.assertEqual(len(report["stages"]), 5)

    def test_refuses_more_than_ten_notice_fetches(self):
        with self.assertRaises(ValueError):
            monday.execute(industrial_limit=11)
        with self.assertRaises(ValueError):
            monday.execute(industrial_limit=-1)


if __name__ == "__main__":
    unittest.main()
