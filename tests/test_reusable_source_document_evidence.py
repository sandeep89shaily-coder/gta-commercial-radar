"""Offline tests for reusable platform registry and registered PDF evidence."""
import json
from pathlib import Path
import tempfile
import unittest

from pypdf import PdfWriter
from gta_municipal_platform_registry import build as registry_build
from gta_registered_document_evidence import build as pdf_build, run as pdf_run, OUTPUT


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _csv(self, data):
        path = self.root / "sources.csv"
        path.write_text("id,city,url,system,source_type,status,evidence\n" + data,
                        encoding="utf-8")
        return path

    def test_provider_is_explicit_not_inferred_from_city(self):
        reg = registry_build(self._csv(
            "one,Brampton,https://brampton.ca/a,eSCRIBE,agenda,INDEX,https://brampton.ca/e\n"
            "two,Mississauga,https://mississauga.ca/a,municipal calendar,agenda,INDEX,https://mississauga.ca/e\n"))
        self.assertEqual(reg["source_count"], 2)
        self.assertEqual(reg["sources"][0]["platform"], "ESCRIBE")
        self.assertEqual(reg["sources"][1]["platform"], "UNKNOWN")
        self.assertFalse(reg["sources"][0]["retrieval_attempted"])
        self.assertEqual(reg["sources"][0]["source_access_authorized_for_automation"],
                         "NOT_ESTABLISHED")

    def test_duplicate_and_unsafe_urls_rejected(self):
        with self.assertRaises(ValueError):
            registry_build(self._csv(
                "one,A,https://example.org/a,eSCRIBE,agenda,INDEX,https://example.org\n"
                "one,B,https://example.org/b,eSCRIBE,agenda,INDEX,https://example.org\n"))
        with self.assertRaises(ValueError):
            registry_build(self._csv(
                "bad,A,http://localhost/private,eSCRIBE,agenda,INDEX,https://example.org\n"))


class PDFTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.results = self.root / "GTA_RADAR_RESULTS"
        self.results.mkdir()

    def _manifest(self, filename, city="Brampton"):
        (self.root / "GTA_RADAR_COUNCIL_INPUTS.json").write_text(
            json.dumps({"version": 1, "documents": [{
                "city": city, "file": filename,
                "agenda_pdf_url": "https://www.brampton.ca/agenda.pdf"}]}),
            encoding="utf-8")

    def test_no_manifest_never_implies_document_coverage(self):
        report = pdf_build(self.root)
        self.assertEqual(report["status"], "NO_EXPLICIT_DOCUMENT_MANIFEST")
        self.assertEqual(report["project_leads_verified"], 0)

    def test_registered_pdf_keeps_hash_page_and_no_buyer_claim(self):
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        with (self.root / "saved.pdf").open("wb") as f:
            writer.write(f)
        self._manifest("saved.pdf")
        report = pdf_run(self.root, self.results)
        self.assertEqual(report["pdfs_examined"], 1)
        self.assertEqual(report["project_leads_verified"], 0)
        self.assertEqual(report["paid_ai_usd"], 0)
        doc = report["documents"][0]
        self.assertEqual(doc["pages_examined"], 1)
        self.assertEqual(len(doc["source_sha256"]), 64)
        self.assertFalse(doc["buyer_verified"])
        self.assertTrue((self.results / OUTPUT).is_file())

    def test_path_escape_and_non_pdf_are_held(self):
        self._manifest("../elsewhere.pdf")
        report = pdf_build(self.root)
        self.assertEqual(report["documents"][0]["status"], "NOT_REGISTERED_WORKSPACE_PDF")
        self._manifest("credentials.txt")
        report = pdf_build(self.root)
        self.assertEqual(report["documents"][0]["status"], "NOT_REGISTERED_WORKSPACE_PDF")

    def test_nonexistent_is_explicit_not_success(self):
        self._manifest("missing.pdf")
        self.assertEqual(pdf_build(self.root)["documents"][0]["status"],
                         "REGISTERED_PDF_MISSING")


if __name__ == "__main__":
    unittest.main()
