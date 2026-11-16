"""Offline regression for Top10 quote rejection and captured PDF bridge."""
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from gta_ai_top10_reranker import _validate
from gta_council_captured_pdf_bridge import review


class November16EvidenceGateTests(unittest.TestCase):
    def test_model_quoting_input_project_description_not_live_source(self):
        answer = {"choices": [{
            "finish_reason": "stop", "message": {"content": json.dumps({
                "reviews": [{
                    "i": 0, "decision": "PREFER",
                    "reason": "Industrial condominium",
                    "investigate": "Find owner's actual purchasing contact",
                    "evidence_j": 0,
                    "evidence_quote": "Community planning Draft Plan of Condominium.",
                    "role_claims": [],
                }]
            })}}]}
        row = {"city": "Toronto", "record_id": "PRIVATE:birchmount"}
        sources = [{
            "url": "https://example.org/real-property-listing",
            "identity": "SAME_ADDRESS_PROJECT_CONTEXT_NOT_LINKED",
            "retrieved_on": "2026-11-16",
            "excerpt": "1430 Birchmount Rd is listed for sale.",
            "role_excerpt": "",
        }]
        result = _validate(answer, 1, batch=[row],
                           live_checks={("toronto", row["record_id"]):
                                        {"sources": sources}})[0]
        self.assertEqual(result["decision"], "CHECK_CONFLICT")
        self.assertIsNone(result["cited_source"])
        self.assertTrue(result["rejected_live_citation"])
        self.assertEqual(result["role_candidates"], [])

    def test_matching_literal_source_still_accepted(self):
        answer = {"choices": [{
            "finish_reason": "stop", "message": {"content": json.dumps({
                "reviews": [{
                    "i": 0, "decision": "NEUTRAL",
                    "reason": "Independent source mentions site",
                    "investigate": "Verify project-specific identity",
                    "evidence_j": 0,
                    "evidence_quote": "1430 Birchmount Rd is listed for sale",
                }]
            })}}]}
        row = {"city": "Toronto", "record_id": "PRIVATE:birchmount"}
        source = {"url": "https://example.org/site",
                  "identity": "SAME_ADDRESS_PROJECT_CONTEXT_NOT_LINKED",
                  "retrieved_on": "2026-11-16",
                  "excerpt": "1430 Birchmount Rd is listed for sale.",
                  "role_excerpt": ""}
        result = _validate(answer, 1, batch=[row],
                           live_checks={("toronto", row["record_id"]):
                                        {"sources": [source]}})[0]
        self.assertFalse(result["rejected_live_citation"])
        self.assertEqual(result["cited_source"]["url"], source["url"])

    def test_captured_pdf_sha_gate_and_no_false_project_match(self):
        from pypdf import PdfWriter
        from pypdf.generic import NameObject, DictionaryObject, DecodedStreamObject
        import io
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "GTA_RADAR_RESULTS"
            pdfdir = root / "DAILY_INTEGRATED_REVIEW" / "TORONTO_DOCUMENTS" / "pdfs"
            pdfdir.mkdir(parents=True)
            path = pdfdir / "captured.pdf"
            data = io.BytesIO()
            writer = PdfWriter()
            page = writer.add_blank_page(width=612, height=792)
            font = DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica")})
            page[NameObject("/Resources")] = DictionaryObject({
                NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
            stream = DecodedStreamObject()
            stream.set_data(
                b"BT /F1 12 Tf 50 700 Td "
                b"(Industrial warehouse Site Plan application 25 249692 ESC 21 CD) Tj ET")
            page[NameObject("/Contents")] = writer._add_object(stream)
            writer.write(data)
            path.write_bytes(data.getvalue())
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            audit = pdfdir.parent / "COMBINED_PDF_FETCH_AUDIT.csv"
            with audit.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "url", "status", "sha256", "saved_path", "city"])
                writer.writeheader()
                writer.writerow({
                    "url": "https://www.toronto.ca/legdocs/mmis/2026/ph/bgrd/test.pdf",
                    "status": "CAPTURED", "sha256": sha,
                    "saved_path": "C:\\\\Desktop\\\\GTA_RADAR_RESULTS\\\\DAILY_INTEGRATED_REVIEW\\\\TORONTO_DOCUMENTS\\\\pdfs\\\\captured.pdf",
                    "city": "Toronto"})
            with (root / "GTA_RADAR_PRIVATE_TOP_10.csv").open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["application_ids"])
                w.writeheader()
                w.writerow({"application_ids": "25 249692 ESC 21 CD"})
            result = review(root)
            self.assertEqual(result["captured_official_pdfs_inspected"], 1)
            self.assertEqual(result["pdfs_with_keyword_evidence"], 1)
            self.assertEqual(result["exact_application_id_text_mentions_for_review"], 1)
            self.assertEqual(result["independently_verified_project_links"], 0)
            self.assertEqual(result["new_paid_calls"], 0)
            path.write_bytes(b"%PDF-corrupt")
            again = review(root)
            self.assertEqual(again["documents"][0]["status"],
                             "CAPTURED_SOURCE_SHA_MISMATCH")
            self.assertEqual(again["pdfs_with_keyword_evidence"], 0)

    def test_council_review_missing_pdf_is_hold(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "GTA_RADAR_RESULTS"
            folder = root / "DAILY_INTEGRATED_REVIEW" / "OTHER_CITY_DOCUMENTS"
            folder.mkdir(parents=True)
            with (folder / "MULTICITY_PDF_FETCH_AUDIT.csv").open(
                    "w", newline="") as fp:
                w = csv.DictWriter(fp, fieldnames=[
                    "city", "url", "status", "sha256", "saved_path"])
                w.writeheader()
                w.writerow({
                    "city": "Mississauga",
                    "url": "https://www.mississauga.ca/agenda/test.pdf",
                    "status": "CAPTURED", "sha256": "a"*64,
                    "saved_path": "C:\\\\new data\\\\GTA_RADAR_RESULTS\\\\missing.pdf"})
            r = review(root)
            self.assertEqual(r["city_counts"]["Mississauga"], 1)
            self.assertEqual(r["documents"][0]["status"],
                             "CAPTURED_PDF_NOT_PRESENT")
            self.assertEqual(r["independently_verified_project_links"], 0)


if __name__ == "__main__":
    unittest.main()
