"""Offline Brampton bookmarked-agenda collector regression tests."""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter

from gta_brampton_bookmarked_agenda import inspect, LEDGER, REPORT, CSV

MEETING = "https://www1.brampton.ca/EN/City-Hall/Council-Committees/meetings-agendas/"
PDF_URL = "https://pub-brampton.escribemeetings.com/filestream.ashx?DocumentId=12345"
NOW = dt.datetime(2026, 11, 12, tzinfo=dt.timezone.utc)


def write_bookmarked_pdf(path, label="Industrial Manufacturing Facility Expansion"):
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=612, height=792)
    parent = writer.add_outline_item("7. Planning and Development", 0)
    writer.add_outline_item("7.1 " + label, 1, parent=parent)
    writer.add_outline_item("8. Confirmation of Minutes", 2)
    with Path(path).open("wb") as handle:
        writer.write(handle)


class BramptonBookmarkedAgendaTests(unittest.TestCase):
    def test_bookmark_pages_and_guarded_claims(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pdf = root / "agenda.pdf"
            write_bookmarked_pdf(pdf)
            report = inspect(pdf, meeting_url=MEETING,
                             agenda_pdf_url=PDF_URL, results=root, now=NOW)
            self.assertEqual(report["event"], "FIRST_LOCAL_BASELINE_NOT_FIRST_PUBLICATION")
            self.assertEqual(report["bookmarks_parsed"], 3)
            self.assertEqual(report["bookmarks_screened_for_research"], 1)
            self.assertEqual(report["project_records_verified"], 0)
            self.assertEqual(report["deepseek_spend_usd"], 0)
            with (root / CSV).open(encoding="utf-8-sig") as handle:
                from csv import DictReader
                rows = list(DictReader(handle))
            self.assertEqual([int(x["page_1based"]) for x in rows], [1, 2, 3])
            self.assertEqual(rows[1]["depth"], "1")
            self.assertTrue(rows[1]["item_path"].startswith("7. Planning and Development / "))
            self.assertEqual(rows[1]["project_verified"], "False")

    def test_revised_pdf_not_falsely_new_project(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); pdf = root / "agenda.pdf"
            write_bookmarked_pdf(pdf)
            first = inspect(pdf, meeting_url=MEETING,
                            agenda_pdf_url=PDF_URL, results=root, now=NOW)
            repeat = inspect(pdf, meeting_url=MEETING,
                             agenda_pdf_url=PDF_URL, results=root,
                             now=NOW+dt.timedelta(days=1))
            self.assertEqual(repeat["event"], "UNCHANGED_SAVED_PDF")
            write_bookmarked_pdf(pdf, "Industrial Warehouse Revised")
            revised = inspect(pdf, meeting_url=MEETING,
                              agenda_pdf_url=PDF_URL, results=root,
                              now=NOW+dt.timedelta(days=2))
            self.assertEqual(revised["event"], "SAVED_AGENDA_PDF_REVISION_NOT_NEW_PROJECT")
            self.assertEqual(revised["saved_pdf_versions_seen"], 2)
            self.assertEqual(revised["first_observed_utc"], first["first_observed_utc"])
            self.assertEqual(revised["first_publications_verified"], 0)

    def test_untrusted_host_and_corrupt_pdf_fail_before_ledger_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); pdf = root / "agenda.pdf"
            write_bookmarked_pdf(pdf)
            with self.assertRaises(ValueError):
                inspect(pdf, meeting_url="https://untrusted.example/meeting",
                        agenda_pdf_url=PDF_URL, results=root, now=NOW)
            self.assertFalse((root / LEDGER).exists())
            pdf.write_bytes(b"PDF is not a real PDF" * 50)
            with self.assertRaises(ValueError):
                inspect(pdf, meeting_url=MEETING, agenda_pdf_url=PDF_URL,
                        results=root, now=NOW)
            self.assertFalse((root / LEDGER).exists())

    def test_changed_source_url_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); pdf = root / "agenda.pdf"
            write_bookmarked_pdf(pdf)
            inspect(pdf, meeting_url=MEETING, agenda_pdf_url=PDF_URL,
                    results=root, now=NOW)
            saved = (root / LEDGER).read_bytes()
            with self.assertRaisesRegex(ValueError, "SOURCE_CHANGED"):
                inspect(pdf, meeting_url=MEETING,
                        agenda_pdf_url="https://www.brampton.ca/other.pdf",
                        results=root, now=NOW)
            self.assertEqual((root / LEDGER).read_bytes(), saved)


if __name__ == "__main__":
    unittest.main()
