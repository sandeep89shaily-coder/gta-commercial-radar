import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from toronto_source_validator import check_package, choose_candidates, should_run

class TorontoSourceValidatorTests(unittest.TestCase):
 def test_source_family_diversity_and_limit(self):
  rows=[
   {'package_id':'building1','priority_score':'100','priority_families':'construction_development'},
   {'package_id':'building2','priority_score':'99','priority_families':'construction_development'},
   {'package_id':'contracts','priority_score':'95','priority_families':'procurement_finance'},
   {'package_id':'roads','priority_score':'85','priority_families':'infrastructure_transport'}]
  selected=choose_candidates(rows,limit=3)
  self.assertEqual({r['package_id'] for r in selected},{'building1','contracts','roads'})
 def test_official_metadata_and_field_names_only(self):
  class Session:
   def get(self,url,params,timeout):
    r=Mock()
    if url.endswith('package_show'):
     r.json.return_value={'success':True,'result':{
      'id':'package-123','name':'test-procurement','title':'Tender dataset',
      'organization':{'title':'Purchasing'}, 'resources':[{
        'id':'resource-123','format':'CSV','name':'Contracts','datastore_active':True}]}}
    else:
     self.assertEqual(params['limit'],1)
     r.json.return_value={'success':True,'result':{'fields':[{'id':'CONTRACT_ID'},{'id':'SUPPLIER'}],
                                                    'records':[{'SUPPLIER':'PRIVATE VALUE'}]}}
    return r
   def assertEqual(self,a,b):assert a==b
  result=check_package(Session(),{'package_id':'package-123'})
  self.assertEqual(result['schema_status'],'DATASTORE_FIELDS_OBSERVED')
  self.assertEqual(result['field_names'],['CONTRACT_ID','SUPPLIER'])
  self.assertNotIn('PRIVATE VALUE',str(result))
 def test_reject_non_id_path(self):
  with self.assertRaises(ValueError):
   check_package(None,{'package_id':'https://bad.example/path'})
 def test_cache_linked_to_current_catalogue(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp)/'validation.json'
   self.assertTrue(should_run(p,'2026-10-11'))
   p.write_text(json.dumps({'catalog_observed_at':'2026-10-11'}),encoding='utf-8')
   self.assertFalse(should_run(p,'2026-10-11'))
   self.assertTrue(should_run(p,'2026-10-18'))
if __name__=='__main__':unittest.main()
