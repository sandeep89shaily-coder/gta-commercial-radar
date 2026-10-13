import csv
import tempfile
from pathlib import Path
from unittest.mock import patch
import daily_top_ten as m
import daily_radar

def write_queue(path, count=20):
 path.mkdir(parents=True,exist_ok=True)
 columns=['investigation_id','address','city','source_id','source_group','description','event_date','research_priority','source_evidence_urls','linked_events']
 with (path/'matured_opportunities_REVIEW_ONLY.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=columns);w.writeheader()
  for i in range(count):
   w.writerow({'investigation_id':str(i),'address':f'{i} Business Street','city':'Toronto','source_id':f'source{i%4}','source_group':'MUNICIPAL' if i%4 else 'MUNICIPAL_CHANGE','description':'New commercial warehouse','event_date':'2026-10-12','research_priority':str(100-i),'source_evidence_urls':f'https://example.org/{i}','linked_events':'1'})

def test_ten_max_preserves_daily_snapshot_and_source():
 with tempfile.TemporaryDirectory() as t:
  d=Path(t);write_queue(d)
  selected=m.build(d,'2026-10-13')
  assert len(selected)==10
  assert len(set(x['investigation_id'] for x in selected))==10
  assert 'New commercial warehouse' in (d/'daily_top_10_dashboard.html').read_text()
  assert 'https://example.org/' in (d/'daily_top_10_dashboard.html').read_text()
  assert (d/'matured_opportunities_REVIEW_ONLY.csv').exists()
  original=(d/'DAILY_TOP_10_CANDIDATES.csv').read_bytes()
  write_queue(d,3)
  assert len(m.build(d,'2026-10-13'))==10
  assert original==(d/'DAILY_TOP_10_CANDIDATES.csv').read_bytes()
  assert len(m.build(d,'2026-10-14'))==3
  assert (d/'daily_top10_history'/'2026-10-13.csv').exists()

def test_no_data_does_not_reuse_yesterday_candidates():
 with tempfile.TemporaryDirectory() as t:
  d=Path(t);write_queue(d,4)
  assert len(m.build(d,'2026-10-13'))==4
  (d/'matured_opportunities_REVIEW_ONLY.csv').unlink()
  assert len(m.build(d,'2026-10-14'))==0

def test_no_automatic_deepseek_in_daily_workflow():
 steps=dict((name,args) for name,args,_ in daily_radar.STEPS)
 assert 'daily_top_ten' in steps
 assert not any('deepseek' in ' '.join(args).lower() for args in steps.values())

def test_only_uses_actual_collector_urls():
 assert not m.valid_url('javascript:alert(1)')
 assert not m.valid_url('file:///key')
 assert m.valid_url('https://toronto.ca/planning')
