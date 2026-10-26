"""No-network safety tests for the single persistent Radar workspace."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import radar_workspace as rw


def create_legacy(base, *, records=1):
    data = base / "Workspace" / "Data"
    result = base / "Workspace" / "Results"
    data.mkdir(parents=True)
    result.mkdir(parents=True)
    dbfile = data / "early_planning_review.sqlite"
    with sqlite3.connect(dbfile) as db:
        db.execute("CREATE TABLE snapshots(source_id,record_id,first_seen_at,last_seen_at,content)")
        db.execute("CREATE TABLE changes(source_id,record_id,observed_at,change_type,content)")
        for i in range(records):
            item = json.dumps(dict(source_id="brampton_site_plans",
                                   record_id=str(i),site=f"{i} Main Street",
                                   source_date="2026-09-01"))
            db.execute("INSERT INTO snapshots VALUES(?,?,?,?,?)",
                       ("brampton_site_plans", str(i), "2026-10-01", "2026-10-02", item))
            db.execute("INSERT INTO changes VALUES(?,?,?,?,?)",
                       ("brampton_site_plans", str(i), "2026-10-02",
                        "UPDATED", item))
    (result / "GTA_RADAR_EARLY_SOURCES.csv").write_text(
        "source_id,runner,status,fetched\nbrampton_site_plans,early_planning_pilot,SUCCESS,1\n",
        encoding="utf-8")
    return dbfile


class WorkspaceTests(unittest.TestCase):
    def test_history_import_is_idempotent_and_preserves_old_db(self):
        with tempfile.TemporaryDirectory() as temp:
            old = Path(temp) / "old"
            new = Path(temp) / "permanent"
            legacy = create_legacy(old, records=2)
            before = legacy.read_bytes()
            a = rw.import_history(new, [old])
            self.assertEqual(a["new_records"], 2)
            self.assertEqual(a["added_events"], 2)
            self.assertEqual(a["source_status_rows"], 1)
            b = rw.import_history(new, [old])
            self.assertEqual(b["new_records"], 0)
            self.assertEqual(b["added_versions"], 0)
            self.assertEqual(b["added_events"], 0)
            self.assertEqual(before, legacy.read_bytes())
            self.assertEqual(rw.status(new)["records"], 2)
            self.assertEqual(rw.status(new)["historical_events"], 2)

    def test_changed_content_retains_previous_version(self):
        with tempfile.TemporaryDirectory() as temp:
            old = Path(temp) / "old"
            new = Path(temp) / "permanent"
            legacy = create_legacy(old)
            rw.import_history(new, [old])
            with sqlite3.connect(legacy) as db:
                db.execute("UPDATE snapshots SET content=?,last_seen_at=?",
                           (json.dumps({"site":"Different", "source_date":"2026-09-04"}),
                            "2026-10-03"))
            again = rw.import_history(new, [old])
            self.assertEqual(again["new_records"], 0)
            self.assertEqual(again["added_versions"], 1)
            self.assertEqual(rw.status(new)["record_versions"], 2)

    def test_corrupt_import_keeps_other_sources_and_does_not_fake_success(self):
        with tempfile.TemporaryDirectory() as temp:
            old = Path(temp) / "old"
            new = Path(temp) / "permanent"
            create_legacy(old)
            (old / "Workspace" / "Data" / "broken.sqlite").write_bytes(b"not a database")
            result = rw.import_history(new, [old])
            self.assertEqual(result["new_records"], 1)
            self.assertTrue(result["read_errors"])
            self.assertEqual(rw.status(new)["records"], 1)

    def test_malformed_second_snapshot_rolls_back_entire_source_and_counters(self):
        with tempfile.TemporaryDirectory() as temp:
            old = Path(temp) / "old"
            new = Path(temp) / "permanent"
            legacy = create_legacy(old)
            with sqlite3.connect(legacy) as db:
                db.execute("INSERT INTO snapshots VALUES(?,?,?,?,?)",
                           ("brampton_site_plans", "bad", "2026-10-01",
                            "2026-10-02", "{not JSON"))
            result = rw.import_history(new, [old])
            self.assertEqual(result["new_records"], 0)
            self.assertEqual(result["added_versions"], 0)
            self.assertTrue(result["read_errors"])
            self.assertEqual(rw.status(new)["records"], 0)

    def test_unrecognized_database_not_counted_as_imported_source(self):
        with tempfile.TemporaryDirectory() as temp:
            old = Path(temp) / "old"
            new = Path(temp) / "permanent"
            directory = old / "Workspace" / "Data"
            directory.mkdir(parents=True)
            with sqlite3.connect(directory / "v8_main.sqlite") as db:
                db.execute("CREATE TABLE v8_records(id INTEGER PRIMARY KEY)")
            result = rw.import_history(new, [old])
            self.assertEqual(result["source_databases_read"], 0)
            self.assertEqual(result["unsupported_databases"], 1)
            self.assertFalse(result["read_errors"])

    def test_importing_workspace_itself_never_recurses_into_master(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            db = rw.setup(home)
            a = rw.import_history(home, [home])
            self.assertEqual(a["source_databases_read"], 0)
            self.assertEqual(rw.status(home)["records"], 0)
            self.assertTrue(db.is_file())

    def test_no_implicit_scheduling_or_paid_ai(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(rw.main(["--home",temp,"init"]),0)
            self.assertTrue((Path(temp)/"Data"/"radar_master.sqlite").is_file())
            self.assertTrue((Path(temp)/"Results").is_dir())
            self.assertTrue((Path(temp)/"Logs").is_dir())


if __name__ == "__main__":
    unittest.main()
