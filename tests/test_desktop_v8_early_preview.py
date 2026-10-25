import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from desktop_v8_early_preview import PREVIEW_DIR, prepare, snapshot_once

class SafeDesktopPreview(unittest.TestCase):
    def test_sqlite_backup_is_persistent_and_original_not_modified(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            source=root/"data"/"radar.sqlite"
            source.parent.mkdir(parents=True)
            with closing(sqlite3.connect(source)) as db:
                db.execute("CREATE TABLE records_current(id INTEGER)")
                db.execute("INSERT INTO records_current VALUES(17)")
                db.commit()
            ws,database,results=prepare(workspace=root,original_db=source)
            self.assertEqual(ws,root)
            self.assertEqual(database,root/PREVIEW_DIR/"data"/"radar.sqlite")
            with closing(sqlite3.connect(database)) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM records_current").fetchone()[0],1)
            with closing(sqlite3.connect(source)) as db:
                db.execute("INSERT INTO records_current VALUES(18)")
                db.commit()
            prepare(workspace=root,original_db=source)
            with closing(sqlite3.connect(database)) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM records_current").fetchone()[0],1)
            with closing(sqlite3.connect(source)) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM records_current").fetchone()[0],2)
            self.assertTrue(results.is_dir())

    def test_refuse_same_source_and_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/"a.sqlite"
            with closing(sqlite3.connect(source)) as db:
                db.execute("CREATE TABLE t(id)")
                db.commit()
            with self.assertRaises(ValueError):
                snapshot_once(source,source)

if __name__ == "__main__":
    unittest.main()
