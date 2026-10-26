"""V8 migration must retain history, statuses, active flag and old DB unchanged."""
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
import radar_workspace as rw
import radar_v8_migration as v8


def make_v8(file):
    file.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(file)) as db:
        db.executescript("""
        CREATE TABLE records_current(
            source_id TEXT,record_key TEXT,content_hash TEXT,first_seen_at TEXT,
            last_seen_at TEXT,source_date TEXT,active INTEGER,normalized_json TEXT,
            PRIMARY KEY(source_id,record_key));
        CREATE TABLE record_versions(version_id INTEGER PRIMARY KEY,
            source_id TEXT,record_key TEXT,content_hash TEXT,observed_at TEXT,payload_json TEXT);
        CREATE TABLE changes(change_id INTEGER PRIMARY KEY,run_id INTEGER,
            source_id TEXT,record_key TEXT,change_type TEXT,observed_at TEXT,
            old_hash TEXT,new_hash TEXT,normalized_json TEXT);
        CREATE TABLE runs(run_id INTEGER PRIMARY KEY,source_id TEXT,started_at TEXT,
            finished_at TEXT,success INTEGER,baseline INTEGER,record_count INTEGER,
            new_count INTEGER,updated_count INTEGER,removed_count INTEGER,
            latest_source_date TEXT,resource_url TEXT,error TEXT,metadata_json TEXT);
        """)
        db.execute("INSERT INTO records_current VALUES(?,?,?,?,?,?,?,?)",(
            "toronto_development_applications","REC-1","xx",
            "2026-09-01","2026-10-22","2026-09-01",0,
            json.dumps({"title":"Old factory","site":"2 Test Street"})))
        db.execute("INSERT INTO record_versions VALUES(?,?,?,?,?,?)",(
            8,"toronto_development_applications","REC-1","old",
            "2026-09-01",json.dumps({"title":"Original factory"})))
        db.execute("INSERT INTO record_versions VALUES(?,?,?,?,?,?)",(
            9,"toronto_development_applications","REC-1","new",
            "2026-10-22",json.dumps({"title":"Old factory"})))
        db.execute("INSERT INTO changes VALUES(?,?,?,?,?,?,?,?,?)",(
            1,1,"toronto_development_applications","REC-1","UPDATED",
            "2026-10-22","old","new",json.dumps({"title":"Old factory"})))
        db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
            1,"toronto_development_applications","2026-10-22","2026-10-22",1,
            0,1,0,1,0,"2026-09-01","","",json.dumps({"snapshot_mode":"incremental"})))
        db.commit()


class V8MigrationTests(unittest.TestCase):
    def test_import_v8_all_history_and_idempotence(self):
        with tempfile.TemporaryDirectory() as td:
            old=Path(td)/"old";home=Path(td)/"permanent"
            source=old/"data"/"radar.sqlite"
            make_v8(source)
            prior=source.read_bytes()
            first=rw.import_history(home,[old])
            self.assertEqual(first["source_databases_read"],1)
            self.assertEqual(first["new_records"],1)
            self.assertEqual(first["added_versions"],2)
            self.assertEqual(first["added_events"],1)
            self.assertEqual(first["source_runs_imported"],1)
            with closing(sqlite3.connect(home/"Data"/"radar_master.sqlite")) as db:
                data=json.loads(db.execute("SELECT payload_json FROM records").fetchone()[0])
                self.assertIs(data["_radar_v8_active"],False)
            second=rw.import_history(home,[old])
            self.assertEqual(second["new_records"],0)
            self.assertEqual(second["added_versions"],0)
            self.assertEqual(second["added_events"],0)
            self.assertEqual(second["source_runs_imported"],0)
            self.assertEqual(source.read_bytes(),prior)

    def test_v8_disabled_source_catalog_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/"v8"/"data"/"radar.sqlite"
            make_v8(source)
            with closing(sqlite3.connect(source)) as db:
                db.execute("CREATE TABLE sources(source_id TEXT,name TEXT,"
                           "jurisdiction TEXT,family TEXT,enabled INTEGER,official_page TEXT)")
                db.execute("INSERT INTO sources VALUES(?,?,?,?,?,?)",
                           ("closed_source","Closed source","Toronto","permit",0,
                            "https://example.org/"))
                db.commit()
            home=Path(td)/"master"
            rw.import_history(home,[source.parent.parent])
            with closing(sqlite3.connect(home/"Data"/rw.DB_NAME)) as db:
                row=db.execute("SELECT enabled,name FROM source_catalog "
                               "WHERE source_id='closed_source'").fetchone()
                self.assertEqual(row,(0,"Closed source"))

    def test_adopt_v8_one_time_only(self):
        with tempfile.TemporaryDirectory() as td:
            old=Path(td)/"old"/"radar.sqlite";home=Path(td)/"home"
            make_v8(old)
            rw.setup(home)
            adopted=v8.adopt_database(home,old,rw._has_fields)
            self.assertTrue(Path(adopted).exists())
            with self.assertRaises(FileExistsError):
                v8.adopt_database(home,old,rw._has_fields)
            self.assertEqual(rw.import_history(home,[home])["new_records"],1)

    def test_reject_wrong_schema_without_creating_active_database(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/"other.sqlite";home=Path(td)/"home"
            with closing(sqlite3.connect(src)) as db:
                db.execute("CREATE TABLE arbitrary(x INTEGER)")
            with self.assertRaises(ValueError):
                v8.adopt_database(home,src,rw._has_fields)
            self.assertFalse((home/"Data"/"radar.sqlite").exists())


if __name__=="__main__":
    unittest.main()
