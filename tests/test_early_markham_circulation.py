"""Offline Markham PDF index baseline / no phantom application counts."""
import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path
import early_markham_circulation as m

HTML="""<html><body><h1>Current Planning Applications and Agendas</h1>
<div><h2>Circulated Planning and Development Applications</h2>
<a href="/sites/default/files/2026-10/Circulated%20Planning%20Development%20Applications%20September%2028%20to%20October%2011_AOD.pdf">
Circulated Planning Development Applications September 28 - October 11, 2026 (PDF)</a>
<a href="/sites/default/files/2026-09/Circulated%20Planning%20Development%20Applications%20August%2031%20to%20September%2027.pdf">
Circulated Planning Development Applications August 31 - September 27, 2026 (PDF)</a>
<a href="https://other.example.com/notours.pdf">Circulated Planning Development Applications July 1 - July 14, 2026 (PDF)</a>
</div></body></html>"""

class Reply:
    def __init__(self,text):self.text=text
    def raise_for_status(self):pass
class Session:
    def __init__(self,html):self.html=html
    def get(self,url,**kwargs):return Reply(self.html)

class Tests(unittest.TestCase):
    def test_official_reports_not_individual_projects(self):
        result=m.parse_index(HTML)
        self.assertEqual(len(result),2)
        self.assertEqual(result[0]["source_date"],"")
        self.assertEqual(result[0]["date_basis"],
          "CIRCULATION_WINDOW_NOT_PDF_PUBLICATION_DATE")
        self.assertEqual(result[0]["procurement_status"],"UNKNOWN")
        self.assertIn("markham.ca",result[0]["source_url"])
        self.assertNotIn("other.example.com",str(result))

    def test_incomplete_page_is_source_failure(self):
        with self.assertRaisesRegex(RuntimeError,"Too few"):
            m.parse_index(HTML.replace('href="/sites/default/files/2026-09/', 'href="https://elsewhere.example/'))

    def test_baseline_does_not_create_false_new_projects(self):
        with tempfile.TemporaryDirectory() as directory:
            d=Path(directory)
            opts=dict(data_dir=d/"data",output_dir=d/"reports")
            self.assertEqual(m.run(**opts,session=Session(HTML),observed="2026-10-24T14:00:00Z"),0)
            self.assertEqual(m.run(**opts,session=Session(HTML),observed="2026-10-25T14:00:00Z"),0)
            with (d/"reports"/"EARLY_MARKHAM_NEW_REPORTS_REVIEW_ONLY.csv").open(
               encoding="utf-8-sig",newline="") as f:
                self.assertEqual(list(csv.DictReader(f)),[])
            db=sqlite3.connect(d/"data"/"early_markham_reports_review.sqlite")
            self.assertEqual(db.execute("SELECT count(*) FROM snapshots").fetchone()[0],2)
            self.assertEqual(db.execute("SELECT count(*) FROM changes").fetchone()[0],0)
            db.close()

    def test_source_failure_keeps_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            opts=dict(data_dir=Path(directory)/"data",output_dir=Path(directory)/"out")
            self.assertEqual(m.run(**opts,session=Session(HTML),observed="2026-10-24"),0)
            self.assertEqual(m.run(**opts,session=Session("<html>denied</html>"),observed="2026-10-25"),1)
            db=sqlite3.connect(Path(directory)/"data"/"early_markham_reports_review.sqlite")
            self.assertEqual(db.execute("SELECT count(*) FROM snapshots").fetchone()[0],2)
            db.close()

if __name__=="__main__":unittest.main()
