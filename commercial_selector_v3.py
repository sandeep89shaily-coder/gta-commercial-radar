"""Offline, evidence-aware candidate gate; never edits collector data or calls paid AI."""
from __future__ import annotations
import argparse,csv,html,re
from collections import Counter
from pathlib import Path
from urllib.parse import quote_plus,urlparse

FIELDS=['lane','review_priority','candidate_id','address','city','source_id','source_key','description','event_date','date_basis','source_group','company_name','services_to_research','source_url','manual_search_url','reason','review_status']
EXCLUDE_FIELDS=['candidate_id','source_id','source_key','address','description','reason']
SMALL=re.compile(r'\b(two[ -]unit dwelling|second(?:ary)? (?:suite|unit|apartment)|basement (?:apartment|suite)|single[ -]family|single[ -]detached|semi[ -]detached|detached dwelling|garden suite|laneway suite|accessory dwelling|(?:interior )?alteration to (?:an? )?(?:existing )?(?:residential )?dwelling|(?:existing )?(?:one|two|three)[ -]storey (?:residential )?dwelling|duplex conversion|triplex conversion|dwelling conversion|private (?:residence|garage|home))\b',re.I)
HOUSE=re.compile(r'\b(sfd|single[ -]family|single[ -]detached|semi[ -]detached|detached (?:house|dwelling)|(?:new|existing|proposed) (?:2|two|3|three)[ -]storey (?:detached )?dwelling|houseplex|fourplex|duplex|triplex|two[ -]unit dwelling|secondary suite|basement apartment|garden suite|laneway suite|townhouse (?:unit|conversion))\b',re.I)
MAJOR=re.compile(r'\b(apartment (?:building|tower)|condominium (?:building|tower)|residential (?:tower|high[ -]rise|apartment building)|(?:[5-9]|[1-9]\d+)[ -]storey|\d{2,}\s+(?:residential|rental|apartment|condo|dwelling) units|mixed[ -]use (?:development|building)|purpose[ -]built rental)\b',re.I)
BUSINESS=re.compile(r'\b(industrial|warehouse|factory|manufactur\w*|distribution (?:centre|center|facility)|logistics|data cent(?:er|re)|commercial|retail|office|medical|pharmacy|clinic|restaurant|hotel|hospitality|food processing|auto(?:motive)? (?:service|repair|dealership)|dealership|self[ -]storage|shopping (?:mall|centre|center)|storefront|tenant fit[ -]?out|business licen[cs]e)\b',re.I)
ACTION=re.compile(r'\b(propos\w*|construction|construct\w*|addition|renovat\w*|alterat\w*|new building|new unit|installation|fit[ -]?out|expansion|occupancy|change of use|retrofit|permit|replacement|site service)\b',re.I)
TRADE=re.compile(r'\b(hvac|mechanical|security|fire alarm|sprinkler|elevator|electrical|plumbing|roof|chiller|boiler|access control)\b',re.I)

def read(path):
 if not path.is_file():raise FileNotFoundError('Missing opportunity export: '+str(path))
 with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def safe_url(value):
 try:
  p=urlparse(str(value or '').strip())
  return str(value).strip() if p.scheme in ('https','http') and p.hostname and not p.username and not p.password else ''
 except ValueError:return ''

def assess(r):
 d=(r.get('description') or '').strip();sid=(r.get('source_id') or '').lower()
 major=bool(MAJOR.search(d));business=bool(BUSINESS.search(d))
 exception=bool(re.search(r'\b(industrial|commercial|warehouse|office|retail|medical|restaurant|factory|manufacturing|store|clinic|mixed[ -]use)\b',d,re.I))
 if (SMALL.search(d) or HOUSE.search(d)) and not major and not exception:
  return 'EXCLUDE_SMALL_RESIDENTIAL','Small dwelling, secondary unit or home alteration'
 if sid.startswith('peel_health'):
  return 'ENRICHMENT_ONLY','Inspection/directory change is not a new business opening'
 if 'development_applications' in sid:
  return ('PLANNING_WATCH','Planning-stage record: submission date and current status unverified') if (business or major) else ('EXCLUDE_UNRELATED','No commercial-scale demand in planning record')
 if not (business or major):
  return 'EXCLUDE_UNRELATED','No identifiable commercial-scale demand'
 if 'active_building_permits' in sid or 'building_permits' in sid:
  return ('PERMIT_REVIEW','Commercial permit record; issuance and project status unverified') if (ACTION.search(d) or business and TRADE.search(d)) else ('WATCH_UNCLEAR','Unclear commercial permit activity')
 if 'licence' in sid or 'license' in sid:
  return 'BUSINESS_REVIEW','Licence status requires source confirmation'
 return 'WATCH_UNCLEAR','Commercial signal, action not established'

