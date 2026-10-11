import tempfile,sqlite3,unittest
from pathlib import Path
from datetime import datetime,timezone
from radar_health import health
class HealthTests(unittest.TestCase):
 def test_missing_is_not_healthy(self):
  with tempfile.TemporaryDirectory() as td:
   result=health(Path(td),datetime(2026,10,11,tzinfo=timezone.utc))
   self.assertEqual(result['status'],'ATTENTION')
 def test_baseline_not_classified_as_fresh_change(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'brampton_sources.sqlite'
   db=sqlite3.connect(p)
   db.executescript("""CREATE TABLE sources(id TEXT,department TEXT,access_status TEXT,last_checked TEXT,frequency TEXT);
    CREATE TABLE runs(source_id TEXT,ended TEXT);
    CREATE TABLE versions(id INTEGER PRIMARY KEY,source_id TEXT,record_id TEXT,observed_at TEXT,json TEXT);""")
   db.execute("INSERT INTO sources VALUES('a','Building','OK',NULL,'daily')")
   db.execute("INSERT INTO runs VALUES('a','2026-10-11T09:00:00+00:00')")
   db.execute("INSERT INTO versions(source_id,record_id,observed_at,json) VALUES('a','1','2026-10-11T09:00:00+00:00','{}')")
   db.commit();db.close()
   report=health(Path(td),datetime(2026,10,11,12,tzinfo=timezone.utc))
   self.assertEqual(report['historical_observations'],1)
   self.assertEqual(len(report['fresh_changes']),0)
if __name__=='__main__':unittest.main()
