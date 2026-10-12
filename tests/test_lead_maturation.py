import csv,sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from lead_maturation import mature,write_csv,group_recent,balanced_focus,rank

def test_group_and_select_without_assuming_operator():
 with TemporaryDirectory() as tmp:
  d=Path(tmp)
  rows=[dict(opportunity_id='one',source_id='brampton',source_key='1',source_group='MUNICIPAL',address='12 Main Street',company_name='',commercial_priority='HIGH',event_date='2026-10-10',buyer_categories='commercial_hvac'),dict(opportunity_id='two',source_id='mississauga',source_key='2',source_group='MUNICIPAL',address='12 Main St',company_name='',commercial_priority='LOW',event_date='2026-10-09'),dict(opportunity_id='three',source_id='business',source_key='3',source_group='BUSINESS_DISCOVERY',address='',company_name='Other',commercial_priority='HIGH',event_date='2026-10-10')]
  write_csv(d/'opportunities_ALL_REVIEW_ONLY.csv',list(rows[0].keys()),rows)
  db=sqlite3.connect(d/'business_discovery.sqlite');db.execute('CREATE TABLE observations(company_name TEXT,address TEXT,city TEXT,source_id TEXT)');db.execute("INSERT INTO observations VALUES('Possible Franchisee Inc','12 Main Road','','directory')");db.commit();db.close()
  result=mature(d,maximum=2)
  assert result['groups']==2 and result['prioritized']==2
  with (d/'research_priority_queue.csv').open(encoding='utf-8-sig') as f:q=list(csv.DictReader(f))
  assert len(q)==2 and q[0]['linked_events']=='2'
  assert q[0]['contact_status']=='NOT_VERIFIED' and q[0]['review_status']=='UNVERIFIED_NOT_FOR_SALE'

def test_unknown_sites_not_merged():
 a=[{'opportunity_id':'a','address':''},{'opportunity_id':'b','address':''}]
 assert len(group_recent(a))==2

def test_empty_current_selection_clears_previous_investigations():
 with TemporaryDirectory() as tmp:
  d=Path(tmp)
  write_csv(d/'matured_opportunities_REVIEW_ONLY.csv',['investigation_id'],[{'investigation_id':'old'}])
  write_csv(d/'research_priority_queue.csv',['investigation_id'],[{'investigation_id':'old'}])
  (d/'investigation_dashboard.html').write_text('OLD INVESTIGATION')
  write_csv(d/'opportunities_ALL_REVIEW_ONLY.csv',['opportunity_id'],[])
  result=mature(d)
  assert result['prioritized']==0
  with (d/'research_priority_queue.csv').open(encoding='utf-8-sig') as f:
   assert not list(csv.DictReader(f))
  with (d/'matured_opportunities_REVIEW_ONLY.csv').open(encoding='utf-8-sig') as f:
   assert not list(csv.DictReader(f))
  assert 'OLD INVESTIGATION' not in (d/'investigation_dashboard.html').read_text()

def test_balanced_research_queue_preserves_alternative_sources():
 rows=[]
 for i in range(40):
  rows.append({'investigation_id':f'update{i}','source_group':'MUNICIPAL_CHANGE','source_id':'toronto_permits','research_priority':'99'})
 for i in range(12):
  rows.append({'investigation_id':f'new{i}','source_group':'MUNICIPAL','source_id':'toronto_development','research_priority':'75'})
 for i in range(8):
  rows.append({'investigation_id':f'other{i}','source_group':'MUNICIPAL','source_id':'mississauga_permits','research_priority':'70'})
 selection=balanced_focus(rows,30)
 assert len(selection)==30
 assert sum(r['source_group']=='MUNICIPAL_CHANGE' for r in selection)<=10
 assert len({r['source_id'] for r in selection})==3
 assert all(r['investigation_id'] for r in selection)

def test_changed_and_residential_records_downranked():
 base={'source_id':'toronto_active_building_permits','source_group':'MUNICIPAL','description':'commercial tenant construction','commercial_priority':'HIGH','address':'123 King St','company_name':'Example','evidence_url':'https://example.org/permit'}
 changed={**base,'source_group':'MUNICIPAL_CHANGE'}
 residential={**base,'description':'residential basement renovation','commercial_priority':'LOW'}
 assert rank(base,[base],[])>rank(changed,[changed],[])
 assert rank(base,[base],[])>rank(residential,[residential],[])
