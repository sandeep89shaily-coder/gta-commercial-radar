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
