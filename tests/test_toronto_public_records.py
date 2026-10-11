import sqlite3
import unittest
from unittest.mock import Mock, patch
from toronto_public_records import (SPECS, fetch, identify, persist, setup)

class TorontoPublicRecordsTests(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(':memory:')
  setup(self.db)
  self.spec=next(s for s in SPECS if s['id']=='toronto_noncompetitive_contracts')
  self.meta={'package_id':'package-1','resource_id':'resource-1',
             'resource_url':'https://ckan.toronto.example/contract.csv',
             'source_url':'https://open.toronto.ca/dataset/tobids-non-competitive-contracts/'}
 def tearDown(self):
  self.db.close()
 def test_baseline_does_not_become_leads_updates_keep_versions(self):
  data=[{'CONTRACT_ID':'12','VENDOR':'A'},{'CONTRACT_ID':'13','VENDOR':'B'}]
  result=persist(self.db,self.spec,data,self.meta,'2026-10-11T14:00:00Z')
  self.assertEqual((result['status'],result['fetched']),('BASELINE',2))
  self.assertEqual(self.db.execute('SELECT count(*) FROM changes').fetchone()[0],0)
  update=[{'CONTRACT_ID':'12','VENDOR':'A'}, {'CONTRACT_ID':'13','VENDOR':'C'},
          {'CONTRACT_ID':'14','VENDOR':'D'}]
  result=persist(self.db,self.spec,update,self.meta,'2026-10-12T14:00:00Z')
  self.assertEqual((result['status'],result['new_observations'],result['modified_observations']),('OK',1,1))
  types=[r[0] for r in self.db.execute('SELECT change_type FROM changes ORDER BY id')]
  self.assertEqual(types,['DATASET_ROW_UPDATED','DATASET_ROW_FIRST_SEEN'])
  self.assertEqual(self.db.execute('SELECT count(*) FROM versions').fetchone()[0],4)
  result=persist(self.db,self.spec,update,self.meta,'2026-10-13T14:00:00Z')
  self.assertEqual(result['new_observations']+result['modified_observations'],0)
  self.assertEqual(self.db.execute('SELECT count(*) FROM versions').fetchone()[0],4)
 def test_missing_snapshot_rows_do_not_infer_closure(self):
  persist(self.db,self.spec,[{'CONTRACT_ID':'12','VENDOR':'A'},{'CONTRACT_ID':'13','VENDOR':'B'}],self.meta,'day1')
  persist(self.db,self.spec,[{'CONTRACT_ID':'12','VENDOR':'A'}],self.meta,'day2')
  self.assertEqual(self.db.execute('SELECT count(*) FROM records').fetchone()[0],2)
  self.assertEqual(self.db.execute('SELECT count(*) FROM changes').fetchone()[0],0)
 def test_identity_fallback_and_duplicate_refusal(self):
  field,ids=identify([{'X':'a'},{'X':'b'}],self.spec)
  self.assertEqual(field,'ROW_HASH')
  self.assertEqual(len(set(ids)),2)
  with self.assertRaises(ValueError):identify([{'X':'a'},{'X':'a'}],self.spec)
 def test_key_field_switch_is_rejected_not_blended(self):
  persist(self.db,self.spec,[{'CONTRACT_ID':'1','VENDOR':'A'}],self.meta,'day1')
  with self.assertRaisesRegex(ValueError,'key strategy changed'):
   persist(self.db,self.spec,[{'ID':'other','VENDOR':'A'}],self.meta,'day2')
  self.assertEqual(self.db.execute('SELECT count(*) FROM versions').fetchone()[0],1)
 def test_wrong_resource_or_format_is_rejected(self):
  class HTTP:
   def get(self,url,**kwargs):
    return Mock(content=b'one,two\\nA,B')
  package={'id':'p1','name':'tobids-non-competitive-contracts'}
  with patch('toronto_public_records.resolve_ckan_package',return_value=package):
   with patch('toronto_public_records.choose_ckan_resource',return_value={'id':'r1','name':'Different data','format':'CSV','url':'https://open.toronto.ca/abc.csv'}):
    with self.assertRaisesRegex(ValueError,'Expected named resource'):fetch(HTTP(),self.spec)
   with patch('toronto_public_records.choose_ckan_resource',return_value={'id':'r1','name':'Non-Competitive Contracts','format':'PDF','url':'https://open.toronto.ca/abc.pdf'}):
    with self.assertRaisesRegex(ValueError,'Unsupported resource'):fetch(HTTP(),self.spec)
 def test_all_sources_are_toronto_only(self):
  self.assertEqual(len(SPECS),7)
  self.assertEqual({s['id'] for s in SPECS},{
   'toronto_open_solicitations','toronto_awarded_contracts',
   'toronto_noncompetitive_contracts','toronto_road_restrictions','toronto_council_meeting_schedule',
   'toronto_development_pipeline','toronto_development_application_history'})
  self.assertEqual([s['slug'] for s in SPECS if s['department']=='City Planning'],
   ['development-pipeline','development-applications'])
  self.assertEqual([s['slug'] for s in SPECS[:2]],
   ['tobids-all-open-solicitations','tobids-awarded-contracts'])
if __name__=='__main__':unittest.main()
