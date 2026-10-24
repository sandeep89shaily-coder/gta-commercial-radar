"""Research queue never asserts buyer contacts or procurement availability."""
import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path

from early_signal_buyer_research import queue, write_queue

class BuyerQueueTests(unittest.TestCase):
    def test_industrial_preconsultation_ranked_but_not_sale_ready(self):
        row = {
            "project_group_key":"brampton_preconsultation|APP|PRE-2026-0014",
            "source_id":"brampton_preconsultation", "city":"Brampton",
            "stage":"PRE_CONSULTATION","application_id":"PRE-2026-0014",
            "source_application_date":"2026-09-30",
            "first_observed_at":"2026-10-24",
            "description":"Proposed industrial energy-from-waste plant expansion and equipment installation",
            "location":"7656 Bramalea Rd", "commercial_signal":"POSSIBLE_COMMERCIAL",
            "status":"Submitted", "published_company":"Engineering Consultant Inc",
            "company_role":"PUBLISHED_AGENT_NOT_BUYER",
            "record_identity_confidence":"SOURCE_APPLICATION_GROUP_REVIEW",
            "source_date_basis":"DATE_RECEIVED", "source_url":"https://example.org"
        }
        selected=queue([row],today=dt.date(2026,10,24))
        self.assertEqual(len(selected),1)
        self.assertEqual(selected[0]["priority"],"RESEARCH_FIRST")
        self.assertIn("POWER_PROCESS",selected[0]["specific_scope_terms"])
        self.assertEqual(selected[0]["purchasing_decision_maker"],"UNVERIFIED")
        self.assertEqual(selected[0]["procurement_status"],"UNKNOWN")
        self.assertEqual(selected[0]["verified_business_contact"],"NOT_FOUND")
        self.assertEqual(selected[0]["evidence_tier"],"MUNICIPAL_RECORD_RESEARCH_ONLY")
        self.assertEqual(queue([{**row,"status":"Withdrawn"}],today=dt.date(2026,10,24)),[])
        self.assertEqual(queue([{**row,"source_application_date":""}],
                               today=dt.date(2026,10,24)),[])

    def test_repeat_features_deduped(self):
        row={"project_group_key":"same", "source_id":"toronto_development",
             "commercial_signal":"POSSIBLE_COMMERCIAL","stage":"PLANNING",
             "source_application_date":"2026-10-01","description":"Hotel",
             "status":"Under review"}
        self.assertEqual(len(queue([row,row],today=dt.date(2026,10,24))),1)

    def test_csv_has_expected_uncertainty_fields(self):
        with tempfile.TemporaryDirectory() as root:
            inp=Path(root)/"review.csv"
            with inp.open("w",encoding="utf-8-sig",newline="") as f:
                writer=csv.DictWriter(f,fieldnames=[
                    "project_group_key","source_id","commercial_signal","stage",
                    "source_application_date","description","status"])
                writer.writeheader()
                writer.writerow({"project_group_key":"a","source_id":"s",
                     "commercial_signal":"POSSIBLE_COMMERCIAL","stage":"PRE_CONSULTATION",
                     "source_application_date":"2026-10-03","description":"Warehouse and loading docks",
                     "status":"Submitted"})
            outcome=write_queue(inp,root,today=dt.date(2026,10,24))
            self.assertEqual(outcome["investigation_candidates"],1)
            with (Path(root)/"EARLY_SIGNALS_BUYER_RESEARCH_QUEUE.csv").open(
                encoding="utf-8-sig",newline="") as f:
                lines=list(csv.DictReader(f))
            self.assertEqual(lines[0]["vendor_selection_status"],"UNKNOWN")

if __name__=="__main__":
    unittest.main()
