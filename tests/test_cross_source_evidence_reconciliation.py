"""Tests for exact city/application reconciliation without unearned verification."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from gta_cross_source_evidence_reconciliation import build, run, OUTPUT


class CrossSourceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)

    def applications(self, rows):
        with (self.root / "GTA_RADAR_EARLY_APPLICATION_CANDIDATES.csv").open(
                "w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=[
                "city", "application_id", "project_id", "record_source_url",
                "record_source_url_basis"])
            writer.writeheader()
            writer.writerows(rows)

    def doc(self, city, excerpt):
        (self.root / "GTA_RADAR_DOCUMENT_EVIDENCE_SEGMENTS.json").write_text(
            json.dumps({"status": "OFFLINE_DOCUMENT_REVIEW_ONLY", "documents": [{
                "city": city,
                "status": "PDF_TEXT_REVIEW_ONLY",
                "source_url": "https://example.org/agenda.pdf",
                "source_sha256": "f" * 64,
                "segments": [{"page": 3, "excerpt": excerpt,
                              "evidence_level": "UNVERIFIED_PDF_TEXT_MENTION"}]
            }]}), encoding="utf-8")

    def test_missing_sources_do_not_become_no_city_activity(self):
        result = build(self.root)
        self.assertEqual(result["application_input_status"], "NO_CURRENT_APPLICATION_CSV")
        self.assertEqual(result["source_statuses"]["CAPTION"], "SOURCE_NOT_PRESENT")
        self.assertEqual(result["independently_verified_project_links"], 0)

    def test_matching_exact_city_and_id_only_creates_review_candidate(self):
        self.applications([{
            "city": "Mississauga", "application_id": "OZ 26-123",
            "project_id": "EARLY_APP:MISSISSAUGA:OZ26-123",
            "record_source_url": "https://mississauga.ca/planning",
            "record_source_url_basis": "OFFICIAL_INDEX_CONTEXT_ONLY_NOT_EXACT_RECORD",
        }])
        self.doc("Mississauga", "Discussed warehouse proposal file OZ 26-123.")
        result = run(self.root)
        self.assertEqual(result["exact_id_review_candidates"], 1)
        self.assertEqual(result["independently_verified_project_links"], 0)
        match = result["review_candidates"][0]
        self.assertEqual(match["page"], 3)
        self.assertEqual(match["application_id"], "OZ26-123")
        self.assertFalse(match["source_identity_verified"])
        self.assertFalse(match["buyer_verified"])
        self.assertTrue((self.root / OUTPUT).exists())

    def test_different_city_same_id_is_never_matched(self):
        self.applications([{
            "city": "Brampton", "application_id": "OZ 26-123",
            "project_id": "BRAMPTON:1", "record_source_url": ""
        }])
        self.doc("Mississauga", "Warehouse file OZ 26-123")
        result = build(self.root)
        self.assertEqual(result["exact_id_review_candidates"], 0)
        self.assertEqual(result["holds"][0]["status"], "NO_SAME_CITY_APPLICATION_ID_MATCH")

    def test_ambiguous_project_ids_are_held(self):
        self.applications([
            {"city": "Mississauga", "application_id": "OZ 26-123",
             "project_id": "project-1", "record_source_url": ""},
            {"city": "Mississauga", "application_id": "OZ 26-123",
             "project_id": "project-2", "record_source_url": ""},
        ])
        self.doc("Mississauga", "Warehouse planning OZ 26-123.")
        report = build(self.root)
        self.assertEqual(report["exact_id_review_candidates"], 0)
        self.assertEqual(report["holds"][0]["status"],
                         "AMBIGUOUS_MULTIPLE_APPLICATION_PROJECTS")

    def test_keyword_only_never_creates_project_link(self):
        self.applications([{
            "city": "Mississauga", "application_id": "OZ 26-123",
            "project_id": "project-1", "record_source_url": ""
        }])
        self.doc("Mississauga", "New logistics facility and industrial plant")
        report = build(self.root)
        self.assertEqual(report["exact_id_review_candidates"], 0)
        self.assertEqual(report["holds"][0]["status"],
                         "NO_EXACT_APPLICATION_ID_IN_EXCERPT")

    def test_asr_input_is_review_only(self):
        self.applications([{
            "city": "Toronto", "application_id": "D23ZZZ22.012",
            "project_id": "TOR:1", "record_source_url": ""
        }])
        (self.root / "GTA_RADAR_LOCAL_TRANSCRIPTION_REVIEW.json").write_text(json.dumps({
            "status": "LOCAL_SPEECH_TRANSCRIPTION_REVIEW_ONLY",
            "city": "Toronto", "source_audio_sha256": "a" * 64,
            "original_recording_url": "https://toronto.ca/recording",
            "mentions": [{"start_ms": 13000,
                          "excerpt": "Application D23ZZZ22.012 proposed industrial warehouse"}]
        }))
        report = build(self.root)
        self.assertEqual(report["mentions_considered"], 1)
        self.assertEqual(report["exact_id_review_candidates"], 1)
        self.assertEqual(report["review_candidates"][0]["start_ms"], 13000)


if __name__ == "__main__":
    unittest.main()
