import csv
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import gta_industrial_equipment_pilot as pilot


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class IndustrialEquipmentPilotTests(unittest.TestCase):
    def test_change_vs_existing_equipment(self):
        text = ("This application is to replace Line 3 dust collector with a scrubber. "
                "The sources at the facility include scrubber; boilers; heaters; cooling tower.")
        found = pilot.equipment_changes(text)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["equipment"], "Dust collection")
        self.assertEqual(found[0]["action"], "REPLACEMENT")
        self.assertEqual(found[0]["replacement_equipment"], "Scrubber")
        self.assertFalse(any(x["equipment"] == "Boiler" for x in found))

    def test_inventory_and_generic_approval_are_not_purchases(self):
        for text in ("Sources at the facility include scrubber; boilers and cooling tower.",
                     "Environmental Compliance Approval for an existing dust collector.",
                     "No replacement of the dust collector is proposed.",
                     "This is a renewal with no changes to existing scrubbers."):
            with self.subTest(text=text):
                self.assertEqual(pilot.equipment_changes(text), [])

    def test_real_pintys_sentence_does_not_invent_scrubber_removal(self):
        text = ("This application is to replace Line 3 dust collector with a scrubber "
                "and remove the limited operational flexibility condition. "
                "The sources at the facility include scrubber; boilers; heaters; "
                "cooling tower; fryers and ovens.")
        result = pilot.equipment_changes(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["equipment"], "Dust collection")
        self.assertEqual(result[0]["action"], "REPLACEMENT")
        self.assertEqual(result[0]["replacement_equipment"], "Scrubber")
        self.assertNotIn("REMOVAL", {x["action"] for x in result})

    def test_distinct_physical_removal_not_confused_with_permit_condition(self):
        changes = pilot.equipment_changes(
            "Replace the dust collector with a scrubber and remove the old boiler.")
        self.assertEqual({(x["equipment"], x["action"]) for x in changes},
                         {("Dust collection", "REPLACEMENT"), ("Boiler", "REMOVAL")})
        self.assertEqual(changes[0]["replacement_equipment"], "Scrubber")

    def test_candidate_never_marked_open_or_verified(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            docs = root / "notices.csv"
            write_csv(docs, [{
                "ero_number": "026-1152",
                "official_notice_url": "https://ero.ontario.ca/notice/026-1152",
                "proponent": "Pinty's Delicious Foods Inc.",
                "site_address": "2714 Bristol Circle",
                "city": "Oakville",
                "proposal_posted": "2026-11-06",
                "notice_stage": "Proposal",
                "proposal_details": "This application is to replace Line 3 dust collector with a scrubber.",
            }])
            results = root / "GTA_RADAR_RESULTS"
            results.mkdir()
            write_csv(results / "GTA_RADAR_COLLECTION_MASTER.csv", [{
                "project_id": "oakville:0001", "address": "2714 BRISTOL CIRCLE",
                "city": "Oakville", "source_url": "https://www.oakville.ca/planning/0001"
            }])
            summary = pilot.run(root / "output", notice_csv=docs, results=results)
            self.assertEqual(summary["equipment_change_candidates"], 1)
            self.assertEqual(summary["same_site_candidate_links"], 1)
            self.assertEqual(summary["verified_open_procurement"], 0)
            rows = pilot._read_csv(root / "output" / pilot.OUTPUT)
            self.assertTrue(all(row["procurement_status"] == "UNKNOWN" for row in rows))
            self.assertTrue(all(row["buyer_verified"] == "NO" for row in rows))
            self.assertTrue(all(row["radar_first_seen_at"] == "" for row in rows))
            self.assertTrue(all(row["project_match_status"] ==
                                "UNVERIFIED_SINGLE_SITE_CANDIDATE" for row in rows))
            self.assertTrue(all(row["evidence_basis"].startswith("USER_SUPPLIED") for row in rows))
            self.assertIn("not verified orders", (root / "output" / pilot.HTML).read_text())

    def test_first_seen_from_existing_readonly_radar_db_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            db = root / "radar.sqlite"
            con = sqlite3.connect(db)
            con.executescript("""
                CREATE TABLE records_current (
                  source_id TEXT,record_key TEXT,first_seen_at TEXT,source_date TEXT,active INTEGER);
                CREATE TABLE record_versions (
                  version_id INTEGER PRIMARY KEY,source_id TEXT,record_key TEXT,payload_json TEXT);
            """)
            card = {"ERO_NUMBER": "026-1152",
                    "NOTICE_URL": "https://ero.ontario.ca/notice/026-1152",
                    "NOTICE_STAGE": "Proposal", "ENTITY_NAME": "Pinty's Delicious Foods Inc.",
                    "PROPOSAL_POSTED": "2026-11-06",
                    "SUMMARY": "Air approval proposal, Oakville"}
            con.execute("INSERT INTO records_current VALUES(?,?,?,?,?)",
                        (pilot.ERO_SOURCE, "026-1152", "2026-11-07T13:12:00Z",
                         "2026-11-06", 1))
            con.execute("INSERT INTO record_versions VALUES(?,?,?,?)",
                        (1, pilot.ERO_SOURCE, "026-1152", json.dumps(card)))
            con.commit()
            con.close()
            before = hashlib.sha256(db.read_bytes()).hexdigest()
            saved = pilot.read_radar_ero(db)
            self.assertEqual(saved["026-1152"]["radar_first_seen_at"],
                             "2026-11-07T13:12:00Z")
            self.assertNotEqual(saved["026-1152"]["radar_first_seen_at"],
                                saved["026-1152"]["proposal_posted"])
            self.assertEqual(hashlib.sha256(db.read_bytes()).hexdigest(), before)

    def test_nonofficial_or_mismatched_notice_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            csvfile = root / "notices.csv"
            write_csv(csvfile, [
                {"ero_number": "026-1152", "notice_url": "https://ero.ontario.ca.evil.test/notice/026-1152",
                 "proposal_details": "replace scrubber"},
                {"ero_number": "026-1152", "notice_url": "https://ero.ontario.ca/notice/026-9999",
                 "proposal_details": "replace scrubber"},
                {"ero_number": "026-1152", "notice_url": "https://ero.ontario.ca/notice/026-1152",
                 "proposal_details": "upgrade boiler"},
            ])
            accepted, rejected = pilot._notices(csvfile)
            self.assertEqual(set(accepted), {"026-1152"})
            self.assertEqual(len(rejected), 2)

    def test_no_address_or_city_means_no_project_link(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            docs = root / "doc.csv"
            write_csv(docs, [{
                "ero_number": "026-1152", "notice_url": "https://ero.ontario.ca/notice/026-1152",
                "site_address": "", "city": "Oakville",
                "proposal_details": "upgrade the industrial refrigeration system",
            }])
            results = root / "results"
            results.mkdir()
            write_csv(results / "GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv", [{
                "project_id": "a", "address": "2714 Bristol Circle", "city": "Oakville"
            }])
            pilot.run(root / "output", notice_csv=docs, results=results)
            rows = pilot._read_csv(root / "output" / pilot.OUTPUT)
            self.assertEqual(rows[0]["project_match_status"], "NO_PROJECT_MATCH")
            self.assertFalse(rows[0]["related_project_id"])

    def test_outside_gta_site_not_allowed_from_brand_york1(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            docs = root / "doc.csv"
            write_csv(docs, [{
                "ero_number": "026-0989",
                "official_notice_url": "https://ero.ontario.ca/notice/026-0989",
                "proponent": "York1 Environmental Waste Solutions",
                "site_address": "29831 Irish School Road", "city": "Dresden",
                "proposal_details": "install new wastewater treatment system",
            }])
            summary = pilot.run(root / "out", notice_csv=docs)
            self.assertEqual(summary["equipment_change_candidates"], 0)
            self.assertEqual(summary["excluded_out_of_scope_sites"],
                             [{"ero_number": "026-0989",
                               "reason": "MISSING_OR_OUT_OF_SCOPE_SITE_CITY"}])

    def test_deterministic_rerun_not_a_new_announcement(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            docs = root / "doc.csv"
            write_csv(docs, [{
                "ero_number": "026-1152", "notice_url": "https://ero.ontario.ca/notice/026-1152",
                "proposal_details": "install a new cooling tower.",
            }])
            pilot.run(root / "out", notice_csv=docs)
            first = (root / "out" / pilot.OUTPUT).read_bytes()
            pilot.run(root / "out", notice_csv=docs)
            self.assertEqual((root / "out" / pilot.OUTPUT).read_bytes(), first)


if __name__ == "__main__":
    unittest.main()
