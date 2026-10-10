import csv,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import autonomous_investigator as a

class AutonomousTests(unittest.TestCase):
 def test_queries_and_safe_domains(self):
  self.assertEqual(len(a.candidate_queries('ABC Foods','Toronto')),4)
  self.assertFalse(a.is_company_site('https://linkedin.com/company/abc'))
  self.assertTrue(a.is_company_site('https://www.example.com/contact'))
 def test_no_key_fails_closed(self):
  with tempfile.TemporaryDirectory() as tmp:
   with patch.dict('os.environ',{},clear=True):
    self.assertEqual(a.run(tmp),2)
 def test_discovery_cache_dry_run_and_live(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)
   a.write_csv(p/'lead_research_REVIEW_ONLY.csv',['candidate_id','candidate_company','candidate_address'],[{'candidate_id':'one','candidate_company':'ABC Foods','candidate_address':'Toronto'}])
   hits=[{'url':'https://www.abcfoods.example/contact','title':'ABC Foods Contact','description':'Company contact details'}]
   with patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':'fake'}),patch.object(a,'search_brave',return_value=hits) as search,patch.object(a,'collect_public_page',return_value=({'title':'ABC Foods Contact','emails':['info@abcfoods.example'],'phones':['416-555-1234']},'')):
    self.assertEqual(a.run(p,limit=2,max_searches=4,max_pages=2),0)
    self.assertGreater(search.call_count,0)
   rows=a.read_csv(p/'autonomous_investigations_REVIEW_ONLY.csv')
   self.assertEqual(len(rows),1)
   self.assertEqual(rows[0]['status'],'SEARCH_EVIDENCE_REVIEW_REQUIRED')
   self.assertEqual(rows[0]['business_email'],'') # no automatic unverified contact promotion
   ev=a.read_csv(p/'autonomous_evidence_REVIEW_ONLY.csv')
   self.assertTrue(any('info@abcfoods.example' in r['notes'] for r in ev))
   with patch.dict('os.environ',{'BRAVE_SEARCH_API_KEY':'fake'}),patch.object(a,'search_brave',side_effect=AssertionError('cache was ignored')):
    self.assertEqual(a.run(p,limit=1,max_pages=0),0)
 def test_dry_run_zero_network(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)
   a.write_csv(p/'lead_research_REVIEW_ONLY.csv',['candidate_id','candidate_company','candidate_address'],[{'candidate_id':'two','candidate_company':'XYZ Inc','candidate_address':'Brampton'}])
   with patch.object(a,'search_brave',side_effect=AssertionError('network')):
    self.assertEqual(a.run(p,dry_run=True),0)
    self.assertFalse((p/'autonomous_research_cache.json').exists())
if __name__=='__main__':unittest.main()
