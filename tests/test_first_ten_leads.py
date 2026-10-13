import csv
from tempfile import TemporaryDirectory
from pathlib import Path
from first_ten_leads import build

def test_first_ten_review_profiles_are_not_sale_ready():
 with TemporaryDirectory() as td:
  d=Path(td)
  rows=[
   {'investigation_id':'a','source_id':'toronto_development_applications',
    'source_group':'MUNICIPAL','event_class':'DEVELOPMENT_APPLICATION',
    'description':'new restaurant and retail construction','address':'12 King St',
    'research_priority':'80','event_date':'2026-10-12','source_evidence_urls':''},
   {'investigation_id':'b','source_id':'toronto_active_building_permits',
    'source_group':'MUNICIPAL_CHANGE','event_class':'BUILDING_PERMIT',
    'company_name':'Example Company','description':'tenant improvement',
    'event_date':'2026-10-12','source_evidence_urls':'https://example.org/permit'}
  ]
  with (d/'research_priority_queue.csv').open('w',encoding='utf-8',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
   w.writeheader();w.writerows(rows)
  result=build(d)
  assert len(result)==2
  assert all(r['readiness']=='RESEARCH_ONLY_NOT_FOR_SALE' for r in result)
  assert all(r['contact_status']=='NOT_VERIFIED' for r in result)
  assert 'Identify business/operator' in result[0]['missing_to_qualify']
  assert 'Attach official record URL' in result[0]['missing_to_qualify']
  assert 'Restaurant/equipment suppliers' in result[0]['buyer_categories']
  assert result[1]['date_basis']=='CHANGE_DETECTED_NOT_NEW_ISSUANCE'
  page=(d/'first_10_leads_dashboard.html').read_text()
  assert 'RESEARCH ONLY' in page
  assert 'https://example.org/permit' in page

def test_html_is_escaped_and_limit_respected():
 with TemporaryDirectory() as td:
  d=Path(td)
  with (d/'research_priority_queue.csv').open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=['investigation_id','company_name'])
   w.writeheader()
   w.writerow({'investigation_id':'1','company_name':'<script>alert(1)</script>'})
   w.writerow({'investigation_id':'2','company_name':'Other'})
  assert len(build(d,maximum=1))==1
  html=(d/'first_10_leads_dashboard.html').read_text()
  assert '<script>alert(1)</script>' not in html
  assert '&lt;script&gt;' in html
