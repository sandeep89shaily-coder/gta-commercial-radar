import csv,json,sqlite3,tempfile,unittest
from pathlib import Path
from datetime import date,timedelta
from opportunity_engine import collect,export

class EventGateTests(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.data=Path(t.name)
  old=(date.today()-timedelta(days=400)).isoformat();fresh=date.today().isoformat()
  db=sqlite3.connect(self.data/'business_discovery.sqlite')
  db.execute('CREATE TABLE observations(source_id TEXT,source_key TEXT,company_name TEXT,address TEXT,city TEXT,industry TEXT,event_date TEXT,event_type TEXT,observed_at TEXT)')
  rows=[('york_dir','historical','Old Shop','A','','',old,'BUSINESS_DIRECTORY_OBSERVATION',fresh),('york_dir','today_dir','New Shop','B','','',fresh,'BUSINESS_DIRECTORY_OBSERVATION',fresh),('federal_active_cbca','oldco','Old Corp','C','','',old,'FEDERAL_INCORPORATION_RECORD',fresh),('federal_active_cbca','newco','New Corp','D','','',fresh,'FEDERAL_INCORPORATION_RECORD',fresh),('kitchener_business_licences','lic','New Licensed','E','','',fresh,'BUSINESS_LICENCE_OBSERVATION',fresh),('kitchener_business_licences','no_date','Undated','F','','','','BUSINESS_LICENCE_OBSERVATION',fresh)]
  db.executemany('INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?)',rows);db.commit();db.close()
  db=sqlite3.connect(self.data/'radar.sqlite')
  db.execute('CREATE TABLE records_current(source_id TEXT,record_key TEXT,source_date TEXT,normalized_json TEXT,active INTEGER)')
  db.execute('INSERT INTO records_current VALUES(?,?,?,?,1)',('hamilton','p1',fresh,json.dumps({'description':'commercial permit','commercial_relevance':'LOW'})))
  db.commit();db.close()
 def test_no_baseline_lead_explosion(self):
  rows,stats,sources=collect(self.data)
  self.assertEqual({r['source_key'] for r in rows},{'newco','lic','p1'})
  self.assertEqual(rows[0]['source_group'],'MUNICIPAL')
  self.assertEqual(stats[('BUSINESS_DISCOVERY','enrichment_only')],2)
  self.assertIn('COMPANY_UNKNOWN',rows[0]['missing_information'])
 def test_bounded_queue_and_stable_repeat(self):
  count,pending=export(self.data,limit=2)
  self.assertEqual((count,pending),(3,2))
  self.assertEqual(export(self.data,limit=2),(3,2))
  with (self.data/'collector_opportunity_audit.csv').open(encoding='utf-8-sig') as f: d=list(csv.DictReader(f))
  self.assertEqual(sum(int(r['recent_events_selected']) for r in d),3)
  self.assertEqual(next(r for r in d if r['source_id']=='york_dir')['recent_events_selected'],'0')

if __name__=='__main__':unittest.main()
