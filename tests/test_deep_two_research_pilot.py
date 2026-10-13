import csv
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import deepseek_research_agent as agent

def test_deep_pilot_two_leads_only_and_stays_free_without_confirmation():
 with TemporaryDirectory() as td:
  path=Path(td)
  with (path/'research_priority_queue.csv').open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=['source_id','source_key','address']);w.writeheader()
   for n in range(11):w.writerow({'source_id':'official','source_key':str(n),'address':'%d Test Road'%n})
  with patch.object(agent,'key_from_windows',side_effect=AssertionError('No paid key in dry run')):
   assert agent.run(path,confirm_paid=False)==0
  assert not (path/'deepseek_budget.sqlite').exists()

def test_two_leads_have_20_round_pessimistic_budget_within_dollar():
 assert agent.ROUND_RESERVE_USD*20*2 <= 1.0

def test_research_notebook_compacts_after_tool_cycle():
 counts=[]
 def ai(key,msgs):
  counts.append(len(msgs))
  if len(counts)<8:
   return {'message':{'role':'assistant','tool_calls':[{'id':'c%d'%len(counts),'type':'function','function':{'name':'search_public','arguments':'{"query":"project developer"}'}}]}},{'prompt_tokens':100,'completion_tokens':100}
  return {'message':{'role':'assistant','content':'{"summary":"Unknown","evidence_urls":[]}'}},{'prompt_tokens':100,'completion_tokens':100}
 with patch.object(agent,'api_call',side_effect=ai),patch.object(agent,'search_public',return_value=[]):
  result,cost=agent.investigate_one('dummy',{'address':'6 Forest Laneway','description':'application'})
 assert result['searches']==7
 assert len(counts)==8
 assert max(counts)<=3
