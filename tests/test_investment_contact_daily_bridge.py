"""Offline release tests: integrate discovery/qualification/contacts once.

Real DeepSeek, collector DB and web are never invoked.
"""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from gta_investment_contact_daily_bridge import run

DAY = dt.date(2026, 11, 16)
PROJECT = {
    "project_name": "Harbour Works", "city": "Brampton",
    "companies": [{"kind": "developer", "subject": "Harbourlight Inc."}],
    "sources_used": ["https://example.org/announced-development"],
}
DISCOVERY = {
    "status": "SOURCE_BACKED_DISCOVERY_NOT_SALE_QUALIFIED",
    "source_pages": [{"url": "https://example.org/announced-development",
                      "content": "Harbourlight Inc. announces Harbour Works."}],
    "discovered_projects": [PROJECT],
    "search_calls": 2, "fetch_calls": 1, "model_calls": 1,
}


class IntegratedInvestmentContactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_free_preflight_does_not_call_any_external_provider(self):
        def cannot_call(*a, **k):
            self.fail("No paid stage may run without explicit --paid")
        r = run(self.root, today=DAY, discoverer=cannot_call,
                qualifier=cannot_call, investigator=cannot_call)
        self.assertEqual(r["status"], "NO_SPEND_PREFLIGHT")
        self.assertFalse(r["paid_allowed"])
        self.assertTrue(Path(r["report_path"]).is_file())
        self.assertFalse((self.root / "v5_ai_budget.sqlite").exists())

    def test_paid_source_backed_company_integration_is_not_hardcoded_ace(self):
        calls = []
        def discoverer(root, **kwargs):
            calls.append(("discover", kwargs))
            return DISCOVERY
        def qualify(root, **kwargs):
            calls.append(("qualify", kwargs))
            return {
                "status": "RESEARCH_INCOMPLETE_CONTACT_OR_EVIDENCE",
                "assessment": {"classification": "HOLD"},
                "accepted_claims": [{"kind": "developer"}],
                "model_calls": 1,
                "report_path": "qualification.json",
            }
        def contacts(root, **kwargs):
            calls.append(("contacts", kwargs))
            return {
                "status": "PUBLIC_COMPANY_CHANNELS_ONLY",
                "people": [], "public_channels": [{
                    "company": "Harbourlight Inc.", "value": "office@example.org"}],
                "model_calls": 1, "report_path": "contacts.json",
            }
        r = run(self.root, today=DAY, paid=True, discoverer=discoverer,
                qualifier=qualify, investigator=contacts)
        self.assertEqual([x[0] for x in calls],
                         ["discover", "qualify", "contacts"])
        self.assertEqual(r["project"], "Harbour Works")
        self.assertEqual(calls[1][1]["project_name"], "Harbour Works")
        self.assertEqual(calls[2][1]["project_name"], "Harbour Works")
        self.assertEqual(r["qualification"]["assessment"], "HOLD")
        self.assertEqual(r["contacts"]["public_company_channels"], 1)
        self.assertEqual(r["status"],
                         "SOURCE_BACKED_PROJECT_RESEARCH_COMPLETE_REVIEW_ONLY")
        self.assertFalse(r["buyer_verified"])
        self.assertFalse(r["open_supplier_contract_verified"])
        self.assertFalse(r["outreach_authorized"])
        saved = json.loads(Path(r["report_path"]).read_text(encoding="utf-8"))
        self.assertEqual(saved["project"], "Harbour Works")
        self.assertEqual(saved["date"], "2026-11-16")

    def test_no_cited_developer_keeps_qualification_and_contacts_off(self):
        r = run(self.root, paid=True, today=DAY,
                discoverer=lambda *_a, **_k: {
                    **DISCOVERY, "discovered_projects": [{
                        **PROJECT, "sources_used": []}]},
                qualifier=lambda *_a, **_k: self.fail("No cited company"),
                investigator=lambda *_a, **_k: self.fail("No cited company"))
        self.assertEqual(r["status"],
                         "NO_NEW_SOURCE_BACKED_PROJECT_FOR_QUALIFICATION")
        self.assertEqual(r["qualification"]["status"], "NOT_RUN")

    def test_source_failure_stays_visible_without_false_buyer(self):
        r = run(self.root, paid=True, today=DAY,
                discoverer=lambda *_a, **_k: DISCOVERY,
                qualifier=lambda *_a, **_k:
                    (_ for _ in ()).throw(ValueError("No exact cited report")),
                investigator=lambda *_a, **_k:
                    (_ for _ in ()).throw(ValueError("No source evidence")))
        self.assertEqual(r["status"],
                         "PARTIAL_SOURCE_OR_BUDGET_REVIEW_REQUIRED")
        self.assertEqual(r["qualification"]["status"],
                         "QUALIFICATION_ERROR_REVIEW")
        self.assertEqual(r["contacts"]["status"],
                         "CONTACTS_ERROR_REVIEW")
        self.assertFalse(r["outreach_authorized"])


    def test_three_cited_projects_export_without_inventing_buyers(self):
        projects = [{**PROJECT, "project_name": f"Factory {i}",
                     "location_text": f"{i} Test Road",
                     "claims": [{"kind": "scope", "quote": "new production line installed"}]}
                    for i in range(1, 5)]
        calls = []
        def qualify(_root, **kwargs):
            calls.append(("qualification", kwargs["project_name"]))
            return {"status": "HOLD", "assessment": {"classification": "HOLD"}}
        def investigate(_root, **kwargs):
            calls.append(("contacts", kwargs["project_name"]))
            return {"status": "PUBLIC_CHANNELS_ONLY", "public_channels": []}
        r = run(self.root, paid=True, today=DAY,
                discoverer=lambda *_a, **_k: {**DISCOVERY,
                    "discovered_projects": projects},
                qualifier=qualify, investigator=investigate)
        self.assertEqual(r["discovery"]["exported_source_backed_opportunities"], 4)
        self.assertEqual(r["research_completed_count"], 3)
        self.assertEqual(len(calls), 6)
        self.assertTrue(Path(r["equipment_opportunities_csv"]).exists())
        import csv
        with Path(r["equipment_opportunities_csv"]).open(encoding="utf-8-sig") as fp:
            rows = list(csv.DictReader(fp))
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(x["buyer_verified"] == "False" and
                            x["published_date_verified"] == "False" and
                            not x["purchasing_email"] for x in rows))



if __name__ == "__main__":
    unittest.main()
