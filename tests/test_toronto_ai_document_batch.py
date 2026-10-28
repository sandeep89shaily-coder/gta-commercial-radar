import csv,hashlib,tempfile,unittest
from pathlib import Path
from toronto_ai_document_batch import process

URL="https://www.toronto.ca/legdocs/mmis/2026/ph/bgrd/backgroundfile-287454.pdf"
class BatchTest(unittest.TestCase):
 def test_batch_verify_checksum_and_paid_opt_in(self):
  with tempfile.TemporaryDirectory() as t:
   base=Path(t);pdf=base/"a.pdf";pdf.write_bytes(b"file bytes test")
   audit=base/"fetch.csv"
   with audit.open("w",newline="") as h:
    w=csv.DictWriter(h,fieldnames=["attachment_url","status","saved_path","sha256"]);w.writeheader()
    w.writerow({"attachment_url":URL,"status":"CAPTURED","saved_path":str(pdf),"sha256":hashlib.sha256(pdf.read_bytes()).hexdigest()})
   calls=[]
   def analyzer(*a,**kw):
    calls.append((a,kw))
    a[1].write_text("{}")
    return {"status":"AI_REVIEW_ONLY_NOT_SALE_READY","paid_ai_calls":1,"supported_claims":2,"rejected_claims":0}
   no=process(audit,base/"review",base,analyzer=analyzer)
   self.assertEqual(no["ai_calls_reported"],0)
   self.assertEqual(len(calls),0)
   yes=process(audit,base/"review",base,paid=True,analyzer=analyzer)
   self.assertEqual(yes["ai_calls_reported"],1)
   self.assertEqual(yes["review_outputs"],1)
   self.assertEqual(yes["sale_ready"],0)
 def test_corrupted_pdf_not_passed_to_ai(self):
  with tempfile.TemporaryDirectory() as t:
   base=Path(t);pdf=base/"a.pdf";pdf.write_bytes(b"tampered")
   audit=base/"fetch.csv"
   with audit.open("w",newline="") as h:
    w=csv.DictWriter(h,fieldnames=["url","status","saved_path","sha256"]);w.writeheader()
    w.writerow({"url":URL,"status":"CAPTURED","saved_path":str(pdf),"sha256":"0"*64})
   def fail(*a,**kw):raise AssertionError("Must not run AI")
   result=process(audit,base/"review",base,paid=True,analyzer=fail)
   self.assertEqual(result["errors"],1)
   self.assertEqual(result["ai_calls_reported"],0)
if __name__=="__main__": unittest.main()
