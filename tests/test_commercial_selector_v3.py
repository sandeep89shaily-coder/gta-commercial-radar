import csv,tempfile
from pathlib import Path
import commercial_selector_v3 as s

def r(desc,source='toronto_active_building_permits',key='1'):
 return dict(description=desc,source_id=source,source_key=key,opportunity_id=key,
  address='123 Sample Road',city='Toronto',event_date='2026-10-12',source_group='MUNICIPAL_CHANGE')

def test_residential_rejection():
 for desc in ('Convert existing dwelling to Two Unit Dwelling','Basement apartment and secondary suite','Interior alteration to existing residential dwelling','New 2-storey detached dwelling with HVAC and plumbing'):
  assert s.assess(r(desc))[0]=='EXCLUDE_SMALL_RESIDENTIAL'
def test_commercial_not_all_residential_excluded():
 assert s.assess(r('38-storey apartment tower construction'))[0]=='PERMIT_REVIEW'
 assert s.assess(r('Industrial warehouse building construction'))[0]=='PERMIT_REVIEW'
 assert s.assess(r('Food processing operation commercial interior alterations'))[0]=='PERMIT_REVIEW'
def test_planning_cannot_be_promoted_by_date():
 x=r('Proposed 40-storey apartment tower','toronto_development_applications')
 assert s.assess(x)[0]=='PLANNING_WATCH'
 assert s.priority(x,'PLANNING_WATCH')<s.priority(r('Industrial warehouse construction'),'PERMIT_REVIEW')
def test_health_directory_is_enrichment():
 assert s.assess(r('Restaurant inspection','peel_health_establishments'))[0]=='ENRICHMENT_ONLY'
def test_100_plus_no_quota_preserve_input_and_audit():
 with tempfile.TemporaryDirectory() as tmp:
  p=Path(tmp);data=[r('New industrial building construction',key=str(i)) for i in range(125)]
  data.append(r('Two Unit Dwelling',key='bad'))
  src=p/'input.csv'
  with src.open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=data[0].keys());w.writeheader();w.writerows(data)
  before=src.read_bytes()
  result=s.run(src,p/'output')
  assert len(result)==125
  assert src.read_bytes()==before
  assert (p/'output'/'CANDIDATES_V3_EXCLUDED_AUDIT.csv').is_file()
  assert (p/'output'/'commercial_candidates_v3.html').is_file()
