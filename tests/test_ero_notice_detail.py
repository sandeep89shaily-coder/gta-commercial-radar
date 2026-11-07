"""Offline fixtures for the opt-in ERO full-notice retriever."""
import csv
import tempfile
import unittest
from pathlib import Path

import gta_ero_notice_detail as detail
import gta_industrial_equipment_pilot as pilot


def example_html(*, stage="Decision", with_site=True, with_proposal=True,
                 number="026-0424"):
    site = ('<h2>Location details</h2><h3>Site address</h3>'
            '<p>185 Belfield Road<br>Etobicoke, ON<br>Canada</p>'
            '<h3>Site location map</h3>') if with_site else ""
    prop = ("<h2>Original proposal</h2><div>Proposal posted April 17, 2026</div>"
            "<h2>Proposal details</h2><p>This application is for the addition "
            "of a new dust collector and incorporation of maintenance welding "
            "activities.</p><h2>Supporting materials</h2>") if with_proposal else ""
    return f"""<!doctype html><html><body><main>
    <h1>Bunge Loders Croklaan Canada Inc. - Environmental Compliance Approval (air)</h1>
    <dl><dt>ERO (Environmental Registry of Ontario) number</dt><dd>{number}</dd>
    <dt>Notice stage</dt><dd>{stage}</dd>
    <dt>Decision posted</dt><dd>August 13, 2026</dd></dl>
    {site}<h2>Proponent(s)</h2><div>Bunge Loders Croklaan Canada Inc.<br>
    185 Belfield Road<br>Etobicoke, ON</div>
    <h2>Decision details</h2><p>The approval has been granted.</p>
    {prop}
    </main></body></html>"""


class FakeResponse:
    def __init__(self, text, status_code=200, ctype="text/html"):
        self.status_code = status_code
        self.headers = {"Content-Type": ctype}
        self._data = text.encode("utf-8")
    def iter_content(self, chunk_size=65536):
        yield self._data
    def close(self):
        pass


class FakeSession:
    def __init__(self, robots="User-agent: *\nAllow: /notice/\n", pages=None):
        self.robots = robots
        self.pages = pages or {}
        self.urls = []
    def get(self, url, **kwargs):
        self.urls.append(url)
        if url == detail.ROBOTS_URL:
            return FakeResponse(self.robots, ctype="text/plain")
        return FakeResponse(self.pages.get(url, example_html()))
    def close(self):
        pass


