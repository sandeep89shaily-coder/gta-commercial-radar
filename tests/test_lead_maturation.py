import csv,sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from lead_maturation import mature,write_csv,group_recent

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
