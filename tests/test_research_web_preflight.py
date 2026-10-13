from unittest.mock import patch
import research_web_preflight as probe

def test_free_check_requires_address_in_result_and_page():
 hits={'results':[{'url':'https://city.example/37-shorncliffe-road','title':'37 Shorncliffe Road planning','snippet':'Toronto project'}],'error':''}
 with patch.object(probe,'search_public',return_value=hits) as search,patch.object(probe,'read_public_page',return_value={'url':'https://city.example/37-shorncliffe-road','text':'Official 37 Shorncliffe Road Toronto development'}) as page:
  assert probe.main()==0
 assert search.call_count==1
 assert page.call_count==1

def test_free_check_rejects_irrelevant_wikipedia_number():
 hits={'results':[{'url':'https://en.wikipedia.org/wiki/37_(number)','title':'37 (number)','snippet':'A number'}],'error':''}
 with patch.object(probe,'search_public',return_value=hits),patch.object(probe,'read_public_page',side_effect=AssertionError('irrelevant page must not be opened')):
  assert probe.main()==1

def test_free_check_reports_provider_failure():
 with patch.object(probe,'search_public',return_value={'results':[],'error':'RSS unavailable'}),patch.object(probe,'read_public_page',side_effect=AssertionError('no pages')):
  assert probe.main()==1

def test_free_check_rejects_relevant_snippet_if_page_not_about_project():
 hits={'results':[{'url':'https://example.org/project','title':'37 Shorncliffe Road','snippet':'Planning'}],'error':''}
 with patch.object(probe,'search_public',return_value=hits),patch.object(probe,'read_public_page',return_value={'url':'https://example.org/project','text':'Unrelated content about the number 37'}):
  assert probe.main()==1
