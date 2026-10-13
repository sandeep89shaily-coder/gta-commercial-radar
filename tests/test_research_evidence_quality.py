from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError
import deepseek_research_agent as agent

def test_robots_404_does_not_block_public_html():
 class Response:
  status_code=200
  headers={'Content-Type':'text/html; charset=utf-8'}
  def __enter__(self):return self
  def __exit__(self,*args):return False
  def iter_content(self,size):yield b'<html><body>Official project owner: Example Company</body></html>'
 class Session:
  trust_env=True
  def get(self,*args,**kwargs):
   assert kwargs['allow_redirects'] is False
   return Response()
 def robots(req,timeout=None):
  raise HTTPError(req.full_url,404,'Not Found',{},BytesIO())
 with patch.object(agent,'secure_url',return_value='https://example.com/permit'),patch.object(agent,'urlopen',side_effect=robots),patch('requests.Session',return_value=Session()):
  found=agent.read_public_page('https://example.com/permit')
 assert 'Example Company' in found['text']
 assert found['url']=='https://example.com/permit'

def test_investigator_fails_closed_on_truncated_json():
 with patch.object(agent,'api_call',return_value=({'finish_reason':'length','message':{'content':'{"summary":'}},{'prompt_tokens':1,'completion_tokens':1})):
  try:agent.investigate_one('fake',{'address':'100 Example Road'})
  except ValueError as e:assert 'truncated' in str(e)
  else:assert False

def test_agent_only_accepts_url_it_read():
 scripted=[
  ({'message':{'role':'assistant','tool_calls':[{'id':'tool1','type':'function','function':{'name':'read_public_page','arguments':'{"url":"https://example.com/p"}'}}]}},{'prompt_tokens':10,'completion_tokens':10}),
  ({'message':{'role':'assistant','content':'{"summary":"Owner is Example","developer":"Example Company","evidence_urls":["https://example.com/p","https://fabricated.com/no"]}'}},{'prompt_tokens':10,'completion_tokens':10})]
 with patch.object(agent,'api_call',side_effect=scripted),patch.object(agent,'read_public_page',return_value={'url':'https://example.com/p','text':'Example Company owns the project'}):
  answer,cost=agent.investigate_one('fake',{'address':'100 Example Road'})
 assert answer['developer']=='Example Company'
 assert answer['evidence_urls']=='https://example.com/p'
 assert answer['pages']==1
