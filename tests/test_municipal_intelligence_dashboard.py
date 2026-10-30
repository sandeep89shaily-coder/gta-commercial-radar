import tempfile,unittest,json,csv
from pathlib import Path
from municipal_intelligence_dashboard import render
class DashboardTests(unittest.TestCase):
 def test_review_renders_official_bids_and_escapes_untrusted_text(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)
   (p/"INTEGRATED_PILOT_AUDIT.json").write_text(json.dumps({"city":"Toronto","buyer_evidence_status":"SOURCE_CHECKED_NOT_VERIFIED"}))
   (p/"TORONTO_MEETINGS.json").write_text(json.dumps({"meetings":[]}))
   with (p/"TORONTO_OFFICIAL_PROCUREMENT.csv").open("w",encoding="utf-8-sig",newline="") as h:
    w=csv.DictWriter(h,fieldnames=["document_number","status","title","buyer_name","buyer_email","closing_date","public_portal_url"])
    w.writeheader();w.writerow({"document_number":"1234567890","status":"OPEN",
      "title":"<script>alert(1)</script> HVAC","buyer_name":"City Buyer",
      "buyer_email":"buyer@toronto.ca","closing_date":"2026-11-01",
      "public_portal_url":"https://www.toronto.ca/bids"})
   html=render(p).read_text()
   self.assertIn("&lt;script&gt;",html)
   self.assertNotIn("<script>alert(1)</script>",html)
   self.assertIn("not a confirmed current offer",html)
   self.assertIn("buyer@toronto.ca",html)
 def test_future_closing_candidates_from_ckan_appear_first(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   (root/"INTEGRATED_PILOT_AUDIT.json").write_text(json.dumps({"city":"Toronto"}))
   (root/"TORONTO_MEETINGS.json").write_text(json.dumps({"meetings":[]}))
   (root/"TORONTO_CURRENT_OPEN_CKAN.json").write_text(json.dumps({
    "status":"FETCHED","complete":True,"records":[
      {"document_number":"1234567890","title":"Future mechanical maintenance",
       "closing_date":"2026-11-23","buyer_name_official_publication":"City procurement",
       "temporal_review":"FUTURE_CLOSING_DATE_REQUIRES_LIVE_CONFIRMATION"},
      {"document_number":"9876543210","title":"2010 archival bid",
       "closing_date":"2010-11-24","temporal_review":"PAST_CLOSING_DATE_STALE_OPEN_STATUS"}]}))
   data=render(root).read_text(encoding="utf-8")
   self.assertIn("Future mechanical maintenance",data)
   self.assertNotIn("2010 archival bid",data)
   self.assertIn("Future-closing bids from official open dataset",data)
if __name__=="__main__":unittest.main()
