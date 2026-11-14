"""No-network integration tests for registered direct municipal PDF capture."""
import io
import json
from pathlib import Path
import tempfile
import unittest

from pypdf import PdfWriter
from gta_official_platform_pdf_intake import (
    allowed_pdf, fetch_pdf, run, MAX_FILES
)


URL = "https://www1.brampton.ca/EN/City-Hall/Council-Committees/meetings-agendas/"
PDF = "https://www1.brampton.ca/documents/planning-agenda-2026.pdf"
SOURCE_ID = "brampton_planning"


def valid_pdf():
    document = PdfWriter()
    document.add_blank_page(width=100, height=100)
    out = io.BytesIO()
    document.write(out)
    return out.getvalue()


class Response:
    def __init__(self, status=200, content=None, mime="application/pdf", url=PDF):
        self.status_code = status
        self.body = content if content is not None else valid_pdf()
        self.headers = {"Content-Type": mime}
        self.url = url
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
        self.calls.append(kwargs)
        return self.response


def public_resolver(*args, **kwargs):
    return [(2, 1, 6, "", ("8.8.8.8", 443))]


class OfficialPDFTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.evidence = self.root / "GTA_RADAR_PLATFORM_INDEX_BRAMPTON_PLANNING_EVIDENCE.json"

    def write_index(self, links=None):
        obj = {
            "source_id": SOURCE_ID, "city": "Brampton",
            "original_index_url": URL,
            "document_links": [{"city": "Brampton", "url": u}
                               for u in (links or [PDF])],
        }
        self.evidence.write_text(json.dumps(obj), encoding="utf-8")

    def test_no_evidence_or_opt_in_means_no_download(self):
        self.assertEqual(run(self.root, SOURCE_ID)["status"],
                         "MISSING_EXACT_INDEX_EVIDENCE")
        self.write_index()
        def unexpected(*_):
            raise AssertionError("should not fetch")
        result = run(self.root, SOURCE_ID, getter=unexpected)
        self.assertEqual(result["pdfs_fetched"], 0)
        self.assertEqual(result["status"], "NOT_FETCHED_EXPLICIT_OPT_IN_REQUIRED")

    def test_only_exact_direct_pdf_host_is_allowed(self):
        self.assertTrue(allowed_pdf(PDF, URL))
        for candidate in [
            "http://www1.brampton.ca/doc.pdf",
            "https://another.brampton.ca/doc.pdf",
            "https://pub-brampton.escribemeetings.com/filestream.ashx?DocumentId=11",
            PDF + "?download=1", PDF + "#fragment",
            "https://www1.brampton.ca/doc.html",
        ]:
            self.assertFalse(allowed_pdf(candidate, URL))

    def test_permission_denied_before_document_request(self):
        sess = Session(Response())
        with self.assertRaises(PermissionError):
            fetch_pdf(PDF, URL, session=sess, resolver=public_resolver,
                      policy_reader=lambda _: (200, "User-agent: *\nDisallow: /"))
        self.assertEqual(sess.calls, [])

    def test_403_and_redirect_and_mime_hold(self):
        for response in [Response(status=403),
                         Response(url="https://example.org/a.pdf"),
                         Response(mime="text/html")]:
            sess = Session(response)
            with self.assertRaises((PermissionError, ValueError)):
                fetch_pdf(PDF, URL, session=sess, resolver=public_resolver,
                          policy_reader=lambda _: (200, "User-agent: *\nAllow: /"))
            self.assertFalse(sess.calls[0]["allow_redirects"])

    def test_valid_pdf_records_page_and_sha_without_lead(self):
        self.write_index()
        payload = valid_pdf()
        result = run(self.root, SOURCE_ID, fetch=True,
                     getter=lambda url, index_url: payload)
        self.assertEqual(result["pdfs_fetched"], 1)
        self.assertEqual(result["pages_inspected"], 1)
        self.assertEqual(result["verified_projects"], 0)
        self.assertEqual(result["paid_ai_usd"], 0)
        row = result["documents"][0]
        self.assertEqual(row["status"], "PDF_REVIEW_ONLY")
        self.assertEqual(len(row["sha256"]), 64)
        self.assertTrue(Path(row["saved_path"]).is_file())

    def test_failure_does_not_destroy_successful_evidence(self):
        self.write_index()
        run(self.root, SOURCE_ID, fetch=True, getter=lambda *_: valid_pdf())
        path = self.root / "GTA_RADAR_OFFICIAL_PDF_BRAMPTON_PLANNING_REVIEW.json"
        saved = path.read_bytes()
        def fail(*_):
            raise PermissionError("blocked")
        result = run(self.root, SOURCE_ID, fetch=True, getter=fail)
        self.assertEqual(result["pdfs_fetched"], 0)
        self.assertEqual(path.read_bytes(), saved)

    def test_three_document_cap(self):
        self.write_index([PDF.replace("2026", str(2026+i)) for i in range(10)])
        result = run(self.root, SOURCE_ID, fetch=True,
                     getter=lambda *_: valid_pdf())
        self.assertEqual(len(result["documents"]), MAX_FILES)
        self.assertEqual(result["pdfs_fetched"], MAX_FILES)

    def test_untrusted_index_origin_rejected(self):
        self.write_index()
        obj = json.loads(self.evidence.read_text())
        obj["original_index_url"] = "https://example.org/"
        self.evidence.write_text(json.dumps(obj))
        report = run(self.root, SOURCE_ID, fetch=True,
                     getter=lambda *_: valid_pdf())
        self.assertEqual(report["status"], "INDEX_EVIDENCE_REJECTED_PREVIOUS_REVIEW_PRESERVED")
        self.assertFalse((self.root / "GTA_RADAR_OFFICIAL_PDF_BRAMPTON_PLANNING_REVIEW.json").exists())


if __name__ == "__main__":
    unittest.main()
