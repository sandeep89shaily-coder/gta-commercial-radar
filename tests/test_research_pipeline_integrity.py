import csv,sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import deepseek_research_agent as agent
from lead_research import candidate_id

def test_skip_previous_attempts_and_take_two_new_candidates():
 with TemporaryDirectory() as td:
  d=Path(td)
  rows=[{'source_id':'city','source_key':str(i),'address':f'{i} Example Street'} for i in range(4)]
  with (d/'research_priority_queue.csv').open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
  import datetime
  day=datetime.datetime.now().astimezone().date().isoformat()
  db=sqlite3.connect(d/'deepseek_budget.sqlite')
  agent.ledger(db)
  existing=agent.claim(db,candidate_id(rows[0]),day,reservation_amount=agent.ROUND_RESERVE_USD*20)
  agent.complete(db,existing,'ERROR',None);db.close()
  called=[]
  def research(key,row):
   called.append(row['address'])
   return {'summary':'Investigated','searches':2,'pages':1,'evidence_urls':''},0.0003
  with patch.object(agent,'key_from_windows',return_value='test-only'),patch.object(agent,'investigate_one',side_effect=research):
   assert agent.run(d,confirm_paid=True,max_leads=2)==0
  assert called==['1 Example Street','2 Example Street']
  with (d/'autonomous_deepseek_REVIEW_ONLY.csv').open(encoding='utf-8-sig',newline='') as f:results=list(csv.DictReader(f))
  assert len(results)==2
  assert all(x['status']=='NO_SOURCE_EVIDENCE' for x in results)
  assert all(x['searches']=='2' for x in results)

def test_multiple_tool_calls_all_get_replies():
 seen=[]
 def fake_api(key,messages):
  seen.append(messages)
  if len(seen)==1:
   return {'message':{'role':'assistant','tool_calls':[
    {'id':'a','type':'function','function':{'name':'search_public','arguments':'{"query":"test address"}'}},
    {'id':'b','type':'function','function':{'name':'search_public','arguments':'{"query":"test developer"}'}},
    {'id':'c','type':'function','function':{'name':'search_public','arguments':'{"query":"test owner"}'}}]}},{'prompt_tokens':10,'completion_tokens':10}
  return {'message':{'role':'assistant','content':'{"summary":"not verified","evidence_urls":[]}' }},{'prompt_tokens':10,'completion_tokens':10}
 with patch.object(agent,'api_call',side_effect=fake_api),patch.object(agent,'search_public',return_value={'results':[],'error':'provider unavailable'}) as search:
  answer,cost=agent.investigate_one('fake',{'address':'10 Example Street'})
 assert search.call_count==3
 assert answer['searches']==3
 assert any('provider unavailable' in str(m) for m in seen[1])

def test_search_outage_is_not_empty_success():
 from urllib.error import URLError
 with patch.object(agent,'urlopen',side_effect=URLError('offline')):
  result=agent.search_public('10 Example Street owner')
 assert result['results']==[]
 assert 'unavailable' in result['error'].lower()
