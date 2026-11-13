"""Hermetic evidence gates for Mississauga eSCRIBE agenda and 20-case join."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter

from gta_mississauga_pdc_agenda import parse_pages, official_pdf, run as parse_pdf, OUT
from gta_agenda_application_permit_20_case import compare, run as compare_run

URL = "https://pub-mississauga.escribemeetings.com/FileStream.ashx?DocumentId=82234"
TEXT = [
    "Planning and Development Committee", "March 9, 2026",
    "6.", "MATTERS TO BE CONSIDERED",
    "6.1", "PUBLIC MEETING RECOMMENDATION REPORT (WARD 11)",
    "Rezoning application for new commercial and industrial building",
    "123 Example Road", "Owner: Project Holdings Inc.",
    "File: OZ/OPA 25-3 W11",
    "6.2", "RECOMMENDATION REPORT (WARD 7)",
    "Rezoning for six townhouses", "321 Other Street",
    "File: OZ/OPA 24-14 W7", "7.", "ADJOURNMENT",
    "6.1", "Staff Report further repeated file OZ/OPA 25-3 W11"
]


class MississaugaAgendaTests(unittest.TestCase):
    def test_actual_document_url_and_item_text(self):
        self.assertEqual(official_pdf(URL), URL)
        rows, found = parse_pages([(1, TEXT)], URL, "f"*64)
        self.assertTrue(found)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["item_number"], "6.1")
        self.assertEqual(rows[0]["application_id"], "OZ/OPA 25-3 W11")
        self.assertEqual(rows[0]["owner_raw"], "Project Holdings Inc.")
        self.assertIn("123 Example Road", rows[0]["address_raw"])
        self.assertEqual(rows[0]["screening"], "COMMERCIAL_TITLE_REVIEW_ONLY")
        self.assertEqual(rows[0]["project_verified"], False)
        self.assertEqual(rows[1]["screening"], "OTHER_AGENDA_ITEM")
        self.assertEqual(rows[0]["first_published_at"], "")

    def test_real_official_agenda_excerpt_structures_hold_multisite_and_policy(self):
        # These short agenda-item excerpts correspond to genuine public City
        # PDC PDFs: DocumentId 82234 (Mar 9) and 84942 (May 11, 2026).
        march = [
            "6.", "MATTERS TO BE CONSIDERED",
            "6.1", "PUBLIC MEETING RECOMMENDATION REPORT (WARD 11)",
            "Official Plan Amendment and Rezoning applications",
            "64 & 66 Thomas Street, 95 Joymar Drive & 65 Tannery Street",
            "Owner: Dezen Realty Company Limited",
            "File: OZ/OPA 25-3 W11",
            "6.2", "RECOMMENDATION REPORT (WARD 7)",
            "2463 and 2469 Mimosa Row",
            "File: OZ/OPA 24-14 W7",
            "6.3", "PUBLIC MEETING RECOMMENDATION REPORT (WARD 1)",
            "Rezoning application to permit two semi-detached dwelling units",
            "893 Seventh Street, north of Atwater Avenue",
            "Owner: Biocca Homes Inc.", "File: OZ 25-20 W1",
            "7.", "ADJOURNMENT",
        ]
        rows, observed = parse_pages([(1, march)], URL, "1"*64)
        self.assertTrue(observed)
        self.assertEqual(len(rows), 3)
        self.assertEqual([r["application_id"] for r in rows],
                         ["OZ/OPA 25-3 W11", "OZ/OPA 24-14 W7", "OZ 25-20 W1"])
        self.assertEqual(rows[0]["address_raw"], "")
        self.assertEqual(rows[1]["address_raw"], "")
        self.assertIn("893 Seventh Street", rows[2]["address_raw"])
        may = ["6.", "MATTERS TO BE CONSIDERED",
               "6.1", "INFORMATION REPORT (ALL WARDS)",
               "Neighbourhood Commercial: Solutions at Home",
               "File: BL.09-NBR (All Wards)",
               "7.", "ADJOURNMENT"]
        policy, _ = parse_pages([(1, may)],
                                "https://pub-mississauga.escribemeetings.com/FileStream.ashx?DocumentId=84942",
                                "2"*64)
        self.assertEqual(policy[0]["screening"],
                         "COMMERCIAL_TOPIC_NO_EXACT_SITE_OR_FILE_HOLD")
        self.assertEqual(policy[0]["address_raw"], "")

    def test_unapproved_url_rejected(self):
        for url in [
            "https://www.mississauga.ca/FileStream.ashx?DocumentId=1",
            "https://pub-mississauga.escribemeetings.com/FileStream.ashx?DocumentId=abc",
            "https://pub-mississauga.escribemeetings.com/FileStream.ashx?DocumentId=1#f",
            "http://pub-mississauga.escribemeetings.com/FileStream.ashx?DocumentId=1",
            "https://pub-mississauga.escribemeetings.com/other?DocumentId=1"
        ]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                official_pdf(url)

    def test_empty_or_unstructured_not_claimed_success(self):
        rows, found = parse_pages([(1, ["Mississauga Calendar", "Planning 6.1"])], URL, "f"*64)
        self.assertFalse(found)
        self.assertEqual(rows, [])


class Linkage20Tests(unittest.TestCase):
    def setUp(self):
        self.agenda = [
            {"city": "Mississauga", "application_id": "OZ/OPA 25-3 W11",
             "address_raw": "123 Example Road", "item_number": "6.1",
             "source_pdf_url": URL, "pdf_sha256": "f"*64}]
        self.app = [
            {"city": "Mississauga", "application_id": "OZ/OPA 25-3 W11",
             "address": "123 Example Road", "project_id": "app-a",
             "source_url": "https://www.mississauga.ca/example/app"}]
        self.permit = [
            {"city": "Mississauga", "application_id": "OZ/OPA 25-3 W11",
             "address": "123 Example Road", "permit_id": "permit-b",
             "source_url": "https://www.mississauga.ca/example/permit"}]

    def test_full_exact_match_is_still_review_only(self):
        rows = compare(self.agenda, self.app, self.permit)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["matched_application_project_id"], "app-a")
        self.assertEqual(rows[0]["matched_permit_id"], "permit-b")
        self.assertTrue(rows[0]["status"].startswith("THREE_SOURCE"))
        self.assertFalse(rows[0]["official_publication_verified"])
        self.assertEqual(rows[0]["early_detection_days"], "")
        self.assertFalse(rows[0]["buyer_verified"])

    def test_unavailable_sources_and_ambiguous_sites_hold(self):
        self.assertEqual(compare(self.agenda, None, None)[0]["hold_reason"],
                         "APPLICATION_EXPORT_UNAVAILABLE")
        other = dict(self.permit[0], address="999 Other Road")
        self.assertEqual(compare(self.agenda, self.app, [other])[0]["hold_reason"],
                         "NO_EXACT_PERMIT_APPLICATION_ID_AND_SITE")
        self.assertEqual(compare(self.agenda, self.app*2, self.permit)[0]["hold_reason"],
                         "AMBIGUOUS_APPLICATION_MATCH")
        self.assertEqual(compare(self.agenda, self.app, self.permit*2)[0]["hold_reason"],
                         "AMBIGUOUS_PERMIT_MATCH")

    def test_multi_agenda_csv_batch_deduplicates_exact_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = []
            for i in range(3):
                file = root / ("agenda_" + str(i) + ".csv")
                row = dict(self.agenda[0])
                if i == 2:
                    row["item_number"] = "6.2"
                    row["application_id"] = "OZ 25-20 W1"
                with file.open("w", newline="", encoding="utf-8") as output:
                    writer = csv.DictWriter(output, fieldnames=row.keys())
                    writer.writeheader()
                    writer.writerow(row)
                files.append(file)
            result = compare_run(files, None, None, root / "batch", 20)
            self.assertEqual(result["cases_reviewed"], 2)
            self.assertEqual(result["missing_case_count"], 18)
            self.assertEqual(result["three_source_identity_review_candidates"], 0)

    def test_twenty_case_no_fabrication_with_missing_exports(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            file = root/"agenda.csv"
            with file.open("w", encoding="utf-8", newline="") as out:
                writer = csv.DictWriter(out, fieldnames=self.agenda[0].keys())
                writer.writeheader()
                writer.writerow(self.agenda[0])
            summary = compare_run(file, None, None, root/"audit", 20)
            self.assertEqual(summary["cases_reviewed"], 1)
            self.assertEqual(summary["missing_case_count"], 19)
            self.assertEqual(summary["source_verified_same_project_matches"], 0)
            self.assertFalse(summary["early_detection_advantage_proven"])

if __name__ == "__main__":
    unittest.main()