def priority(r,lane):
 d=(r.get('description') or '').lower()
 score={'PERMIT_REVIEW':60,'BUSINESS_REVIEW':54,'PLANNING_WATCH':20,'WATCH_UNCLEAR':12}[lane]
 if re.search(r'\b(new (?:industrial|commercial|building|construction)|industrial building|food processing operation|new restaurant|new business|tenant fit[ -]?out|medical clinic)\b',d):score+=13
 if lane=='PERMIT_REVIEW' and TRADE.search(d):score+=7
 if BUSINESS.search(d):score+=5
 if r.get('company_name'):score+=2
 if safe_url(r.get('evidence_url')):score+=4
 if r.get('source_group')=='MUNICIPAL_CHANGE':score-=6
 return max(0,min(score,85))

def transform(r,lane,reason):
 sid=r.get('source_id') or '';key=r.get('source_key') or '';address=r.get('address') or ''
 q=' '.join(x for x in ('"'+address+'"' if address else '',r.get('city') or '',key,sid.replace('_',' ')) if x)
 return dict(lane=lane,review_priority=priority(r,lane),candidate_id=r.get('opportunity_id') or sid+':'+key,
  address=address,city=r.get('city') or '',source_id=sid,source_key=key,description=r.get('description') or '',
  event_date=r.get('event_date') or '',date_basis='SOURCE/DETECTION DATE — NOT VERIFIED PERMIT ISSUE OR OPENING DATE',
  source_group=r.get('source_group') or '',company_name=r.get('company_name') or 'UNKNOWN',
  services_to_research=r.get('buyer_categories') or '',source_url=safe_url(r.get('evidence_url')),
  manual_search_url='https://www.google.com/search?q='+quote_plus(q[:220]),reason=reason,
  review_status='RESEARCH CANDIDATE ONLY — NOT VERIFIED FOR SALE')

def save(path,fields,rows):
 with path.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def html_report(rows,counts):
 e=lambda x:html.escape(str(x or ''),quote=True)
 out=['<!doctype html><html><head><meta charset="utf-8"><title>GTA Radar V3 Review</title><style>body{max-width:1150px;margin:30px auto;font:15px Segoe UI,Arial;background:#f4f6fa;color:#223;padding:0 15px}article{padding:15px;margin:14px 0;background:white;border-radius:8px}a{color:#145da2}</style></head><body>',
 '<h1>GTA Commercial Radar — V3 candidate review</h1><p>Not verified leads. Detection dates do not prove new permits. No paid AI.</p>']
 for lane in ('PERMIT_REVIEW','BUSINESS_REVIEW','PLANNING_WATCH','WATCH_UNCLEAR'):
  group=[r for r in rows if r['lane']==lane];out.append('<h2>'+e(lane)+' ('+str(len(group))+')</h2>')
  for r in group:
   out.append('<article><b>'+e(r['address'])+'</b> · '+e(r['review_priority'])+'/85 · '+e(r['source_id'])+
   '<p>'+e(r['description'])+'</p><p>Source date: '+e(r['event_date'])+' (unverified) · Reference: '+e(r['source_key'])+'</p>')
   if r['source_url']:out.append('<a href="'+e(r['source_url'])+'">Original source</a> · ')
   out.append('<a href="'+e(r['manual_search_url'])+'">Research project</a></article>')
 out.append('</body></html>');return ''.join(out)

def run(input_csv,out):
 source=read(Path(input_csv));out=Path(out);out.mkdir(parents=True,exist_ok=True)
 counts=Counter();selected=[];excluded=[];seen=set()
 for r in source:
  lane,reason=assess(r);counts[lane]+=1
  key=(r.get('source_id'),r.get('source_key'))
  if key in seen:continue
  seen.add(key)
  if lane.startswith('EXCLUDE') or lane=='ENRICHMENT_ONLY':
   excluded.append(dict(candidate_id=r.get('opportunity_id'),source_id=key[0],source_key=key[1],address=r.get('address'),description=r.get('description'),reason=reason))
  else:selected.append(transform(r,lane,reason))
 order={'PERMIT_REVIEW':0,'BUSINESS_REVIEW':1,'PLANNING_WATCH':2,'WATCH_UNCLEAR':3}
 selected.sort(key=lambda r:(order[r['lane']],-r['review_priority'],r['source_id'],r['source_key']))
 save(out/'CANDIDATES_V3_ALL_REVIEW_ONLY.csv',FIELDS,selected)
 save(out/'CANDIDATES_V3_EXCLUDED_AUDIT.csv',EXCLUDE_FIELDS,excluded)
 save(out/'CANDIDATES_V3_COUNTS.csv',['category','count'],[dict(category=k,count=v) for k,v in sorted(counts.items())])
 (out/'commercial_candidates_v3.html').write_text(html_report(selected,counts),encoding='utf-8')
 print('V3 audited:',len(source),'source rows;',len(selected),'candidates;',len(excluded),'excluded/enrichment;',len(seen),'unique source keys')
 print('Report:',out/'commercial_candidates_v3.html')
 return selected

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parent/'data');p.add_argument('--input',type=Path)
 a=p.parse_args();run(a.input or a.data_dir/'opportunities_ALL_REVIEW_ONLY.csv',a.data_dir)
