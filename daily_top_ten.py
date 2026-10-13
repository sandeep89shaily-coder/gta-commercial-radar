"""Local review pack: at most ten highest-ranked commercial candidates each day.

This is NOT a lead-verification agent. No networks, AI, contacts or database writes.
Keep an immutable-per-day snapshot on repeat runs, plus a latest dashboard alias.
"""
from __future__ import annotations
import csv,html,os,shutil,tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus,urlparse
from lead_maturation import balanced_focus

ROOT=Path(__file__).resolve().parent
KEYS=['investigation_id','priority','address','city','company_name','source_id','linked_sources',
      'commercial_signal','description','event_date','date_basis','source_group',
      'buyer_categories','possible_operator','operator_note','source_urls','research_url',
      'linked_events','review_status']
MAX_DAILY=10

def rows(path):
 if not path.is_file():return []
 with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def valid_url(value):
 p=urlparse(str(value or '').strip())
 return str(value).strip() if p.scheme in ('https','http') and p.hostname and not p.username and not p.password else ''

def pack(row):
 urls=[]
 for key in ('source_evidence_urls','evidence_url'):
  for value in str(row.get(key) or '').split(' | '):
   u=valid_url(value)
   if u and u not in urls:urls.append(u)
 addr=(row.get('address') or '').strip()
 city=(row.get('city') or '').strip()
 desc=(row.get('description') or '').strip()
 company=(row.get('company_name') or '').strip()
 query=' '.join(x for x in (('"'+addr+'"') if addr else '',city,company,'commercial development') if x)
 return dict(investigation_id=row.get('investigation_id',''),
  priority=row.get('research_priority',''),address=addr,city=city,
  company_name=company or 'UNKNOWN / NOT VERIFIED',source_id=row.get('source_id',''),
  linked_sources=row.get('linked_sources',''),
  commercial_signal=row.get('event_class') or row.get('event_type',''),
  description=desc,event_date=row.get('event_date',''),
  date_basis=('DETECTED CHANGE — NOT NEW PERMIT' if row.get('source_group')=='MUNICIPAL_CHANGE'
              else row.get('event_confidence') or 'DATE UNVERIFIED'),
  source_group=row.get('source_group',''),
  buyer_categories=row.get('service_opportunities') or row.get('buyer_categories',''),
  possible_operator=row.get('operator_candidates') or row.get('possible_operator') or '',
  operator_note='Unverified address-only identity hint; not proof of ownership/tenancy',
  source_urls=' | '.join(urls),
  research_url='https://www.google.com/search?q='+quote_plus(query) if query else '',
  linked_events=row.get('linked_events') or '1',review_status='RESEARCH CANDIDATE — NOT VERIFIED')

