"""Exercise the actual upgrade command, including committed WAL data."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from radar import open_db, process_snapshot, Snapshot

ROOT=Path(__file__).resolve().parents[1]


class UpgradeTests(unittest.TestCase):
    def test_adoption_keeps_wal_history_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); src=base/'v04/data'; src.mkdir(parents=True); dst=base/'v05/data'
            con=open_db(src/'radar.sqlite')
            try:
                con.execute('PRAGMA wal_autocheckpoint=0')
                source=next(s for s in json.loads((ROOT/'tests/fixtures/v04_sources.json').read_text()) if s['id']=='brampton_building_permits')
                process_snapshot(con,Snapshot(source,[{'OBJECTID':'1','ADDRESS':'1 Test St','DATE':'2026-10-08'}],b'','x',{}),src/'raw_deltas')
                cmd=[sys.executable,str(ROOT/'main.py'),'adopt','--from-data',str(src),'--data-dir',str(dst)]
                result=subprocess.run(cmd,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                target=sqlite3.connect(dst/'radar.sqlite')
                try:
                    self.assertEqual(target.execute('select count(*) from records_current').fetchone()[0],1)
                    self.assertEqual(target.execute('select count(*) from record_versions').fetchone()[0],1)
                    self.assertEqual(target.execute('select count(*) from runs').fetchone()[0],1)
                    self.assertEqual(target.execute('select universe_hash from source_state').fetchone()[0],con.execute('select universe_hash from source_state').fetchone()[0])
                    self.assertEqual(target.execute('pragma quick_check').fetchone()[0],'ok')
                finally: target.close()
                second=subprocess.run(cmd,capture_output=True,text=True)
                self.assertNotEqual(second.returncode,0)
                self.assertIn('already contains',second.stderr)
                self.assertTrue(list((dst/'raw_deltas').rglob('*.gz')))
            finally: con.close()


if __name__=='__main__': unittest.main()
