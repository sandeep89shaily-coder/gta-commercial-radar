import tempfile, unittest, csv
from pathlib import Path
from toronto_verified_report_queue import run
URL="https://www.toronto.ca/legdocs/mmis/2026/ph/bgrd/backgroundfile-287454.pdf"
SOURCE="https://secure.toronto.ca/council/report.do?meeting=2026.PH31&type=agenda"
class QueueTest(unittest.TestCase):
 def test_fetches_proven_official_pdf_only(self):
  with tempfile.TemporaryDirectory() as t:
   q=Path(t)/"queue.csv"
   with q.open("w",newline="") as h:
    w=csv.DictWriter(h,fieldnames=["agenda_or_item_url","attachment_url","source_label","evidence_status"]);w.writeheader()
    w.writerow(dict(agenda_or_item_url=SOURCE,attachment_url=URL,source_label="PH31",evidence_status="OFFICIAL_PAGE_LINK_OBSERVED"))
    w.writerow(dict(agenda_or_item_url=SOURCE,attachment_url="https://evil.example.org/report.pdf",source_label="bad",evidence_status="OFFICIAL_PAGE_LINK_OBSERVED"))
   called=[]
   def downloader(url,path):
    called.append(url)
    return dict(status="CAPTURED",reason="OK",http_status=200,bytes=1000,sha256="abc",saved_path=str(path))
   result=run(q,Path(t)/"out",fetch=True,downloader=downloader)
   self.assertEqual(result["queue_unique_checked"],2)
   self.assertEqual(result["captured"],1)
   self.assertEqual(called,[URL])
   self.assertFalse(result["automatic_agenda_discovery"])
   self.assertEqual(result["paid_ai_calls"],0)
if __name__=="__main__": unittest.main()
