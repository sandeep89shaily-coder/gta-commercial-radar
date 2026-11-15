"""Offline acceptance: discover a previously unnamed industrial investment.

No real company, brand, street or project is seeded in the input queries.
A street-level coincidence is NOT a verified city application connection.
"""
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from gta_investment_announcement_discovery import (
    _citation_claims, _municipal_candidates, _safe_rows, run,
    search_queries, reconcile_saved,
)

DAY = dt.date(2026, 11, 15)
NEWS = (
    "Harbourlight Developments has acquired the Northfield Works industrial "
    "condominium site in Brampton in partnership with Atlas Capital. "
    "Northfield Works is planned for 90,000 square feet across 35 industrial "
    "units on Willow Drive, Brampton, Ontario, with construction expected "
    "in Q3 2027 and completion planned in 2028."
)
CLAIMS = [
    {"kind": "developer", "subject": "Harbourlight Developments",
     "source_index": 0,
     "quote": "Harbourlight Developments has acquired the Northfield Works industrial condominium site in Brampton"},
    {"kind": "partner", "subject": "Atlas Capital", "source_index": 0,
     "quote": "in partnership with Atlas Capital"},
    {"kind": "project", "subject": "Northfield Works", "source_index": 0,
     "quote": "Northfield Works is planned for 90,000 square feet across 35 industrial units on Willow Drive, Brampton, Ontario"},
    {"kind": "construction", "subject": "Q3 2027", "source_index": 0,
     "quote": "construction expected in Q3 2027 and completion planned in 2028"},
]


class GenericInvestmentDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self._municipal()

    def _municipal(self):
        path = self.root / "GTA_RADAR_V8_PENDING_QUEUE.csv"
        fields = ["project_id", "city", "address", "source_keys",
                  "description", "record_source_url"]
        with path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            writer.writerow({
                "project_id": "brampton_site_plan:SPA-2026-0089",
                "city": "Brampton", "address": "60 Willow Drive",
                "source_keys": "SPA-2026-0089",
                "description": "Three proposed industrial buildings",
                "record_source_url": "https://example.org/official"})
            writer.writerow({
                "project_id": "brampton_site_plan:SPA-2024-0100",
                "city": "Brampton", "address": "75 Willow Drive",
                "source_keys": "SPA-2024-0100",
                "description": "Older industrial site plan",
                "record_source_url": "https://example.org/older"})
            writer.writerow({
                "project_id": "toronto_site_plan:1",
                "city": "Toronto", "address": "60 Willow Drive",
                "source_keys": "1",
                "description": "Different city",
                "record_source_url": "https://example.org/other"})

    def test_free_preflight_has_generic_queries_only(self):
        result = run(self.root, city="Brampton", today=DAY)
        self.assertEqual(result["status"], "PREFLIGHT_NO_SPEND")
        self.assertEqual(result["local_project_candidates"], 2)
        self.assertEqual(result["search_calls"], 0)
        self.assertFalse((self.root / "v5_ai_budget.sqlite").exists())
        for query in result["search_queries"]:
            self.assertIn("Brampton", query)
            self.assertNotIn("Harbourlight", query)
            self.assertNotIn("Northfield", query)
            self.assertNotIn("Atlas", query)
            self.assertNotIn("Willow", query)

    def test_complete_unseeded_discovery_and_no_false_municipal_link(self):
        calls = []
        def provider(endpoint, payload):
            calls.append(endpoint)
            if endpoint == "/v1/tools/search":
                self.assertNotIn("Northfield", payload["query"])
                self.assertNotIn("Willow", payload["query"])
                return {"results": [
                    {"url": "https://example.org/developer-announcement",
                     "title": "Brampton new industrial condominium developer",
                     "snippet": "Industrial development in Brampton"},
                    {"url": "https://example.org/unrelated",
                     "snippet": "Unrelated pet supplies"},
                ]}
            if endpoint == "/v1/tools/fetch":
                self.assertEqual(payload["url"],
                                 "https://example.org/developer-announcement")
                return {"content": NEWS}
            if endpoint == "/chat/completions":
                data = json.loads(payload["messages"][1]["content"])
                self.assertEqual(len(data["sources"]), 1)
                return {"choices": [{"finish_reason": "stop", "message": {
                    "content": json.dumps({"projects": [{
                        "project_name": "Northfield Works",
                        "city": "Brampton",
                        "location_text": "Willow Drive, Brampton",
                        "construction_timing": "Q3 2027",
                        "claims": CLAIMS,
                    }]})}}],
                    "usage": {"prompt_tokens": 700, "completion_tokens": 280}}
            self.fail(endpoint)
        result = run(self.root, city="Brampton", paid=True,
                     today=DAY, token="test", transport=provider)
        self.assertEqual(result["status"],
                         "SOURCE_BACKED_DISCOVERY_NOT_SALE_QUALIFIED")
        self.assertEqual(result["search_calls"], 2)
        self.assertEqual(result["fetch_calls"], 1)
        self.assertEqual(result["model_calls"], 1)
        self.assertEqual(len(result["discovered_projects"]), 1)
        case = result["discovered_projects"][0]
        self.assertEqual(case["project_name"], "Northfield Works")
        self.assertEqual({x["subject"] for x in case["companies"]},
                         {"Harbourlight Developments", "Atlas Capital"})
        self.assertEqual(len(case["municipal_possible_links"]), 2)
        self.assertTrue(all(not x["same_project_confirmed"]
                            for x in case["municipal_possible_links"]))
        self.assertFalse(case["exact_municipal_application_confirmed"])
        self.assertEqual(case["verified_open_contracts"], 0)
        self.assertFalse(result["outreach_authorized"])
        self.assertEqual(calls.count("/chat/completions"), 1)
        reused = run(self.root, city="Brampton", paid=True, today=DAY,
                     token="test", transport=lambda *_:
                     self.fail("No repeat of paid provider calls"))
        self.assertTrue(reused["checkpoint_reused"])

    def test_direct_citation_must_include_verbatim_company(self):
        source = [{"url": "https://example.org/developer-announcement",
                   "content": NEWS}]
        answer = {"data": {"projects": [{
            "project_name": "Northfield Works", "city": "Brampton",
            "location_text": "Willow Drive",
            "claims": [
                {"kind": "developer", "subject": "Invented Builder",
                 "source_index": 0, "quote": CLAIMS[0]["quote"]},
                {"kind": "developer", "subject": "Harbourlight Developments",
                 "source_index": 0, "quote": "not in the original text"},
            ],
        }]}}
        self.assertEqual(_citation_claims(answer, source, "Brampton"), [])

    def test_unrelated_same_city_investor_is_not_joined_to_named_project(self):
        pages = [
            {"url": "https://example.org/northfield", "content": NEWS},
            {"url": "https://example.org/other-development",
             "content": "Atlas Capital is developing South Dock industrial "
                        "warehouses in Brampton with another company."},
        ]
        proposal = {"data": {"projects": [{
            "project_name": "Northfield Works", "city": "Brampton",
            "location_text": "Willow Drive, Brampton",
            "construction_timing": "Q3 2027",
            "claims": [
                CLAIMS[0], CLAIMS[2], CLAIMS[3],
                {"kind": "partner", "subject": "Atlas Capital",
                 "source_index": 1,
                 "quote": "Atlas Capital is developing South Dock industrial "
                          "warehouses in Brampton"},
            ],
        }]}}
        findings = _citation_claims(proposal, pages, "Brampton")
        self.assertEqual(len(findings), 1)
        self.assertEqual(
            {x["subject"] for x in findings[0]["companies"]},
            {"Harbourlight Developments"})

    def test_birchmount_style_name_recovered_from_developer_quote(self):
        source = [{"url": "https://example.org/developer",
                   "content": "Storytime Developments is pleased to announce "
                              "the acquisition of Ace Brampton, an approximately "
                              "six-acre industrial development site in Brampton, "
                              "Ontario, in partnership with Fiera Real Estate."}]
        data = {"data": {"projects": [{
            "project_name": "Ace Brampton", "city": "Brampton",
            "location_text": "", "construction_timing": "UNKNOWN",
            "claims": [
                {"kind": "developer", "subject": "Storytime Developments",
                 "source_index": 0,
                 "quote": source[0]["content"]},
                {"kind": "partner", "subject": "Fiera Real Estate",
                 "source_index": 0,
                 "quote": "in partnership with Fiera Real Estate"},
                {"kind": "project", "subject": "Ace Brampton",
                 "source_index": 0,
                 "quote": "six-acre industrial development site in Brampton"},
            ]}]}}
        found = _citation_claims(data, source, "Brampton")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["project_name"], "Ace Brampton")
        self.assertEqual([x["subject"] for x in found[0]["companies"]],
                         ["Storytime Developments", "Fiera Real Estate"])
        self.assertFalse(found[0]["verified_buyers"])

    def test_reconcile_saved_report_without_provider_calls(self):
        folder = self.root / "GTA_RADAR_INVESTMENT_DISCOVERY"
        folder.mkdir()
        source = {"url": "https://example.org/ace",
                  "content": "Storytime Developments announced the acquisition "
                             "of Ace Brampton in Brampton, Ontario, with "
                             "Fiera Real Estate."}
        payload = {"projects": [{
            "project_name": "Ace Brampton", "city": "Brampton",
            "location_text": "", "construction_timing": "UNKNOWN",
            "claims": [
                {"kind": "developer", "subject": "Storytime Developments",
                 "source_index": 0, "quote": source["content"]},
                {"kind": "partner", "subject": "Fiera Real Estate",
                 "source_index": 0, "quote": "with Fiera Real Estate"}
            ]}]}
        original = folder / "INVESTMENT_fakedigest.json"
        original.write_text(json.dumps({
            "city": "Brampton", "model_status": "OK",
            "model_output_excerpt": json.dumps(payload),
            "source_pages": [source], "discovered_projects": [{
                "project_name": "UNNAMED_PROJECT"}]}), encoding="utf-8")
        report = reconcile_saved(self.root, city="Brampton")
        self.assertEqual(report["paid_calls"], 0)
        self.assertEqual(report["discovered_projects"][0]["project_name"],
                         "Ace Brampton")
        self.assertEqual(json.loads(original.read_text())[
            "discovered_projects"][0]["project_name"], "UNNAMED_PROJECT")
        self.assertFalse((self.root / "v5_ai_budget.sqlite").exists())

    def test_exact_civic_mismatch_is_rejected(self):
        project = {"city": "Brampton", "location_text": "75 Willow Drive"}
        links = _municipal_candidates(project, _safe_rows(self.root))
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["municipal_address"], "75 Willow Drive")
        self.assertFalse(links[0]["same_project_confirmed"])

    def test_missing_civic_does_not_confirm_an_application(self):
        project = {"city": "Brampton", "location_text": "Willow Drive"}
        links = _municipal_candidates(project, _safe_rows(self.root))
        self.assertEqual(len(links), 2)
        self.assertTrue(all(x["identity"] ==
                            "UNVERIFIED_POSSIBLE_SAME_STREET"
                            for x in links))
        self.assertTrue(all(not x["same_project_confirmed"] for x in links))

    def test_nonbillable_failure_keeps_checkpoint(self):
        def provider(endpoint, payload):
            if endpoint == "/v1/tools/search":
                raise RuntimeError("Provider failed with unknown billing")
            self.fail("Should not reach another API call")
        failed = run(self.root, city="Brampton", paid=True,
                     today=DAY, token="test", transport=provider)
        self.assertIn("UNCERTAIN_RuntimeError", failed["status"])
        again = run(self.root, city="Brampton", paid=True, today=DAY,
                    token="test", transport=lambda *_: self.fail("No retry"))
        self.assertTrue(again["checkpoint_reused"])


if __name__ == "__main__":
    unittest.main()
