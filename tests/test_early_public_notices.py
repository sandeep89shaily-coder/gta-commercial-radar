"""Offline fixtures for free Milton, Pickering and ERO public-source review."""
import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import early_public_notices as n


def milton_html(entries=True):
    body = """<main><h1>Development Notices</h1><ul>
    <li class="news-item">
    <a href="/news/posts/notice-of-complete-application-6554-tremaine-road/">
      Notice of Complete Application: 6554 Tremaine Road</a>
    <time>Oct 09, 2026</time><a href="/news/development-notices/">Development Notices</a></li>
    <li class="news-item"><a href="/news/posts/notice-of-complete-application-0-quarry-crescent/">
    Notice of Complete Application: 0 Quarry Crescent</a><time>Oct 21, 2026</time></li>
    </ul></main>""" if entries else "<main><h1>Development Notices</h1><p>No items</p></main>"
    return "<!doctype html><html><body>"+body+"</body></html>"


PICKERING_HTML = """<html><body><main><h1>Current Development Proposals</h1>
    <h2>Ward 2</h2><table><thead><tr>
       <th>Applicant</th><th>Address</th><th>Date Posted</th></tr></thead>
       <tbody><tr><td><a href="/news/posts/bessada-ev-division-inc/">Bessada EV Division Inc.</a></td>
       <td>1675 and 1695 Bayly Street <a href="https://media-002-ca.cdn.govstack.com/test.pdf">Location Map</a></td>
       <td>May 19, 2026</td></tr>
       <tr><td><a href="/news/posts/seaton-commercial-development-ltd/">Seaton Commercial Development Ltd.</a></td>
       <td>South side of Taunton Road, between Burkholder Drive and Peter Matthews Drive</td>
       <td>August 5, 2025</td></tr></tbody></table></main></body></html>"""

PICKERING_DETAIL = """<html><body><main><h1>Bessada EV Division Inc.</h1>
<h2>File Number</h2><p>A 02/26</p>
<h2>Proposal</h2>
<p>The applicant is proposing a two-storey addition to the existing Kia dealership,
including a new electric vehicle division and service bays.</p>
<h2>Supporting Documents</h2></main></body></html>"""


class Reply:
    def __init__(self, html):self.text=html
    def raise_for_status(self):pass


class Session:
    def __init__(self,mapping):self.mapping=mapping;self.calls=[]
    def get(self,url,params=None,headers=None,timeout=None):
        self.calls.append((url,params))
        if url not in self.mapping:
            raise n.requests.RequestException("not in test fixture")
        return Reply(self.mapping[url])


