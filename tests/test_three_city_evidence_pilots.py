"""Offline acceptance: three new source-evidence pilots never invent fresh leads."""
from __future__ import annotations

import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

import gta_three_city_evidence_pilots as p

NIAGARA_URL = "https://webpublic.niagarafalls.ca/Planning/Details/411"
STC_URL = ("https://www.stcatharines.ca/news/posts/"
           "notice-of-complete-applications-and-open-house-109-st-paul-crescent/")


def niagara_page(scope="The applicant proposes construction of a new retail store "
                            "(Shoppers Drug Mart) with an environmental protection area."):
    return f"""<html><main><h1>Current Planning Application Details</h1>
    <h2>8168 McLeod Road (AM-2026-013)</h2>
    <p>{scope}</p>
    <h3>Meeting Date</h3><p>Tuesday, November 24, 2026</p>
    <h3>Application Types</h3><p>Zoning By-law Amendment</p>
    <h3>Associated Files</h3>
    <a href="/Files/Planning/Applications/411/site-plan.pdf">Site Plan</a>
    <a href="/Files/Planning/Applications/411/notice.pdf">Public Meeting Notice</a>
    <h3>Contact</h3><p>Nick DeBenedetti Planner 2, 905-356-7521</p>
    <a href="mailto:ndebenedetti@niagarafalls.ca">ndebenedetti@niagarafalls.ca</a>
    </main></html>"""


def stc_page(annex="a three-storey, 15-room annex building"):
    return f"""<html><main>
    <h1>Notice of Complete Applications and Open house - 109 St. Paul Crescent</h1>
    <p>Nov 12, 2026</p>
    <h3>PROPOSAL</h3>
    <p>The Planning Department received applications for lands located at 109 St. Paul Crescent.
    The Applications were declared complete as of October 16, 2025.</p>
    <p>The Applicant is seeking to facilitate {annex}.</p>
    <h3>MORE INFORMATION</h3>
    <p>Contact Dasha Litviniuc, Planner, at 905-680-7115,
    or by email dlitviniuc@stcatharines.ca.</p>
    <p>Refer to File No: 26 106602 OP &amp; 26 106603 ZA</p>
    </main></html>"""


def stc_index():
    return f"""<html><main><a href="{STC_URL}">
    Notice of Complete Applications and Open house - 109 St. Paul Crescent</a>
    <a href="/news/posts/notice-of-inaugural-meeting/">
    Notice of Inaugural Meeting</a></main></html>"""


def niagara_row():
    return {
        "project_id": "GGH:NIAGARA FALLS:AM-2026-013",
        "city": "Niagara Falls", "application_id": "AM-2026-013",
        "address": "8168 McLeod Road",
        "description": "Zoning By-law Amendment (ZBA) Official Plan Amendment (OPA)",
        "official_record_url": NIAGARA_URL,
    }


def schema(layer):
    attrs = p.FIELDS_PLANNING if layer == "PLANNING" else p.FIELDS_PERMIT
    fields = [{"name":"OBJECTID","type":"esriFieldTypeOID"}]
    for names in attrs.values():
        if names:
            fields.append({"name":names[0],"type":"esriFieldTypeString"})
    return {"objectIdField":"OBJECTID","fields":fields}


def brantford_json(base, params):
    layer = next(k for k,v in p.BRANTFORD.items() if v == base)
    if params == {"f":"json"}:
        return schema(layer)
    if layer == "PLANNING":
        return {"features":[{"attributes":{
            "OBJECTID":77, "ApplicationNum":"ZBA-2026-009",
            "Address":"200 Industrial Road", "Description":"New industrial warehouse",
            "Submitted_date":1793491200000, "Status":"Under Review",
            "Applicant":"Example Manufacturing Ltd", "Planner_assigned":"City Planner",
            "Planner_email":"planning@brantford.ca"}}]}
    return {"features":[{"attributes":{
        "OBJECTID":11, "PermitNumber":"PR-2026-0321",
        "Address":"101 Industrial Street", "WorkType":"Addition to industrial building",
        "IssueDate":1793491200000, "Status":"Issued",
        "Applicant":"Example Components Inc"}}]}


class ThreeCityEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        with (self.root/p.NIAGARA_INDEX).open("w",newline="",encoding="utf-8") as fp:
            writer=csv.DictWriter(fp, fieldnames=list(niagara_row()))
            writer.writeheader()
            writer.writerow(niagara_row())

    def html_fetch(self, url):
        if url == NIAGARA_URL:
            return niagara_page()
        if url == p.STC_INDEX:
            return stc_index()
        if url == STC_URL:
            return stc_page()
        raise AssertionError("Unexpected network URL " + url)

    def read(self, name):
        with (self.root/name).open(encoding="utf-8-sig",newline="") as fp:
            return list(csv.DictReader(fp))

    def test_niagara_id_scope_documents_meeting_planner(self):
        got=p.parse_niagara(niagara_page(),niagara_row())
        self.assertIn("Shoppers Drug Mart",got["scope"])
        self.assertEqual(got["application_id"],"AM-2026-013")
        self.assertEqual(got["meeting_date"],"2026-11-24")
        self.assertEqual(got["source_document_count"],"2")
        self.assertEqual(got["planner_name"],"Nick DeBenedetti")
        self.assertEqual(got["planner_email_public"],"ndebenedetti@niagarafalls.ca")
        self.assertEqual(got["supplier_buyer_verified"],"False")
        self.assertEqual(got["first_project_publication_verified"],"False")

    def test_niagara_rejects_unrelated_page_and_nonofficial_link(self):
        wrong = dict(niagara_row())
        wrong["application_id"] = "AM-2026-018"
        with self.assertRaisesRegex(ValueError,"DETAIL_ID_NOT_MATCHED"):
            p.parse_niagara(niagara_page(),wrong)
        wrong["official_record_url"] = "https://evil.example/Planning/Details/411"
        with self.assertRaisesRegex(ValueError,"INVALID_NIAGARA_DETAIL_LINK"):
            p.parse_niagara(niagara_page(),wrong)

    def test_stc_posted_vs_completed_are_not_first_project_publication(self):
        got=p.parse_stc(stc_page(), STC_URL, today=dt.date(2026,11,17))
        self.assertEqual(got["notice_posted_date"],"2026-11-12")
        self.assertEqual(got["application_complete_date"],"2025-10-16")
        self.assertIn("15-room annex",got["scope"])
        self.assertEqual(got["planner_email_public"],"dlitviniuc@stcatharines.ca")
        self.assertEqual(got["planner_name"],"Dasha Litviniuc")
        self.assertIn("106602 OP",got["application_id"])
        self.assertFalse(got["first_project_publication_verified"]=="True")

    def test_stc_live_article_metadata_date_and_lowercase_contact_name(self):
        # November 17 run returned blank dates despite the official news
        # pages showing dates just above the notice category/PROPOSAL heading.
        page=stc_page().replace("<p>Nov 12, 2026</p>",
            "<p>Nov 12, 2026</p><div>Public Notices</div>")
        page=page.replace("Contact Dasha Litviniuc", "contact Dasha Litviniuc")
        record=p.parse_stc(page,STC_URL,today=dt.date(2026,11,17))
        self.assertEqual(record["notice_posted_date"],"2026-11-12")
        self.assertEqual(record["application_complete_date"],"2025-10-16")
        self.assertEqual(record["planner_name"],"Dasha Litviniuc")

    def test_date_is_not_fabricated_when_notice_lacks_posting(self):
        got=p.parse_stc(stc_page().replace("Nov 12, 2026",""),STC_URL,
                        today=dt.date(2026,11,17))
        self.assertEqual(got["notice_posted_date"],"")
        self.assertEqual(got["application_complete_date"],"2025-10-16")

    def test_brantford_both_official_schema_lanes(self):
        planning, audit=p._fetch_brantford("PLANNING",json_fetch=brantford_json,
                                         today=dt.date(2026,11,17))
        permit,_=p._fetch_brantford("BUILDING_PERMIT",json_fetch=brantford_json,
                                   today=dt.date(2026,11,17))
        self.assertEqual(len(planning),1)
        self.assertEqual(len(permit),1)
        self.assertEqual(planning[0]["application_id"],"ZBA-2026-009")
        self.assertEqual(planning[0]["applicant_name_source_claim"],"Example Manufacturing Ltd")
        self.assertEqual(planning[0]["source_date_basis"],
                         "CITY_PLANNING_SUBMITTED_DATE_NOT_PUBLICATION")
        self.assertEqual(permit[0]["source_date_basis"],
                         "CITY_PERMIT_ISSUE_DATE_NOT_PUBLICATION")
        self.assertEqual(permit[0]["record_kind"],"OFFICIAL_PERMIT")
        self.assertFalse(audit["publisher_publication_date_verified"])

    def test_brantford_missing_application_number_is_held(self):
        def no_id(base,params):
            if params == {"f":"json"}:
                return {"objectIdField":"OBJECTID","fields":[
                    {"name":"OBJECTID","type":"esriFieldTypeOID"},
                    {"name":"Applicant","type":"esriFieldTypeString"}]}
            raise AssertionError("MUST_NOT_QUERY_UNKNOWN_SCHEMA")
        with self.assertRaisesRegex(ValueError,"IDENTIFIER_FIELD_MISSING"):
            p._fetch_brantford("PLANNING",json_fetch=no_id)

    def test_first_run_baseline_then_change_no_freshness_claim(self):
        now=dt.date(2026,11,17)
        first=p.run(self.root, today=now,html_fetch=self.html_fetch,
                    json_fetch=brantford_json)
        self.assertEqual(first["candidate_rows"],4)
        self.assertEqual(first["changed_source_rows_not_new_project_proof"],0)
        self.assertEqual(first["municipalities_added_to_verified_16_city_count"],0)
        self.assertTrue(all(x["observation"]=="INITIAL_BASELINE_NOT_NEW_PUBLICATION"
                            for x in self.read(p.OUTPUT)))
        again=p.run(self.root,today=now,html_fetch=self.html_fetch,
                    json_fetch=brantford_json)
        self.assertEqual(again["changed_source_rows_not_new_project_proof"],0)
        def altered(url):
            return niagara_page(scope="New commercial retail pharmacy with altered site plan") \
                if url == NIAGARA_URL else self.html_fetch(url)
        after=p.run(self.root,today=now,html_fetch=altered,
                    json_fetch=brantford_json)
        self.assertEqual(after["changed_source_rows_not_new_project_proof"],1)
        self.assertEqual(after["original_publisher_first_disclosures_verified"],0)
        self.assertEqual(self.read(p.CHANGES)[0]["city"],"Niagara Falls")

    def test_brantford_access_blocked_no_fake_success_or_baseline(self):
        def blocked(base,params):
            raise ValueError("ROBOTS_DENIED:DISALLOWED")
        report=p.run(self.root,today=dt.date(2026,11,17),
                     html_fetch=self.html_fetch,json_fetch=blocked)
        self.assertEqual(report["candidate_rows"],2)
        self.assertTrue(all(x["status"]=="SOURCE_BLOCKED_OR_UNSUPPORTED"
             for x in report["sources"] if x["city"]=="Brantford"))
        self.assertEqual(report["verified_project_buyers"],0)
        self.assertTrue((self.root/p.STATUS).is_file())

    def test_niagara_csv_only_uses_true_detail_links(self):
        bad = dict(niagara_row())
        bad["official_record_url"] = "https://webpublic.niagarafalls.ca/Planning"
        with (self.root/p.NIAGARA_INDEX).open("w",newline="",encoding="utf-8") as fp:
            writer=csv.DictWriter(fp,fieldnames=list(bad))
            writer.writeheader()
            writer.writerow(bad)
        self.assertEqual(p._niagara_sources(self.root),[])


if __name__ == "__main__":
    unittest.main()
