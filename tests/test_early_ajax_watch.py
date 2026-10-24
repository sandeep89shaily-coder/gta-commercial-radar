"""Offline Ajax public application snapshot tests."""
import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path
import early_ajax_watch as ajax

INDEX="""<html><body><h1>Planning Applications</h1><main>
<h2>All applications</h2><p>2 properties, 3 applications</p>
<h3>211 Bayly Street East</h3><ul><li>Z18/26Open</li></ul>
<h3>789 Salem Road North</h3><ul>
<li>SPA9/26Open</li><li>SPA6/24Approved</li>
</ul></main></body></html>"""

class R:
    def __init__(self,txt):self.text=txt
    def raise_for_status(self):pass
class S:
    def __init__(self,txt):self.txt=txt
    def get(self,url,**kw):return R(self.txt)


class Tests(unittest.TestCase):
    def test_source_ids_address_status(self):
        rows,totals=ajax.parse_ajax(INDEX)
        self.assertEqual(totals,(2,3))
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[1]["stage"],"PLANNING_FILE_OPEN")
        self.assertEqual(rows[1]["site"],"789 Salem Road North")
        self.assertEqual(rows[0]["commercial_fit"],"USE_UNKNOWN")
        self.assertEqual(rows[0]["source_date"],"")
        self.assertEqual(rows[0]["procurement_status"],"UNKNOWN")

    def test_missing_header_fails(self):
        with self.assertRaises(RuntimeError):
            ajax.parse_ajax("<html>Access Denied</html>")

    def test_incomplete_index_fails(self):
        html=INDEX.replace("2 properties, 3 applications","80 properties, 120 applications")
        with self.assertRaisesRegex(RuntimeError,"coverage too low"):
            ajax.parse_ajax(html)

    def test_snapshot_baseline_and_no_false_new(self):
        with tempfile.TemporaryDirectory() as d:
            opts=dict(data_dir=Path(d)/"data",out_dir=Path(d)/"out")
            self.assertEqual(ajax.run(**opts,session=S(INDEX),stamp="2026-10-24T12:00:00"),0)
            self.assertEqual(ajax.run(**opts,session=S(INDEX),stamp="2026-10-25T12:00:00"),0)
            database=sqlite3.connect(Path(d)/"data"/"early_ajax_review.sqlite")
            self.assertEqual(database.execute("SELECT count(*) FROM snapshots").fetchone()[0],3)
            self.assertEqual(database.execute("SELECT count(*) FROM changes").fetchone()[0],0)
            database.close()
            self.assertEqual(ajax.run(**opts,session=S("<html>blocked</html>"),
                                      stamp="2026-10-26T12:00:00"),1)
            database=sqlite3.connect(Path(d)/"data"/"early_ajax_review.sqlite")
            self.assertEqual(database.execute("SELECT count(*) FROM snapshots").fetchone()[0],3)
            database.close()

if __name__=="__main__":unittest.main()