def html_page(selected,date):
 esc=lambda x:html.escape(str(x or ''),quote=True)
 content=['<!doctype html><html lang="en"><head><meta charset="utf-8">',
 '<meta name="viewport" content="width=device-width, initial-scale=1">',
 '<title>GTA Commercial Radar - Daily 10</title>',
 '<style>body{font:15px Segoe UI,Arial,sans-serif;background:#f3f6fa;color:#1c2937;max-width:1150px;margin:30px auto;padding:0 16px}',
 'header{margin:0 0 23px}article{background:#fff;border:1px solid #dce3ea;border-radius:12px;padding:21px;margin:18px 0;box-shadow:0 2px 8px #00000009}',
 'h1{margin-bottom:6px}h2{margin:3px 0 10px}p{line-height:1.5}small,.muted{color:#59687a}',
 'dl{display:grid;grid-template-columns:170px 1fr;gap:8px 12px}dt{font-weight:650}dd{margin:0;overflow-wrap:anywhere}',
 'a{color:#145ba2}code{overflow-wrap:anywhere} .tag{font-weight:700;font-size:12px;background:#e8f1fc;padding:6px 10px;border-radius:20px}</style></head><body>',
 '<header><h1>GTA Commercial Radar — Daily Top 10</h1>',
 '<p><strong>Date: '+esc(date)+'</strong> · '+str(len(selected))+' research candidates selected (maximum 10).</p>',
 '<p class="muted">Automatically selected from collected public records. Not verified, not sale-ready. '
 'Dates may reflect source changes rather than new construction or permits. Buyer categories are possible fits, not purchasing intent. No DeepSeek charges.</p></header>']
 if not selected:content.append('<article><h2>No eligible candidates today</h2><p>No candidates in the current ranked queue. Historical data remains untouched.</p></article>')
 for index,r in enumerate(selected,1):
  content.append('<article><span class="tag">#'+str(index)+' · Priority '+esc(r['priority'])+'/100</span>')
  content.append('<h2>'+esc(r['address'] or r['company_name'])+'</h2>')
  items=[('Municipality',r['city']),('Event',r['commercial_signal']),('Project / activity',r['description']),
  ('Source / detected date',r['event_date']),('Date interpretation',r['date_basis']),
  ('Source',r['source_id']),('Other linked sources',r['linked_sources']),
  ('Organization in public data (unverified)',r['company_name']),
  ('Possible operator matches',r['possible_operator'] or 'Unknown'),
  ('Possible service categories',r['buyer_categories'] or 'Not classified'),
  ('Records grouped',r['linked_events']),('Review status',r['review_status'])]
  content.append('<dl>')
  for label,value in items:content.append('<dt>'+esc(label)+'</dt><dd>'+esc(value or 'Not provided')+'</dd>')
  urls=[u for u in r['source_urls'].split(' | ') if u]
  content.append('<dt>Original evidence</dt><dd>')
  if urls:
   for url in urls:content.append('<div><a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">'+esc(url)+'</a></div>')
  else:content.append('No direct official record URL supplied by collector — find source manually')
  content.append('</dd><dt>Manual research</dt><dd>')
  if r['research_url']:content.append('<a href="'+esc(r['research_url'])+'" target="_blank" rel="noopener noreferrer">Search this project / address</a>')
  content.append('</dd></dl></article>')
 content.append('</body></html>')
 return ''.join(content)

def build(data,date=None):
 data=Path(data)
 date=date or datetime.now().astimezone().date().isoformat()
 if not __import__('re').fullmatch(r'\d{4}-\d{2}-\d{2}',date):raise ValueError('Date must be YYYY-MM-DD')
 data.mkdir(parents=True,exist_ok=True)
 history=data/'daily_top10_history';history.mkdir(exist_ok=True)
 daily_csv=history/(date+'.csv');daily_html=history/(date+'.html')
 # Preserve first review cohort of the day; a second run cannot increase or
 # silently replace the day's ten chosen projects.
 if daily_csv.exists() and daily_html.exists():
  selected=rows(daily_csv)
 else:
  ranked=rows(data/'matured_opportunities_REVIEW_ONLY.csv')
  if not ranked:ranked=rows(data/'research_priority_queue.csv')
  ranked.sort(key=lambda r:(int(r.get('research_priority') or 0),r.get('event_date',''),r.get('investigation_id','')),reverse=True)
  selected=[pack(r) for r in balanced_focus(ranked,MAX_DAILY)]
  # Date-stamped snapshot; if interrupted, later rerun recreates same day.
  with daily_csv.open('w',encoding='utf-8-sig',newline='') as f:
   writer=csv.DictWriter(f,fieldnames=KEYS);writer.writeheader();writer.writerows(selected)
  daily_html.write_text(html_page(selected,date),encoding='utf-8')
 shutil.copyfile(daily_csv,data/'DAILY_TOP_10_CANDIDATES.csv')
 shutil.copyfile(daily_html,data/'daily_top_10_dashboard.html')
 print('Daily review date:',date,'| selected:',len(selected),'of maximum',MAX_DAILY)
 print('Dashboard:',data/'daily_top_10_dashboard.html')
 print('CSV:',data/'DAILY_TOP_10_CANDIDATES.csv')
 return selected

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--data-dir',type=Path,default=ROOT/'data');p.add_argument('--date')
 a=p.parse_args();build(a.data_dir,a.date)
