"""Hermetic source-index adapter tests; no real network or paid AI."""
import json
from pathlib import Path
import tempfile
import unittest

from gta_platform_index_adapter import run, fetch_index


class Response:
    def __init__(self, content=b"<html></html>", status=200, url="https://www1.brampton.ca/EN/City-Hall/Council-Committees/meetings-agendas/", mime="text/html"):
        self.body = content
        self.status_code = status
        self.url = url
        self.headers = {"Content-Type": mime}
        self.history = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def iter_content(self, chunk_size=None):
        yield self.body


class Session:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def public_resolver(*_, **__):
    return [(2, 1, 6, "", ("8.8.8.8", 443))]


URL = "https://www1.brampton.ca/EN/City-Hall/Council-Committees/meetings-agendas/"


class PolicyFetchTests(unittest.TestCase):
    def test_exact_registered_html_bounded_and_no_redirects(self):
        s = Session(Response())
        payload = fetch_index(URL, session=s, resolver=public_resolver,
                              policy_reader=lambda _: (200, "User-agent: *\nAllow: /"))
        self.assertEqual(payload, b"<html></html>")
        self.assertFalse(s.calls[0][1]["allow_redirects"])

    def test_robots_denial_never_downloads_html(self):
        s = Session(Response())
        with self.assertRaises(PermissionError):
            fetch_index(URL, session=s, resolver=public_resolver,
                        policy_reader=lambda _: (200, "User-agent: *\nDisallow: /"))
        self.assertEqual(len(s.calls), 0)

    def test_403_is_a_failure(self):
        s = Session(Response(status=403))
        with self.assertRaises(PermissionError):
            fetch_index(URL, session=s, resolver=public_resolver,
                        policy_reader=lambda _: (200, "User-agent: *\nAllow: /"))

    def test_changed_host_or_mime_is_rejected(self):
        s = Session(Response(url="https://example.com/"))
        with self.assertRaises(ValueError):
            fetch_index(URL, session=s, resolver=public_resolver,
                        policy_reader=lambda _: (200, "User-agent: *\nAllow: /"))
        s = Session(Response(mime="application/pdf"))
        with self.assertRaises(ValueError):
            fetch_index(URL, session=s, resolver=public_resolver,
                        policy_reader=lambda _: (200, "User-agent: *\nAllow: /"))

    def test_private_dns_rejected_before_request(self):
        s = Session(Response())
        with self.assertRaises(PermissionError):
            fetch_index(URL, session=s, resolver=lambda *_, **__: [(2,1,6,"",("127.0.0.1",443))])
        self.assertEqual(len(s.calls), 0)


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.results = Path(self.tmp.name)

    def test_default_is_zero_network_and_zero_leads(self):
        out = run(self.results, "brampton_planning")
        self.assertEqual(out["status"], "NOT_FETCHED_MANUAL_OPT_IN_REQUIRED")
        self.assertEqual(out["verified_projects"], 0)
        self.assertFalse((self.results / 'GTA_RADAR_PLATFORM_INDEX_BRAMPTON_PLANNING_EVIDENCE.json').exists())

    def test_explicit_fetch_captures_links_not_documents(self):
        html = (b'<a href="/docs/Planning-Agenda-2026.pdf">'
                b'Planning Committee Agenda November 2026</a>')
        out = run(self.results, "brampton_planning",
                  fetch=True, getter=lambda _: html)
        self.assertEqual(out["official_document_links_read"], 1)
        self.assertEqual(out["documents_downloaded"], 0)
        self.assertEqual(out["buyers_verified"], 0)
        saved = json.loads((self.results / 'GTA_RADAR_PLATFORM_INDEX_BRAMPTON_PLANNING_EVIDENCE.json').read_text())
        self.assertEqual(len(saved["index_sha256"]), 64)
        self.assertFalse(saved["source_first_publication_verified"])

    def test_failure_preserves_prior_source_evidence(self):
        run(self.results, "brampton_planning", fetch=True,
            getter=lambda _: b"<html>empty but valid</html>")
        original = (self.results / 'GTA_RADAR_PLATFORM_INDEX_BRAMPTON_PLANNING_EVIDENCE.json').read_bytes()
        def denied(_):
            raise PermissionError("robots")
        out = run(self.results, "brampton_planning", fetch=True, getter=denied)
        self.assertIn("FAILED", out["status"])
        self.assertEqual((self.results / 'GTA_RADAR_PLATFORM_INDEX_BRAMPTON_PLANNING_EVIDENCE.json').read_bytes(), original)
        self.assertTrue((self.results / 'GTA_RADAR_PLATFORM_INDEX_BRAMPTON_PLANNING_STATUS.json').is_file())

    def test_unknown_id_never_fetches(self):
        with self.assertRaises(ValueError):
            run(self.results, "made_up_provider", fetch=True, getter=lambda _: b"")


if __name__ == "__main__":
    unittest.main()
