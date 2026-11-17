"""Offline acceptance for permitted Mississauga HTML detail intake.

No internet, GIS access bypass, paid AI or automatic sales qualification.
"""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from gta_mississauga_detail_recovery import (
    parse_detail, run, INDEX, OUTPUT, CHANGES, STATUS, LEDGER, _safe_link,
)

LINK = ("https://www.mississauga.ca/services-and-programs/planning-and-development/"
        "development-applications/active-development-applications/"
        "2915-derry-road-east-oz-opa-26-15-w5/")

def html(scope="To permit the construction of a 9-storey hotel building with a "
               "restaurant and banquet hall space.",
         posted="October 29, 2026", updated="October 29, 2026"):
    return f"""<!DOCTYPE html><html><main>
      <div>Received</div><div>2849404 Ontario Inc.</div>
      <h1>2915 Derry Road East – OZ/OPA 26-15 W5</h1>
      <p>{scope}</p>
      <p>Posted: {posted} - Updated: {updated}</p>
      <h2>Project documents</h2>
      <p><a href="/plans/notice.pdf">Public Meeting Notice</a></p>
      <h2>Contact</h2>
      <p>For more information on this application, email City Planner
      Connor Di Pietro at connor.dipietro@mississauga.ca.</p>
    </main></html>"""

def candidate(url=LINK, city="Mississauga"):
    return {
        "project_id": "EARLY_APP:MISSISSAUGA:OZ/OPA26-15W5",
        "city": city, "application_id": "OZ/OPA 26-15 W5",
        "description": "Received 2915 Derry Road East – OZ/OPA 26-15 W5 hotel",
        "record_source_url": url,
        "source_url": ("https://www.mississauga.ca/services-and-programs/"
                       "planning-and-development/development-applications/"
                       "active-development-applications/"),
    }

def write_index(root, items):
    with (root / INDEX).open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(items[0]))
        writer.writeheader()
        writer.writerows(items)

def read(root, name):
    with (root / name).open(encoding="utf-8-sig", newline="") as fp:
        return list(csv.DictReader(fp))


class MississaugaDetailTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        write_index(self.root, [candidate()])

    def test_official_posted_date_applicant_and_planner_not_buyer(self):
        record = parse_detail(html(), candidate(), today=date(2026, 11, 17))
        self.assertEqual(record["application_id"], "OZ/OPA 26-15 W5")
        self.assertEqual(record["publisher_page_posted_date"], "2026-10-29")
        self.assertEqual(record["publisher_page_updated_date"], "2026-10-29")
        self.assertEqual(record["applicant_name_source_claim"], "2849404 Ontario Inc.")
        self.assertEqual(record["city_planner_name"], "Connor Di Pietro")
        self.assertEqual(record["city_planner_email"], "connor.dipietro@mississauga.ca")
        self.assertIn("banquet hall", record["description"])
        self.assertEqual(record["buyer_verified"], "False")
        self.assertEqual(record["publisher_first_construction_disclosure_verified"], "False")

    def test_first_detail_crawl_baseline_not_new_project(self):
        called = []
        def fetch(url):
            called.append(url)
            return html()
        report = run(self.root, fetcher=fetch, today=date(2026,11,17))
        self.assertEqual(called, [LINK])
        self.assertEqual(report["pages_collected"], 1)
        self.assertEqual(report["pages_with_named_applicant"], 1)
        self.assertEqual(report["pages_with_planner_email"], 1)
        self.assertEqual(report["publisher_first_construction_disclosures_verified"], 0)
        self.assertEqual(read(self.root,OUTPUT)[0]["observation"], "INITIAL_DETAIL_BASELINE")
        self.assertEqual(read(self.root,CHANGES), [])

    def test_changed_page_is_update_only_not_first_publication(self):
        run(self.root, fetcher=lambda _:html(), today=date(2026,11,17))
        result = run(self.root, fetcher=lambda _:html(scope=
            "To construct the revised 9-storey hotel plus rooftop amenity."),
            today=date(2026,11,17))
        self.assertEqual(result["changed_detail_pages_not_new_projects"], 1)
        self.assertEqual(read(self.root, CHANGES)[0]["observation"],
                         "DETAIL_PAGE_CHANGED_NOT_NEW_PUBLICATION")
        self.assertEqual(result["publisher_first_construction_disclosures_verified"], 0)

    def test_failed_source_preserves_prior_history(self):
        run(self.root, fetcher=lambda _:html(), today=date(2026,11,17))
        def blocked(_):
            raise ValueError("ROBOTS_ACCESS_DENIED")
        result=run(self.root, fetcher=blocked, today=date(2026,11,17))
        self.assertEqual(result["pages_collected"], 0)
        self.assertEqual(result["page_failures"][0]["error"], "ValueError:ROBOTS_ACCESS_DENIED")
        saved=json.loads((self.root/LEDGER).read_text())
        self.assertEqual(len(saved["records"]), 1)

    def test_mismatched_application_id_held(self):
        report=run(self.root,fetcher=lambda _:html().replace(
            "OZ/OPA 26-15 W5", "OZ 20-13 W5"),today=date(2026,11,17))
        self.assertEqual(report["pages_collected"], 0)
        self.assertIn("DETAIL_APPLICATION_ID_NOT_IN_TITLE",report["page_failures"][0]["error"])

    def test_cross_host_and_portal_urls_rejected(self):
        self.assertFalse(_safe_link("https://services6.arcgis.com/rest/query"))
        self.assertFalse(_safe_link("https://www.mississauga.ca.evil.example/applications/"))
        self.assertFalse(_safe_link(LINK+"?redirect=1"))
        write_index(self.root, [candidate(url="https://attacker.example/bait")])
        report=run(self.root,fetcher=lambda _:self.fail("network request"),today=date(2026,11,17))
        self.assertEqual(report["pages_attempted"],0)

    def test_future_posting_date_rejected(self):
        report=run(self.root,fetcher=lambda _:html(posted="December 9, 2027"),
                   today=date(2026,11,17))
        self.assertEqual(report["pages_collected"],0)
        self.assertIn("FUTURE_DETAIL_PAGE_DATE",report["page_failures"][0]["error"])


if __name__ == "__main__":
    unittest.main()
