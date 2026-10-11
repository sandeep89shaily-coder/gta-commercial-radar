import json,sqlite3,tempfile,unittest
from pathlib import Path
from entity_intelligence import extract,normalize_address,run
class EntityIntelligenceTests(unittest.TestCase):
 def test_normalization(self):
  self.assertEqual(normalize_address(' 12 King St.,  Unit 3 '),'12 king st unit 3')
 def test_address_only_is_unverified(self):
  with tempfile.TemporaryDirectory() as temp:
   d=Path(temp)
   a=sqlite3.connect(d/'business_discovery.sqlite')
   a.executescript("CREATE TABLE observations(source_id TEXT,source_key TEXT,company_name TEXT,address TEXT,city TEXT);")
   a.execute("INSERT INTO observations VALUES(?,?,?,?,?)",('fed','1','Acme Foods','123 Long Avenue','Brampton'));a.commit();a.close()
   b=sqlite3.connect(d/'brampton_sources.sqlite')
   b.executescript("CREATE TABLE records(source_id TEXT,record_id TEXT,json TEXT);")
   b.execute("INSERT INTO records VALUES(?,?,?)",('brampton_lic_food','X',json.dumps({'fields':{'organization_name':'Other Tenant','business_address':'123 Long Avenue'},'source_url':'https://brampton.ca/license'})))
   b.commit();b.close()
   r=extract(d)
   self.assertEqual(len(r),1)
   self.assertEqual(r[0]['verified_identity'],'NO')
   self.assertEqual(r[0]['classification'],'UNVERIFIED_ADDRESS_MATCH')
   self.assertEqual(run(d)['verified_links'],0)
   self.assertEqual(r[0]['classification'],'UNVERIFIED_ADDRESS_MATCH')
 def test_name_and_address_match_remains_unverified(self):
  with tempfile.TemporaryDirectory() as temp:
   d=Path(temp)
   a=sqlite3.connect(d/'business_discovery.sqlite')
   a.execute('CREATE TABLE observations(source_id TEXT,source_key TEXT,company_name TEXT,address TEXT,city TEXT)')
   a.execute('INSERT INTO observations VALUES(?,?,?,?,?)',('registry','b1','Acme Inc.','123 Long Avenue','Brampton'))
   a.commit();a.close()
   b=sqlite3.connect(d/'brampton_sources.sqlite')
   b.execute('CREATE TABLE records(source_id TEXT,record_id TEXT,json TEXT)')
   b.execute('INSERT INTO records VALUES(?,?,?)',('brampton_lic_test','l1',json.dumps({'fields':{'organization_name':'ACME INC','business_address':'123 Long Avenue'}})))
   b.commit();b.close()
   candidates=extract(d)
   self.assertEqual(candidates[0]['classification'],'UNVERIFIED_NAME_AND_ADDRESS_MATCH')
   self.assertEqual(candidates[0]['verified_identity'],'NO')
 def test_no_database_not_created(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td)
   self.assertEqual(extract(d),[])
   self.assertFalse((d/'business_discovery.sqlite').exists())
if __name__=='__main__':unittest.main()
