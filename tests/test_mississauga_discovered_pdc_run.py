"""Source-proven Mississauga discovered PDF handoff, without real network."""
import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from gta_council_document_delta import LEDGER, STATUS as INDEX_STATUS
from gta_mississauga_discovered_pdc_run import (
    run, select_sources, STATUS as OUTPUT_STATUS
)
from gta_mississauga_pdc_agenda import OUT as CSV

URL = "https://pub-mississauga.escribemeetings.com/FileStream.ashx?DocumentId=82234"
OTHER = "https://pub-mississauga.escribemeetings.com/FileStream.ashx?DocumentId=81898"
AT = "2026-11-13T15:00:00+00:00"


def source_evidence(root, *, items=None, state="INDEX_LINK_DELTA_REVIEW_ONLY",
                    index_status="INDEX_FETCHED_LINK_ONLY", visible=1):
    root.mkdir(parents=True, exist_ok=True)
    data = items if items is not None else {
        "item-a": {
            "city": "Mississauga",
            "discovery_source":
                "https://www.mississauga.ca/council/council-activities/council-and-committees-calendar/",
            "url": URL, "title": "Planning and Development Committee Agenda 2026",
            "first_observed_utc": AT, "last_observed_utc": AT,
            "source_content_checked": False
        }
    }
    (root / LEDGER).write_text(json.dumps({"version": 1, "items": data}),
                               encoding="utf-8")
    (root / ("MISSISSAUGA_" + INDEX_STATUS)).write_text(json.dumps({
        "city": "Mississauga", "status": state,
        "checked_utc": AT, "valid_individual_document_links": visible,
        "official_index_status": index_status
    }), encoding="utf-8")


class MississaugaPdcDiscoveredTests(unittest.TestCase):
    def test_requires_current_source_status_and_no_stale_reuse(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_evidence(root)
            selected, status = select_sources(root)
            self.assertEqual(status, "OFFICIAL_PDC_LINKS_AVAILABLE_FOR_PERMISSION_CHECK")
            self.assertEqual([r["url"] for r in selected], [URL])
            source_evidence(root, index_status="HTTP_403_ACCESS_DENIED")
            selected, status = select_sources(root)
            self.assertEqual(selected, [])
            self.assertEqual(status, "CURRENT_PDC_SOURCE_NOT_VERIFIED_OR_NO_LINKS")
            source_evidence(root)
            payload = json.loads((root / LEDGER).read_text())
            payload["items"]["item-a"]["last_observed_utc"] = "2026-11-12T15:00:00+00:00"
            (root / LEDGER).write_text(json.dumps(payload))
            self.assertEqual(select_sources(root)[0], [])

    def test_non_pdc_and_unapproved_urls_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entries = {
                "other": {
                    "city": "Mississauga",
                    "discovery_source":
                        "https://www.mississauga.ca/council/council-activities/council-and-committees-calendar/",
                    "url": OTHER, "title": "Audit Committee Agenda",
                    "last_observed_utc": AT},
                "bad": {
                    "city": "Mississauga",
                    "discovery_source":
                        "https://www.mississauga.ca/council/council-activities/council-and-committees-calendar/",
                    "url": "https://evil.example/file.pdf",
                    "title": "Planning and Development Committee Agenda",
                    "last_observed_utc": AT}
            }
            source_evidence(root, items=entries, visible=2)
            self.assertEqual(select_sources(root)[0], [])

    def test_default_is_no_network_and_no_paid_ai(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_evidence(root / "index")
            result = run(root / "index", root / "outputs")
            self.assertEqual(result["status"], "EXPLICIT_MANUAL_FETCH_NOT_REQUESTED")
            self.assertEqual(result["captured_pdfs"], 0)
            self.assertEqual(result["paid_ai_calls"], 0)
            self.assertTrue((root / "outputs" / OUTPUT_STATUS).is_file())

    def test_exact_source_to_pdf_csv_and_review_handoff(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_evidence(root / "index")
            called = []
            def fake_fetch(urls, folder, authorized=False):
                called.append((urls, authorized))
                stem = hashlib.sha256(urls[0].encode()).hexdigest()[:32]
                destination = Path(folder) / "items" / stem
                destination.mkdir(parents=True, exist_ok=True)
                (destination / CSV).write_text(
                    "city,application_id,address_raw,source_pdf_url,item_number,pdf_sha256\n"
                    "Mississauga,OZ/OPA 25-3 W11,123 Example Road," +
                    URL + ",6.1," + "a"*64 + "\n", encoding="utf-8")
                return {"captured": 1, "records": [{
                    "url": urls[0], "status": "CAPTURED",
                    "item_extraction": {"status": "REVIEW_ONLY_ITEM_EXTRACTION",
                                        "toc_items": 1}}]}
            result = run(root / "index", root / "outputs", fetch=True,
                         fetcher=fake_fetch)
            self.assertEqual(called, [([URL], True)])
            self.assertEqual(result["status"], "EXTRACTED_REVIEW_ONLY")
            self.assertEqual(result["parsed_agenda_pdfs"], 1)
            self.assertEqual(result["verified_commercial_projects"], 0)
            self.assertEqual(result["original_publisher_dates_verified"], 0)
            self.assertEqual(result["paid_ai_calls"], 0)

    def test_zero_link_source_gap_is_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_evidence(root / "index", visible=0)
            result = run(root / "index", root / "out", fetch=True)
            self.assertEqual(result["status"], "NO_DIRECT_PDC_URLS_SOURCE_ADAPTER_GAP")
            self.assertEqual(result["selected_for_fetch"], 0)


if __name__ == "__main__":
    unittest.main()
