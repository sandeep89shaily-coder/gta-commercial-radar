import unittest
from urllib.parse import urlparse,parse_qs
from mississauga_catalog_audit import (allowed,next_link,crawl_pages,inventory,
                                      classify,compare_existing)

class FakeResponse:
 def __init__(self,body):self.body=body
 def raise_for_status(self):pass
 def json(self):return self.body
class Session:
 def __init__(self,pages):self.pages=pages;self.calls=[]
 def get(self,url,params=None,timeout=None):
  self.calls.append((url,params))
  return FakeResponse(self.pages[url])

class MississaugaCatalogTests(unittest.TestCase):
 def test_page_link_must_be_city_owned(self):
  self.assertTrue(allowed('https://data.mississauga.ca/api/search/v1/collections/a/items'))
  self.assertFalse(allowed('https://data.mississauga.ca.evil.test/api/search/v1/collections/a/items'))
  with self.assertRaisesRegex(ValueError,'Out-of-scope'):
   next_link({'links':[{'rel':'next','href':'https://other.example/data'}]},
             'https://data.mississauga.ca/api/search/v1/collections')
 def test_all_collections_and_pagination_merge_duplicates(self):
  base='https://data.mississauga.ca/api/search/v1/collections'
  next1=base+'/dataset/items?start=1'
  response={
   base:{'collections':[{'id':'dataset'},{'id':'maps'}],'links':[]},
   base+'/dataset/items':{'features':[{'id':'abc','properties':{'title':'Industrial building permits','description':'new construction'},
                                      'links':[{'href':'https://services6.arcgis.com/demo'}]}],
                          'numberMatched':2,'links':[{'rel':'next','href':next1}]},
   next1:{'features':[{'id':'def','properties':{'title':'Road closure'}}],
          'numberMatched':2,'links':[]},
   base+'/maps/items':{'features':[{'id':'abc','properties':{'title':'Industrial building permits','description':'new construction'}}],
                       'numberMatched':1,'links':[]}
  }
  items,groups=inventory(Session(response))
  self.assertEqual(groups,['dataset','maps'])
  self.assertEqual(len(items),2)
  self.assertEqual(items[0]['collections'],['dataset','maps'])
  self.assertIn('construction_development',items[0]['priority_families'])
 def test_incomplete_pagination_is_not_published(self):
  url='https://data.mississauga.ca/api/search/v1/collections/x/items'
  with self.assertRaisesRegex(ValueError,'Incomplete'):
   crawl_pages(Session({url:{'features':[{'id':'1'}],'numberMatched':10,'links':[]}}),
               url,'features')
 def test_wrong_or_looping_pages_are_rejected(self):
  url='https://data.mississauga.ca/api/search/v1/collections/x/items'
  with self.assertRaisesRegex(ValueError,'loop'):
   crawl_pages(Session({url:{'features':[],'links':[{'rel':'next','href':url}]}}),url,'features')
 def test_title_similarity_never_assumed_to_be_ingested(self):
  sample=[{'item_id':'abc','links':[],'title':'Issued Building Permits',
           'priority_families':['construction_development']}]
  current=[{'id':'mississauga_issued_building_permits','jurisdiction':'Mississauga',
            'name':'Issued Building Permits','url':'https://example.com/something'}]
  result=compare_existing(sample,current)[0]
  self.assertEqual(result['coverage_state'],'NOT_ID_VERIFIED')
  self.assertEqual(result['configured_exact_ids'],'')
if __name__=='__main__':unittest.main()
