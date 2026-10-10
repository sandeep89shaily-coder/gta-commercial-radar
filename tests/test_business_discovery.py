import sys, tempfile, unittest, json, sqlite3
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from business_discovery import database,upsert_source,federal_rows,queue_ontario,output,import_radar_events

class FederalResponse:
    def iter_lines(self):
        data='Corporation number,Corporate name - form 1,Province/territory,City/town,Street,Date of incorporation\n1001234,Ontario Test Ltd,ON,Mississauga,23 King St,2026-10-01\n1005678,Alberta Test Ltd,AB,Calgary,41 Main St,2026-10-02\n'
        return (x.encode() for x in data.splitlines())

class BusinessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.data=Path(self.temp.name);self.db=database(self.data/'business_discovery.sqlite')
        self.source={'id':'unit','kind':'federal_csv','url':'https://example.gov/test.csv'}
        self.sample={'source_key':'1','company_name':'A Business','address':'1 King St','city':'Toronto','province':'ON','industry':'','website':'','event_date':'2026-10-01','event_type':'FEDERAL_INCORPORATION_RECORD','raw':{}}
    def tearDown(self):self.db.close();self.temp.cleanup()
    def test_federal_ontario_filter(self):
        rows=list(federal_rows(FederalResponse()))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['source_key'],'1001234')
        self.assertEqual(rows[0]['province'],'ON')
    def test_baseline_and_change_suppression(self):
        r=upsert_source(self.db,self.source,[self.sample]);self.assertTrue(r['baseline']);self.assertEqual(r['new'],0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM events').fetchone()[0],0)
        r=upsert_source(self.db,self.source,[self.sample]);self.assertEqual(r['new'],0);self.assertEqual(r['updated'],0)
        changed={**self.sample,'address':'2 King St'}
        r=upsert_source(self.db,self.source,[changed]);self.assertEqual(r['updated'],1)
        self.assertEqual(self.db.execute('SELECT count(*) FROM events').fetchone()[0],1)
        self.assertEqual(self.db.execute('SELECT count(*) FROM verification_queue').fetchone()[0],1)
    def test_atomic_on_partial_failure(self):
        upsert_source(self.db,self.source,[self.sample])
        def broken():
            yield {**self.sample,'source_key':'2'}
            raise RuntimeError('connection lost')
        with self.assertRaises(RuntimeError):upsert_source(self.db,self.source,broken())
        self.assertEqual(self.db.execute('SELECT count(*) FROM observations').fetchone()[0],1)
    def test_empty_snapshot_not_committed(self):
        with self.assertRaises(ValueError):upsert_source(self.db,self.source,[])
        self.assertEqual(self.db.execute('SELECT count(*) FROM runs').fetchone()[0],0)
    def test_queue_deduplicates(self):
        queue_ontario(self.db,self.sample,'a','test');queue_ontario(self.db,self.sample,'a','test');self.db.commit()
        self.assertEqual(self.db.execute('SELECT count(*) FROM verification_queue').fetchone()[0],1)
    def test_prior_radar_event_queue_no_baseline(self):
        other=self.data/'radar.sqlite';con=sqlite3.connect(other)
        con.execute('CREATE TABLE changes(id INTEGER PRIMARY KEY,source_id TEXT,record_key TEXT,change_type TEXT,observed_at TEXT,normalized_json TEXT)')
        con.execute('INSERT INTO changes(source_id,record_key,change_type,observed_at,normalized_json) VALUES(?,?,?,?,?)',('permit','abc','NEW','2026-10-09',json.dumps({'entity_name':'New Ontario Firm','address':'Toronto'})))
        con.execute('INSERT INTO changes(source_id,record_key,change_type,observed_at,normalized_json) VALUES(?,?,?,?,?)',('permit','def','REMOVED','2026-10-09',json.dumps({'entity_name':'Gone Firm'})))
        con.commit();con.close()
        self.assertEqual(import_radar_events(self.db,other),1)
        self.assertEqual(self.db.execute('SELECT count(*) FROM verification_queue').fetchone()[0],1)

if __name__=='__main__':unittest.main()
