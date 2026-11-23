"""Tests for public five-day opportunity site and fail-closed publication contract."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from website.validate_public_feed import PROOF_FIELDS, record_digest, validate, validate_publication

ROOT = Path(__file__).resolve().parent.parent / "website"

def row(**updates):
    record = {
        "id": "commercial_development:Toronto:SP-1",
        "lane": "commercial_development",
        "title": "Industrial warehouse expansion",
        "city": "Toronto",
        "address": "100 Industrial Road",
        "scope": "A new industrial manufacturing warehouse development.",
        "source_url": "https://www.toronto.ca/development/source",
        "source_date": "2026-11-20",
        "date_basis": "APPLICATION_DATE_NOT_FIRST_PUBLICATION",
        "stage": "Under Review",
        "source_project_id": "SP-1",
        "company": "",
        "first_publication_verified": False,
        "buyer_verified": False,
        "open_supplier_package_verified": False,
        "approved_for_publication": True,
        "rights_checked": True,
        "source_checked": True,
    }
    record.update(updates)
    return record

def check(payload):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "opportunities.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return validate(path)

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []
    def handle_starttag(self, tag, attrs):
        props = dict(attrs)
        if props.get("id"):
            self.ids.add(props["id"])
        if tag in ("script", "link") and (
                props.get("src") or props.get("href")):
            asset = props.get("src") or props.get("href")
            if asset.startswith("./") and not asset.endswith(".html"):
                self.links.append(asset)

class PublicOpportunityWebsite(unittest.TestCase):
    def test_public_feed_contains_only_approved_source_linked_records(self):
        metadata = validate()
        body = json.loads((ROOT / "data" / "opportunities.json").read_text())
        self.assertEqual(metadata["records"], len(body["records"]))
        self.assertEqual(body["window_days"], 5)
        self.assertEqual(len({r["id"] for r in body["records"]}), len(body["records"]))
        if body["records"]:
            issue = dt.date.fromisoformat(body["published_on"])
            self.assertTrue(all(0 <= (issue - dt.date.fromisoformat(r["source_date"])).days <= 4
                                for r in body["records"]))
        self.assertTrue(all(r["approved_for_publication"] and
                            r["rights_checked"] and r["source_checked"]
                            for r in body["records"]))
        self.assertTrue(all(not r["buyer_verified"] and
                            not r["open_supplier_package_verified"]
                            for r in body["records"]))

    def test_valid_published_record_and_exact_five_day_boundary(self):
        payload = {"schema_version": 1, "window_days": 5,
                   "published_on": "2026-11-22", "records": [row(source_date="2026-11-18")]}
        self.assertEqual(check(payload)["records"], 1)

    def test_new_release_requires_record_specific_proof_and_saved_source(self):
        record = row()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            feed = root / "opportunities.json"
            feed.write_text(json.dumps({"schema_version": 1, "window_days": 5,
                                        "published_on": "2026-11-22", "records": [record]}))
            with self.assertRaisesRegex(ValueError, "PUBLICATION_PROOF_REQUIRED"):
                validate_publication(feed, root)

            capture = root / "captures" / "SP-1.txt"
            capture.parent.mkdir()
            capture.write_text("SP-1 source notice with address, scope and date")
            proof = {
                "record_sha256": record_digest(record),
                "publisher": "City of Toronto",
                "capture_file": "captures/SP-1.txt",
                "capture_sha256": hashlib.sha256(capture.read_bytes()).hexdigest(),
                "captured_at": "2026-11-22T10:00:00-05:00",
                "reviewer": "Editorial reviewer",
                "approved_at": "2026-11-22T11:00:00-05:00",
                "stage_as_of": "2026-11-22",
                "rights_basis": "Open dataset with attribution",
                "rights_url": "https://www.toronto.ca/open-data/licence/",
                "verification_limitation": "One publisher notice",
                "reviewed_claims": {key: record[key] for key in PROOF_FIELDS},
            }
            (root / "publication-proof.json").write_text(json.dumps({record["id"]: proof}))
            self.assertEqual(validate_publication(feed, root)["records"], 1)
            capture.write_text("edited after review")
            with self.assertRaisesRegex(ValueError, "SOURCE_CAPTURE_MISSING_OR_CHANGED"):
                validate_publication(feed, root)

    def test_rejects_stale_future_unapproved_and_unsourced_records(self):
        base = {"schema_version": 1, "window_days": 5,
                "published_on": "2026-11-22"}
        variants = [
            row(source_date="2026-11-17"),
            row(source_date="2026-11-23"),
            row(approved_for_publication=False),
            row(rights_checked=False),
            row(source_checked=False),
            row(source_url="http://example.com/not-secure"),
            row(source_url="https://user:pass@evil.test"),
            row(buyer_verified=True),
            row(open_supplier_package_verified=True),
            row(first_publication_verified=True),
            row(contact_email="hidden@example.com"),
        ]
        for item in variants:
            with self.subTest(record=item):
                with self.assertRaises(ValueError):
                    check({**base, "records": [item]})

    def test_rejects_duplicate_and_unbounded_release(self):
        with self.assertRaises(ValueError):
            check({"schema_version": 1, "window_days": 5,
                   "published_on": "2026-11-22", "records": [row(), row()]})

    def test_browse_page_has_real_navigation_and_filter_controls(self):
        markup = (ROOT / "opportunities.html").read_text(encoding="utf-8")
        parse = Page()
        parse.feed(markup)
        for expected in ("main", "board", "op-results", "op-empty", "op-search-input",
                         "op-city", "op-sort", "op-clear", "publication-status"):
            self.assertIn(expected, parse.ids)
        for asset in parse.links:
            self.assertTrue((ROOT / asset).is_file(), asset)
        self.assertIn("No approved public records in this five-day window", (ROOT / "opportunities.js").read_text())
        self.assertIn('timeZone: "America/Toronto"', (ROOT / "opportunities.js").read_text())
        self.assertIn("noopener noreferrer", (ROOT / "opportunities.js").read_text())
        self.assertNotIn("innerHTML", (ROOT / "opportunities.js").read_text())
        self.assertIn("@media(max-width:760px)", (ROOT / "opportunities.css").read_text())
        self.assertIn("prefers-reduced-motion", (ROOT / "opportunities.css").read_text())

    def test_local_publisher_requires_per_row_approval_and_no_backend(self):
        html = (ROOT / "publisher.html").read_text()
        script = (ROOT / "publisher.js").read_text()
        self.assertIn('id="pub-general"', html)
        self.assertIn('id="pub-equipment"', html)
        self.assertIn('id="pub-confirm"', html)
        self.assertIn("noindex,nofollow", html)
        self.assertIn("approved_for_publication: true", script)
        self.assertIn("source_checked: true", script)
        self.assertIn("rights_checked: true", script)
        self.assertIn("checked: false", script)
        self.assertIn("URL.createObjectURL", script)
        self.assertNotIn("fetch(", script)
        self.assertNotIn("localStorage", script)
        self.assertNotIn("innerHTML", script)

    def test_both_browser_scripts_parse_in_node_when_available(self):
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed on this machine")
        for name in ("opportunities.js", "publisher.js"):
            with self.subTest(script=name):
                result = subprocess.run(
                    [node, "--check", str(ROOT / name)],
                    capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_homepage_links_directly_to_opportunity_board(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="./opportunities.html"', html)
        self.assertIn("Browse five-day research", html)
        self.assertIn("No arbitrary Top 10", html)

if __name__ == "__main__":
    unittest.main()
