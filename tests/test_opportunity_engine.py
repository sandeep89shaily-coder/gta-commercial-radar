import csv,sqlite3,json,tempfile,unittest
from datetime import date
from pathlib import Path
from opportunity_engine import collect,export

class MunicipalOpportunityTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.data=Path(self.tmp.name); db=sqlite3.connect(self.data/'radar.sqlite')
  db.execute('CREATE TABLE records_current (source_id TEXT,record_key TEXT,source_date TEXT,normalized_json TEXT,active INTEGER)')
  day=date.today().isoformat()
  for source,key,p in [('brampton','a',{'commercial_relevance':'LOW','description':'unknown permit'}),('hamilton','b',{'entity_name':'ABC Retail','address':'1 Main St','description':'new retail store'}),('york','c',{'address':'2 Unnamed Ave','description':'site plan'})]:
   db.execute('INSERT INTO records_current VALUES (?,?,?,?,1)',(source,key,day,json.dumps(p)))
  db.commit();db.close()
 def test_missing_name_location_and_low_relevance_retained(self):
  rows,stats,sources=collect(self.data)
  self.assertEqual(len(rows),3)
  self.assertEqual({r['source_id'] for r in rows},{'brampton','hamilton','york'})
  b=next(r for r in rows if r['source_id']=='brampton')
  self.assertIn('COMPANY_UNKNOWN',b['missing_information']);self.assertIn('LOCATION_UNRESOLVED',b['missing_information'])
  self.assertEqual(b['commercial_priority'],'LOW')
 def test_per_collector_counts_and_stable_pending(self):
  self.assertEqual(export(self.data),(3,3))
  self.assertEqual(export(self.data),(3,3))
  with (self.data/'collector_opportunity_audit.csv').open(encoding='utf-8-sig') as f: audits=list(csv.DictReader(f))
  self.assertEqual(sum(int(r['recent_events_selected']) for r in audits),3)
 def test_date_quality_audit_explains_zero_selected_feeds(self):
  db=sqlite3.connect(self.data/'radar.sqlite')
  db.execute('INSERT INTO records_current VALUES (?,?,?,?,1)',
             ('mississauga_permit','old','2020-01-01',json.dumps({'address':'10 King St'})))
  db.execute('INSERT INTO records_current VALUES (?,?,?,?,1)',
             ('toronto_licence','missing','',json.dumps({'entity_name':'Test'})))
  db.execute('INSERT INTO records_current VALUES (?,?,?,?,1)',
             ('toronto_licence','future','2099-01-01',json.dumps({'entity_name':'Test'})))
  db.commit();db.close()
  export(self.data)
  with (self.data/'source_date_quality_audit.csv').open(encoding='utf-8-sig') as f:
   audit={r['source_id']:r for r in csv.DictReader(f)}
  self.assertEqual(audit['mississauga_permit']['older_than_window'],'1')
  self.assertEqual(audit['toronto_licence']['missing_or_invalid_date'],'1')
  self.assertEqual(audit['toronto_licence']['future_date'],'1')
  self.assertEqual(audit['toronto_licence']['selected_recent'],'0')
 def test_address_only_match_not_verified(self):
  db=sqlite3.connect(self.data/'business_discovery.sqlite')
  db.execute('CREATE TABLE observations (source_id TEXT,source_key TEXT,company_name TEXT,address TEXT,city TEXT,industry TEXT,event_date TEXT,event_type TEXT,observed_at TEXT)')
  db.execute('INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?)',('directory','xyz','Maybe Foods','2 Unnamed Ave','','',date.today().isoformat(),'DIRECTORY',''))
  db.commit();db.close()
  export(self.data)
  with (self.data/'opportunities_ALL_REVIEW_ONLY.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
  a=next(r for r in rows if r['source_id']=='york')
  self.assertEqual(a['maturity'],'ENRICHED');self.assertEqual(a['identity_confidence'],'ADDRESS_ONLY_POSSIBLE_MATCH')
  self.assertNotEqual(a['review_status'],'SALES_READY')

if __name__=='__main__':unittest.main()
