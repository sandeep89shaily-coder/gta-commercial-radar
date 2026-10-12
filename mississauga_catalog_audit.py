"""Weekly Mississauga ArcGIS Hub OGC Records inventory (metadata only).

The City publishes a public /api/search/v1/collections endpoint. This module
discovers each public collection and follows server-provided OGC next links.
It NEVER downloads the underlying permit/property records, calls restricted
portals, assumes source-date metadata is accurate, or enables unverified feeds.
"""
from __future__ import annotations
import csv, io, json, re, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from toronto_catalog_audit import due

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
BASE='https://data.mississauga.ca'
START=BASE+'/api/search/v1/collections'
MAX_COLLECTIONS=30
MAX_PAGES=300
MAX_ITEMS=20000
FAMILIES=(
 ('construction_development',r'building permit|construction|development application|site plan|rezoning|zoning|subdivision|planning|growth management'),
 ('procurement_finance',r'procurement|tender|contract|purchasing|budget|capital spending|award'),
 ('business_licensing',r'business licen|establishment|inspection|food premise|business directory'),
 ('infrastructure_transport',r'road work|road closure|construction project|transportation|traffic|watermain|stormwater|bridge'),
 ('land_property',r'property|parcel|address point|land use|industrial land|employment lands'),
 ('council_governance',r'council|committee|agenda|by.law|decision'),
)
def classify(title,description):
 text=(str(title or '')+' '+str(description or '')).lower()
 return [family for family,rx in FAMILIES if re.search(rx,text)]

def allowed(url):
 p=urlparse(url)
 return p.scheme=='https' and p.hostname=='data.mississauga.ca' and not p.username and not p.password and p.path.startswith('/api/search/v1/collections')

def next_link(payload,current):
 for link in payload.get('links') or []:
  if isinstance(link,dict) and str(link.get('rel','')).lower()=='next':
   target=urljoin(current,str(link.get('href') or ''))
   if not allowed(target):raise ValueError('Out-of-scope OGC pagination URL')
   return target
 return None

def page_json(session,url,params=None):
 if not allowed(url):raise ValueError('Unexpected Mississauga catalogue URL')
 response=session.get(url,params=params,timeout=(10,60))
 response.raise_for_status()
 payload=response.json()
 if not isinstance(payload,dict):raise ValueError('Mississauga OGC returned non-object JSON')
 return payload

def crawl_pages(session,url,kind):
 current=url
 visited=set()
 out=[]
 count=0
 while current:
  if current in visited:raise ValueError('OGC pagination loop detected')
  visited.add(current);count+=1
  if count>MAX_PAGES:raise ValueError('OGC pagination exceeded safety budget')
  payload=page_json(session,current,{'limit':100} if count==1 and kind=='features' else None)
  key='features' if kind=='features' else 'collections'
  batch=payload.get(key)
  if not isinstance(batch,list):raise ValueError('OGC '+key+' was not a list')
  out.extend(batch)
  if len(out)>MAX_ITEMS:raise ValueError('OGC catalogue exceeded item safety budget')
  nxt=next_link(payload,current)
  if not nxt and kind=='features' and isinstance(payload.get('numberMatched'),int) and len(out)<payload['numberMatched']:
   raise ValueError('Incomplete OGC catalogue: page continuation missing')
  if not nxt and kind=='collections' and isinstance(payload.get('numberMatched'),int) and len(out)<payload['numberMatched']:
   raise ValueError('Incomplete OGC collections list')
  current=nxt
 return out

