"""Offline harness tests: default no-spend, evidence safety, resume and failure."""
import csv
import hashlib
import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

import gta_agent_harness as harness
from radar_config import DEEPSEEK_DAILY_LIMIT_USD

URL = "https://www.toronto.ca/planning"


def sample_csv(root):
    path = root / "GTA_RADAR_V8_PENDING_QUEUE.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "project_id", "address", "source_id", "source_keys",
            "record_source_url", "description", "current_source_status",
        ])
        writer.writeheader()
        writer.writerow({
            "project_id": "TEST-42", "address": "100 Test Road",
            "source_id": "toronto", "source_keys": "APP-42",
            "record_source_url": URL,
            "description": ("Construct new one-storey 120,000 sq ft industrial "
                            "cold storage warehouse with rooftop HVAC and fire sprinklers"),
            "current_source_status": "Under Review",
        })
    return path


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.queue = sample_csv(self.root)
        self.out = self.root / "HARNESS"

    def _sample_row(self):
        return harness.locate_candidates(self.root, self.queue)[1][0]

    def _save_review(self, *, sources, stale=False):
        row = self._sample_row()
        path = harness.review_paths(self.out / "PROJECT_RESEARCH", row)[0]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "project_id": row["project_id"],
            "input_hash": "obsolete" if stale else harness.input_hash(row),
            "research_status": "AI_REVIEW_ONLY",
            "sources": sources,
            "model_suggestions": {"developer": "UNVERIFIED MODEL GUESS"},
            "sale_ready": False,
        }), encoding="utf-8")
        return path

    def test_default_does_not_lock_spend_or_promote(self):
        with patch.object(harness, "execute_project_research") as paid, \
             patch.object(harness, "once_lock") as lock:
            result = harness.run(self.root, self.out)
        paid.assert_not_called()
        lock.assert_not_called()
        self.assertEqual(result["status"], "PREFLIGHT_READY_NO_SPEND")
        self.assertEqual(result["daily_deepseek_cap_usd"], DEEPSEEK_DAILY_LIMIT_USD)
        self.assertEqual(result["verified_leads_created"], 0)
        self.assertFalse(result["production_promotion"])
        self.assertTrue(result["projects"])
        self.assertTrue(result["projects"][0]["planned_tasks"])
        self.assertEqual(result["metrics"]["saved_current_input_reviews"], 0)
        self.assertTrue((self.out / "AI_HARNESS_EVENTS.jsonl").is_file())

    def test_paid_opt_in_calls_existing_executor_under_shared_lock(self):
        sequence = []

        def lock(root):
            self.assertEqual(root, self.root)
            sequence.append("lock")
            return nullcontext()

        def fake_execute(source, results, review, **kw):
            self.assertEqual(source, self.queue)
            self.assertEqual(results, self.root)
            self.assertTrue(kw["paid"])
            self.assertEqual(kw["max_projects"], 1)
            sequence.append("execute")
            self._save_review(sources=[
                {"url": URL, "page_identity": harness.EXACT_IDENTITY},
            ])
            return {"status": "REVIEW_ONLY_RESULTS", "attempted": 1,
                    "completed": 1, "budget_used_or_held_usd": 0.007}

        result = harness.run(
            self.root, self.out, paid=True, max_projects=1,
            executor=fake_execute, acquire_lock=lock,
        )
        self.assertEqual(sequence, ["lock", "execute"])
        self.assertEqual(result["metrics"]["exact_id_source_review_candidates"], 1)
        self.assertEqual(result["verified_leads_created"], 0)
        self.assertEqual(result["metrics"]["verified_commercial_leads"], 0)
        self.assertFalse(result["production_promotion"])
        self.assertFalse(result["projects"][0]["evidence_gate"]["verified_lead"])

    def test_only_fetched_project_context_is_accepted(self):
        gate = harness.evidence_gate({
            "sources": [
                {"url": URL, "page_identity": harness.CONTEXT_ONLY},
                {"url": "https://somewhere.example", "page_identity": "SEARCH_ONLY"},
                {"url": "http://insecure.example", "page_identity": harness.EXACT_IDENTITY},
            ],
            "model_suggestions": {"buyer": "Guess"},
        })
        self.assertEqual(gate["status"], "PROJECT_CONTEXT_REVIEW_ONLY")
        self.assertEqual(gate["accepted_source_pages"], 1)
        self.assertEqual(gate["exact_project_id_source_pages"], 0)
        self.assertTrue(gate["human_review_required"])

    def test_stale_checkpoint_is_not_accepted(self):
        self._save_review(
            sources=[{"url": URL, "page_identity": harness.EXACT_IDENTITY}],
            stale=True,
        )
        result = harness.run(self.root, self.out)
        self.assertEqual(result["metrics"]["saved_current_input_reviews"], 0)
        self.assertEqual(result["projects"][0]["checkpoint"], "PENDING_OR_BUDGET_DEFERRED")

    def test_paid_failure_is_logged_and_never_reports_success(self):
        def boom(*args, **kwargs):
            raise RuntimeError("simulated interruption")
        with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
            harness.run(
                self.root, self.out, paid=True,
                executor=boom, acquire_lock=lambda _: nullcontext(),
            )
        record = json.loads(
            (self.out / "AI_HARNESS_STATUS.json").read_text(encoding="utf-8")
        )
        self.assertEqual(record["status"], "FAILED_SAFE")
        self.assertEqual(record["failure"]["type"], "RuntimeError")
        self.assertEqual(record["verified_leads_created"], 0)
        event = (self.out / "AI_HARNESS_EVENTS.jsonl").read_text(encoding="utf-8")
        self.assertIn("FAILED_SAFE", event)

    def test_work_limit_must_be_bounded(self):
        for value in (0, 11, -1):
            with self.assertRaises(ValueError):
                harness.run(self.root, self.out, max_projects=value)


if __name__ == "__main__":
    unittest.main()