class OfficialNoticeDetailTests(unittest.TestCase):
    def test_exact_notice_decision_and_original_proposal_extracted_separately(self):
        url = "https://ero.ontario.ca/notice/026-0424"
        row = detail.parse_notice_html(example_html(), "026-0424", url)
        self.assertEqual(row["notice_stage"], "Decision")
        self.assertEqual(row["decision_posted"], "2026-08-13")
        self.assertEqual(row["proposal_posted"], "2026-04-17")
        self.assertEqual(row["site_address"], "185 Belfield Road")
        self.assertEqual(row["city"], "Toronto")  # Etobicoke = Toronto
        self.assertIn("new dust collector", row["proposal_details"])
        self.assertNotIn("Supporting materials", row["proposal_details"])
        self.assertEqual(row["content_provenance"], "FETCHED_EXACT_ERO_OFFICIAL_NOTICE")

    def test_nested_ero_sections_use_document_order_not_siblings(self):
        # ERO headings and contents can be in separate wrapper containers.
        # The previous next_siblings parser returned PROPOSAL_DETAILS_MISSING.
        page = """<!doctype html><html><body><main>
            <h1>Pinty's Delicious Foods Inc. - Environmental Compliance Approval (air)</h1>
            <div><span>ERO (Environmental Registry of Ontario) number</span>
                 <span>026-1152</span></div>
            <div><span>Notice stage</span><span>Proposal</span></div>
            <div><span>Proposal posted</span><span>November 6, 2026</span></div>
            <section>
              <div><h2>Location details</h2></div>
              <div><div><h3>Site address</h3></div></div>
              <div><div><p>2714 Bristol Circle<br>Oakville, ON<br>L6H 6A1</p></div></div>
              <div><h3>Site location map</h3></div>
            </section>
            <section>
              <div><h2>Proponent(s)</h2></div>
              <div><p>Pinty's Delicious Foods Inc.<br>5063 North Service Road</p></div>
            </section>
            <section>
              <div><h2>Proposal details</h2></div>
              <div><div><p>This application is to replace Line 3 dust collector
              with a scrubber and remove the limited operational flexibility condition.</p></div></div>
              <div><h2>Supporting materials</h2></div>
              <p>Not part of the proposal section.</p>
            </section>
        </main></body></html>"""
        url = "https://ero.ontario.ca/notice/026-1152"
        row = detail.parse_notice_html(page, "026-1152", url)
        self.assertEqual(row["site_address"], "2714 Bristol Circle")
        self.assertEqual(row["city"], "Oakville")
        self.assertEqual(row["notice_stage"], "Proposal")
        self.assertEqual(row["proposal_posted"], "2026-11-06")
        self.assertIn("Line 3 dust collector", row["proposal_details"])
        self.assertIn("scrubber", row["proposal_details"])
        self.assertNotIn("Supporting materials", row["proposal_details"])
        changes = pilot.equipment_changes(row["proposal_details"])
        self.assertEqual({x["equipment"] for x in changes},
                         {"Dust collection", "Scrubber"})

    def test_nested_heading_does_not_steal_following_section(self):
        page = """<html><body><h1>Example - ECA</h1>
        <p>ERO (Environmental Registry of Ontario) number 026-1152</p>
        <p>Notice stage Proposal</p>
        <section><div><h2>Proposal details</h2></div>
        <div><p>We request an upgrade of the cooling tower.</p></div></section>
        <section><div><h2>Supporting materials</h2></div>
        <div><p>This unrelated section proposes to install a boiler.</p></div></section>
        <section><div><h2>Site address</h2></div>
        <div><p>1 Industrial Drive<br>Oakville, ON</p></div></section></body></html>"""
        row = detail.parse_notice_html(page, "026-1152",
                                       "https://ero.ontario.ca/notice/026-1152")
        self.assertIn("cooling tower", row["proposal_details"])
        self.assertNotIn("boiler", row["proposal_details"])

    def test_styled_label_without_heading_tags_is_supported_only_with_bounds(self):
        page = """<html><body><h1>Food Manufacturer - Air approval</h1>
          <div>ERO (Environmental Registry of Ontario) number</div><div>026-1152</div>
          <div>Notice stage</div><div>Proposal</div>
          <div>Proposal posted</div><div>November 6, 2026</div>
          <div class='label'>Site address</div>
          <div>2714 Bristol Circle<br>Oakville, ON<br>L6H 6A1<br>Canada</div>
          <div>Site location map</div>
          <div>Proponent(s)</div>
          <div>Pinty's Delicious Foods Inc.</div><div>5063 North Service Road</div>
          <div>Proposal details</div>
          <div>This application is to replace Line 3 dust collector with a scrubber.</div>
          <div>Supporting materials</div>
          <div>This unrelated page footer includes a new boiler.</div>
        </body></html>"""
        row = detail.parse_notice_html(
            page, "026-1152", "https://ero.ontario.ca/notice/026-1152")
        self.assertEqual(row["site_address"], "2714 Bristol Circle")
        self.assertEqual(row["city"], "Oakville")
        self.assertIn("dust collector", row["proposal_details"])
        self.assertNotIn("unrelated page footer", row["proposal_details"])

    def test_styled_label_without_safe_end_is_rejected(self):
        page = """<html><body><h1>Food Manufacturer - Air approval</h1>
        <p>ERO (Environmental Registry of Ontario) number 026-1152</p>
        <p>Notice stage Proposal</p>
        <div>Proposal details</div>
        <div>New equipment is not documented here.</div>
        </body></html>"""
        with self.assertRaisesRegex(ValueError, "PROPOSAL_DETAILS_MISSING"):
            detail.parse_notice_html(
                page, "026-1152", "https://ero.ontario.ca/notice/026-1152")

    def test_extra_lot_concession_line_before_site_city(self):
        page = example_html().replace(
            "185 Belfield Road<br>Etobicoke, ON<br>Canada",
            "1660 Union Avenue<br>Lots 9 &amp; 10, Concession 1<br>Kingsville, ON<br>N9Y 2M6<br>Canada",
            1
        )
        row = detail.parse_notice_html(
            page, "026-0424", "https://ero.ontario.ca/notice/026-0424")
        self.assertEqual(row["site_address"], "1660 Union Avenue")
        self.assertEqual(row["city"], "Kingsville")
        # Kingsville is outside the pilot's Southern Ontario target-city gate.
        self.assertNotIn(row["city"].lower(), pilot.TARGET_CITIES)

    def test_requires_exact_notice_id_and_explicit_site(self):
        url = "https://ero.ontario.ca/notice/026-0424"
        cases = [
            (example_html(number="026-0400"), "ERO_ID_NOT_IN_NOTICE"),
            (example_html(with_site=False), "EXPLICIT_SITE_ADDRESS_MISSING"),
            (example_html(with_proposal=False), "PROPOSAL_DETAILS_MISSING"),
        ]
        for html, code in cases:
            with self.subTest(code=code):
                with self.assertRaisesRegex(ValueError, code):
                    detail.parse_notice_html(html, "026-0424", url)

    def test_source_not_phishing_or_redirected(self):
        self.assertFalse(detail.exact_ero_url(
            "026-0424", "https://ero.ontario.ca.evil.test/notice/026-0424"))
        self.assertFalse(detail.exact_ero_url(
            "026-0424", "https://ero.ontario.ca/notice/026-0424?next=evil"))
        self.assertFalse(detail.exact_ero_url(
            "026-0424", "http://ero.ontario.ca/notice/026-0424"))

    def test_robots_denial_prevents_notice_fetch(self):
        url = "https://ero.ontario.ca/notice/026-0424"
        cards = {"026-0424": {"official_notice_url": url}}
        session = FakeSession("User-agent: *\nDisallow: /notice/\n")
        notices, audit = detail.fetch_notice_details(cards, session=session)
        self.assertEqual(notices, [])
        self.assertIn("ROBOTS_DISALLOW_ALL", [r["status"] for r in audit])
        self.assertEqual(session.urls, [detail.ROBOTS_URL])

    def test_robots_missing_refuses_fetch(self):
        url = "https://ero.ontario.ca/notice/026-0424"
        class DeniedSession(FakeSession):
            def get(self, url, **kwargs):
                self.urls.append(url)
                return FakeResponse("not available", 403, "text/plain")
        session = DeniedSession()
        notices, audit = detail.fetch_notice_details(
            {"026-0424": {"official_notice_url": url}}, session=session)
        self.assertEqual(notices, [])
        self.assertEqual(audit[0]["status"], "ROBOTS_POLICY_UNAVAILABLE")
        self.assertEqual(session.urls, [detail.ROBOTS_URL])

    def test_optin_fetch_is_bounded_and_requires_source_cards(self):
        u = "https://ero.ontario.ca/notice/026-0424"
        cards = {"026-0424": {"official_notice_url": u}}
        ses = FakeSession()
        out, audit = detail.fetch_notice_details(cards, max_notices=1,
                                                session=ses, sleep=lambda _: None)
        self.assertEqual(len(out), 1)
        self.assertEqual([a["status"] for a in audit], ["DETAIL_RETRIEVED"])
        self.assertEqual(ses.urls, [detail.ROBOTS_URL, u])
        self.assertEqual(out[0]["notice_stage"], "Decision")

    def test_review_workflow_accepts_fetched_detail_without_open_bid(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            # The live importer uses read_radar_ero; inject source cards here
            # so the integration is isolated from real SQLite/network.
            old = pilot.read_radar_ero
            pilot.read_radar_ero = lambda db: {
                "026-0424": {
                    "ero_number": "026-0424",
                    "official_notice_url": "https://ero.ontario.ca/notice/026-0424",
                    "radar_first_seen_at": "2026-11-01T08:00:00Z",
                }
            }
            try:
                result = pilot.run(
                    root / "output", db=root / "irrelevant.db",
                    fetch_official=True,
                    official_fetcher=lambda cards, max_notices: (
                        [detail.parse_notice_html(
                            example_html(), "026-0424",
                            "https://ero.ontario.ca/notice/026-0424")],
                        [{"ero_number": "026-0424", "status": "DETAIL_RETRIEVED"}],
                    ),
                )
            finally:
                pilot.read_radar_ero = old
            self.assertEqual(result["equipment_change_candidates"], 1)
            with (root / "output" / pilot.OUTPUT).open(encoding="utf-8-sig", newline="") as f:
                row = next(csv.DictReader(f))
            self.assertEqual(row["notice_stage"], "Decision")
            self.assertEqual(row["review_status"], "HISTORICAL_DECISION_REVIEW_ONLY")
            self.assertEqual(row["procurement_status"], "UNKNOWN")
            self.assertEqual(row["buyer_verified"], "NO")
            self.assertEqual(row["evidence_basis"], "FETCHED_EXACT_ERO_OFFICIAL_NOTICE")
            self.assertEqual(row["radar_first_seen_at"], "2026-11-01T08:00:00Z")


if __name__ == "__main__":
    unittest.main()
