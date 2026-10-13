from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path
import csv
import deepseek_research_agent as agent

def test_search_only_dry_run_does_not_spend():
 with TemporaryDirectory() as td:
  d=Path(td)
  with (d/'research_priority_queue.csv').open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=['source_id','source_key','address']);w.writeheader()
   w.writerow({'source_id':'city','source_key':'one','address':'10 Example Road'})
  with patch.object(agent,'key_from_windows',side_effect=AssertionError('Must not read API key')):
   assert agent.run(d)==0
  assert not (d/'deepseek_budget.sqlite').exists()

def test_search_requires_short_query_and_errors_are_graceful():
 assert agent.search_public('x'*181)==[]

def test_public_url_rejects_internal_targets_without_dns():
 with patch.object(agent,'public_host',return_value=False):
  assert agent.secure_url('https://localhost:443')==''
  assert agent.secure_url('https://127.0.0.1')==''
  assert agent.secure_url('http://toronto.ca')==''
  assert agent.secure_url('https://toronto.ca:444')==''
  assert agent.secure_url('https://toronto.ca.evil.test')==''
