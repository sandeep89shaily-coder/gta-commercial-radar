"""Commercial eligibility first, opportunity ranking second. Offline and read-only to collectors."""
import csv,html,re
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus,urlparse

ROOT=Path(__file__).resolve().parent
FIELDS=['investigation_id','tier','score','reason','address','city','company','description','event_type','event_date','date_basis','source_group','source_id','source_urls','service_opportunities','operator_hints','research_url','review_status']
# Standalone small-dwelling renovations have little B2B buyer potential.
SMALL_RESIDENTIAL=('second suite','second unit','two unit dwelling','two-unit dwelling','secondary dwelling',
 'secondary suite','basement apartment','basement suite','single family','single-family','single detached',
 'single-detached','semi detached','semi-detached','garden suite','laneway suite','residential conversion',
 'convert to two','additional dwelling unit','accessory dwelling unit','duplex conversion','triplex conversion')
MAJOR_PROJECT=('apartment building','rental tower','condominium tower','mixed use','mixed-use','high rise','high-rise',
 'multi residential','multi-residential','purpose built rental','purpose-built rental','residential tower')
COMMERCIAL=('industrial','warehouse','factory','manufactur','logistics','distribution centre','distribution center',
 'commercial','restaurant','retail','store','office','clinic','medical','hotel','hospitality','self storage',
 'self-storage','shopping centre','shopping center','tenant fit','fit-out','fit out','data centre','data center',
 'business expansion','new business','food service','automotive service','dealership','institutional','school')
BUYABLE=('new construction','new building','building permit','interior alteration','tenant fit','fit-out','fit out',
 'installation','renovation','retrofit','addition','expansion','new licence','new license','occupancy')
COMPLETED=('completed in 20','built in 20','occupied in 20','finished in 20','fully completed','operational since 20')
COLUMNS=FIELDS

def read(path):
 if not path.exists():return []
 with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def contains_any(text,needles):return any(n in text for n in needles)

def classify(r):
 desc=' '.join(str(r.get(k) or '') for k in ('description','event_type','event_class','source_id')).lower()
 low=(r.get('commercial_priority') or '').upper()=='LOW'
 if contains_any(desc,SMALL_RESIDENTIAL) and not contains_any(desc,COMMERCIAL):
  return None,'EXCLUDED_SMALL_RESIDENTIAL'
 if low and not contains_any(desc,COMMERCIAL+MAJOR_PROJECT):
  return None,'EXCLUDED_LOW_RELEVANCE'
 if contains_any(desc,COMPLETED):
  return None,'EXCLUDED_HISTORICAL_COMPLETED'
 commercial=contains_any(desc,COMMERCIAL)
 major=contains_any(desc,MAJOR_PROJECT)
 if not (commercial or major):
  # Explicit business licenses can be relevant despite sparse descriptions.
  if r.get('event_class')!='BUSINESS_LICENSING':
   return None,'EXCLUDED_NO_COMMERCIAL_SIGNAL'
 kind=r.get('event_class','')
 group=r.get('source_group','')
 date_basis=(r.get('event_date_basis') or '').upper()
 change_only=group=='MUNICIPAL_CHANGE' or 'CHANGE_DETECTED' in date_basis
 dated_source=bool(r.get('event_date')) and not change_only
 score=30
 if commercial:score+=20
 if major:score+=12
 if contains_any(desc,BUYABLE):score+=16
 if kind in ('BUILDING_PERMIT','BUSINESS_LICENSING'):score+=12
 elif kind=='DEVELOPMENT_APPLICATION':score+=5
 if dated_source:score+=10
 if change_only:score-=32
 if not (r.get('source_evidence_urls') or r.get('evidence_url')):score-=12
 if not r.get('address') and not r.get('company_name'):score-=15
 # Company name and address-only hints are NOT proof of a buyer.
 score=max(0,min(score,100))
 tier=('C - WATCHLIST' if change_only or score<55 else 'A - PRIORITY' if score>=77 else 'B - REVIEW')
 rationale=('Material source-record update, not a new issuance' if change_only
            else 'Dated commercial activity requiring verification')
 return (tier,score,rationale),'ELIGIBLE'

def valid_url(url):
 try:
  p=urlparse(str(url).strip())
  return str(url).strip() if p.scheme in ('http','https') and p.hostname and not p.username and not p.password else ''
 except ValueError:return ''

