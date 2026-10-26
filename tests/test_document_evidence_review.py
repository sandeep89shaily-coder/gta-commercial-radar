"""Offline regression coverage for the document evidence workbench."""
import csv
import tempfile
import unittest
from pathlib import Path

from document_evidence_review import build, rows


def csv_file(path, columns, entries):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(entries)


class DocumentEvidenceReviewTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.out = self.root / "results"
        self.candidates = self.root / "candidates.csv"
        self.manifest = self.root / "manifest.csv"
        csv_file(self.candidates,
                 ("project_id", "address", "city", "source_id", "official_permit_id"),
                 [
                     dict(project_id="one", address="10 Main St", city="Brampton",
                          source_id="municipality", official_permit_id="A-123"),
                     dict(project_id="two", address="10 Main St", city="Brampton",
                          source_id="other", official_permit_id="B-100"),
                     dict(project_id="three", address="200 Example Ave", city="Toronto",
                          source_id="municipality", official_permit_id="A-123"),
                 ])

    def test_mentions_are_review_only_and_sources_provenanced(self):
        (self.root / "meeting.txt").write_text(
            "Staff discuss rezoning for warehouse use. Request for proposal "
            "is mentioned, but no buyer or actual award is established.", encoding="utf-8")
        csv_file(self.manifest,
                 ("project_id", "local_path", "source_url", "source_id", "source_date", "title"),
                 [dict(project_id="one", local_path="meeting.txt",
                       source_url="https://www.brampton.ca/meeting",
                       source_id="council", source_date="2026-10-23",
                       title="Council meeting")])
        stats = build(self.candidates, self.manifest, self.out)
        self.assertEqual(stats["ai_calls"], 0)
        self.assertEqual(stats["sale_ready"], 0)
        self.assertEqual(stats["documents"], 1)
        facts = rows(self.out / "DOCUMENT_EVIDENCE_REVIEW.csv")
        self.assertGreaterEqual(len(facts), 3)
        self.assertTrue(all(f["verification_status"] == "UNVERIFIED_TEXT_MENTION" for f in facts))
        self.assertTrue(all(f["source_date"] == "2026-10-23" for f in facts))
        queue = rows(self.out / "PROJECT_QUALITY_QUEUE_REVIEW.csv")
        self.assertTrue(all(x["sale_ready"] == "NO" for x in queue))
        self.assertTrue(all(x["supplier_status"] == "UNKNOWN" for x in queue))
        links = rows(self.out / "PROJECT_IDENTITY_LINKS_REVIEW.csv")
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["link_type"], "SAME_ADDRESS_REVIEW_ONLY")

    def test_unlisted_and_escaped_documents_are_skipped(self):
        csv_file(self.manifest, ("project_id", "local_path", "source_url"), [
            {"project_id": "nonexistent", "local_path": "missing.txt", "source_url": ""},
            {"project_id": "one", "local_path": "../secret.txt", "source_url": ""},
        ])
        stats = build(self.candidates, self.manifest, self.out)
        self.assertEqual(stats["documents"], 0)
        self.assertEqual(len(rows(self.out / "DOCUMENT_EXTRACTION_AUDIT.csv")), 2)

    def test_html_is_escaped_and_scripts_are_ignored(self):
        (self.root / "page.html").write_text(
            "<script>rezoning</script><p>Warehouse &amp; storage</p>",
            encoding="utf-8")
        csv_file(self.manifest, ("project_id", "local_path", "source_url"), [
            {"project_id": "one", "local_path": "page.html",
             "source_url": "https://brampton.ca/info"}
        ])
        build(self.candidates, self.manifest, self.out)
        facts = rows(self.out / "DOCUMENT_EVIDENCE_REVIEW.csv")
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["fact_type"], "development_mention")
        self.assertNotIn("<script>", (self.out / "DOCUMENT_INTELLIGENCE_REVIEW.html").read_text())

    def test_different_cities_do_not_merge_even_with_same_application_number(self):
        csv_file(self.manifest, ("project_id", "local_path"), [])
        build(self.candidates, self.manifest, self.out)
        links = rows(self.out / "PROJECT_IDENTITY_LINKS_REVIEW.csv")
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["review_status"], "HUMAN_REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
