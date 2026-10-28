import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from toronto_meeting_pdf_pipeline import run

MEETING="https://secure.toronto.ca/council/report.do?meeting=2026.CC41&type=agenda"
PDF="https://www.toronto.ca/legdocs/mmis/2026/cc/bgrd/backgroundfile-287146.pdf"
class Response:
    def __init__(self,url,content):
        self.url=url
        self.content=content
        self.status_code=200
        self.headers={"Content-Type":"text/html"}
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def iter_content(self,size):yield self.content
class Session:
    def __init__(self,body):self.body=body;self.headers={};self.trust_env=True
    def get(self,url,**kwargs):return Response(url,self.body)
def dns(*args,**kwargs):
    return [(0,0,0,"",("8.8.8.8",443))]

class PipelineTest(unittest.TestCase):
    def test_real_link_extraction_and_bounded_download(self):
        with tempfile.TemporaryDirectory() as t:
            seed=Path(t)/"seeds.csv"
            seed.write_text("meeting_url\n"+MEETING+"\n",encoding="utf-8")
            with patch("toronto_meeting_pdf_pipeline.fetch_one") as fetch:
                fetch.return_value=dict(url=PDF,status="CAPTURED",reason="OK",http_status=200,bytes=200,sha256="abc",saved_path="x.pdf")
                result=run(seed,Path(t)/"out",fetch=True,session=Session(('<a href="'+PDF+'">Report</a>').encode()),resolver=dns,
                    meeting_policy=lambda _: "User-agent: *\nAllow: /",
                    pdf_policy=lambda _: "User-agent: *\nAllow: /")
            self.assertEqual(result["meetings_fetched"],1)
            self.assertEqual(result["pdf_links_discovered"],1)
            self.assertEqual(result["pdf_downloaded"],1)
            self.assertEqual(result["paid_ai_calls"],0)
            fetch.assert_called_once()
            self.assertTrue((Path(t)/"out"/"TORONTO_DISCOVERED_PDFS.csv").exists())
    def test_default_is_no_network(self):
        with tempfile.TemporaryDirectory() as t:
            seed=Path(t)/"seeds.csv"
            seed.write_text("meeting_url\n"+MEETING+"\n",encoding="utf-8")
            result=run(seed,Path(t)/"out")
            self.assertEqual(result["meetings_fetched"],0)
            self.assertEqual(result["pdf_downloaded"],0)
if __name__=="__main__":unittest.main()
