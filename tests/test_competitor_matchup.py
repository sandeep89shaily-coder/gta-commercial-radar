"""GROUND/Datum comparison uses only Radar evidence and manual provider checks."""
from __future__ import annotations

import csv
from contextlib import closing
import datetime as dt
import sqlite3
import tempfile
import unittest
from pathlib import Path

import gta_competitor_matchup as matchup
import gta_manual_project_list as handoff


PROJECT = {
    "project_id": "toronto_active_building_permits:26 257023",
    "address": "8 Prince Arthur Avenue",
    "city": "Toronto",
    "source_description": "Three-storey office addition",
    "source_record_date": "2026-10-19",
    "freshness_band": "SOURCE_DATED_8_30_DAYS",
    "freshness_date_basis": "SOURCE_RECORD_DATE_NOT_PUBLICATION_PROOF",
    "radar_first_seen": "2026-11-01",
    "source_url": "https://www.toronto.ca/official-application",
}


class CompetitorMatchupTests(unittest.TestCase):
    def test_initial_comparison_is_unknown_not_automatic_competitor_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = matchup.build(root, [PROJECT])
            records = matchup._read(result["comparison_csv"])
            self.assertEqual([r["competitor"] for r in records], ["GROUND", "Datum"])
            self.assertTrue(all(r["match_level"] == "NOT_CHECKED" for r in records))
            self.assertTrue(all(not r["radar_lead_days_if_verified"] for r in records))
            self.assertEqual(result["comparable_first_detection_pairs"], 0)
            self.assertEqual(result["confirmed_same_project_or_exact_permit"], 0)
            self.assertFalse(result["public_competitor_data_scraped"])
            html = Path(result["comparison_html"]).read_text(encoding="utf-8")
            self.assertIn("HUMAN REVIEW", html)
            self.assertIn("groundintel.ca/places", html)
            self.assertIn("datumai.ca", html)

    def test_record_link_and_address_only_cannot_claim_lead(self):
        row = dict(PROJECT, match_level="ADDRESS_ONLY",
                   match_evidence_url="https://groundintel.ca/places",
                   competitor_record_url="https://groundintel.ca/places",
                   radar_first_seen_precise_utc="2026-11-01T18:00:00Z",
                   competitor_first_detected_at="2026-11-02T18:00:00Z",
                   competitor_detection_proof_url="https://groundintel.ca/places")
        self.assertEqual(matchup._compare(row),
                         ("NOT_COMPARABLE_NOT_SAME_PROJECT_CONFIRMED", ""))

    def test_first_seen_leadtime_requires_same_project_and_evidence_and_precise_time(self):
        record = dict(PROJECT, match_level="EXACT_PERMIT",
                      match_evidence_url="https://datumai.ca/record",
                      competitor_record_url="https://datumai.ca/record",
                      radar_first_seen_precise_utc="2026-11-01T12:00:00Z",
                      competitor_first_detected_at="2026-11-03T12:00:00Z",
                      competitor_detection_proof_url="https://datumai.ca/detection")
        self.assertEqual(matchup._compare(record), ("COMPARABLE_REVIEW_ONLY", "2.00"))
        record["competitor_detection_proof_url"] = ""
        self.assertEqual(matchup._compare(record)[0],
                         "NOT_COMPARABLE_DETECTION_TIMESTAMP_UNPROVEN")
        record["competitor_detection_proof_url"] = "https://datumai.ca/detection"
        record["competitor_first_detected_at"] = "2026-11-03"
        self.assertEqual(matchup._compare(record)[0],
                         "NOT_COMPARABLE_DETECTION_TIMESTAMP_UNPROVEN")

    def test_preserves_manual_edits_and_old_projects_on_next_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = matchup.build(root, [PROJECT])
            rows = matchup._read(root / matchup.PERMANENT)
            record = next(r for r in rows if r["competitor"] == "GROUND")
            record["match_level"] = "ADDRESS_ONLY"
            record["researcher_notes"] = "Public listing found; permit identity not confirmed"
            record["reviewed_on"] = "2026-11-02"
            matchup._write_atomic(root / matchup.PERMANENT, rows)
            newer = dict(PROJECT, project_id="toronto:another", address="20 Example Rd")
            second = matchup.build(root, [newer])
            all_rows = matchup._read(root / matchup.PERMANENT)
            self.assertEqual(len(all_rows), 4)
            old = next(r for r in all_rows if r["project_id"] == PROJECT["project_id"]
                       and r["competitor"] == "GROUND")
            self.assertEqual(old["match_level"], "ADDRESS_ONLY")
            self.assertEqual(old["reviewed_on"], "2026-11-02")
            self.assertIn("permit identity", old["researcher_notes"])
            self.assertEqual(second["competitor_review_rows"], 2)
            self.assertTrue(Path(first["comparison_csv"]).exists())

    def test_radars_own_ledger_readonly_enables_only_a_precise_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "RADAR_DISCOVERY_LEDGER.sqlite"
            with closing(sqlite3.connect(db)) as conn:
                conn.execute("CREATE TABLE discovery(project_id TEXT PRIMARY KEY, first_seen_at TEXT NOT NULL, source_url TEXT)")
                conn.execute("INSERT INTO discovery VALUES(?,?,?)",
                             (PROJECT["project_id"], "2026-11-01T14:30:00+00:00",
                              "https://www.toronto.ca/official-application"))
                conn.commit()
            pack = matchup.build(root, [PROJECT])
            rows = matchup._read(pack["comparison_csv"])
            self.assertEqual(rows[0]["radar_first_seen_precise_utc"],
                             "2026-11-01T14:30:00+00:00")
            self.assertEqual(rows[0]["first_seen_comparison_status"],
                             "NOT_COMPARABLE_NOT_SAME_PROJECT_CONFIRMED")

    def test_html_escapes_untrusted_project_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = dict(PROJECT, address="<img src=x onerror=alert(1)>")
            pack = matchup.build(root, [project])
            text = Path(pack["comparison_html"]).read_text(encoding="utf-8")
            self.assertNotIn("<img src=x", text)
            self.assertIn("&lt;img", text)

    def test_integrated_into_normal_manual_handoff_without_ai_or_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_file = root / handoff.SOURCE
            data = dict(PROJECT, observation="FIRST_OBSERVED",
                        description="Office addition to commercial building",
                        first_seen_local="2026-11-01",
                        current_source_status="Under review",
                        record_source_url="https://www.toronto.ca/official-application",
                        lane="PERMIT_REVIEW")
            with csv_file.open("w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(data))
                w.writeheader()
                w.writerow(data)
            out = handoff.build(root, today=dt.date(2026, 11, 2))
            self.assertTrue(Path(out["ground_datum_comparison_csv"]).exists())
            self.assertTrue(Path(out["ground_datum_comparison_html"]).exists())
            manual_html = Path(out["manual_review_html"]).read_text(encoding="utf-8")
            self.assertIn("GROUND / Datum", manual_html)
            self.assertEqual(out["ground_datum_comparable_pairs"], 0)
            self.assertEqual(out["new_or_changed_source_records"], 1)


if __name__ == "__main__":
    unittest.main()
