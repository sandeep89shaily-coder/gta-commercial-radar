import tempfile,unittest,json
from pathlib import Path
from toronto_procurement_odata import normalize,collect,endpoint
class ProcurementTests(unittest.TestCase):
 def test_buyer_and_award_evidence_preserved(self):
  r=normalize({"Solicitation_Document_Number":"1234567890","Status":"Awarded",
    "Buyer_Name":"City purchasing buyer","Buyer_Email":"buyer@toronto.ca",
    "Client_Division":"Facilities","Awarded_Suppliers":[{"Successful_Bidder":"Example Ltd","Date_Awarded":"2026-10-01"}]})
  self.assertEqual(r["status"],"AWARDED")
  self.assertEqual(r["buyer_email_official_publication"],"buyer@toronto.ca")
  self.assertEqual(r["awarded_suppliers"][0]["supplier"],"Example Ltd")
  self.assertFalse(r["verified_private_work_package"])
 def test_unknown_stage_not_relabelled_open(self):
  r=normalize({"Solicitation_Document_Number":"1234567890","Status":"Awaiting finance review"})
  self.assertEqual(r["status"],"UNKNOWN")
 def test_official_paged_request_and_review_output(self):
  with tempfile.TemporaryDirectory() as td:
   called=[]
   def fake(url):
    called.append(url)
    return {"value":[{"Solicitation_Document_Number":"1234567890","Status":"Open"}]}
   result=collect(Path(td)/"out.json",fetch=fake,max_pages=2,page_size=5)
   self.assertEqual(len(called),1)
   self.assertIn("%24top=5",called[0])
   self.assertEqual(result["records"][0]["status"],"OPEN")
   self.assertEqual(result["verified_private_opportunities"],0)
 def test_paging_cap(self):
  self.assertRaises(ValueError,endpoint,0,1000)
if __name__=="__main__":unittest.main()
