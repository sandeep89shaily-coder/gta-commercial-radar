import tempfile,unittest,csv
from pathlib import Path
from unittest.mock import patch
from toronto_ai_one_click import discover,run,make_review
class EndToEndTest(unittest.TestCase):
 def test_reuses_existing_pdf_and_produces_review_without_ai(self):
  with tempfile.TemporaryDirectory() as td:
   home=Path(td);base=home/"Desktop"/"GTA_RADAR_INSTALL"/"prior_zip"/"TORONTO_VERIFIED_REPORTS"
   base.mkdir(parents=True);audit=base/"VERIFIED_REPORT_FETCH_AUDIT.csv"
   audit.write_text("attachment_url,status,saved_path,sha256\n",encoding="utf-8")
   results=home/"Desktop"/"new data"/"GTA_RADAR_RESULTS";results.mkdir(parents=True)
   self.assertEqual(discover(home),audit)
   with patch("toronto_ai_one_click.diagnose",return_value={"status":"READ_ONLY_DIAGNOSTIC","budget_allows_new_request":True}):
    report=run(home,results)
   self.assertEqual(report["status"],"NO_COST_READY")
   self.assertEqual(report["batch"]["ai_calls_reported"],0)
 def test_blocks_paid_when_budget_not_proven(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);audit=root/"VERIFIED_REPORT_FETCH_AUDIT.csv"
   audit.write_text("attachment_url,status,saved_path,sha256\n",encoding="utf-8")
   with patch("toronto_ai_one_click.diagnose",return_value={"status":"READ_ONLY_DIAGNOSTIC","budget_allows_new_request":False}):
    report=run(root,root,paid=True,audit=audit)
   self.assertEqual(report["status"],"LOCAL_BUDGET_HOLD_STOPPED")
if __name__=="__main__":unittest.main()
