"""Regression: November 2 run failure modes + sixteen early-application sources."""
from __future__ import annotations

import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import gta_early_applications as ea
import gta_document_priority as triage
import gta_daily_intelligence as daily
import free_daily_report as free

DAY=dt.date(2026,11,2)

class SixteenEarlyApplicationsTests(unittest.TestCase):
    def test_all_sixteen_municipalities_are_present_and_unique(self):
        self.assertEqual(len(ea.SOURCES),16)
        self.assertEqual(len(set(ea.SOURCES.values())),16)
        self.assertEqual(set(ea.SOURCES),{
            "Toronto","Brampton","Mississauga","Hamilton","Burlington",
            "Oakville","Vaughan","Kitchener","Markham","Oshawa","Milton",
            "Halton Hills","Caledon","Cambridge","Waterloo","Guelph"})

    def test_extracts_file_id_only_with_actual_commercial_project(self):
        html="""<html><nav><a href='/menu'>Planning applications</a></nav>
          <li>New industrial warehouse development application OZ/OPA 26-12 W7
            at 1770 Industrial Road with industrial units</li>
          <li>OZ 26-13 W1: new residential apartments, 200 dwelling units</li>
          <li>Historical citywide planning policies and annual calendar</li>
          </html>"""
        p,links=ea._rows(html,"Mississauga",ea.SOURCES["Mississauga"])
        self.assertEqual(len(p),1)
        self.assertEqual(p[0]["application_id"],"OZ/OPA 26-12 W7")
        self.assertIn("INDUSTRIAL",p[0]["description"].upper())
        self.assertEqual(p[0]["record_source_url_basis"],
                         "OFFICIAL_INDEX_CONTEXT_ONLY_NOT_EXACT_RECORD")
        self.assertEqual(p[0]["source_record_date"],"")

    def test_baseline_then_changed_then_stable_without_creating_false_publication(self):
        with tempfile.TemporaryDirectory() as td:
            city="Mississauga";url=ea.SOURCES[city];root=Path(td)
            doc1="<li>OZ 26-4 W9 proposed industrial distribution warehouse</li>"
            doc2="<li>OZ 26-4 W9 expanded industrial distribution warehouse addition</li>"
            a=ea.run(root,today=DAY,fetcher=lambda _:doc1,sources={city:url})
            self.assertTrue(a["baseline_only"])
            self.assertEqual(a["new_or_changed_application_records"],0)
            self.assertEqual(a["application_candidate_rows"],1)
            b=ea.run(root,today=DAY+dt.timedelta(days=1),fetcher=lambda _:doc2,sources={city:url})
            self.assertFalse(b["baseline_only"])
            self.assertEqual(b["new_or_changed_application_records"],1)
            rows=daily._csv(root/ea.NEW)
            self.assertEqual(rows[0]["observation"],"RECORD_CHANGED")
            self.assertEqual(rows[0]["changed_fields"],"description")
            self.assertEqual(rows[0]["first_seen_local"],DAY.isoformat())
            self.assertFalse(rows[0]["source_record_date"])
            c=ea.run(root,today=DAY+dt.timedelta(days=2),fetcher=lambda _:doc2,sources={city:url})
            self.assertEqual(c["new_or_changed_application_records"],0)

    def test_mixed_success_and_blocked_city_never_claims_all_city_data(self):
        with tempfile.TemporaryDirectory() as td:
            sources={"Mississauga":ea.SOURCES["Mississauga"],
                     "Vaughan":ea.SOURCES["Vaughan"]}
            def fake(url):
                if "vaughan" in url:raise PermissionError("HTTP 403")
                return "<li>OZ 26-4 W9 proposed industrial warehouse</li>"
            result=ea.run(td,fetcher=fake,sources=sources,today=DAY)
            self.assertEqual(result["cities_configured"],2)
            self.assertEqual(result["indexes_fetched"],1)
            self.assertEqual(result["indexes_failed"],1)
            self.assertEqual(result["cities_with_parsed_ids"],1)
            self.assertEqual(result["project_filing_or_first_publication_dates_verified"],0)
            self.assertEqual(result["automatically_promoted_to_canonical_projects"],0)

    def test_city_that_first_blocks_and_later_succeeds_starts_with_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            city="Vaughan";url=ea.SOURCES[city]
            denied=ea.run(td,today=DAY,fetcher=lambda _:(_ for _ in ()).throw(
                PermissionError("HTTP 403")),sources={city:url})
            self.assertEqual(denied["indexes_failed"],1)
            allowed=ea.run(td,today=DAY+dt.timedelta(days=1),
                           fetcher=lambda _:"<li>OZ 26-17 W1 new industrial warehouse</li>",
                           sources={city:url})
            self.assertEqual(allowed["application_candidate_rows"],1)
            self.assertEqual(allowed["new_or_changed_application_records"],0)
            self.assertEqual(daily._csv(Path(td)/ea.CANDIDATES)[0]["observation"],
                             "INITIAL_BASELINE")

    def test_external_links_not_promoted_as_official_citations(self):
        url=ea.SOURCES["Mississauga"]
        html="""<li><a href='https://evil.example/OZ-26-4'>OZ 26-4 W9 new industrial warehouse</a></li>"""
        projects,_=ea._rows(html,"Mississauga",url)
        self.assertEqual(len(projects),1)
        self.assertEqual(projects[0]["record_source_url"],url)
        self.assertFalse(ea._safe("https://www.mississauga.ca.evil.com/x",url))

    def test_aggregated_environmental_notices_not_miscounted_as_one_project(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            source=root/"v4.csv"
            samples=[
                {"project_id":"toronto:permit","source_id":"toronto_active_building_permits",
                 "source_keys":"26 255555 BLD|00","description":"New industrial warehouse building",
                 "source_record_date":"2026-11-01","lane":"PERMIT_REVIEW",
                 "source_group":"MUNICIPAL_CHANGE"},
                {"project_id":"ero:provincewide","source_id":"ero_gta_environmental_instruments",
                 "source_keys":"provincial notices","description":("Unrelated environmental notice "+
                   "Windsor, Ottawa and other Ontario municipalities. ")*100,
                 "source_record_date":"2026-10-31","lane":"ENVIRONMENT_WATCH",
                 "source_group":"MUNICIPAL_CHANGE"},
            ]
            with source.open("w",newline="",encoding="utf-8-sig") as h:
                w=csv.DictWriter(h,fieldnames=list(samples[0]))
                w.writeheader();w.writerows(samples)
            free.build(source,root,today=DAY)
            # Subsequent source change makes both records first-observed.
            (root/free.STATE_NAME).write_text(
                json.dumps({"schema":1,"seen":{}}),encoding="utf-8")
            result=free.build(source,root,today=DAY+dt.timedelta(days=1))
            rows=free._read(root/free.CSV_NAME)
            self.assertEqual([r["project_id"] for r in rows],["toronto:permit"])
            self.assertEqual(result["new_or_changed"],1)
            full=free._read(root/free.ALL_NAME)
            self.assertEqual(len(full),2)
            self.assertTrue(rows[0].get("official_source_portal_url","").startswith("https://"))
            self.assertFalse(rows[0].get("record_source_url"))

    def test_legacy_change_without_original_field_values_not_manufactured(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=root/"input.csv"
            attrs={"project_id":"toronto:legacy","source_id":"toronto_active_building_permits",
                   "source_keys":"26 222222 BLD","description":"Proposed new warehouse",
                   "source_record_date":"2026-10-31","lane":"PERMIT_REVIEW",
                   "current_source_status":"Under Review"}
            with p.open("w",encoding="utf-8-sig",newline="") as fh:
                writer=csv.DictWriter(fh,fieldnames=attrs.keys());writer.writeheader()
                writer.writerow(attrs)
            old={"schema":1,"seen":{"toronto:legacy":{
                "fingerprint":"old-hash-without-snapshot","first_seen_local":"2026-10-10"}}}
            (root/free.STATE_NAME).write_text(json.dumps(old),encoding="utf-8")
            free.build(p,root,today=DAY)
            rows=free._read(root/free.CSV_NAME)
            self.assertEqual(rows[0]["observation"],"RECORD_CHANGED")
            self.assertEqual(rows[0]["changed_fields"],"UNDETERMINED_LEGACY_FINGERPRINT_CHANGE")

class PdfPriorityTests(unittest.TestCase):
    def fake_pdf(self,contents):
        class Page:
            def extract_text(self):return contents
        class Document:
            is_encrypted=False
            pages=[Page()]
        return Document()
    def test_nov2_calendar_condolence_and_procedural_bylaw_never_consume_ai(self):
        docs=(
            "Expression of Condolence for a community member by Toronto City Council",
            "2026 Municipal Meeting Calendar January February March",
            "A By-law to govern the proceedings of council and committees",
            "City of Burlington Consolidated Procedure By-law",
        )
        with tempfile.TemporaryDirectory() as td:
            fake=Path(td)/"report.pdf";fake.write_bytes(b"%PDF-TEST")
            for text in docs:
                with self.subTest(text=text):
                    with patch.object(triage,"PdfReader",return_value=self.fake_pdf(text)):
                        got=triage.assess({"url":"https://www.toronto.ca/report.pdf",
                                           "saved_path":str(fake)})
                    self.assertFalse(got["eligible_for_paid_ai"])
                    self.assertEqual(got["class"],"UNRELATED_NONPROJECT_DOCUMENT")
    def test_new_industrial_site_plan_report_is_priority(self):
        with tempfile.TemporaryDirectory() as td:
            fake=Path(td)/"report.pdf";fake.write_bytes(b"%PDF-TEST")
            contents="City Planning Staff Recommendation Report. Site Plan Application. Proposed industrial warehouse development at 14 Example Road. Applicant file no OZ 26-12."
            with patch.object(triage,"PdfReader",return_value=self.fake_pdf(contents)):
                result=triage.assess({"url":"https://www.mississauga.ca/report.pdf","saved_path":str(fake)})
            self.assertTrue(result["eligible_for_paid_ai"])
            self.assertGreaterEqual(result["score"],12)
    def test_bad_or_unextractable_pdf_is_not_sent_to_paid_ai(self):
        with tempfile.TemporaryDirectory() as td:
            bad=Path(td)/"report.pdf";bad.write_bytes(b"not a PDF")
            status=triage.assess({"url":"https://example.com/a.pdf","saved_path":str(bad)})
            self.assertFalse(status["eligible_for_paid_ai"])
            self.assertEqual(status["class"],"NEEDS_TEXT_EXTRACTION_REVIEW")


if __name__=="__main__":
    unittest.main()
