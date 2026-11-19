"""Offline regression for official Windsor/Pickering application HTML adapters."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from gta_windsor_pickering_source_pilot import (
    parse_windsor_index, parse_pickering_index, parse_pickering_detail,
    run, approved_url, iso_date,
)

WINDSOR_HTML = """<html><body><h1>Current Development Applications</h1>
<table><tr><th>File Name</th><th>Address</th><th>Application Type</th><th>Other Information</th></tr>
<tr><td><a href='/residents/planning/land-development/development-applications/current-development-applications/turner-road'>
Z-012/26, ZNG/7372</a></td><td>1785 Turner Road</td><td>Zoning</td><td>N/A</td></tr>
<tr><td><a href='https://evil.example.org/dossier'>OPA 202, OPA-7377 & SDN 001-26, SDN-7378</a></td>
<td>0 St. Luke Road</td><td>Official Plan, Zoning & Subdivision</td><td>N/A</td></tr>
<tr><td>Not a file ID</td><td>12 Warehouse Street</td><td>Industrial</td></tr></table></body></html>"""
PICKERING_INDEX = """<html><body><h1>Current Development Proposals</h1>
<table><thead><tr><th>Applicant</th><th>Address</th><th>Date Posted</th></tr></thead>
<tbody><tr><td><a href='/news/posts/plaza-6-inc/'>Plaza 6 Inc.</a></td>
<td>666, 668, 672, 678 & 682 Liverpool Road</td><td>January 27, 2026</td></tr>
<tr><td><a href='/news/posts/another/'>Old Builder</a></td><td>100 Old Road</td>
<td>June 1, 2020</td></tr></tbody></table></body></html>"""
PICKERING_DETAIL = """<html><body><h1>Plaza 6 Inc.</h1>
<p>By City of Pickering - Sep 29, 2026</p>
<h2>File Numbers</h2><p>Official Plan Amendment OPA 26-001P</p>
<p>Draft Plan of Subdivision SP-2026-01</p>
<p>Draft Plan of Condominium CP-2026-01</p>
<p>Zoning By-law Amendment A 01/26</p>
<h2>Applicant</h2><p>Plaza 6 Inc.</p>
<h2>Site Address</h2><p>666, 668, 672, 678 & 682 Liverpool Road</p><p>Ward 2</p>
<h2>City Contact</h2><p>Liam Crawford Planner II</p>
<h2>Proposal</h2><p>Proposed townhouse dwellings and new residential construction.</p>
<h2>Supporting Documents</h2><p>Architect drawings</p>
</body></html>"""

class HTMLPlanningPilotTests(unittest.TestCase):
    def test_windsor_composite_ids_and_no_external_link(self):
        rows=parse_windsor_index(WINDSOR_HTML)
        self.assertEqual(len(rows),2)
        self.assertIn("ZNG/7372",rows[0]["all_file_numbers"])
        self.assertIn("OPA-7377",rows[1]["all_file_numbers"])
        self.assertNotIn("evil.example.org",rows[1]["source_url"])
        self.assertEqual(rows[0]["source_date"],"")
        self.assertEqual(rows[0]["source_level"],"INDEX_ONLY")
        self.assertEqual(rows[0]["buyer_verified"],"False")
        self.assertFalse(any(r["original_publication_verified"]=="True" for r in rows))

    def test_pickering_index_date_not_a_fabricated_app_id(self):
        rows=parse_pickering_index(PICKERING_INDEX)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["index_posted_date"],"2026-01-27")
        self.assertEqual(rows[1]["index_posted_date"],"2020-06-01")
        self.assertEqual(rows[0]["status"],"INDEX_LINK_AWAIT_EXACT_FILE_NUMBER")
        self.assertEqual(rows[0]["project_page_url"],
                         "https://www.pickering.ca/news/posts/plaza-6-inc/")

    def test_pickering_project_detail_parses_exact_files_and_scope(self):
        rows=parse_pickering_detail(PICKERING_DETAIL,
                    page_url="https://www.pickering.ca/news/posts/plaza-6-inc/")
        self.assertEqual(len(rows),1)
        r=rows[0]
        self.assertEqual(r["application_id"],"OPA 26-001P")
        self.assertIn("CP-2026-01",r["all_file_numbers"])
        self.assertIn("A 01/26",r["all_file_numbers"])
        self.assertEqual(r["address"],
                         "666, 668, 672, 678 & 682 Liverpool Road")
        self.assertEqual(r["applicant_source_claim"],"Plaza 6 Inc.")
        self.assertEqual(r["source_date"],"2026-09-29")
        self.assertEqual(r["source_date_basis"],
                         "PUBLISHER_ARTICLE_DATE_NOT_PROVEN_FIRST_NOTICE")
        self.assertNotIn("Liam Crawford",r["applicant_source_claim"])
        self.assertEqual(r["buyer_verified"],"False")

    def test_pickering_missing_project_application_numbers_fail_closed(self):
        text=PICKERING_DETAIL.replace("OPA 26-001P","Unknown").replace(
            "SP-2026-01","Unknown").replace("CP-2026-01","Unknown").replace(
            "A 01/26","Unknown")
        self.assertEqual(parse_pickering_detail(
            text,page_url="https://www.pickering.ca/news/posts/plaza-6-inc/"),[])
        self.assertEqual(parse_pickering_detail(
            PICKERING_DETAIL,page_url="https://attacker.invalid/plaza-6/"),[])

    def test_snapshot_only_offline_and_zero_no_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            result=run(root/"results")
            self.assertEqual(result["records_with_file_ids_by_city"],
                             {"Windsor":0,"Pickering":0})
            self.assertFalse(result["live_source_fetch_performed"])
            source=root/"snapshots"
            (source/"pickering_details").mkdir(parents=True)
            (source/"windsor.html").write_text(WINDSOR_HTML,encoding="utf-8")
            (source/"pickering.html").write_text(PICKERING_INDEX,encoding="utf-8")
            (source/"pickering_details"/"one.html").write_text(
                PICKERING_DETAIL,encoding="utf-8")
            (source/"pickering_detail_urls.json").write_text(json.dumps(
                {"one.html":"https://www.pickering.ca/news/posts/plaza-6-inc/"}))
            result=run(root/"results",snapshot_dir=source)
            self.assertEqual(result["records_with_file_ids_by_city"],
                             {"Windsor":2,"Pickering":1})
            self.assertEqual(result["pickering_index_rows_without_verified_file_id"],2)
            self.assertEqual(result["production_city_count_unchanged"],24)
            with (root/"results"/"GTA_RADAR_WINDSOR_PICKERING_RESEARCH_APPLICATIONS.csv"
                  ).open(encoding="utf-8-sig") as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),3)
            self.assertTrue(all(x["buyer_verified"]=="False" for x in rows))
            self.assertFalse((root/"results"/"v5_ai_budget.sqlite").exists())

if __name__=="__main__":
    unittest.main()
