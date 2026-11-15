"""Offline commercial qualification tests: source-backed project, contacts, checks.

No real DeepSeek or paid requests; tests use synthetic independent developer
announcements and provider Search/Fetch/JSON responses.
"""
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from gta_announcement_commercial_qualification import (
    _accepted_claims, _discovery, _public_contacts, qualify,
)

DAY = dt.date(2026, 11, 15)
SOURCE = (
    "Harbourlight Developments announced acquisition of Northfield Works "
    "in Brampton, Ontario, in partnership with Atlas Capital. "
    "The project is planned for a 90,000 square foot industrial condo site "
    "on Willow Drive. Construction anticipated to begin Q3 2027."
)
MODEL = {"projects": [{
    "project_name": "Northfield Works", "city": "Brampton",
    "location_text": "Willow Drive", "construction_timing": "Q3 2027",
    "claims": [
        {"kind": "developer", "subject": "Harbourlight Developments",
         "source_index": 0,
         "quote": "Harbourlight Developments announced acquisition of Northfield Works"},
        {"kind": "partner", "subject": "Atlas Capital", "source_index": 0,
         "quote": "in partnership with Atlas Capital"},
    ],
}]}
CONTACT = ("Harbourlight Developments official contact. "
           "Please email office@harbourlight.example for business enquiries.")


class AnnouncementQualificationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        p = self.root / "GTA_RADAR_INVESTMENT_DISCOVERY"
        p.mkdir()
        self.discovery_path = p / "INVESTMENT_original_RECONCILED.json"
        self.discovery_path.write_text(json.dumps({
            "city": "Brampton",
            "model_status": "OK",
            "source_pages": [{"url": "https://example.org/announcement",
                              "content": SOURCE,
                              "fetched_on_not_publication": "2026-11-15"}],
            "model_output_excerpt": json.dumps(MODEL),
            "discovered_projects": [{
                "project_name": "Northfield Works", "city": "Brampton",
                "location_text": "Willow Drive",
                "companies": [{"kind": "developer",
                               "subject": "Harbourlight Developments"}]}],
        }), encoding="utf-8")

    def test_preflight_reuses_discovery_without_api_or_budget(self):
        output = qualify(self.root, project_name="Northfield Works",
                         day=DAY)
        self.assertEqual(output["status"], "PREFLIGHT_NO_SPEND")
        self.assertEqual(output["project"]["project_name"], "Northfield Works")
        self.assertEqual(len(output["evidence"]), 1)
        self.assertEqual(output["evidence"][0]["fetched_on"], "2026-11-15")
        self.assertEqual(output["evidence"][0]["published_on"], "UNKNOWN")
        self.assertEqual(output["model_calls"], 0)
        self.assertFalse(output["municipal_application_verified"])
        self.assertFalse((self.root / "v5_ai_budget.sqlite").exists())

    def test_exact_source_link_needed_not_company_hardcoding(self):
        with self.assertRaisesRegex(ValueError,
                                    "EXACT_CITED_DISCOVERY_NOT_FOUND"):
            qualify(self.root, project_name="Other Project", day=DAY,
                    paid=True, token="fake",
                    transport=lambda *_: self.fail("Never spend for wrong name"))

    def test_paid_company_search_and_one_ai_synthesis_and_checkpoint(self):
        calls = []
        def provider(endpoint, payload):
            calls.append(endpoint)
            if endpoint == "/v1/tools/search":
                return {"results": [
                    {"url": "https://harbourlight.example/contact",
                     "title": "Harbourlight Developments business contact",
                     "snippet": "Harbourlight Developments official contact"},
                    {"url": "https://example.org/other",
                     "title": "Unrelated supplier catalog",
                     "snippet": "completely unrelated"},
                ]}
            if endpoint == "/v1/tools/fetch":
                self.assertEqual(payload["url"],
                                 "https://harbourlight.example/contact")
                return {"content": CONTACT}
            if endpoint == "/chat/completions":
                self.assertEqual(payload["response_format"],
                                 {"type": "json_object"})
                packet = json.loads(payload["messages"][1]["content"])
                self.assertEqual(packet["project"]["name"], "Northfield Works")
                self.assertEqual(len(packet["sources"]), 2)
                self.assertIn("Harbourlight Developments",
                              packet["sources"][1]["text"])
                return {"choices": [{"finish_reason": "stop",
                                     "message": {"content": json.dumps({
                    "classification": "HOLD",
                    "commercial_reason": "Project announced; construction planned",
                    "timing_risks": "Current procurement stage not known",
                    "procurement_status": "OPEN",
                    "possible_supplier_trades": ["Electrical", "HVAC"],
                    "next_specific_verification":
                        "Ask the developer whether sourcing is underway",
                    "source_claims": [
                        {"kind": "company",
                         "subject": "Harbourlight Developments",
                         "source_index": 0,
                         "quote":
                         "Harbourlight Developments announced acquisition of Northfield Works"},
                        {"kind": "contact",
                         "subject": "Harbourlight Developments",
                         "source_index": 1, "quote": CONTACT},
                    ]})}}],
                    "usage": {"prompt_tokens": 800, "completion_tokens": 200}}
            self.fail(endpoint)
        result = qualify(self.root, project_name="Northfield Works",
                         paid=True, token="test", transport=provider,
                         day=DAY,
                         customer_profile="Industrial HVAC contractors")
        self.assertEqual(result["status"],
                         "RESEARCH_READY_HUMAN_COMMERCIAL_REVIEW")
        self.assertEqual(result["model_calls"], 1)
        self.assertEqual(result["assessment"]["classification"], "HOLD")
        self.assertEqual(result["assessment"]["procurement_status"], "UNKNOWN")
        self.assertFalse(result["open_supplier_contract_verified"])
        self.assertFalse(result["purchasing_authority_verified"])
        self.assertFalse(result["outreach_authorized"])
        self.assertEqual(len(result["accepted_claims"]), 2)
        self.assertEqual(
            result["public_contact_routes"][0]["channel"],
            "office@harbourlight.example")
        self.assertEqual(calls.count("/chat/completions"), 1)
        self.assertEqual(calls.count("/v1/tools/search"), 3)
        self.assertEqual(calls.count("/v1/tools/fetch"), 1)
        with (self.root / "GTA_RADAR_EARLY_INVESTMENT_LEADS.csv").open(
                newline="", encoding="utf-8") as stream:
            lead = list(csv.DictReader(stream))
        self.assertEqual(len(lead), 1)
        self.assertEqual(lead[0]["project_name"], "Northfield Works")
        self.assertEqual(lead[0]["municipal_match"], "UNRESOLVED")
        self.assertEqual(lead[0]["verified_open_contract"], "false")
        again = qualify(self.root, project_name="Northfield Works",
                        paid=True, token="test", transport=lambda *_:
                        self.fail("No duplicate calls"), day=DAY,
                        customer_profile="Industrial HVAC contractors")
        self.assertTrue(again["checkpoint_reused"])

    def test_contact_is_not_a_confirmed_project_buyer(self):
        page = [{"url": "https://example.org/company/contact",
                 "content": CONTACT,
                 "relationship": "NAMED_COMPANY_ONLY_NOT_PROJECT",
                 "company_names": ["Harbourlight Developments"]}]
        leads = _public_contacts(page, ["Harbourlight Developments"])
        self.assertEqual(len(leads), 1)
        self.assertTrue(leads[0]["publicly_listed"])
        self.assertFalse(leads[0]["purchasing_authority_verified"])
        self.assertFalse(leads[0]["project_procurement_role_verified"])

    def test_invented_procurement_claim_is_discarded(self):
        sources = [{"url": "https://example.org/announcement",
                    "content": SOURCE}]
        parsed = {"source_claims": [
            {"kind": "company", "subject": "Imaginary Corp",
             "source_index": 0, "quote": "Imaginary Corp supplies steel"},
            {"kind": "procurement", "subject": "OPEN",
             "source_index": 0, "quote": "Unawarded $10m HVAC contract"},
        ]}
        self.assertEqual(_accepted_claims(parsed, sources), [])


if __name__ == "__main__":
    unittest.main()
