import csv,tempfile
from pathlib import Path
from unittest.mock import patch
import commercial_selection_v2 as s
import daily_radar

def row(description,group='MUNICIPAL',kind='BUILDING_PERMIT',priority='HIGH',i='1'):
 return dict(investigation_id=i,address=i+' Sample Street',city='Toronto',description=description,
  source_group=group,event_class=kind,commercial_priority=priority,event_date='2026-10-12',
  source_id='toronto_permits',source_evidence_urls='https://example.com/permit/'+i,
  company_name='',service_opportunities='HVAC;security;insurance')

def test_excludes_small_residential_not_major_rental():
 for desc in ('Convert existing single detached dwelling to two unit dwelling',
              'Construction basement apartment and second suite',
              'Residential conversion to duplex'):
  assert s.classify(row(desc))[0] is None
 assert s.classify(row('New construction 38-storey apartment building'))[0] is not None
 assert s.classify(row('Industrial warehouse expansion'))[0] is not None

def test_prevents_change_detection_promotion_to_new_commercial():
 item,_=s.prepare(row('Industrial warehouse development',group='MUNICIPAL_CHANGE'))
 assert item['tier']=='C - WATCHLIST'
 assert 'NOT PROJECT START' in item['date_basis']

def test_no_fixed_limit_and_retains_originals():
 with tempfile.TemporaryDirectory() as d:
  folder=Path(d)
  records=[row('New construction industrial warehouse',i=str(i)) for i in range(115)]
  records+= [row('Single family basement second unit',i='residential')]
  with (folder/'matured_opportunities_REVIEW_ONLY.csv').open('w',newline='',encoding='utf-8') as f:
   w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
  before=(folder/'matured_opportunities_REVIEW_ONLY.csv').read_bytes()
  result=s.build(folder,'2026-10-13')
  assert len(result)==115
  assert result[0]['tier']=='A - PRIORITY'
  assert before==(folder/'matured_opportunities_REVIEW_ONLY.csv').read_bytes()
  assert (folder/'commercial_candidates_dashboard.html').exists()
  assert sum(1 for line in (folder/'COMMERCIAL_CANDIDATES_REVIEW_ONLY.csv').open(encoding='utf-8-sig'))==116

def test_daily_pipeline_keeps_all_existing_collector_steps_and_no_ai():
 names=[x[0] for x in daily_radar.STEPS]
 assert 'commercial_selection_v2' in names
 assert 'daily_top_ten' not in names
 assert 'municipal_poll' in names
 assert 'business_collection' in names
 assert not any('deepseek_daily.py' in str(x) for x in daily_radar.STEPS)
