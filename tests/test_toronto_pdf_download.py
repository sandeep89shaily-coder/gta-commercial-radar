import csv
import tempfile
import unittest
from pathlib import Path
from toronto_pdf_download import valid_url, robots_allowed, fetch_one, batch

URL="https://www.toronto.ca/legdocs/mmis/2026/cc/bgrd/backgroundfile-287146.pdf"
def dns(*args,**kwargs):
    return [(0,0,0,"",("8.8.8.8",443))]
class Response:
    status_code=200
    url=URL
    headers={"Content-Type":"application/pdf"}
    def __init__(self,content):self.content=content
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def iter_content(self,chunk_size=65536):yield self.content
class Session:
    def __init__(self,resp):
        self.resp=resp
        self.headers={}
        self.trust_env=True
    def get(self,*args,**kwargs):return self.resp

class DownloaderTest(unittest.TestCase):
    def test_valid_official_url_only(self):
        self.assertTrue(valid_url(URL))
        self.assertFalse(valid_url("https://www.toronto.ca.evil.net/legdocs/mmis/2026/cc/bgrd/backgroundfile-287146.pdf"))
        self.assertFalse(valid_url(URL+"?redirect=1"))
    def test_robots_failure_blocks_fetch(self):
        with tempfile.TemporaryDirectory() as t:
            result=fetch_one(URL,Path(t)/"report.pdf",resolver=dns,
                get_policy=lambda url:None,session=Session(Response(b"bad")))
            self.assertEqual(result["reason"],"ROBOTS_UNAVAILABLE")
            self.assertFalse((Path(t)/"report.pdf").exists())
    def test_html_disguised_pdf_rejected_and_not_saved(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/"report.pdf"
            result=fetch_one(URL,path,resolver=dns,
                get_policy=lambda _: "User-agent: *\\nAllow: /",
                session=Session(Response(b"<html>denied</html>")))
            self.assertEqual(result["reason"],"INVALID_PDF_SIGNATURE")
            self.assertFalse(path.exists())
    def test_batch_no_paid_ai_and_explicit_fetch_required(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/"discovery.csv"
            with path.open("w",newline="") as h:
                w=csv.DictWriter(h,fieldnames=["attachment_url"]);w.writeheader()
                w.writerow({"attachment_url":URL})
            result=batch(path,Path(t)/"out")
            self.assertEqual(result["captured"],0)
            self.assertEqual(result["paid_ai_calls"],0)
            self.assertTrue(Path(result["audit"]).exists())
if __name__=="__main__":
    unittest.main()
