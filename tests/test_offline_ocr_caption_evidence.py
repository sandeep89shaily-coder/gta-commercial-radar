"""Hermetic offline OCR and caption review regression tests."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from pypdf import PdfWriter

from gta_local_pdf_ocr import scan
from gta_local_caption_evidence import build, parse_vtt, run, OUTPUT


class OfflineEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.results = self.root / "GTA_RADAR_RESULTS"
        self.results.mkdir()

    def pdf(self, name="document.pdf"):
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=300)
        out = self.root / name
        with out.open("wb") as f:
            writer.write(f)
        return out

    def test_ocr_text_and_page_provenance(self):
        self.pdf()
        def render(pdf, page, folder):
            path = folder / "image.png"
            path.write_bytes(b"fake-image")
            return path
        result = scan(self.root, "document.pdf", render=render,
                      recognize=lambda image: "Industrial warehouse expansion proposal")
        self.assertEqual(result["pages_ocr_attempted"], 1)
        self.assertEqual(result["pages_ocr_succeeded"], 1)
        self.assertEqual(result["ocr_excerpts"][0]["page"], 1)
        self.assertEqual(result["ocr_excerpts"][0]["evidence_level"], "UNVERIFIED_OCR_TEXT")
        self.assertEqual(len(result["source_sha256"]), 64)
        self.assertFalse(result["project_verified"])
        self.assertEqual(result["paid_ai_usd"], 0)

    def test_ocr_traversal_and_caps_fail_closed(self):
        self.pdf()
        with self.assertRaises(ValueError):
            scan(self.root, "../document.pdf",
                 render=lambda *_: None, recognize=lambda *_: "")
        with self.assertRaises(ValueError):
            scan(self.root, "document.pdf", max_pages=4,
                 render=lambda *_: None, recognize=lambda *_: "")

    def test_ocr_missing_engines_are_reported_not_success(self):
        self.pdf()
        # Exercise engine absence without relying on CI host installation.
        from unittest.mock import patch
        with patch("gta_local_pdf_ocr.shutil.which", return_value=None):
            result = scan(self.root, "document.pdf")
        self.assertEqual(result["status"], "OCR_RENDERER_NOT_INSTALLED")
        self.assertEqual(result["pages_ocr_succeeded"], 0)

    def test_vtt_parser_timecodes_and_caption_mentions(self):
        captions = ("WEBVTT\n\n"
                    "00:00:01.000 --> 00:00:04.000\n"
                    "The industrial warehouse expansion is proposed\n\n"
                    "00:00:05.000 --> 00:00:08.500\n"
                    "We will discuss it later\n")
        self.assertEqual(len(parse_vtt(captions)), 2)
        (self.root / "meeting.vtt").write_text(captions, encoding="utf-8")
        (self.root / "GTA_RADAR_MEDIA_INPUTS.json").write_text(json.dumps({
            "version": 1,
            "captions": [{
                "city": "Brampton", "file": "meeting.vtt",
                "recording_url": "https://www.brampton.ca/council/recording"
            }]
        }), encoding="utf-8")
        report = run(self.root, self.results)
        self.assertEqual(report["mentions_for_review"], 2)
        mention = report["files"][0]["mentions"][0]
        self.assertEqual(mention["start_ms"], 1000)
        self.assertEqual(mention["end_ms"], 4000)
        self.assertEqual(mention["evidence_level"], "UNVERIFIED_CAPTION_MENTION")
        self.assertEqual(report["verified_projects"], 0)
        self.assertEqual(report["paid_ai_usd"], 0)
        self.assertTrue((self.results / OUTPUT).is_file())

    def test_invalid_timing_and_missing_manifest(self):
        with self.assertRaises(ValueError):
            parse_vtt("WEBVTT\n\n00:00:04.000 --> 00:00:01.000\ninvalid\n")
        with self.assertRaises(ValueError):
            parse_vtt("WEBVTT\n\n00:00:72.000 --> 00:00:75.000\ninvalid\n")
        self.assertEqual(build(self.root)["status"], "NO_EXPLICIT_CAPTION_MANIFEST")

    def test_caption_path_escape_held(self):
        (self.root / "GTA_RADAR_MEDIA_INPUTS.json").write_text(json.dumps({
            "version": 1,
            "captions": [{
                "city": "Toronto", "file": "../outside.vtt",
                "recording_url": "https://www.toronto.ca/video"
            }]
        }))
        report = build(self.root)
        self.assertEqual(report["files"][0]["status"], "CAPTION_PARSE_HELD")
        self.assertEqual(report["mentions_for_review"], 0)


if __name__ == "__main__":
    unittest.main()
