"""Offline regression tests for the standalone Top 10 DeepSeek probe."""
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from gta_ai_top10_company_probe import run

TODAY = dt.date(2026, 11, 15)


class DirectTop10CompanyProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        with (self.root / "GTA_RADAR_COMMERCIAL_TOP10_ANALYST_REVIEW.csv").open(
                "w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=[
                "record_id", "city", "address", "application_id",
                "project_description", "source_url"])
            writer.writeheader()
            writer.writerow({
                "record_id": "brampton:26-185633-000-00", "city": "Brampton",
                "address": "238 Glidden Road", "application_id": "26-185633-000-00",
                "project_description": "Industrial addition",
                "source_url": "https://example.org/permit"})

    def test_preflight_never_uses_provider_or_ledger(self):
        result = run(self.root, paid=False, today=TODAY)
        self.assertEqual(result["status"], "PREFLIGHT_ONLY")
        self.assertFalse((self.root / "v5_ai_budget.sqlite").exists())
        self.assertFalse((self.root /
                          "GTA_RADAR_TOP10_DEEPSEEK_COMPANY_PROBE_2026-11-15.json"
                          ).exists())

    def test_paid_probe_fetches_evidence_separately_and_reuses_checkpoint(self):
        calls = []
        def send(path, payload):
            calls.append(path)
            if path == "/chat/completions":
                return {
                    "choices": [{"finish_reason": "stop", "message": {
                        "content": "Brenntag likely present at site; purchasing unknown.",
                        "annotations": [{"url_citation": {
                            "url": "https://example.org/site"}}]}}],
                    "usage": {"prompt_tokens": 1100, "completion_tokens": 130,
                              "server_tool_use": {"tool_search": 1, "tool_fetch": 1}}
                }
            if path == "/v1/tools/fetch":
                return {"content":
                        "Brenntag Canada Inc., 238 Glidden Road, Brampton. Contact us."}
            self.fail("Unexpected API route")
        first = run(self.root, paid=True, token="test", today=TODAY,
                    transport=send)
        self.assertEqual(first["status"], "ALL_TOP10_RESEARCH_ATTEMPTED")
        self.assertEqual(first["attempted_count"], 1)
        self.assertEqual(first["completed_fetch_evidence"], 1)
        record = first["reviews"][0]
        self.assertIn("Brenntag", record["model_summary_research_hint_not_verified"])
        self.assertEqual(record["independently_fetched_context"][0]["identity"],
                         "SAME_ADDRESS_COMPANY_CONTEXT_NOT_LINKED")
        self.assertFalse(record["purchasing_authority_verified"])
        self.assertTrue(first["not_authorized_for_outreach"])
        again = run(self.root, paid=True, token="test", today=TODAY,
                    transport=lambda *_: self.fail("A second paid request is not allowed"))
        self.assertEqual(again["completed_fetch_evidence"], 1)
        self.assertEqual(calls, ["/chat/completions", "/v1/tools/fetch"])
        saved = json.loads((self.root /
            "GTA_RADAR_TOP10_DEEPSEEK_COMPANY_PROBE_2026-11-15.json"
            ).read_text(encoding="utf-8"))
        self.assertEqual(saved["attempted_count"], 1)


if __name__ == "__main__":
    unittest.main()
