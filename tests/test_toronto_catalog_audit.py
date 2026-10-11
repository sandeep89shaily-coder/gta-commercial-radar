import unittest
from unittest.mock import Mock
from toronto_catalog_audit import audit,fetch_catalog
class CatalogAuditTests(unittest.TestCase):
 def test_pagination_and_duplicate_protection(self):
  class Session:
   def get(self,url,params,timeout):
    response=Mock()
    start=params['start']
    response.json.return_value={'success':True,'result':{'count':2,'results':[{'id':str(start+1),'name':'x'}] if start<2 else []}}
    return response
  self.assertEqual(len(fetch_catalog(Session(),rows=1)),2)
 def test_unproven_name_search_not_marked_ingested(self):
  p=[{'id':'abc','name':'building-permits-active-permits','title':'Active Building Permits','resources':[{'id':'r1','format':'CSV'}]}]
  s=[{'id':'toronto_active','jurisdiction':'Toronto','package_query':'Active Building Permits','collector':'ckan'}]
  result=audit(p,s)[0]
  self.assertEqual(result['collector_alignment'],'TITLE_SEARCH_POSSIBLE')
  self.assertEqual(result['resource_ids'],'r1')
  self.assertIn('construction_development',result['priority_families'])
 def test_exact_slug_match_even_if_query_differs(self):
  p=[{'id':'p','name':'building-permits-active-permits','title':'Building Permits - Active Permits'}]
  s=[{'id':'toronto_active','jurisdiction':'Toronto','package_slug':'building-permits-active-permits','enabled':True}]
  result=audit(p,s)[0]
  self.assertEqual(result['collector_alignment'],'EXACT_CONFIGURED')
  self.assertEqual(result['configured_enabled_ids'],'toronto_active')
 def test_exact_package_match(self):
  p=[{'id':'abc','name':'x','resources':[]}]
  s=[{'id':'toronto_x','jurisdiction':'Toronto','package_id':'abc'}]
  self.assertEqual(audit(p,s)[0]['configured_exact_ids'],'toronto_x')
if __name__=='__main__':unittest.main()
