"""Toronto TMMIS exact-agenda retrieval: bounded, policy-controlled and offline tested."""
import hashlib
import json
import socket
import tempfile
import unittest
from pathlib import Path

from gta_toronto_tmmis_authorized_agendas import run, fetch_one, STATUS

URL="https://secure.toronto.ca/council/report.do?meeting=2026.PH30&type=agenda"
BAD="https://evil.example/council/report.do?meeting=2026.PH30&type=agenda"
MARKUP='<h3>PH30.1 - Industrial Warehouse Planning Approval Review</h3>'

def public_resolver(host, port, *, type):
    assert host=="secure.toronto.ca"
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "",
             ("8.8.8.8", 443))]

class TorontoExactAgendaTests(unittest.TestCase):
    def test_no_fetch_without_explicit_permission(self):
        result, markup=fetch_one(URL)
        self.assertEqual(result["reason"], "EXPLICIT_MANUAL_FETCH_REQUIRED")
        self.assertIsNone(markup)
        with tempfile.TemporaryDirectory() as root:
            response=run([URL], root)
            self.assertEqual(response["meetings_with_items"], 0)
            self.assertEqual(response["paid_ai_calls"], 0)
            self.assertTrue((Path(root)/STATUS).is_file())

    def test_refuse_unapproved_host_meeting_or_many_urls(self):
        with tempfile.TemporaryDirectory() as root:
            for links in ([BAD], [URL]*4, ["https://secure.toronto.ca/council/"]):
                with self.subTest(links=links), self.assertRaises(ValueError):
                    run(links, root, authorized=True)
            self.assertFalse((Path(root)/STATUS).exists())

    def test_local_stub_source_records_items_but_no_publication_proof(self):
        def transport(url, authorized=False):
            self.assertTrue(authorized)
            self.assertEqual(url, URL)
            return ({"meeting_url": URL, "status": "FETCHED_FOR_ITEM_REVIEW",
                     "source_html_sha256": hashlib.sha256(MARKUP.encode()).hexdigest(),
                     "first_published_at_verified": False}, MARKUP)
        with tempfile.TemporaryDirectory() as root:
            result=run([URL], root, authorized=True, fetcher=transport)
            self.assertEqual(result["meetings_considered"], 1)
            self.assertEqual(result["meetings_with_items"], 1)
            self.assertEqual(result["verified_projects"], 0)
            self.assertEqual(result["verified_original_publication_dates"], 0)
            self.assertEqual(result["paid_ai_calls"], 0)
            self.assertEqual(result["meeting_results"][0]["items"], 1)

    def test_unparseable_source_does_not_claim_success(self):
        with tempfile.TemporaryDirectory() as root:
            response=run([URL], root, authorized=True,
                         fetcher=lambda url, authorized=False:
                            ({"meeting_url": url, "status": "FETCHED_FOR_ITEM_REVIEW"},
                             "<html><body>empty</body></html>"))
            self.assertEqual(response["meetings_with_items"], 0)
            self.assertEqual(response["meeting_results"][0]["status"],
                             "AGENDA_STRUCTURE_NOT_RECOVERED")

if __name__ == "__main__":
    unittest.main()
