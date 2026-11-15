"""Offline acceptance of all ten capabilities, evidence gating, checkpointing."""
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from gta_ai_ten_capabilities import STAGES, run, _evidence, _verified_claims

TODAY = dt.date(2026, 11, 15)
SOURCE_QUOTE = ("The previous proposal for a self-storage facility was "
                "replaced by a residential mixed-use development.")


class TenCapabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.record = {
            "record_id": "test:permit:2021", "city": "Toronto",
            "address": "611 Keele St, Toronto, ON",
            "application_id": "21170364S4505TLAB",
            "project_description": "Self-storage facility",
            "source_url": "https://example.org/permit"}
        with (self.root / "GTA_RADAR_COMMERCIAL_TOP10_ANALYST_REVIEW.csv").open(
                "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(self.record))
            writer.writeheader()
            writer.writerow(self.record)
        self.probe = self.root / (
            "GTA_RADAR_TOP10_DEEPSEEK_COMPANY_PROBE_2026-11-15_FROM_1_COUNT_1.json")
        self.probe.write_text(json.dumps({
            "reviews": [{
                "record_id": self.record["record_id"],
                "city": "Toronto", "model_summary_research_hint_not_verified":
                    "This assertion must NOT be treated as independent evidence",
                "independently_fetched_context": [
                    {"url": "https://example.org/independent-report",
                     "identity": "SAME_ADDRESS_PROJECT_CONTEXT_NOT_LINKED",
                     "excerpt": "611 Keele St, Toronto, ON. " + SOURCE_QUOTE,
                     "role_excerpt": "",
                     "retrieved_on": "2026-11-15"}
                ]}]}), encoding="utf-8")

    def test_preflight_is_free_and_exposes_ten_stages(self):
        result = run(self.root, today=TODAY)
        self.assertEqual(result["status"], "PREFLIGHT_NO_SPEND")
        self.assertEqual(len(STAGES), 10)
        self.assertEqual(result["results"][0]["available_source_count"], 1)
        self.assertFalse((self.root / "v5_ai_budget.sqlite").exists())

    def test_ten_model_stages_and_checkpoint_reuse(self):
        called = []
        def provider(path, payload):
            self.assertEqual(path, "/chat/completions")
            self.assertNotIn("tools", payload)
            stage = json.loads(payload["messages"][1]["content"])["stage"]
            called.append(stage)
            answer = {
                "classification": "SUPERSEDED" if
                    stage == "project_lifecycle_supersession" else "REVIEW",
                "rationale": "An independently fetched source describes change.",
                "claims": [{
                    "subject": "Former self-storage proposal",
                    "relationship": "Historical change",
                    "source_index": 0, "quote": SOURCE_QUOTE}],
                "unresolved": ["Official current permit status"],
                "next_action": "Verify the latest official planning file",
            }
            return {"choices": [{"finish_reason": "stop", "message": {
                "content": json.dumps(answer)}}],
                "usage": {"prompt_tokens": 700, "completion_tokens": 150}}
        first = run(self.root, paid=True, today=TODAY, token="test",
                    customer_profile="Industrial HVAC installers in Ontario",
                    transport=provider)
        self.assertEqual(first["status"], "CHECKPOINTED_AI_REVIEW")
        self.assertEqual(called, list(STAGES))
        dossier = json.loads(Path(first["results"][0]["dossier"]).read_text())
        self.assertEqual(list(dossier["stages"]), list(STAGES))
        for stage in STAGES:
            self.assertEqual(dossier["stages"][stage]["accepted_literal_claim_count"], 1)
            self.assertFalse(dossier["stages"][stage]["verified_buyer"])
        overlay = json.loads((self.root /
            "GTA_RADAR_AI_TEN_CAPABILITIES_OVERLAY.json").read_text())
        item = overlay["projects"][self.record["record_id"]]
        self.assertTrue(item["ai_lifecycle_review_hold"])
        self.assertFalse(item["verified_buyer"])
        self.assertEqual(item["city"], "Toronto")
        again = run(self.root, paid=True, today=TODAY, token="test",
                    customer_profile="Industrial HVAC installers in Ontario",
                    transport=lambda *_: self.fail("Duplicate paid AI request"))
        self.assertEqual(again["results"][0]["stages"],
                         first["results"][0]["stages"])
        self.assertEqual(len(called), 10)

    def test_quote_hallucination_is_not_supported(self):
        sources = _evidence(self.root, self.record, TODAY)
        self.assertEqual(len(sources), 1)
        self.assertEqual(_verified_claims({"claims": [{
            "subject": "Imaginary contractor", "relationship": "Confirmed",
            "source_index": 0, "quote":
                "Imaginary contractor won all unawarded trade packages"}]},
            sources), [])

    def test_missing_source_never_spends_on_invented_evidence(self):
        self.probe.unlink()
        called = []
        result = run(self.root, paid=True, today=TODAY, token="test",
                     customer_profile="Industrial HVAC",
                     transport=lambda *a: called.append(a))
        self.assertEqual(called, [])
        dossier = json.loads(Path(result["results"][0]["dossier"]).read_text())
        self.assertTrue(all(
            x["status"] == "NO_INDEPENDENT_EVIDENCE"
            for name, x in dossier["stages"].items()
            if name != "customer_specific_supplier_fit"))
        self.assertFalse(dossier["outreach_authorized"])

    def test_no_customer_profile_explicitly_holds_matching(self):
        result = run(self.root, paid=True, today=TODAY, token="test",
                     transport=lambda path, payload: {
                         "choices": [{"finish_reason": "stop",
                                      "message": {"content": json.dumps({
                                          "classification": "UNKNOWN",
                                          "claims": []})}}],
                         "usage": {"prompt_tokens": 750,
                                   "completion_tokens": 50}})
        dossier = json.loads(Path(result["results"][0]["dossier"]).read_text())
        self.assertEqual(dossier["stages"]["customer_specific_supplier_fit"][
            "status"], "CUSTOMER_PROFILE_REQUIRED")


if __name__ == "__main__":
    unittest.main()
