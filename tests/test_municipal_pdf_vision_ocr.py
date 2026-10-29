import csv,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from municipal_pdf_vision_ocr import deepseek_ocr,run
from municipal_unified_intelligence import source_chunks
class VisionTests(unittest.TestCase):
 def test_model_sends_image_in_nonthinking_mode(self):
  def transport(path,payload):
   self.assertEqual(payload["model"],"deepseek-flash")
   self.assertEqual(payload["thinking"],{"type":"disabled"})
   self.assertEqual(payload["messages"][1]["content"][1]["type"],"image_url")
   return {"choices":[{"finish_reason":"stop","message":{"content":"Project at 25 Eden Place"}}]}
  text=deepseek_ocr("data:image/png;base64,iVBORw0KGgo=", "unused",transport)
  self.assertEqual(text,"Project at 25 Eden Place")
 def test_ocr_csv_feeds_page_marked_deepseek_intelligence(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/"PDF_OCR_PAGES.csv"
   with p.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=["page","text"])
    w.writeheader();w.writerow({"page":3,"text":"130 Augusta Avenue"})
   chunks,meta=source_chunks(ocr_csv=p)
   self.assertEqual(meta["type"],"pdf_vision_ocr")
   self.assertEqual(chunks[0]["marker"],3)
 def test_no_paid_call_in_vision_preflight(self):
  with tempfile.TemporaryDirectory() as t:
   d={"sha256":"sha","pages":[{"page":1,"text":"","text_present":False},{"page":2,"text":"readable","text_present":True}]}
   with patch("municipal_pdf_vision_ocr.extract_local_pdf",return_value=d),patch("municipal_pdf_vision_ocr.v5._ledger") as ledger:
    report=run("unused","https://www.toronto.ca/report.pdf",t,Path(t)/"out")
    self.assertEqual(report["unreadable_pages"],[1])
    self.assertEqual(report["paid_ai_requests"],0)
    ledger.assert_not_called()
if __name__=="__main__":unittest.main()
