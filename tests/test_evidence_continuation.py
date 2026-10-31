import csv,json,tempfile,unittest
from pathlib import Path
from gta_evidence_continuation import report
from gta_integrated_run_gates import evaluate
class ContinuationTests(unittest.TestCase):
 def test_deduplicated_pdf_count_and_no_false_buyer(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);d=p/"MEETING_DOCUMENTS"/"Toronto";d.mkdir(parents=True)
   with (d/"COMBINED_PDF_FETCH_AUDIT.csv").open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=["url","status","reason"]);w.writeheader()
    w.writerows([{"url":"https://www.toronto.ca/one.pdf","status":"CAPTURED"},
                 {"url":"https://www.toronto.ca/one.pdf","status":"CAPTURED"}])
   r=report(p,p);self.assertEqual(r["documents"]["captured"],1)
   e=evaluate(p,p);self.assertEqual(e["counts"]["captured_documents"],1)
   self.assertFalse(e["production_accepted"])
 def test_missing_provenance_stays_unknown(self):
  with tempfile.TemporaryDirectory() as t:
   result=report(t,t)
   self.assertEqual(result["lead_time"]["measurable_pairs"],0)
   self.assertEqual(result["buyer"]["verified_purchasing_authorities"],0)
if __name__=="__main__":unittest.main()
