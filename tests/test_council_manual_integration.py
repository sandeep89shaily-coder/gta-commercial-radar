"""Manual three-city council integration stays independent from paid daily collection."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfWriter

import gta_council_integrated_manual as council
import gta_daily_result_archive as archive

TORONTO = "https://secure.toronto.ca/council/report.do?meeting=2026.CC41&type=agenda"
BRAMPTON = "https://www1.brampton.ca/EN/City-Hall/Council-Committees/meetings-agendas/"
BRAMPTON_PDF = "https://pub-brampton.escribemeetings.com/filestream.ashx?DocumentId=12345"
MISSISSAUGA = "https://pub-mississauga.escribemeetings.com/FileStream.ashx?DocumentId=82234"


def index_stub(*args):
    return {"cities_checked": 3, "index_link_collections": 0, "cities": [
        {"city": city, "status": "SOURCE_HELD_NO_LEDGER_MUTATION",
         "official_index_status": "HTTP_403_ACCESS_DENIED"}
        for city in ("Toronto", "Brampton", "Mississauga")
    ]}


class CouncilManualIntegrationTests(unittest.TestCase):
    def test_no_manifest_runs_index_audit_and_leaves_source_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            results = root / "GTA_RADAR_RESULTS"
            result = council.execute(root, results, index_auditor=index_stub)
            self.assertEqual(result["source_manifest_status"], "NO_SOURCE_MANIFEST_REGISTERED")
            self.assertEqual(result["documents_considered"], 0)
            self.assertEqual(result["documents_parsed"], 0)
            self.assertEqual(result["agenda_to_application_permit_chains_verified"], 0)
            self.assertEqual(result["paid_ai_usd"], 0)
            self.assertEqual(result["official_index_audit"]["cities_checked"], 3)
            self.assertEqual(result["mississauga_20_case_comparison"]["cases_reviewed"], 0)
            self.assertTrue((results / "COUNCIL_INTELLIGENCE_REVIEW" / council.STATUS).is_file())

    def test_featured_public_source_only_with_explicit_manual_collection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            calls = []
            def fake_featured(folder, fetch=False):
                calls.append((folder, fetch))
                return {"status": "FEATURED_APPLICATIONS_REVIEW_ONLY",
                        "cards_parsed": 2,
                        "commercial_keyword_cards_review_only": 1,
                        "newly_observed_cards_not_new_publications": 2,
                        "first_publications_verified": 0, "paid_ai_calls": 0}
            dry = council.execute(root, root / "GTA_RADAR_RESULTS",
                                  index_auditor=index_stub,
                                  featured_collector=fake_featured)
            self.assertEqual(calls, [])
            self.assertEqual(dry["brampton_featured_public_applications"]["status"],
                             "NOT_REQUESTED_IN_THIS_STAGE")
            active = council.execute(root, root / "GTA_RADAR_RESULTS",
                                     index_auditor=index_stub,
                                     fetch_brampton_featured=True,
                                     featured_collector=fake_featured)
            self.assertEqual(len(calls), 1)
            self.assertTrue(calls[0][1])
            self.assertEqual(active["brampton_featured_public_applications"]["cards_parsed"], 2)
            self.assertEqual(active["publisher_first_publications_verified"], 0)
            self.assertEqual(active["paid_ai_usd"], 0)

    def test_all_three_city_item_adapters_in_one_review_stage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            results = root / "GTA_RADAR_RESULTS"
            src = root / "original_sources"
            src.mkdir()
            (src / "toronto.html").write_text(
                '<h3>PH30.1 - Proposed Industrial Development 10 Test Street</h3>',
                encoding="utf-8")
            writer = PdfWriter()
            writer.add_blank_page(width=612, height=792)
            writer.add_outline_item("7.1 Warehouse Facility Expansion", 0)
            with (src / "brampton.pdf").open("wb") as fh:
                writer.write(fh)
            with (src / "mississauga.pdf").open("wb") as fh:
                writer.write(fh)
            items = [
                {"city": "Toronto", "file": "original_sources/toronto.html",
                 "meeting_url": TORONTO},
                {"city": "Brampton", "file": "original_sources/brampton.pdf",
                 "meeting_url": BRAMPTON, "agenda_pdf_url": BRAMPTON_PDF},
                {"city": "Mississauga", "file": "original_sources/mississauga.pdf",
                 "agenda_pdf_url": MISSISSAUGA},
            ]
            (root / council.CONFIG).write_text(json.dumps({
                "version": 1, "documents": items
            }), encoding="utf-8")
            # The real Mississauga adapter is separately tested against agenda
            # item text; an empty fixture PDF cannot have such text.
            def miss_fixture(pdf, url, destination):
                from gta_mississauga_pdc_agenda import OUT
                destination.mkdir(parents=True, exist_ok=True)
                (destination / OUT).write_text(
                    "city,application_id,address_raw,source_pdf_url,item_number,pdf_sha256\n"
                    "Mississauga,OZ/OPA 25-3 W11,123 Example Road," +
                    MISSISSAUGA + ",6.1," + "a"*64 + "\n", encoding="utf-8")
                return {"status": "REVIEW_ONLY_ITEM_EXTRACTION", "toc_items": 1}
            with patch.object(council, "mississauga_items", side_effect=miss_fixture):
                result = council.execute(root, results, index_auditor=index_stub)
            self.assertEqual(result["documents_considered"], 3)
            self.assertEqual(result["documents_parsed"], 3)
            self.assertEqual(result["cities"]["Toronto"]["parsed"], 1)
            self.assertEqual(result["cities"]["Brampton"]["parsed"], 1)
            self.assertEqual(result["cities"]["Mississauga"]["parsed"], 1)
            self.assertFalse(result["mississauga_20_case_comparison"]["early_detection_advantage_proven"])
            self.assertFalse(result["mississauga_20_case_comparison"]["actual_application_export_present"])
            self.assertEqual(result["paid_ai_usd"], 0)

    def test_missing_document_and_path_escape_are_held(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / council.CONFIG).write_text(json.dumps({
                "version": 1, "documents": [
                    {"city": "Toronto", "file": "../outside.html", "meeting_url": TORONTO},
                    {"city": "Brampton", "file": "not_here.pdf", "meeting_url": BRAMPTON,
                     "agenda_pdf_url": BRAMPTON_PDF}
                ]}), encoding="utf-8")
            result = council.execute(root, root / "GTA_RADAR_RESULTS",
                                     index_auditor=index_stub)
            self.assertEqual(result["documents_parsed"], 0)
            self.assertEqual(result["source_documents_failed"], 1)
            self.assertEqual(result["source_documents_missing"], 1)
            self.assertEqual(result["status"], "PARTIAL_SOURCE_REVIEW_HOLDS")

    def test_new_review_folder_is_in_safe_dated_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result_folder = root / "GTA_RADAR_RESULTS"
            report_folder = result_folder / "MONDAY_FULL_RADAR"
            report_folder.mkdir(parents=True)
            (report_folder / "MONDAY_FULL_RADAR_STATUS.json").write_text(json.dumps({
                "mode": "MANUAL_COMPLETE_RADAR_REVIEW",
                "collection_performed": False, "fresh_collection_verified": False,
                "failed_stages": [], "status": "SAVED_DATA_REVIEW_ONLY_NO_NEW_COLLECTION"
            }), encoding="utf-8")
            council.execute(root, result_folder, index_auditor=index_stub)
            package = archive.create(result_folder)
            with zipfile.ZipFile(package["archive"]) as z:
                self.assertIn(
                    "GTA_RADAR_RESULTS/COUNCIL_INTELLIGENCE_REVIEW/" + council.STATUS,
                    z.namelist())
            self.assertFalse(package["buyer_verified"])


if __name__ == "__main__":
    unittest.main()
