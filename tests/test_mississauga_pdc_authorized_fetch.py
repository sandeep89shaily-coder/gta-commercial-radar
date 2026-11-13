"""Controlled eSCRIBE download tests: no real network, safety gates remain."""
import io
import socket
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter

from gta_mississauga_pdc_authorized_fetch import fetch_one, batch, AUDIT

URL = "https://pub-mississauga.escribemeetings.com/FileStream.ashx?DocumentId=82234"


class FakeResponse:
    def __init__(self, url, data, status=200, mime="application/pdf"):
        self.url = url
        self.status_code = status
        self.headers = {"Content-Type": mime, "Content-Length": str(len(data))}
        self.data = data
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        return False
    def iter_content(self, chunk_size=65536):
        yield self.data


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.headers = {}
        self.trust_env = None
        self.called = 0
    def get(self, url, **kwargs):
        self.called += 1
        return self.response


def resolver(host, port, *, type):
    assert host == "pub-mississauga.escribemeetings.com"
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]


def blank_pdf():
    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(buffer)
    return buffer.getvalue()


class MississaugaAuthorizedCaptureTests(unittest.TestCase):
    def test_default_dry_run_no_provider_calls_or_files(self):
        with tempfile.TemporaryDirectory() as td:
            session = FakeSession(FakeResponse(URL, blank_pdf()))
            result = batch([URL], td, session=session, resolver=resolver)
            self.assertEqual(result["captured"], 0)
            self.assertEqual(result["blocked_or_held"], 1)
            self.assertEqual(session.called, 0)
            self.assertFalse((Path(td)/"source_pdfs").exists())
            self.assertTrue((Path(td)/AUDIT).is_file())

    def test_robots_denial_and_bad_host_never_downloaded(self):
        with tempfile.TemporaryDirectory() as td:
            session = FakeSession(FakeResponse(URL, blank_pdf()))
            blocked = fetch_one(URL, Path(td)/"blocked.pdf",
                authorized=True, resolver=resolver, session=session,
                policy_reader=lambda _: (200, "User-agent: *\nDisallow: /"))
            self.assertIn("ROBOTS", blocked["reason"])
            self.assertEqual(session.called, 0)
            bad = fetch_one("https://evil.example/FileStream.ashx?DocumentId=82234",
                Path(td)/"bad.pdf", authorized=True, resolver=resolver,
                session=session, policy_reader=lambda _: "")
            self.assertEqual(bad["reason"], "NOT_OFFICIAL_ALLOWED_PDF_URL")
            self.assertEqual(session.called, 0)

    def test_allowed_official_pdf_captured_and_items_still_unverified(self):
        with tempfile.TemporaryDirectory() as td:
            session = FakeSession(FakeResponse(URL, blank_pdf()))
            result = batch([URL], td, session=session, resolver=resolver,
                policy_reader=lambda _: (200, "User-agent: *\nAllow: /"),
                authorized=True)
            self.assertEqual(result["captured"], 1)
            self.assertEqual(result["records"][0]["status"], "CAPTURED")
            self.assertEqual(result["records"][0]["item_extraction"]["verified_project_matches"], 0)
            self.assertEqual(result["verified_project_count"], 0)
            self.assertEqual(result["paid_ai_calls"], 0)

    def test_html_disguised_as_pdf_refused(self):
        with tempfile.TemporaryDirectory() as td:
            session = FakeSession(FakeResponse(URL, b"<html>not PDF</html>" * 25))
            result = fetch_one(URL, Path(td)/"bad.pdf", authorized=True,
                resolver=resolver, session=session, policy_reader=lambda _: "")
            self.assertEqual(result["reason"], "NOT_A_PDF")
            self.assertFalse((Path(td)/"bad.pdf").exists())


if __name__ == "__main__":
    unittest.main()
