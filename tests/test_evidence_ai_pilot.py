import csv
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from pilot_evidence import public_official_url,collect,url_list
from pilot_ai import investigate

def test_url_allowlist_blocks_lookalikes_and_internal_hosts():
 assert public_official_url('https://www.toronto.ca/planning')
 assert not public_official_url('https://toronto.ca.evil.org/')
 assert not public_official_url('http://www.toronto.ca/')
 assert not public_official_url('https://127.0.0.1/')
 assert not public_official_url('https://www.toronto.ca:444/')

def test_dry_run_does_not_fetch_or_call_ai():
 with TemporaryDirectory() as td:
  d=Path(td)
  with (d/'research_priority_queue.csv').open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=['source_id','source_key','address','source_evidence_urls'])
   w.writeheader();w.writerow({'source_id':'toronto_dev','source_key':'one','address':'10 Example St',
                                 'source_evidence_urls':'https://www.toronto.ca/planning | https://evil.org/'})
  with patch('pilot_evidence.fetch_official_page',side_effect=AssertionError('network invoked')):
   evidence,audit=collect(d)
  assert not evidence
  assert len(audit)==1 and audit[0]['status']=='DRY_RUN'
  assert investigate(d,confirm_paid=False)==0
  assert not (d/'deepseek_budget.sqlite').exists()

def test_paid_pilot_stops_before_key_if_no_evidence():
 with TemporaryDirectory() as td:
  d=Path(td)
  with (d/'research_priority_queue.csv').open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=['source_id','source_key','address'])
   w.writeheader();w.writerow({'source_id':'s','source_key':'1','address':'123'})
  with patch('pilot_ai.key_from_windows',side_effect=AssertionError('key should not be read')):
   assert investigate(d,confirm_paid=True)==0
