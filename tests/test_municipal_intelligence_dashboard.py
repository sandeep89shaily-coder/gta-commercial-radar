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
if __name__=="__main__":unittest.main()
