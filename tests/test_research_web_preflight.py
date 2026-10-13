from unittest.mock import patch
import research_web_preflight as probe

def test_free_check_uses_only_search_and_page_tools():
 hits={'results':[{'url':'https://city.example/permit','title':'Public permit','snippet':'project'}],'error':''}
 with patch.object(probe,'search_public',return_value=hits) as search,patch.object(probe,'read_public_page',return_value={'url':'https://city.example/permit','text':'Official record '*20}) as page:
  assert probe.main()==0
 assert search.call_count==1
 assert page.call_count==1

def test_free_check_reports_search_provider_failure():
 with patch.object(probe,'search_public',return_value={'results':[],'error':'RSS provider unavailable'}) as search,patch.object(probe,'read_public_page',side_effect=AssertionError('No pages should be read')):
  assert probe.main()==1
 assert search.call_count==2

def test_free_check_reports_pages_blocked():
 with patch.object(probe,'search_public',return_value={'results':[{'url':'https://example.org/project'}],'error':''}),patch.object(probe,'read_public_page',return_value={'error':'Robots disallows retrieval'}):
  assert probe.main()==1
