"""Evidence gating cannot invent a verified buyer or erase manual research."""
import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path
import early_buyer_evidence as e

PROJECT=dict(source_id="brampton_preconsultation",item_id="PRE-2026-0028",
 city="BRAMPTON",site="11462 Coleraine Drive",
 title="Industrial development",record_url="https://www.brampton.ca/official/abc",
 radar_first_seen="2026-10-24T10:00:00+00:00",
 published_entity="Architect Not Buyer",official_public_posting_date="",
 commercial_signal="POSSIBLE_COMMERCIAL",lead_status="NOT_SALE_READY_RESEARCH_ONLY")

class Tests(unittest.TestCase):
    def test_unknown_stays_incomplete(self):
        row=e.make_item(PROJECT)
        status,why=e.review(row,today=dt.date(2026,10,24))
        self.assertEqual(status,"INCOMPLETE_EVIDENCE")
        self.assertIn("buyer_organization_unverified",why)
        self.assertIn("procurement_status_unverified",why)

    def test_field_completeness_does_not_equal_verified_lead(self):
        row=e.make_item(PROJECT)
        row.update(reviewer="Investigator",reviewed_on="2026-10-24",
          project_identity_confirmed="YES",
          identity_evidence_url="https://www.brampton.ca/project/file",
          buyer_organization="Hypothetical Factory Ltd",buyer_relationship="OWNER",
          buyer_role_evidence_url="https://company.example/about",
          specific_work_package="New industrial refrigeration", 
          work_package_evidence_url="https://www.brampton.ca/project/file",
          public_business_contact="Procurement@company.example",
          public_contact_evidence_url="https://company.example/contact",
          procurement_state="OPEN_CONFIRMED",
          procurement_state_evidence_url="https://company.example/bids/2026",
          stage_current_evidence_url="https://www.brampton.ca/project",
          supplier_category="Industrial refrigeration",reviewer_signoff="YES")
        state,reason=e.review(row,today=dt.date(2026,10,24))
        self.assertEqual(state,"ASSEMBLED_FOR_HUMAN_REVIEW_NOT_VERIFIED_LEAD")
        self.assertIn("validate_links",reason)
        row["procurement_state"]="SELECTED_CONFIRMED"
        self.assertEqual(e.review(row,today=dt.date(2026,10,24))[0],
                         "NOT_OPEN_FOR_SALE_REVIEW")

    def test_untrusted_website_rejected(self):
        self.assertFalse(e.official_url("http://www.company.com"))
        self.assertFalse(e.official_url("https://user:pass@example.com/secret"))
        self.assertFalse(e.official_url("https://service.internal"))
        self.assertTrue(e.official_url("https://www.brampton.ca/planning/"))

    def test_repeated_runs_keep_human_research(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            incoming=base/"INPUT.csv"
            e.write(incoming,PROJECT.keys(),[PROJECT])
            self.assertEqual(e.run(incoming,base,today=dt.date(2026,10,24)),0)
            sheet=base/"EARLY_BUYER_EVIDENCE_WORKSHEET.csv"
            old=e.read(sheet)
            old[0]["buyer_organization"]="Manually researched organization"
            old[0]["reviewer"]="Human Reviewer"
            e.write(sheet,e.WORKSHEET_FIELDS,old)
            updated={**PROJECT,"title":"Updated factory description"}
            e.write(incoming,updated.keys(),[updated])
            self.assertEqual(e.run(incoming,base,today=dt.date(2026,10,24)),0)
            again=e.read(sheet)
            self.assertEqual(again[0]["buyer_organization"],"Manually researched organization")
            self.assertEqual(again[0]["reviewer"],"Human Reviewer")
            self.assertEqual(again[0]["title"],"Updated factory description")
            milestone=e.read(base/"EARLY_BUSINESS_MILESTONES.csv")
            metric={r["metric"]:r["value"] for r in milestone}
            self.assertEqual(metric["verified_sale_ready_opportunities"],"0")

    def test_lost_source_retains_original_manual_record(self):
        source=e.make_item(PROJECT)
        source["buyer_organization"]="Manually researched"
        result=e.merge([source],[])
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["buyer_organization"],"Manually researched")
        self.assertIn("NO_LONGER_IN_CURRENT_RESEARCH_QUEUE",result[0]["confidence_notes"])

if __name__=="__main__":
    unittest.main()
