import json
from unittest.mock import patch
from urllib.error import HTTPError
from io import BytesIO
import deepseek_research_agent as agent

def test_tool_request_uses_nonthinking_mode():
 seen={}
 class Response:
  def __enter__(self): return self
  def __exit__(self,*args):return False
  def read(self,*args):return b'{"choices":[{"message":{"content":"{}"}}],"usage":{}}'
 def fake(req,timeout=None):
  seen['payload']=json.loads(req.data)
  return Response()
 with patch.object(agent,'urlopen',side_effect=fake):
  agent.api_call('secret',[{'role':'user','content':'Example project'}])
 assert seen['payload']['thinking']=={'type':'disabled'}
 assert seen['payload']['tool_choice']=='auto'

def test_bad_request_detail_preserved_without_key():
 with patch.object(agent,'urlopen',side_effect=HTTPError('https://api.deepseek.com',400,'Bad Request',{},BytesIO(b'{"error":{"message":"reasoning_content required"}}'))):
  try:agent.api_call('TOPSECRET',[{'role':'user','content':'Example'}])
  except ValueError as e:
   assert 'reasoning_content required' in str(e)
   assert 'TOPSECRET' not in str(e)
  else:assert False
