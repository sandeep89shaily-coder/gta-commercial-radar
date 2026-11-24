"""Official alternative source regressions; entirely offline (no municipal requests)."""
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import gta_approved_alternative_feeds as alternatives

HTML="""<html><body><h1>Current Applications</h1>
<a href="/en/town-services/current-applications">RZ 2025-0026 - 12862 Dixie Road - Armstrong Planning on behalf of Amazon</a>
<a href="/en/town-services/current-applications">RZ 2025-0026 - 12862 Dixie Road - duplicate</a>
<a href="/en/town-services/current-applications">POPA 2026-0004 - Highway 413 corridor policy</a>
<a href="https://evil.example.org/">SPA 2026-0099 - 44 Factory Road</a>
</body></html>"""

def fake_fetch(url,**kwargs):
    if "FeatureServer/0/query?" in url:
        args={"features":[{"attributes":{"OBJECTID":1,"APPLICATION_NO":"ZBA/2026/11",
                "ADDRESS":"100 Industry Street","DESCRIPTION":"Industrial plant expansion",
                "APPLICANT":"Applicant Holdings Ltd","STATUS":"Received",
                "FOLDERTYPE":"Zoning By-law Amendment","INDATE":1794441600000}}]}
        return json.dumps(args)
    if url==alternatives.CALEDON:
        return HTML
    raise AssertionError("Unexpected attempted URL: "+url)

class OfficialAlternativeTests(unittest.TestCase):
    def test_kitchener_open_data_exact_fields(self):
        rows,state=alternatives.arcgis_rows(fetcher=fake_fetch,check_robots=False)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["application_id"],"ZBA/2026/11")
        self.assertEqual(rows[0]["address"],"100 Industry Street")
        self.assertEqual(rows[0]["date_basis"],"APPLICATION_INDATE_NOT_PUBLICATION")
        self.assertEqual(rows[0]["source_permission"],"PUBLISHED_OPEN_DATA_LICENCE_REUSE")
        self.assertEqual(rows[0]["buyer_verified"],"False")
        self.assertEqual(state["features_examined"],1)
        self.assertFalse(state["possibly_truncated"])

    def test_default_kitchener_uses_catalogue_bulk_csv(self):
        record = {"APPLICATION_NO": "ZBA22/024/M/BB", "ADDRESS": "7 Morrison Rd",
                  "DESCRIPTION": "Planning application", "FOLDERTYPE": "Rezoning",
                  "INDATE": "10/14/2022 12:00:00 AM", "APPLICANT": "Personal Name"}
        with tempfile.TemporaryDirectory() as root:
            with patch.object(alternatives, "download_rows", return_value=[record, record]), \
                    patch.object(alternatives, "fetch", side_effect=fake_fetch):
                report = alternatives.run(root)
            self.assertEqual(report["cities"]["Kitchener"]["transport"], "ARCGIS_HUB_CSV")
            with (Path(root) / alternatives.OUT).open(encoding="utf-8-sig", newline="") as f:
                row, _ = list(csv.DictReader(f))
        self.assertEqual(row["date"], "2022-10-14")
        self.assertEqual(row["source_url"], alternatives.KITCHENER_CATALOGUE)
        self.assertEqual(row["applicant"], "")
        self.assertEqual(row["publication_verified"], "False")

    def test_caledon_deduplicated_without_policy_document(self):
        rows=alternatives.caledon_rows(HTML)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["application_id"],"RZ 2025-0026")
        self.assertEqual(rows[0]["address"],"12862 Dixie Road")
        self.assertEqual(rows[0]["source_permission"],"PUBLIC_INDEX_RESEARCH_REUSE_NOT_VERIFIED")
        self.assertEqual(rows[0]["date"],"")
        self.assertEqual(rows[0]["publication_verified"],"False")

    def test_robust_independent_status(self):
        with tempfile.TemporaryDirectory() as d:
            status=alternatives.run(d,fetcher=fake_fetch)
            self.assertEqual(status["records_current_run"],2)
            self.assertEqual(status["cities"]["Kitchener"]["valid_application_rows"],1)
            self.assertEqual(status["cities"]["Caledon"]["valid_application_rows"],1)
            self.assertEqual(status["verified_buyers"],0)
            with (Path(d)/alternatives.OUT).open(encoding="utf-8-sig") as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),2)

    def test_one_blocked_city_does_not_remove_other(self):
        def block_kitchener(url,**kwargs):
            if "/query?" in url:raise PermissionError("Denied")
            return HTML
        with tempfile.TemporaryDirectory() as d:
            result=alternatives.run(d,fetcher=block_kitchener)
            self.assertEqual(result["cities"]["Kitchener"]["status"],"BLOCKED_OR_FAILED")
            self.assertEqual(result["cities"]["Caledon"]["valid_application_rows"],1)
            self.assertEqual(result["records_current_run"],1)

    def test_no_robots_or_cross_host_bypass(self):
        self.assertFalse(alternatives.permitted("http://example.org/"))
        with patch.object(alternatives,"permitted",return_value=False):
            with self.assertRaises(PermissionError):
                alternatives.fetch(alternatives.KITCHENER+"/query?f=json")
        class Response:
            def __enter__(self):return self
            def __exit__(self,*a):return False
            def geturl(self):return "https://evil.example.org/fake"
            def read(self,n):return b"{}"
        with self.assertRaises(PermissionError):
            alternatives.fetch(alternatives.KITCHENER+"/query?f=json",
                               check_robots=False,opener=lambda *a,**kw:Response())
if __name__=="__main__":
    unittest.main()
