"""Regression checks for measured city coverage and missing municipal feeders."""
from __future__ import annotations
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from gta_early_applications import _rows,SOURCES
import gta_additional_city_gis as ag
from gta_city_coverage_report import build

TODAY=dt.date(2026,11,2)

class MunicipalHTMLExtractors(unittest.TestCase):
    def test_caledon_points_to_current_applications_not_forms(self):
        self.assertTrue(SOURCES["Caledon"].endswith("/current-applications.aspx"))
        self.assertEqual(SOURCES["Burlington"], "https://www.burlington.ca/news-and-notices/news-views/current-development-projects/")
        html="<li>RZ 2025-0027 - New industrial warehouse at 20836 Kennedy Road</li>"
        rows,_=_rows(html,"Caledon",SOURCES["Caledon"])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["application_id"],"RZ 2025-0027")
        self.assertFalse(rows[0]["source_record_date"])
        self.assertEqual(rows[0]["observation"] if "observation" in rows[0] else "UNBASELINED",
                         "UNBASELINED")

    def test_halton_hills_table_industrial_is_not_lost(self):
        html="""<table><tr><th>ID</th><th>Location</th><th>File No.</th><th>Description</th></tr>
        <tr><td>18</td><td>49 Commerce Crescent</td><td>D11SPA11.005.RV1</td>
        <td>Addition to existing industrial building</td></tr>
        <tr><td>3</td><td>125 Ninth Line</td><td>D12SUB09.001</td>
        <td>Detached residential lots</td></tr></table>"""
        rows,_=_rows(html,"Halton Hills",SOURCES["Halton Hills"])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["application_id"],"D11SPA11.005.RV1")
        self.assertIn("49 Commerce Crescent",rows[0]["description"])

    def test_cambridge_industrial_case_without_cross_contamination(self):
        html="""<h3>R02/26 - 210 Royal Oak Road</h3>
        <p>The City received a zoning amendment for industrial warehouse use.</p>
        <h3>R10/26 - 579 Grand Ridge Drive</h3>
        <p>52 affordable residential apartment units.</p>"""
        rows,_=_rows(html,"Cambridge",SOURCES["Cambridge"])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["application_id"],"R02/26")

class GISSourceRegression(unittest.TestCase):
    def test_hamilton_kitchener_are_actual_official_service_layers(self):
        self.assertEqual({r["city"] for r in ag.SOURCES.values()},
                         {"Hamilton","Kitchener"})
    def test_commercial_extraction_only_real_file_id(self):
        attrs={"FILE_NAME":"Z-26-021","DESCRIPTION":"New logistics distribution warehouse",
               "LOCATION":"22 Example Street","FILE_TYPE":"Zoning","OBJECTID":11}
        row=ag._parse("Hamilton","https://official.example/2",attrs)
        self.assertEqual(row["application_id"],"Z-26-021")
        self.assertFalse(row["source_record_date"])
        self.assertIsNone(ag._parse("Hamilton","https://official.example/2",
                         {"OBJECTID":11,"DESCRIPTION":"New industrial plant"}))
        self.assertIsNone(ag._parse("Hamilton","https://official.example/2",
                         {**attrs,"DESCRIPTION":"Residential detached lots"}))

    def test_first_successful_fetch_baselines_and_failed_feed_does_not(self):
        def fake(url,params):
            if "qAo1OsXi67t7XgmS" in url:
                raise PermissionError("SOURCE_DENIED")
            if url.endswith("/query"):
                return {"features":[{"attributes":{
                    "OBJECTID":10,"FILE_NAME":"Z-26-021","LOCATION":"22 Main Street",
                    "DESCRIPTION":"Industrial logistics warehouse"}}]}
            return {"objectIdField":"OBJECTID",
                    "fields":[{"name":k} for k in ("OBJECTID","FILE_NAME","LOCATION","DESCRIPTION")]}
        with tempfile.TemporaryDirectory() as td:
            first=ag.run(td,today=TODAY,fetcher=fake)
            self.assertEqual(first["sources_successful"],1)
            self.assertEqual(first["commercial_candidates"],1)
            self.assertEqual(first["new_or_changed"],0)
            self.assertEqual({x["status"] for x in first["source_status"]},
                             {"BASELINE_COMPLETE","FAILED_OR_INCOMPLETE"})
            next_run=ag.run(td,today=TODAY+dt.timedelta(days=1),fetcher=fake)
            self.assertEqual(next_run["new_or_changed"],0)
            allrows=list(csv.DictReader((Path(td)/ag.ALL).open(encoding="utf-8-sig")))
            self.assertEqual(allrows[0]["observation"],"UNCHANGED")

    def test_never_baseline_incomplete_pagination(self):
        def fake(url,params):
            if url.endswith("/query"):
                return {"features":[{"attributes":{
                    "OBJECTID":1,"FILE_NAME":"Z-26-021",
                    "DESCRIPTION":"Industrial warehouse"}}]*ag.PAGE}
            return {"objectIdField":"OBJECTID","fields":[{"name":k} for k in (
                "OBJECTID","FILE_NAME","DESCRIPTION")]}
        with tempfile.TemporaryDirectory() as td:
            result=ag.run(td,fetcher=fake,max_pages=1,
                sources={"HAMILTON_DEVELOPMENT_APPLICATIONS":
                         ag.SOURCES["HAMILTON_DEVELOPMENT_APPLICATIONS"]})
            self.assertEqual(result["sources_successful"],0)
            self.assertFalse(json.loads((Path(td)/ag.STATE).read_text())["sources"])

class MeasuredCoverageTests(unittest.TestCase):
    def test_sixteen_configured_does_not_mean_sixteen_working(self):
        with tempfile.TemporaryDirectory() as td:
            records=[{"city":city,"fetch_status":"INDEX_FETCHED" if city=="Mississauga"
                      else "INDEX_ONLY_NO_STRUCTURED_APPLICATIONS",
                      "actual_application_rows":29 if city=="Mississauga" else 0}
                     for city in SOURCES]
            result=build(td,{"city_status":records},{"source_status":[]},
                         {"source_status":[]},{"rows_extracted":0})
            self.assertEqual(result["cities_configured"],16)
            self.assertEqual(result["cities_with_extracted_application_candidates"],1)
            self.assertEqual(result["cities_without_extracted_applications"],15)
            self.assertEqual(result["verified_citywide_complete_coverage"],0)
            self.assertEqual(len(list(csv.DictReader(
                (Path(td)/"GTA_RADAR_CITY_COVERAGE_AUDIT.csv").open(
                    encoding="utf-8-sig")))),16)

if __name__=="__main__":unittest.main()
