import csv, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

import gta_execute_ai_project_research as ex
import v8_deepseek_native as native

FIELDS = ["project_id", "address", "source_id", "source_keys", "record_source_url",
          "description", "current_source_status", "company_name"]
URL = "https://www.toronto.ca/planning"
STRONG = "Construct a new one-storey 120,000 sq ft cold storage warehouse with rooftop HVAC and sprinkler"
WEAK = "Interior alterations to existing basement; drain and backflow"
HOUSE = "Minor variance for a three-storey detached dwelling"


def write_queue(path, rows):
    with path.open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({**{k: "" for k in FIELDS}, **r})


def row(pid, desc, status="Under Review", company=""):
    return {"project_id": pid, "address": pid + " Test Road", "source_id": "toronto_active_building_permits",
            "source_keys": pid, "record_source_url": URL, "description": desc,
            "current_source_status": status, "company_name": company}


class ExecutorHardeningTests(unittest.TestCase):
    def run_paid(self, rows, **kw):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        queue = root / "q.csv"
        write_queue(queue, rows)
        seen = []

        def fake_fetch(planned, *a, **k):
            seen.append(planned["project_id"])
            return ([{"url": URL, "text": "page text", "page_identity": "EXACT_CURRENT_PERMIT_ID_IN_PAGE"}],
                    {"search": 1, "fetch": 1})
        analyze = kw.pop("analyze", None) or (lambda *a, **k: ({"owner": ""}, 0.0007))
        with patch.object(ex.native, "fetch_native", side_effect=fake_fetch), \
             patch.object(ex.native, "analyze", side_effect=analyze):
            state = ex.execute(queue, root, root / "review", paid=True, key="mock", **kw)
        return root, state, seen

    def test_strong_project_is_researched_before_weak_ones(self):
        rows = [row("WEAK1", WEAK), row("HOUSE1", HOUSE), row("STRONG1", STRONG)]
        _, state, seen = self.run_paid(rows, max_projects=3)
        self.assertEqual(seen, ["STRONG1"])          # only the strong one clears the threshold
        self.assertEqual(state["selection"]["eligible_for_paid_ai"], 1)
        self.assertEqual(state["selection"]["below_threshold"], 2)

    def test_nothing_eligible_means_zero_paid_calls(self):
        _, state, seen = self.run_paid([row("WEAK1", WEAK), row("HOUSE1", HOUSE)])
        self.assertEqual(seen, [])
        self.assertEqual(state["status"], "NO_ELIGIBLE_PROJECTS_ABOVE_THRESHOLD")
        self.assertEqual(state["attempted"], 0)

    def test_public_body_never_gets_paid_ai(self):
        rows = [row("PUB1", STRONG, company="Toronto District School Board")]
        _, state, seen = self.run_paid(rows)
        self.assertEqual(seen, [])
        self.assertEqual(state["selection"]["excluded_public_body"], 1)

    def test_ranking_order_when_several_are_eligible(self):
        big = row("BIG", STRONG)
        mid = row("MID", "Construct a new 25,000 sq ft warehouse addition", status="Applied")
        _, _, seen = self.run_paid([mid, big], max_projects=3)
        self.assertEqual(seen, ["BIG", "MID"])

    def test_model_failure_keeps_paid_evidence_and_records_class(self):
        def boom(*a, **k):
            raise native.ModelResponseError("EMPTY_CONTENT", "Model returned empty content", "", 0.0004)
        root, state, _ = self.run_paid([row("STRONG1", STRONG)], analyze=boom)
        review = root / "review"
        evidence = list(review.glob("AI_PROJECT_*_EVIDENCE_*.json"))
        failures = list(review.glob("AI_PROJECT_*_FAILURE_*.json"))
        self.assertEqual(len(evidence), 1)            # paid evidence survived
        self.assertEqual(len(failures), 1)
        self.assertEqual(len(list(review.glob("AI_PROJECT_????????????????.json"))), 0)
        record = json.loads(failures[0].read_text(encoding="utf-8"))
        self.assertEqual(record["failure_class"], "EMPTY_CONTENT")
        self.assertEqual(record["cost_usd"], 0.0004)
        entry = state["audit"][0]
        self.assertEqual(entry["status"], "MODEL_FAILURE")
        self.assertEqual(entry["failure_class"], "EMPTY_CONTENT")
        self.assertTrue(entry["error_reason"])
        self.assertTrue((review / "AI_PROJECT_RESEARCH_MANIFEST.json").is_file())

    def test_manifest_written_even_when_loop_crashes(self):
        def crash(*a, **k):
            raise RuntimeError("unexpected")
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        write_queue(root / "q.csv", [row("STRONG1", STRONG)])
        with patch.object(ex.native, "fetch_native", return_value=([], {"search": 0, "fetch": 0})), \
             patch.object(ex, "_write_new", side_effect=crash):
            with self.assertRaises(RuntimeError):
                ex.execute(root / "q.csv", root, root / "review", paid=True, key="mock")
        manifest = json.loads((root / "review" / "AI_PROJECT_RESEARCH_MANIFEST.json").read_text())
        self.assertEqual(manifest["status"], "INTERRUPTED_BY_ERROR")

    def test_budget_limit_reported_is_the_central_setting(self):
        from radar_config import DEEPSEEK_DAILY_LIMIT_USD
        _, state, _ = self.run_paid([row("STRONG1", STRONG)])
        self.assertEqual(state["deepseek_budget_limit_usd"], DEEPSEEK_DAILY_LIMIT_USD)

    def test_preflight_costs_nothing_and_shows_selection(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        write_queue(root / "q.csv", [row("STRONG1", STRONG), row("WEAK1", WEAK)])
        with patch.object(ex.native, "fetch_native") as fetch:
            state = ex.execute(root / "q.csv", root, root / "review")
        fetch.assert_not_called()
        self.assertEqual(state["selection"]["top"][0]["project_id"], "STRONG1")


if __name__ == "__main__":
    unittest.main()