def inventory(session=None):
 session=session or requests.Session()
 collections=crawl_pages(session,START,'collections')
 if len(collections)>MAX_COLLECTIONS:raise ValueError('Too many OGC collections; refusing partial scan')
 if not collections:raise ValueError('No Mississauga catalogue collections returned')
 items={}
 for collection in collections:
  cid=str(collection.get('id') or '') if isinstance(collection,dict) else ''
  if not re.fullmatch(r'[a-zA-Z0-9_-]+',cid):raise ValueError('Invalid OGC collection id')
  endpoint=START+'/'+cid+'/items'
  # Every advertised collection is examined, not only a hard-coded "datasets"
  # collection. Duplicate items across collections are merged by stable ID.
  for feature in crawl_pages(session,endpoint,'features'):
   if not isinstance(feature,dict):continue
   props=feature.get('properties') or {}
   if not isinstance(props,dict):props={}
   ident=str(feature.get('id') or props.get('id') or '')
   if not ident:raise ValueError('OGC record has no stable identity')
   title=str(props.get('title') or props.get('name') or '')
   summary=str(props.get('description') or props.get('snippet') or '')[:1600]
   links=feature.get('links') or []
   references=[str(v.get('href')) for v in links if isinstance(v,dict) and
               str(v.get('href') or '').startswith('https://')]
   tags=props.get('keywords') or props.get('tags') or []
   if isinstance(tags,list):
    tags=', '.join(str(x)[:100] for x in tags[:20])
   row={'item_id':ident,'title':title,'description':summary,'collections':[cid],
        'item_type':str(props.get('type') or ''),'publisher':str(props.get('owner') or props.get('publisher') or ''),
        'created':str(props.get('created') or ''),'modified':str(props.get('modified') or ''),
        'tags':str(tags)[:800],'links':references[:12],
        'priority_families':classify(title,summary)}
   if ident in items:
    existing=items[ident]
    if existing['title']!=title:raise ValueError('Duplicate item ID has conflicting titles')
    if cid not in existing['collections']:existing['collections'].append(cid)
   else:
    items[ident]=row
   if len(items)>MAX_ITEMS:raise ValueError('Mississauga catalogue exceeded item safety budget')
 return list(items.values()),[str(c['id']) for c in collections]

def compare_existing(rows,configured):
 """Exact ArcGIS URL IDs only; a similar title is never proof of collection."""
 for row in rows:
  # Exact ArcGIS item ID may appear as an item link. That is discovery evidence,
  # NOT proof of the corresponding feature layer or active successful poll.
  linked=' '.join(row['links'])
  matches=[]
  for item in configured:
   if str(item.get('jurisdiction') or '').lower()!='mississauga':continue
   item_id=str(item.get('arcgis_item_id') or '')
   if item_id and (row['item_id']==item_id or item_id in linked):
    matches.append(item['id'])
  row['configured_exact_ids']=','.join(sorted(matches))
  row['coverage_state']='EXACT_ID_CONFIGURED' if matches else 'NOT_ID_VERIFIED'
 return rows

def run(force=False):
 DATA.mkdir(exist_ok=True)
 current=DATA/'mississauga_catalog_inventory.json'
 if not force and not due(current):
  print('Mississauga catalogue scan: weekly inventory still current')
  return
 items, collections=inventory()
 sources=json.loads((ROOT/'config'/'sources.json').read_text(encoding='utf-8'))
 items=compare_existing(items,sources)
 observed=datetime.now(timezone.utc).isoformat()
 result={'observed_at':observed,'item_count':len(items),'collection_ids':collections,
         'commercial_candidates':sum(bool(x['priority_families']) for x in items),
         'note':'OGC catalogue discovery only. City warns some data modification dates are inaccurate. No live dataset/schema or reuse rights confirmed.',
         'items':items}
 fields=['item_id','title','item_type','publisher','created','modified','tags',
         'priority_families','collections','configured_exact_ids','coverage_state','links']
 stream=io.StringIO();w=csv.DictWriter(stream,fieldnames=fields);w.writeheader()
 for item in items:w.writerow({k:','.join(str(value) for value in item.get(k,[])) if isinstance(item.get(k),list) else item.get(k,'') for k in fields})
 for name,content in [('mississauga_catalog_inventory.json',json.dumps(result,indent=2,ensure_ascii=False)),
                      ('mississauga_catalog_inventory.csv',stream.getvalue())]:
  path=DATA/name;temp=path.with_suffix(path.suffix+'.tmp')
  temp.write_text(content,encoding='utf-8');temp.replace(path)
 print('Mississauga open-data catalogue:',len(items),'items in',len(collections),'collections;',
       result['commercial_candidates'],'commercial source candidates')
if __name__=='__main__':run(force='--force' in sys.argv[1:])
