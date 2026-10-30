import tempfile
import unittest
from pathlib import Path
from toronto_tmmis_documents import parse_agenda, build, agenda_url

URL="https://secure.toronto.ca/council/report.do?meeting=2026.CC41&type=agenda"
PDF="https://www.toronto.ca/legdocs/mmis/2026/cc/bgrd/backgroundfile-287146.pdf"

class TmmisDocumentTest(unittest.TestCase):
    def test_official_pdf_discovery_without_download(self):
        markup='<a href="'+PDF+'">Staff report</a><a href="'+PDF+'">Duplicate</a>'
        markup+='<a href="https://evil.example.com/legdocs/mmis/2026/cc/bgrd/backgroundfile-1.pdf">Bad</a>'
        markup+='<a href="https://www.toronto.ca/legdocs/mmis/2026/cc/comm/communicationfile-20.pdf">Not report</a>'
        rows=parse_agenda(markup,URL)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["attachment_url"],PDF)
        self.assertEqual(rows[0]["retrieval_status"],"DISCOVERED_NOT_FETCHED")
        self.assertEqual(rows[0]["publication_date_status"],"UNVERIFIED")
        with tempfile.TemporaryDirectory() as td:
            inp=Path(td)/"agenda.html";out=Path(td)/"reports.csv"
            inp.write_text(markup,encoding="utf-8")
            result=build(inp,URL,out)
            self.assertEqual(result["documents_downloaded"],0)
            self.assertEqual(result["documents_discovered"],1)
            self.assertTrue(out.exists())

    def test_invalid_meeting_link_rejected(self):
        self.assertFalse(agenda_url("https://bad.site/council/report.do?meeting=2026.CC41&type=agenda"))
        with self.assertRaises(ValueError):
            parse_agenda("<a>hello</a>","https://bad.site/")
if __name__=="__main__":
    unittest.main()
