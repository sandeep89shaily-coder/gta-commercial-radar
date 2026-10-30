import unittest
from toronto_report_fact_review import extract_facts

class StaffReportFactTest(unittest.TestCase):
    def test_explicit_report_fields_with_page_citations_not_buyer_claims(self):
        pages=[{"page":1,"text":"""REPORT FOR ACTION
Ookwemin Minising — Decision Report — Supplementary Report
Date: May 19, 2026
Ward: 14 - Toronto - Danforth
Planning Application Number: 26 132130 STE 14 OZ
SUMMARY
Minor revisions to draft zoning by-law amendments.
"""},{"page":2,"text":"Recommendations to City Council."}]
        facts=extract_facts(pages,"0123456789","https://www.toronto.ca/legdocs/mmis/2026/cc/bgrd/backgroundfile-287146.pdf")
        values={f["field"]:f["value"] for f in facts}
        self.assertEqual(values["planning_application_number"],"26 132130 STE 14 OZ")
        self.assertEqual(values["report_date"],"May 19, 2026")
        self.assertEqual(len({f["page"] for f in facts}),1)
        self.assertTrue(all(f["source_publication_date"]=="" for f in facts))
        self.assertTrue(all(f["buyer_verified"]=="NO" for f in facts))
        self.assertTrue(all(f["supplier_award_verified"]=="NO" for f in facts))

    def test_missing_fields_not_fabricated(self):
        facts=extract_facts([{"page":1,"text":"Council discussed a possible warehouse."}],"sha")
        self.assertEqual(facts,[])

if __name__=="__main__":
    unittest.main()
