import json,sqlite3,tempfile,unittest
from pathlib import Path
from intelligence_dashboard import render,safe_url,inferred_relationships
from production_readiness import audit

class DashboardTests(unittest.TestCase):
 def test_read_only_missing_database_does_not_create_file(self):
  with tempfile.TemporaryDirectory() as folder:
   data=Path(folder)
   out=data/'report.html'
   result=render(data,out)
   self.assertTrue(out.exists())
   self.assertEqual(result['brampton_sources'],0)
   self.assertFalse((data/'brampton_sources.sqlite').exists())
   self.assertIn('UNVERIFIED',out.read_text())
   self.assertEqual(audit(data)['production_verified'],False)
 def test_evidence_url_rejects_script_urls(self):
  self.assertEqual(safe_url('javascript:alert(1)'),'')
  self.assertEqual(safe_url('https://source.example/a'),'https://source.example/a')
 def test_source_health_and_versions_without_writes(self):
  with tempfile.TemporaryDirectory() as folder:
   data=Path(folder);db=sqlite3.connect(data/'brampton_sources.sqlite')
   db.executescript("""CREATE TABLE sources(id TEXT,department TEXT,title TEXT,url TEXT,access_status TEXT);
    CREATE TABLE records(source_id TEXT,record_id TEXT,json TEXT,last_seen TEXT);
    CREATE TABLE runs(id INTEGER PRIMARY KEY,source_id TEXT,ended TEXT,detail TEXT);
    CREATE TABLE versions(id INTEGER PRIMARY KEY,source_id TEXT,record_id TEXT,observed_at TEXT,json TEXT);
    CREATE TABLE arcgis_progress(source_id TEXT,last_oid INTEGER,total_estimate INTEGER,backfilled INTEGER,updated_at TEXT);""")
   db.execute('INSERT INTO sources VALUES(?,?,?,?,?)',('a','Planning','Development','https://brampton.ca','MONITOR'))
   db.execute('INSERT INTO records VALUES(?,?,?,?)',('a','LINK:1',json.dumps({'url':'https://brampton.ca/doc.pdf','label':'Agenda'}),'2026-10-10'))
   db.execute('INSERT INTO versions(source_id,record_id,observed_at,json) VALUES(?,?,?,?)',('a','LINK:1','2026-10-10',json.dumps({'url':'https://brampton.ca/doc.pdf','label':'Agenda'})))
   db.commit();db.close()
   result=render(data,data/'report.html')
   self.assertEqual(result['brampton_records'],1)
   page=(data/'report.html').read_text()
   self.assertIn('Agenda',page)
   self.assertIn('Official evidence',page)
   db=sqlite3.connect(data/'brampton_sources.sqlite')
   self.assertEqual(db.execute('SELECT COUNT(*) FROM records').fetchone()[0],1)
   db.close()
if __name__=='__main__':unittest.main()
