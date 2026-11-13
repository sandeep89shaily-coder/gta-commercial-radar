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

    def test_toronto_planning_notices_fresh_run_only_and_review_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            calls = []
            def fake_notices(folder, fetch=False):
                calls.append(fetch)
                return {"status": "OFFICIAL_NOTICE_DETAILS_REVIEW_ONLY",
                        "index_planning_notices": 9,
                        "details_considered": 9,
                        "details_parsed_with_exact_application_id": 7,
                        "commercial_keyword_source_records_review_only": 3,
                        "unparsed_details_held": 2,
                        "first_local_observations": 7,
                        "source_notice_dates_recorded": 7,
                        "publisher_first_publication_dates_verified": 0,
                        "paid_ai_calls": 0}
            quiet = council.execute(root, root / "GTA_RADAR_RESULTS",
                                    index_auditor=index_stub,
                                    planning_notices_collector=fake_notices)
            self.assertEqual(calls, [])
            self.assertEqual(
                quiet["toronto_official_planning_notices"]["status"], "NOT_REQUESTED")
            result = council.execute(root, root / "GTA_RADAR_RESULTS",
                                     index_auditor=index_stub,
                                     fetch_toronto_planning_notices=True,
                                     planning_notices_collector=fake_notices)
            self.assertEqual(calls, [True])
            self.assertEqual(
                result["toronto_official_planning_notices"][
                    "details_parsed_with_exact_application_id"], 7)
            self.assertEqual(result["publisher_first_publications_verified"], 0)
            self.assertEqual(result["commercial_buyers_verified"], 0)
            self.assertEqual(result["paid_ai_usd"], 0)

    def test_official_toronto_schedule_does_not_claim_agenda_or_project(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            called = []
            def fake_schedule(folder, fetch=False):
                called.append(fetch)
                return {
                    "status": "RECENT_SCHEDULE_REVIEW_ONLY",
                    "schedule_rows_read": 1445, "recent_scheduled_meetings": 4,
                    "high_priority_committee_meetings": 2,
                    "agenda_urls_discovered": 0,
                    "publisher_first_publications_verified": 0,
                    "paid_ai_calls": 0
                }
            baseline = council.execute(root, root / "GTA_RADAR_RESULTS",
                                       index_auditor=index_stub,
                                       schedule_collector=fake_schedule)
            self.assertEqual(called, [])
            self.assertEqual(
                baseline["toronto_official_meeting_schedule"]["status"], "NOT_REQUESTED")
            result = council.execute(root, root / "GTA_RADAR_RESULTS",
                                     index_auditor=index_stub,
                                     fetch_toronto_schedule=True,
                                     schedule_collector=fake_schedule)
            self.assertEqual(called, [True])
            self.assertEqual(
                result["toronto_official_meeting_schedule"]["recent_scheduled_meetings"], 4)
            self.assertEqual(
                result["toronto_official_meeting_schedule"]["agenda_urls_discovered"], 0)
            self.assertEqual(result["publisher_first_publications_verified"], 0)
            self.assertEqual(result["paid_ai_usd"], 0)

    def test_toronto_schedule_can_verified_link_to_official_tmmis_item_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            called = []
            def scheduled(folder, fetch=False):
                called.append(("schedule", fetch))
                return {"status": "RECENT_SCHEDULE_REVIEW_ONLY",
                        "schedule_rows_read": 12, "recent_scheduled_meetings": 1,
                        "agenda_urls_discovered": 0, "paid_ai_calls": 0}
            def bridge(csvfile, output, *, source_status, fetch=False):
                called.append(("bridge", fetch, source_status))
                return {"status": "OFFICIAL_ITEM_LIST_REVIEW_ONLY",
                        "meeting_candidates_from_official_schedule": 1,
                        "official_meeting_pages_matched": 1,
                        "original_tmmis_items_extracted": 8,
                        "paid_ai_calls": 0,
                        "first_publisher_publication_dates_verified": 0}
            result = council.execute(
                root, root / "GTA_RADAR_RESULTS", index_auditor=index_stub,
                fetch_toronto_schedule=True, schedule_collector=scheduled,
                agenda_bridge_collector=bridge)
            self.assertEqual(called, [
                ("schedule", True),
                ("bridge", True, "RECENT_SCHEDULE_REVIEW_ONLY")])
            self.assertEqual(result["toronto_schedule_to_agenda_item_link"][
                "original_tmmis_items_extracted"], 8)
            self.assertEqual(result["publisher_first_publications_verified"], 0)
            self.assertEqual(result["paid_ai_usd"], 0)

    def test_toronto_schedule_failure_cannot_trigger_stale_agenda_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            called = []
            def bridge(csvfile, output, *, source_status, fetch=False):
                called.append(source_status)
                return {"status": "CURRENT_OFFICIAL_SCHEDULE_NOT_VALIDATED_HOLD",
                        "official_meeting_pages_matched": 0,
                        "original_tmmis_items_extracted": 0, "paid_ai_calls": 0}
            result = council.execute(
                root, root / "GTA_RADAR_RESULTS", index_auditor=index_stub,
                fetch_toronto_schedule=True,
                schedule_collector=lambda folder, fetch=False: {
                    "status": "OFFICIAL_SCHEDULE_BLOCKED_OR_SCHEMA_HELD"},
                agenda_bridge_collector=bridge)
            self.assertEqual(called, ["OFFICIAL_SCHEDULE_BLOCKED_OR_SCHEMA_HELD"])
            self.assertEqual(result["toronto_schedule_to_agenda_item_link"]["status"],
                             "CURRENT_OFFICIAL_SCHEDULE_NOT_VALIDATED_HOLD")

    def test_exact_toronto_agenda_urls_use_manual_source_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/council.CONFIG).write_text(json.dumps({
                "version": 1, "documents": [],
                "toronto_meeting_urls": [TORONTO]
            }), encoding="utf-8")
            calls=[]
            def fake_toronto(urls, folder, authorized=False):
                calls.append((urls, authorized))
                return {"status": "REVIEW_ONLY_OFFICIAL_TMMIS_AGENDA_FETCH",
                        "meetings_considered": 1, "meetings_with_items": 1,
                        "meeting_results": [{"meeting_url": TORONTO,
                                             "status": "AGENDA_ITEMS_REVIEW_ONLY"}],
                        "paid_ai_calls": 0}
            dry=council.execute(root, root/"results", index_auditor=index_stub,
                                toronto_fetcher=fake_toronto)
            self.assertEqual(calls, [])
            self.assertEqual(dry["paid_ai_usd"], 0)
            run=council.execute(root, root/"results", index_auditor=index_stub,
                                fetch_toronto_official_agendas=True,
                                toronto_fetcher=fake_toronto)
            self.assertEqual(calls, [([TORONTO], True)])
            self.assertEqual(run["toronto_exact_agenda_retrieval"]["meetings_with_items"], 1)
            self.assertEqual(run["publisher_first_publications_verified"], 0)

    def test_invalid_toronto_meeting_url_is_held(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/council.CONFIG).write_text(json.dumps({
                "version": 1, "documents": [],
                "toronto_meeting_urls": ["https://other.example.com/council/report.do?meeting=2026.PH30&type=agenda"]
            }), encoding="utf-8")
            result=council.execute(root, root/"results", index_auditor=index_stub,
                                   fetch_toronto_official_agendas=True)
            self.assertEqual(result["toronto_exact_agenda_retrieval"]["status"],
                             "OFFICIAL_TMMIS_FETCH_OR_MANIFEST_HELD")
            self.assertEqual(result["source_documents_held"], 1)

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
