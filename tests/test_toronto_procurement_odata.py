import tempfile,unittest,json
from pathlib import Path
from toronto_procurement_odata import normalize,collect,endpoint,temporal_review
import datetime as dt
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
   import csv
   with (Path(td)/"out.csv").open(encoding="utf-8-sig",newline="") as h:
    rows=list(csv.DictReader(h))
   self.assertEqual(rows[0]["status"],"OPEN")
   self.assertEqual(rows[0]["current_status_rechecked"],"False")
   self.assertEqual(result["verified_private_opportunities"],0)
 def test_historical_open_2010_is_not_current(self):
  self.assertEqual(temporal_review("OPEN","2010-11-24",today=dt.date(2026,10,29)),
    "PAST_CLOSING_DATE_STALE_OPEN_STATUS")
  self.assertEqual(temporal_review("OPEN","2026-11-24",today=dt.date(2026,10,29)),
    "FUTURE_CLOSING_DATE_REQUIRES_LIVE_CONFIRMATION")
  self.assertEqual(temporal_review("OPEN",None,today=dt.date(2026,10,29)),
    "DATE_MISSING_OR_INVALID_UNVERIFIED")
  self.assertEqual(temporal_review("AWARDED","2026-11-24",today=dt.date(2026,10,29)),
    "NOT_OPEN_IN_SOURCE")
 def test_paging_cap(self):
  self.assertRaises(ValueError,endpoint,0,1000)
if __name__=="__main__":unittest.main()
