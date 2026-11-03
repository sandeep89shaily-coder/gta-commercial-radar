"""Burlington quarterly totals do not generate application-level records."""
import unittest,io,zipfile,tempfile
from unittest.mock import patch
from gta_burlington_summary_pdf import _extract,run

def fixture():
    b=io.BytesIO()
    with zipfile.ZipFile(b,"w") as z:
        z.writestr("Burlington Development Application Summary Table - Q2 2026.pdf",b"%PDF-1.7 test")
    return b.getvalue()
class Page:
    def extract_text(self):
        return "Total number of active applications 53 Total number of new applications 21 Total number of applications decided 28"
class Reader:
    def __init__(self,raw):self.pages=[Page()]
class TestQuarterly(unittest.TestCase):
    @patch("gta_burlington_summary_pdf.PdfReader",Reader)
    def test_report_counts_are_aggregates(self):
        a=_extract(fixture())
        self.assertEqual(a["2026-Q2"]["new_applications"],21)
        self.assertEqual(a["2026-Q2"]["record_kind"],"AGGREGATE_ACTIVITY_NOT_APPLICATION_FILES")
    @patch("gta_burlington_summary_pdf.PdfReader",Reader)
    def test_baseline_and_repeated_collection(self):
        with tempfile.TemporaryDirectory() as d:
            x=run(d,fetcher=fixture)
            y=run(d,fetcher=fixture)
            self.assertEqual(x["report_quarters"],1)
            self.assertEqual(x["application_id_rows"],0)
            self.assertEqual(y["status"],"COLLECTED")
