"""Protect northern commercial worklist from residential/issued-permit inflation."""
import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from gta_northern_commercial_research import run, SOURCE, OUTPUT, STATUS


class NorthernResearchQualityTests(unittest.TestCase):
    def setUp(self):
        holder=tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.root=Path(holder.name)

    def write(self, rows):
        with (self.root/SOURCE).open("w",newline="",encoding="utf-8") as fp:
            writer=csv.DictWriter(fp,fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def test_commercial_pending_included_issued_residential_and_approved_held(self):
        def r(lane,number,stage,scope,date=""):
            return {"source_lane":lane,"application_id":number,
                    "city":"Barrie","address":"131 Lockhart Road","scope":scope,
                    "source_date":date,
                    "source_date_basis":"OFFICIAL_APPLICATION_RECEIVED_NOT_PUBLICATION",
                    "current_status":stage,"original_record_url":"https://gispublic.barrie.ca/app/",
                    "applicant_name_source_claim":"ISM Architects (not buyer)"}
        rows=[
            r("BARRIE_PLANNING","D11-022-2026","UNDER REVIEW",
                "New 4151 square metre industrial building for crane manufacturing.",
                "2026-09-28"),
            r("BARRIE_PLANNING","D30-015-2026","UNDER REVIEW",
                "Mixed-use residential towers with ground floor commercial retail.","2026-10-16"),
            r("BARRIE_PLANNING","D11-015-2025","APPROVED",
                "Industrial warehouse for manufacturing.","2025-03-01"),
            r("BARRIE_PLANNING","D11-024-2026","UNDER REVIEW",
                "Residential townhouse subdivision only.","2026-10-01"),
            r("BARRIE_ISSUED_PERMITS","PMT26-12345","Issued",
                "Industrial new shell building.","2026-11-01"),
        ]
        self.write(rows)
        state=run(self.root,today=dt.date(2026,11,17))
        self.assertEqual(state["source_rows"],5)
        self.assertEqual(state["historical_issued_permits_excluded_from_early_research"],1)
        self.assertEqual(state["private_research_worklist_rows"],2)
        self.assertEqual(state["verified_buyers"],0)
        self.assertEqual(state["verified_unawarded_contracts"],0)
        with (self.root/OUTPUT).open(encoding="utf-8-sig",newline="") as fp:
            selected=list(csv.DictReader(fp))
        self.assertEqual([x["application_id"] for x in selected],
                         ["D11-022-2026","D30-015-2026"])
        self.assertTrue(all(x["original_publication_verified"]=="False"
                            for x in selected))
        self.assertTrue(all(x["contact_role_verified"]=="False"
                            for x in selected))

    def test_missing_source_writes_empty_review_and_never_invents_opportunities(self):
        report=run(self.root,today=dt.date(2026,11,17))
        self.assertEqual(report["private_research_worklist_rows"],0)
        self.assertTrue((self.root/OUTPUT).is_file())


if __name__=="__main__":
    unittest.main()