class NoticeTests(unittest.TestCase):
    def test_milton_official_links_and_published_dates(self):
        rows,warning=n.parse_milton(milton_html())
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["source_date"],"2026-10-09")
        self.assertIn("www.milton.ca/news/posts",rows[0]["source_url"])
        self.assertEqual(rows[1]["source_date"],"2026-10-21")
        self.assertNotIn("FULL_HISTORY",warning.replace("NOT_FULL_HISTORY","")) # bounded index

    def test_milton_no_listing_fails(self):
        with self.assertRaisesRegex(RuntimeError,"not found"):
            n.parse_milton(milton_html(False))

    def test_pickering_company_address_and_date(self):
        rows,warning=n.parse_pickering(PICKERING_HTML)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["company"],"Bessada EV Division Inc.")
        self.assertEqual(rows[0]["site"],"1675 and 1695 Bayly Street")
        self.assertEqual(rows[0]["source_date"],"2026-05-19")
        self.assertEqual(rows[1]["source_date"],"2025-08-05")
        self.assertIn("ACTIVE_PLANNING_INDEX",warning)

    def test_pickering_detail_converts_unknown_to_commercial(self):
        rows,_=n.parse_pickering(PICKERING_HTML)
        self.assertEqual(rows[0]["commercial_fit"],"USE_UNKNOWN")
        session=Session({"https://www.pickering.ca/news/posts/bessada-ev-division-inc/":PICKERING_DETAIL})
        result,warnings=n.enrich_recent(rows[:1],session,"pickering",1)
        self.assertEqual(warnings,[])
        self.assertEqual(result[0]["commercial_fit"],"POSSIBLE_COMMERCIAL")
        self.assertEqual(result[0]["attributes"]["detail_checked"],"YES")

    def test_mixed_and_residential_without_false_contracts(self):
        self.assertEqual(n.classify("New townhouses and apartments"),"RESIDENTIAL_LIKELY")
        self.assertEqual(n.classify("Residential condos with office retail"),"MIXED_USE_REVIEW")
        self.assertEqual(n.classify("New warehouse and cold storage"),"POSSIBLE_COMMERCIAL")

    def test_ero_proposal_filter_uses_existing_parser(self):
        sample=[dict(ERO_NUMBER="026-1234",TITLE="Example factory - New",
                     NOTICE_STAGE="Proposal",INSTRUMENT_TYPE="Environmental Compliance Approval",
                     SUMMARY="Industrial plant in Mississauga",
                     PROPOSAL_POSTED="October 10, 2026",
                     NOTICE_URL="https://ero.ontario.ca/notice/026-1234",
                     ENTITY_NAME="Example factory"),
               dict(ERO_NUMBER="026-4321",TITLE="Other factory - Decision",
                     NOTICE_STAGE="Decision",INSTRUMENT_TYPE="Environmental Compliance Approval",
                     SUMMARY="Factory Mississauga",PROPOSAL_POSTED="October 10, 2026",
                     NOTICE_URL="https://ero.ontario.ca/notice/026-4321",
                     ENTITY_NAME="Other factory")]
        with patch("radar._parse_ero_search_cards",return_value=sample):
            rows,raw=n.parse_ero_proposals("<html></html>")
        self.assertEqual(raw,2)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["source_date"],"2026-10-10")
        self.assertEqual(rows[0]["geographic_confidence"],"GTA_CITY_MENTIONED_REVIEW")
        self.assertEqual(rows[0]["procurement_status"],"UNKNOWN")

    def test_isolated_baseline_and_new_record(self):
        with tempfile.TemporaryDirectory() as base:
            opts=dict(data_dir=Path(base)/"data",output_dir=Path(base)/"out",
                      sources=["pickering_proposals"],detail_limit=0)
            self.assertEqual(n.run(**opts,session=Session({n.PICKERING:PICKERING_HTML}),
                                   now="2026-10-24T12:00:00+00:00"),0)
            self.assertEqual(n.run(**opts,session=Session({n.PICKERING:PICKERING_HTML}),
                                   now="2026-10-25T12:00:00+00:00"),0)
            enriched=PICKERING_HTML.replace("</tbody>", """<tr><td>
<a href="/news/posts/warehouse-expansion/">Warehouse Expansion Ltd.</a></td>
<td>200 New Industrial Rd</td><td>October 24, 2026</td></tr></tbody>""")
            self.assertEqual(n.run(**opts,session=Session({n.PICKERING:enriched}),
                                   now="2026-10-26T12:00:00+00:00"),0)
            with (Path(base)/"out"/"EARLY_PUBLIC_NOTICES_CHANGES_REVIEW_ONLY.csv").open(
                    encoding="utf-8-sig",newline="") as stream:
                rows=list(csv.DictReader(stream))
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["change_type"],"NEW")
            self.assertIn("warehouse-expansion",rows[0]["record_id"])
            db=sqlite3.connect(Path(base)/"data"/"early_public_notices_review.sqlite")
            self.assertEqual(db.execute("select count(*) from changes").fetchone()[0],1)
            db.close()

    def test_partial_detail_failure_no_fake_deleted(self):
        with tempfile.TemporaryDirectory() as base:
            opts=dict(data_dir=Path(base)/"data",output_dir=Path(base)/"out",
                      sources=["pickering_proposals"],detail_limit=1)
            self.assertEqual(n.run(**opts,session=Session({n.PICKERING:PICKERING_HTML}),
                                   now="2026-10-24T12:00:00+00:00"),0)
            db=sqlite3.connect(Path(base)/"data"/"early_public_notices_review.sqlite")
            count=db.execute("select count(*) from snapshots").fetchone()[0]
            db.close()
            self.assertEqual(count,2)
            self.assertEqual(n.run(**opts,session=Session({}),
                                   now="2026-10-25T12:00:00+00:00"),1)
            db=sqlite3.connect(Path(base)/"data"/"early_public_notices_review.sqlite")
            self.assertEqual(db.execute("select count(*) from snapshots").fetchone()[0],2)
            db.close()

if __name__=="__main__":unittest.main()
