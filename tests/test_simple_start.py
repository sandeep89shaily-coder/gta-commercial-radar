import sys, tempfile, sqlite3, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from simple_start import safe_backup

class SetupSafetyTest(unittest.TestCase):
    def test_copies_database_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); src=root/'old.sqlite';dest=root/'new.sqlite'
            with sqlite3.connect(src) as db:db.execute('create table t (value text)');db.execute("insert into t values ('historic')")
            self.assertTrue(safe_backup(src,dest))
            with sqlite3.connect(dest) as db:self.assertEqual(db.execute('select value from t').fetchone()[0],'historic')
            with sqlite3.connect(src) as db:db.execute("insert into t values ('new')")
            self.assertTrue(safe_backup(src,dest))
            with sqlite3.connect(dest) as db:self.assertEqual(db.execute('select count(*) from t').fetchone()[0],1)
            with sqlite3.connect(src) as db:self.assertEqual(db.execute('select count(*) from t').fetchone()[0],2)
