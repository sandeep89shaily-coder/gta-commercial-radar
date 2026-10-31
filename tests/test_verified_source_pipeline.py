import tempfile,unittest
from pathlib import Path
from gta_verified_source_pipeline import discover,classify_buyer,lead_pair,fetch_discovered

class FakeResponse:
    status_code=200
    content=b'<html><a href="https://www.toronto.ca/legdocs/mmis/2026/ph/bgrd/backgroundfile-287454.pdf">Official PDF</a></html>'
    text=content.decode()
    headers={"Content-Type":"text/html"}
    def __init__(self,url):self.url=url
class FakeSession:
    trust_env=True
    headers={}
    def get(self,url,**kw):
        if url.endswith("/robots.txt"):
            r=FakeResponse(url);r.text="User-agent: *\nAllow: /\n";r.content=r.text.encode();return r
        return FakeResponse(url)
class EvidencePipelineTests(unittest.TestCase):
    def test_live_official_index_parser_and_fetch_audit(self):
        with tempfile.TemporaryDirectory() as t:
            index="https://secure.toronto.ca/council/report.do?meeting=2026.PH31&type=agenda"
            result=discover([{"city":"Toronto","index_url":index}],t,session=FakeSession())
            self.assertEqual(result["documents_discovered"],1)
            def fake_download(url,path):
                return {"status":"CAPTURED","reason":"OK","saved_path":str(path),"sha256":"abc"}
            d=fetch_discovered(result["discovered_csv"],Path(t)/"fetched",downloader=fake_download)
            self.assertEqual(d["captured"],1)
    def test_buyer_claim_without_purchasing_proof_never_verified(self):
        result=classify_buyer({"role":"architect","source_url":"https://www.toronto.ca/x",
                                 "exact_quote":"Architect Example"})
        self.assertEqual(result["buyer_authority"],"NOT_VERIFIED")
        self.assertEqual(result["supplier_status"],"UNKNOWN")
    def test_early_match_requires_explicit_review(self):
        e={"official_project_id":"A","source_url":"https://example.org/a","published_at":"2026-01-01T00:00:00+00:00","radar_first_seen_at":"2026-01-02T00:00:00+00:00"}
        l={"official_project_id":"A","source_url":"https://example.org/b","published_at":"2026-02-01T00:00:00+00:00"}
        self.assertEqual(lead_pair(e,l)["status"],"PROJECT_IDENTITY_NOT_VERIFIED")
if __name__=="__main__":unittest.main()