def prepare(r):
 classification,reason=classify(r)
 if classification is None:return None,reason
 tier,score,note=classification
 urls=[]
 for key in ('source_evidence_urls','evidence_url'):
  for value in (r.get(key) or '').split(' | '):
   url=valid_url(value)
   if url and url not in urls:urls.append(url)
 address=r.get('address') or ''
 city=r.get('city') or ''
 q=' '.join(x for x in ('"'+address+'"' if address else '',city,r.get('company_name') or '',r.get('description') or '') if x)[:200]
 return dict(investigation_id=r.get('investigation_id',''),tier=tier,score=score,reason=note,address=address,
   city=city,company=r.get('company_name') or 'UNKNOWN',description=r.get('description') or '',
   event_type=r.get('event_class') or r.get('event_type') or '',event_date=r.get('event_date') or '',
   date_basis='DETECTION DATE — NOT PROJECT START' if r.get('source_group')=='MUNICIPAL_CHANGE' else 'SOURCE EVENT DATE — VERIFY',
   source_group=r.get('source_group') or '',source_id=r.get('source_id') or '',
   source_urls=' | '.join(urls),service_opportunities=r.get('service_opportunities') or r.get('buyer_categories') or '',
   operator_hints=r.get('operator_candidates') or '',research_url='https://www.google.com/search?q='+quote_plus(q),
   review_status='UNVERIFIED — RESEARCH REQUIRED'),reason

def render(items,day,excluded):
 esc=lambda x:html.escape(str(x or ''),quote=True)
 parts=['<!doctype html><html lang="en"><head><meta charset="utf-8"><title>GTA Radar - Commercial Opportunities</title>',
 '<style>body{font:15px Segoe UI,Arial;max-width:1180px;margin:30px auto;padding:0 18px;background:#f4f6f9;color:#213044}',
 'article{background:white;margin:15px 0;padding:18px;border-radius:10px;border:1px solid #d9e0e9}',
 'a{color:#175996}small{color:#566676}table{border-collapse:collapse;width:100%}td,th{padding:6px;border-bottom:1px solid #ddd}',
 'h1{margin-bottom:5px}</style></head><body><h1>GTA Commercial Radar — Eligible Opportunities</h1>',
 '<p>'+esc(day)+' · <b>'+str(len(items))+' qualifying candidates</b> (no quota) · '+str(excluded)+' excluded from this view</p>',
 '<p><small>Records stay in collector databases. A means research first, B means review, C is a watchlist. '
 'No purchasing demand or decision-maker is verified. A detection date is not a permit issue date. No paid AI.</small></p>']
 for tier in ('A - PRIORITY','B - REVIEW','C - WATCHLIST'):
  group=[r for r in items if r['tier']==tier]
  parts.append('<h2>'+esc(tier)+' ('+str(len(group))+')</h2>')
  for r in group:
   parts.append('<article><h3>'+esc(r['address'] or r['company'])+' — '+esc(r['score'])+'/100</h3>')
   for label,key in [('Municipality','city'),('Commercial activity','description'),('Signal','event_type'),('Source','source_id'),('Event/detection date','event_date'),('Date basis','date_basis'),('Potential buyers','service_opportunities'),('Company in source','company'),('Possible operator hints (unverified)','operator_hints')]:
    parts.append('<p><b>'+esc(label)+':</b> '+esc(r[key] or 'Unknown')+'</p>')
   urls=r['source_urls'].split(' | ') if r['source_urls'] else []
   parts.append('<p><b>Original records:</b> ')
   if urls:parts.extend('<a target="_blank" rel="noopener noreferrer" href="'+esc(u)+'">'+esc(u)+'</a> ' for u in urls)
   else:parts.append('Not supplied by source')
   parts.append('</p><p><a target="_blank" rel="noopener noreferrer" href="'+esc(r['research_url'])+'">Research this opportunity</a></p></article>')
 parts.append('</body></html>')
 return ''.join(parts)

def build(data,date=None):
 data=Path(data);data.mkdir(parents=True,exist_ok=True)
 day=date or datetime.now().astimezone().date().isoformat()
 source=read(data/'matured_opportunities_REVIEW_ONLY.csv')
 output=[];reasons=Counter();seen=set()
 for r in source:
  item,reason=prepare(r);reasons[reason]+=1
  if item is None:continue
  key=item['investigation_id'] or (item['source_id'],item['address'],item['description'])
  if key in seen:continue
  seen.add(key);output.append(item)
 output.sort(key=lambda r:(r['tier'], -r['score'],r['source_id'],r['investigation_id']))
 destination=data/'COMMERCIAL_CANDIDATES_REVIEW_ONLY.csv'
 with destination.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(output)
 (data/'commercial_candidates_dashboard.html').write_text(render(output,day,sum(n for k,n in reasons.items() if k!='ELIGIBLE')),encoding='utf-8')
 with (data/'commercial_selection_audit.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f);w.writerow(['result','count']);w.writerows(sorted(reasons.items()))
 print('Eligible commercial opportunities:',len(output),'A:',sum(x['tier'].startswith('A') for x in output),
       'B:',sum(x['tier'].startswith('B') for x in output),'C:',sum(x['tier'].startswith('C') for x in output))
 print('Dashboard:',data/'commercial_candidates_dashboard.html')
 return output

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--data-dir',type=Path,default=ROOT/'data')
 a=p.parse_args();build(a.data_dir)
