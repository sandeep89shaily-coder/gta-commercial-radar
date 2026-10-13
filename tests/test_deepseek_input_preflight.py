from unittest.mock import patch
import deepseek_research_agent as agent

def test_initial_request_with_tool_definitions_does_not_reject():
 seen={}
 def fake_urlopen(req,timeout=None):
  seen['body']=req.data
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):return False
   def read(self,*args):return b'{"choices":[{"message":{"content":"{}"},"finish_reason":"stop"}}],"usage":{"prompt_tokens":500,"completion_tokens":2}}'
  return Response()
 with patch.object(agent,'urlopen',side_effect=fake_urlopen):
  choice,usage=agent.api_call('dummy',[{'role':'system','content':agent.SYSTEM},
   {'role':'user','content':'{"address":"6 FOREST LANEWAY"}'}])
 assert choice['message']['content']=='{}'
 assert b'search_public' in seen['body']
