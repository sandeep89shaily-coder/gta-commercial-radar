"""Hermetic tests of eSCRIBE provider-specific exact discovered document intake."""
import io
import json
from pathlib import Path
import tempfile
import unittest

from pypdf import PdfWriter
from gta_escribe_exact_document_intake import (
    exact_document, fetch_document, run, MAX_DOCUMENTS
)

CITY = "Brampton"
SID = "brampton_planning"
INDEX = "https://www1.brampton.ca/EN/City-Hall/Council-Committees/meetings-agendas/"
DOC = "https://pub-brampton.escribemeetings.com/filestream.ashx?DocumentId=2345"


def pdf_bytes():
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class Response:
    def __init__(self, *, url=DOC, status=200, mime="application/pdf"):
        self.status_code = status
        self.url = url
        self.history = []
        self.headers = {"Content-Type": mime}
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def iter_content(self, chunk_size=None):
        yield pdf_bytes()


class Session:
    def __init__(self, response):
        self.response = response
        self.calls = []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def resolver(*_, **__):
    return [(2, 1, 6, "", ("8.8.8.8", 443))]


class EscribeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.index_file = self.root / "GTA_RADAR_PLATFORM_INDEX_BRAMPTON_PLANNING_EVIDENCE.json"
        self.review_file = self.root / "GTA_RADAR_ESCRIBE_BRAMPTON_PLANNING_REVIEW.json"

    def index(self, urls=None):
        self.index_file.write_text(json.dumps({
            "source_id": SID, "city": CITY, "original_index_url": INDEX,
            "document_links": [{"city": CITY, "url": x} for x in (urls or [DOC])],
        }), encoding="utf-8")

    def test_strict_discovered_document_shape(self):
        self.assertTrue(exact_document(DOC, CITY))
        for u in (DOC + "&format=pdf", DOC + "#x",
                  "https://evil.example/filestream.ashx?DocumentId=2345",
                  DOC.replace("2345", "0"),
                  DOC.replace("2345", "2345%26bad=1"),
                  DOC.replace("pub-brampton", "pub-mississauga"),
                  "http://pub-brampton.escribemeetings.com/filestream.ashx?DocumentId=2345"):
            self.assertFalse(exact_document(u, CITY))

    def test_no_fetch_without_both_opt_ins(self):
        self.index()
        self.assertEqual(run(self.root, SID, fetch=True)["downloaded_documents"], 0)
        self.assertEqual(run(self.root, SID, authorized=True)["downloaded_documents"], 0)
        self.assertFalse(self.review_file.exists())

    def test_robots_blocks_before_document_download(self):
        sess = Session(Response())
        with self.assertRaises(PermissionError):
            fetch_document(DOC, CITY, session=sess, resolver=resolver,
                           policy_reader=lambda _: (200, "User-agent: *\nDisallow: /"))
        self.assertEqual(sess.calls, [])

    def test_403_and_redirect_and_wrong_content_are_held(self):
        for response in (Response(status=403),
                         Response(url="https://example.org/d.pdf"),
                         Response(mime="text/html")):
            sess = Session(response)
            with self.assertRaises((ValueError, PermissionError)):
                fetch_document(DOC, CITY, session=sess, resolver=resolver,
                               policy_reader=lambda _: (200, "User-agent: *\nAllow: /"))
            self.assertFalse(sess.calls[0][1]["allow_redirects"])

    def test_discovered_document_captured_without_buyer_claim(self):
        self.index()
        out = run(self.root, SID, fetch=True, authorized=True,
                  getter=lambda *args: pdf_bytes())
        self.assertEqual(out["downloaded_documents"], 1)
        self.assertEqual(out["reviewed_pages"], 1)
        self.assertEqual(out["verified_buyers"], 0)
        self.assertEqual(out["verified_project_leads"], 0)
        self.assertEqual(out["paid_ai_usd"], 0)
        self.assertTrue(Path(out["documents"][0]["saved_path"]).exists())
        self.assertEqual(len(out["documents"][0]["sha256"]), 64)

    def test_failed_retry_preserves_prior_document_review(self):
        self.index()
        run(self.root, SID, fetch=True, authorized=True, getter=lambda *_: pdf_bytes())
        original = self.review_file.read_bytes()
        def denied(*_):
            raise PermissionError("blocked")
        state = run(self.root, SID, fetch=True, authorized=True, getter=denied)
        self.assertEqual(state["downloaded_documents"], 0)
        self.assertEqual(self.review_file.read_bytes(), original)

    def test_capped_and_other_city_and_invalid_index_held(self):
        self.index([DOC.replace("2345", str(2000 + x)) for x in range(15)])
        result = run(self.root, SID, fetch=True, authorized=True, getter=lambda *_: pdf_bytes())
        self.assertEqual(result["downloaded_documents"], MAX_DOCUMENTS)
        self.index()
        broken = json.loads(self.index_file.read_text())
        broken["original_index_url"] = "https://example.org/"
        self.index_file.write_text(json.dumps(broken), encoding="utf-8")
        state = run(self.root, SID, fetch=True, authorized=True, getter=lambda *_: pdf_bytes())
        self.assertEqual(state["status"], "INDEX_EVIDENCE_HELD_PREVIOUS_DOCUMENTS_RETAINED")


if __name__ == "__main__":
    unittest.main()
