"""Offline Ajax public application snapshot tests."""
import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
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

    def test_ajax_change_export_excludes_baseline_and_emits_true_new(self):
        sample={"source_id":ajax.SOURCE,"record_id":"P1","title":"Industrial plan",
                "site":"200 Test Rd","company":"","company_role":"",
                "stage":"PRECONSULTATION","source_application_date":"",
                "source_date":"","source_url":"https://ajax.ca/planning",
                "commercial_fit":"USE_UNKNOWN","procurement_status":"UNKNOWN",
                "verification":"SOURCE_ONLY"}
        with tempfile.TemporaryDirectory() as t:
            d=Path(t)
            with patch.object(ajax,"collect_official_gis",side_effect=[
                ([sample],(1,1)),([sample,dict(sample,record_id="P2")],(2,2))]):
                self.assertEqual(ajax.run(d,d,stamp="2026-10-24T08:00:00Z"),0)
                path=d/"EARLY_AJAX_CHANGES_REVIEW_ONLY.csv"
                with path.open(encoding="utf-8-sig",newline="") as f:
                    self.assertEqual(list(csv.DictReader(f)),[])
                self.assertEqual(ajax.run(d,d,stamp="2026-10-25T08:00:00Z"),0)
                with path.open(encoding="utf-8-sig",newline="") as f:
                    rows=list(csv.DictReader(f))
                self.assertEqual([(row["record_id"],row["change_type"]) for row in rows],
                                 [("P2","NEW")])

    def test_missing_header_fails(self):
        with self.assertRaises(RuntimeError):
            ajax.parse_ajax("<html>Access Denied</html>")

    def test_incomplete_index_fails(self):
        html=INDEX.replace("2 properties, 3 applications","80 properties, 120 applications")
        with self.assertRaisesRegex(RuntimeError,"coverage too low"):
            ajax.parse_ajax(html)

    def test_legacy_parser_still_handles_historical_html_fixture(self):
        rows,totals=ajax.parse_ajax(INDEX)
        self.assertEqual(totals,(2,3))
        self.assertEqual(len(rows),3)
        # Actual RUN tests for the replacement GIS service are in
        # tests/test_early_ajax_arcgis.py.


if __name__=="__main__":unittest.main()
