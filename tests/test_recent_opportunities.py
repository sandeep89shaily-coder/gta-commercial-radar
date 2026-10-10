import sqlite3,tempfile,unittest
from pathlib import Path
from datetime import date,timedelta
from recent_opportunities import export,collect

class RecentTest(unittest.TestCase):
 def test_baseline_dates_and_dedup(self):
  with tempfile.TemporaryDirectory() as t:
   data=Path(t);db=sqlite3.connect(data/'business_discovery.sqlite')
   db.execute('CREATE TABLE observations (source_id TEXT, source_key TEXT,company_name TEXT,address TEXT,city TEXT,industry TEXT,event_date TEXT,event_type TEXT,observed_at TEXT)')
   day=date(2026,10,10)
   for key,days in [('recent',1),('old',20),('future',-1)]:
    db.execute('INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?)',('source',key,'ABC Limited','12 Test St','Toronto','restaurant',(day-timedelta(days=days)).isoformat(),'BUSINESS_LICENCE',''))
   db.commit();db.close()
   matches,new,pending=export(data,days=2,today=day)
   self.assertEqual((matches,new,pending),(1,1,1))
   self.assertEqual(export(data,days=2,today=day),(1,0,1))
 def test_empty_does_not_claim_records(self):
  with tempfile.TemporaryDirectory() as t:self.assertEqual(export(Path(t)),(0,0,0))
if __name__=='__main__':unittest.main()
