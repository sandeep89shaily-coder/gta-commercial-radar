"""Toronto official current Planning Act notices collector: no live network."""
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from gta_toronto_official_planning_notices import (
    INDEX_URL, REVIEW_CSV, LEDGER, STATUS, parse_index, parse_detail, run,
    valid_url
)

TITLE = "Notice of Application - Under the Planning Act - 309 and 311 Augusta Avenue"
URL = "https://secure.toronto.ca/nm/api/individual/notice/8004.do"
SECOND = "https://secure.toronto.ca/nm/api/individual/notice/8002.do"
SECOND_TITLE = "Notice of Application - Under the Planning Act - 7 Labatt Avenue and 77 River Street"
DATE = "2026-11-06"

LISTING = f"""
<html><body><h2>Current Notices</h2>
<a href="/nm/api/individual/notice/8004.do">{TITLE}</a>
<p>Topic</p><div>Planning &gt; Complete application for Zoning By-law Amendment</div>
<div>Notice Date</div><div>2026-11-06</div>
<a href="{SECOND}">{SECOND_TITLE}</a>
<p>Topic</p><div>Planning &gt; Complete application for an Official Plan Amendment</div>
<div>Notice Date</div><div>2026-11-06</div>
<a href="https://evil.example/nm/api/individual/notice/7.do">Notice of Application - Outside source</a>
<a href="/nm/api/individual/notice/999.do">Notice of Adoption of Official Plan Amendment 111</a>
<a href="/nm/api/individual/notice/8004.do">more</a>
</body></html>
"""
DETAIL = f"""
<html><body>
<h2>{TITLE}</h2>
<h3>Planning Application Number</h3><span>26 206718 STE 11 OZ</span>
<h3>Decision Body</h3><span>Toronto and East York Community Council</span>
<h3>Description</h3>
<div>NOTICE OF APPLICATION(S)</div>
<div>Under the Planning Act.</div>
<p>Application Number: 26 206718 STE 11 OZ</p>
<p>The application proposes to amend Zoning By-law 569-2013
to allow a six-storey hotel with a restaurant component,
containing 2,194 square metres of non-residential gross floor area.</p>
<p>309 and 311 Augusta Avenue</p><p>Hector Alonso, Planner at
Hector.Alonso2@toronto.ca</p>
<h3>For More Information Contact</h3>
<p>RegistrarCCO@toronto.ca</p>
<h3>Date</h3><p>November 6, 2026</p>
<h3>Additional Information</h3><p>Administrative details.</p>
</body></html>
"""
SECOND_DETAIL = f"""
<html><body>
<h2>{SECOND_TITLE}</h2>
<h3>Planning Application Number</h3><p>26 246687 STE 13 OZ</p>
<h3>Description</h3>
<p>The application proposes to amend the Official Plan and Zoning By-law
to permit two 46-storey residential buildings and a two-storey commercial
building providing 1,111 square metres of non-residential space.
Planner contact Allsun.Campbell@toronto.ca</p>
<h3>Date</h3><p>November 6, 2026</p>
</body></html>
"""

class TorontoOfficialPlanningNoticeTests(unittest.TestCase):
    def test_exact_index_ids_and_dates_only(self):
        items = parse_index(LISTING)
        self.assertEqual(len(items), 2)
        self.assertEqual({i["notice_id"] for i in items}, {"8002", "8004"})
        self.assertTrue(all(i["municipal_notice_date"] == DATE for i in items))
        self.assertTrue(valid_url(URL))
        self.assertFalse(valid_url("https://evil.example/nm/api/individual/notice/8004.do"))
        self.assertFalse(valid_url(URL + "?guess=1"))
        self.assertFalse(valid_url("https://secure.toronto.ca/nm/api/individual/notice/8005.do#fragment"))

    def test_extract_original_application_and_municipal_contact_only(self):
        row = parse_detail(DETAIL, {
            "notice_id": "8004", "notice_url": URL,
            "title": TITLE, "municipal_notice_date": DATE
        })
        self.assertEqual(row["application_id"], "26 206718 STE 11 OZ")
        self.assertEqual(row["location_from_notice_title"],
                         "309 and 311 Augusta Avenue")
        self.assertIn("2,194 square metres", row["description_excerpt"])
        self.assertEqual(row["public_city_planner_email"],
                         "Hector.Alonso2@toronto.ca")
        self.assertTrue(row["commercial_keyword_source_text"])

    def test_no_mismatch_date_or_heading_or_ambiguous_ids(self):
        original = {"notice_id": "8004", "notice_url": URL,
                    "title": TITLE, "municipal_notice_date": DATE}
        with self.assertRaisesRegex(ValueError, "NOTICE_HEADING_DIFFERS"):
            parse_detail(DETAIL.replace(TITLE, TITLE + " TEST"), original)
        with self.assertRaisesRegex(ValueError, "LISTING_DATE_DIFFERS"):
            parse_detail(DETAIL.replace("November 6", "November 7"), original)
        with self.assertRaisesRegex(ValueError, "AMBIGUOUS"):
            parse_detail(DETAIL.replace("Under the Planning Act.</div>",
                                        "Under the Planning Act.</div><p>Application Number: 26 206719 STE 11 OZ</p>"),
                         original)

    def test_observation_ledger_retained_when_provider_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls = []
            def getter(url):
                calls.append(url)
                return {INDEX_URL: LISTING, URL: DETAIL,
                        SECOND: SECOND_DETAIL}[url]
            first = run(root, fetch=True, getter=getter,
                        now=dt.datetime(2026, 11, 13, tzinfo=dt.timezone.utc))
            self.assertEqual(first["details_parsed_with_exact_application_id"], 2)
            self.assertEqual(first["first_local_observations"], 2)
            self.assertEqual(first["publisher_first_publication_dates_verified"], 0)
            self.assertEqual(first["paid_ai_calls"], 0)
            self.assertEqual(len(calls), 3)
            self.assertTrue((root / STATUS).is_file())
            self.assertTrue((root / REVIEW_CSV).is_file())
            stable = (root / LEDGER).read_bytes()
            second = run(root, fetch=True, getter=getter,
                         now=dt.datetime(2026, 11, 14, tzinfo=dt.timezone.utc))
            self.assertEqual(second["first_local_observations"], 0)
            with (root / REVIEW_CSV).open(encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual({r["change_event"] for r in rows}, {"UNCHANGED"})
            def fail(url):
                raise PermissionError("SOURCE_ROBOTS_DISALLOW")
            blocked = run(root, fetch=True, getter=fail)
            self.assertEqual(blocked["status"], "OFFICIAL_NOTICE_SOURCE_OR_PARSER_HOLD")
            self.assertEqual((root / LEDGER).read_bytes(),
                             (root / LEDGER).read_bytes())
            self.assertEqual(len(json.loads(stable)["items"]), 2)
            self.assertEqual(len(json.loads((root/LEDGER).read_text())["items"]), 2)

    def test_no_request_unless_explicit_fresh_manual_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            called = []
            r = run(tmp, getter=lambda _: called.append("network"))
            self.assertEqual(r["status"], "MANUAL_FETCH_NOT_REQUESTED")
            self.assertEqual(called, [])
            self.assertFalse((Path(tmp) / LEDGER).exists())

    def test_not_all_notices_are_planning_applications(self):
        self.assertEqual(parse_index(
            '<a href="/nm/api/individual/notice/99.do">'
            'Notice of Adoption of Official Plan Amendment 12 - Site</a>'
            '<div>Notice Date</div><div>2026-11-06</div>'), [])

if __name__ == "__main__":
    unittest.main()
