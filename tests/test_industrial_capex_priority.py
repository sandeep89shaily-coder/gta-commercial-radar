"""Focused industrial capex triage: real equipment vs facility-only, no false RFQs."""
import csv,json,tempfile,unittest
from pathlib import Path
from gta_industrial_capex_priority import run,INPUT,OUTPUT

class IndustrialFocus(unittest.TestCase):
    def test_prioritizes_specific_equipment_and_does_not_invent_buyers(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            rows=[
              {"source_type":"SOURCE_BACKED_INVESTMENT_ANNOUNCEMENT","company":"Maxxit",
               "municipality":"Toronto","equipment_or_scope":"To acquire and install steel printing and bending equipment",
               "source_url":"https://canada.ca/announcement","contact_name_verified":"Jane","contact_professional_title":"President"},
              {"source_type":"SOURCE_BACKED_INVESTMENT_ANNOUNCEMENT","company":"Data Centre",
               "municipality":"Burlington","equipment_or_scope":"Proposed data centre",
               "source_url":"https://burlington.ca/site"},
              {"source_type":"SOURCE_BACKED_INVESTMENT_ANNOUNCEMENT","company":"Residential",
               "municipality":"Toronto","equipment_or_scope":"New residential subdivision with 100 townhouses",
               "source_url":"https://example.com/project"},
            ]
            with (root/INPUT).open("w",newline="",encoding="utf-8") as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            result=run(root)
            self.assertEqual(result["qualified_industrial_research_candidates"],2)
            with (root/OUTPUT).open(encoding="utf-8-sig") as f:
                resultrows=list(csv.DictReader(f))
            self.assertEqual(resultrows[0]["company"],"Maxxit")
            self.assertEqual(resultrows[1]["evidence_stage"],"FACILITY_OR_PROCESS_SCOPE_ONLY")
            self.assertTrue(all(x["purchase_stage"]=="UNKNOWN_NOT_A_LIVE_RFQ" for x in resultrows))
            self.assertTrue(all(x["buyer_status"]=="INDEPENDENT_PURCHASER_VERIFICATION_REQUIRED" for x in resultrows))
            self.assertEqual(result["additional_paid_ai_calls"],0)

    def test_empty(self):
        with tempfile.TemporaryDirectory() as d:
            s=run(Path(d))
            self.assertEqual(s["qualified_industrial_research_candidates"],0)

if __name__=="__main__":unittest.main()
