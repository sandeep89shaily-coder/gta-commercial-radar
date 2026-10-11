"""Brampton official-source archive: additive, source-faithful, no guessed business links.
Run via python brampton_network.py. Never modifies Radar's original radar.sqlite.
"""
import csv,hashlib,html,json,re,sqlite3,time,sys,os,random,argparse
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'; DB=DATA/'brampton_sources.sqlite'
BASE='https://maps1.brampton.ca/arcgis/rest/services/BuildingPermit/Building_Permits/FeatureServer'
LIC='https://www.brampton.ca/EN/Business/Licensing/Pages/'
SOURCES=[
('brampton_permit_activity','Building','Permit process activities',BASE+'/1','arcgis','daily'),
('brampton_upcoming_inspections','Building','Upcoming permit inspections',BASE+'/2','arcgis','daily'),
('brampton_food_licences_structured','Licensing','Licensed fixed food premises',LIC+'Licensed-Fixed-Food-Premises.aspx','html_table','weekly'),
('brampton_stationary_licensing_directory','Licensing','Stationary licensed-business directory',LIC+'Stationary-Licensing.aspx','discovery','weekly'),
('brampton_planning','Planning','Planning applications','https://www.brampton.ca/EN/Business/planning-development/','discovery','weekly'),
('brampton_council','City Clerk','Agendas and minutes','https://www.brampton.ca/EN/City-Hall/Council-Committees/meetings-agendas/','discovery','weekly'),
('brampton_roads','Public Works','Road construction projects','https://www.brampton.ca/EN/residents/Roads-and-Traffic/pages/construction-projects.aspx','discovery','weekly'),
]
# Brampton expansion: official published licence lists and public roadworks layers.
# Each category is separate so failures and incompleteness stay visible.
LICENCE_CATEGORIES = [
 'Licensed-Animal-Kennels-Doggie-Daycare', 'Licensed-Auto-Service-Stations',
 'Licensed-Building-Renovators','Licensed-Caterers','Licensed-Driveway-Contractors',
 'Licensed-Fence-Installation-Contractors','Licensed-HVAC-Contractors',
 'Licensed-Payday-Loans','Licensed-Pawnbrokers','Licensed-Pet-Grooming',
 'Licensed-Pet-Shops','Licensed-Personal-Services','Licensed-Places-of-Amusement',
 'Licensed-Places-of-Public-Assembly','Licensed-Plumbing-Contractors',
 'Licensed-Pool-Contractors','Licensed-Salvage-Yards-Salvage-Shops',
 'Licensed-Second-Hand-Goods','Licensed-Wildlife-Removal',
 'Licensed-Horse-Riding-Establishments',
]
for slug in LICENCE_CATEGORIES:
 SOURCES.append(('brampton_lic_'+('licensed-animal-kennels-or-doggie-daycare' if slug=='Licensed-Animal-Kennels-Doggie-Daycare' else slug).lower().replace('-','_'),'Licensing',slug.replace('-',' '),(LIC+'Licensed-Contractors-HVAC.aspx' if slug=='Licensed-HVAC-Contractors' else LIC+slug+'.aspx'),'html_table_extended','weekly'))
ROAD='https://maps1.brampton.ca/arcgis/rest/services/Roadworks/RoadClosuresAndConstruction/FeatureServer'
for layer,name in [(0,'Road construction projects'),(1,'Active road closures'),(2,'Upcoming road closures'),(3,'All road projects'),(4,'All road closures')]:
 SOURCES.append((f'brampton_roadworks_{layer}','Public Works',name,ROAD+'/'+str(layer),'arcgis_small','weekly'))
MONITOR_SOURCES=[
 ('brampton_council_agendas_content','City Clerk','Council agendas and linked reports','https://www1.brampton.ca/EN/City-Hall/Council-Committees/meetings-agendas/'),
 ('brampton_council_agenda_rules','City Clerk','Agenda publication rules','https://www.brampton.ca/EN/City-Hall/Council-Committees/meetings-agendas/Pages/General-Information.aspx'),
 ('brampton_planning_content','Planning','Planning and development announcements','https://www.brampton.ca/EN/Business/planning-development/'),
 ('brampton_construction_content','Public Works','Construction project announcements','https://www.brampton.ca/EN/residents/Roads-and-Traffic/pages/construction-projects.aspx'),
 ('brampton_stationary_licensing_content','Licensing','Stationary licensing news and categories','https://www.brampton.ca/EN/Business/Licensing/Pages/Stationary-Licensing.aspx'),
 ('brampton_mobile_licensing_content','Licensing','Mobile licensing announcements','https://www.brampton.ca/EN/Business/Licensing/Pages/Mobile-Licensing.aspx'),
 ('brampton_procurement_content','Procurement','Brampton procurement public page','https://www.brampton.ca/EN/Business/purchasing/Pages/welcome.aspx'),
 ('brampton_economic_content','Economic Development','Business and investment public page','https://investbrampton.ca/'),
 ('brampton_budget_content','Finance','City budget and capital planning','https://www.brampton.ca/EN/City-Hall/Budget/Pages/Welcome.aspx'),
]
for sid,dept,title,url in MONITOR_SOURCES:
 SOURCES.append((sid,dept,title,url,'content_monitor','weekly'))
UA={'User-Agent':'GTACommercialRadar/1.0 (+official public-source collection; respectful rate-limited access)'}
# Resolve category paths from official Brampton navigation, never guess off-domain links.
LICENSING_INDEX='https://www.brampton.ca/EN/Business/Licensing/Pages/welcome.aspx'
def resolve_licence_urls(session):
 response=get(session,LICENSING_INDEX,timeout=(8,25),attempts=2)
 soup=BeautifulSoup(response.text,'html.parser')
 from urllib.parse import urlsplit
 def key(t):return re.sub(r'[^a-z0-9]','',str(t or '').lower()).replace('or','')
 official={}
 for a in soup.find_all('a',href=True):
  href=urljoin(response.url,a['href'])
  parts=urlsplit(href)
  if parts.scheme!='https' or parts.hostname not in ('www.brampton.ca','www1.brampton.ca'):continue
  if '/business/licensing/pages/' not in parts.path.lower():continue
  label=a.get_text(' ',strip=True)
  if not label.lower().startswith('licensed '):continue
  normalized=key(label)
  if normalized and normalized not in official:official[normalized]=href.split('?')[0]
 return official

def utc():return datetime.now(timezone.utc).isoformat()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
def setup(con):
 con.executescript('''CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,department TEXT,title TEXT,url TEXT,adapter TEXT,frequency TEXT,access_status TEXT DEFAULT 'candidate',last_checked TEXT,notes TEXT);
 CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY,source_id TEXT,started TEXT,ended TEXT,status TEXT,seen INTEGER DEFAULT 0,created INTEGER DEFAULT 0,changed INTEGER DEFAULT 0,detail TEXT);
 CREATE TABLE IF NOT EXISTS records(source_id TEXT,record_id TEXT,first_seen TEXT,last_seen TEXT,hash TEXT,json TEXT,PRIMARY KEY(source_id,record_id));
 CREATE TABLE IF NOT EXISTS versions(id INTEGER PRIMARY KEY,source_id TEXT,record_id TEXT,observed_at TEXT,hash TEXT,json TEXT,UNIQUE(source_id,record_id,hash));
 CREATE INDEX IF NOT EXISTS ix_ver_src ON versions(source_id,observed_at);
 CREATE TABLE IF NOT EXISTS arcgis_progress(source_id TEXT PRIMARY KEY,last_oid INTEGER NOT NULL DEFAULT -1,total_estimate INTEGER,backfilled INTEGER NOT NULL DEFAULT 0,updated_at TEXT,notes TEXT);
 CREATE TABLE IF NOT EXISTS discoveries(id INTEGER PRIMARY KEY,source_id TEXT,url TEXT,anchor TEXT,first_seen TEXT,last_seen TEXT,UNIQUE(source_id,url));''')
 for sid,dept,title,url,adapter,freq in SOURCES:
  con.execute('INSERT OR IGNORE INTO sources(id,department,title,url,adapter,frequency) VALUES(?,?,?,?,?,?)',(sid,dept,title,url,adapter,freq))
 con.commit()
def put(con,sid,key,obj,stamp):
 j=json.dumps(obj,sort_keys=True,ensure_ascii=False,default=str); h=digest(obj)
 old=con.execute('SELECT hash FROM records WHERE source_id=? AND record_id=?',(sid,key)).fetchone()
 if old and old[0]==h:
  con.execute('UPDATE records SET last_seen=? WHERE source_id=? AND record_id=?',(stamp,sid,key));return 0,0
 con.execute('INSERT OR IGNORE INTO versions(source_id,record_id,observed_at,hash,json) VALUES(?,?,?,?,?)',(sid,key,stamp,h,j))
 con.execute('INSERT INTO records(source_id,record_id,first_seen,last_seen,hash,json) VALUES(?,?,?,?,?,?) ON CONFLICT(source_id,record_id) DO UPDATE SET last_seen=excluded.last_seen,hash=excluded.hash,json=excluded.json',(sid,key,stamp,stamp,h,j))
 return (1,0) if not old else (0,1)
def get(session,url,params=None,timeout=(10,25),attempts=3):
 last=None
 for i in range(attempts):
  try:
   r=session.get(url,params=params,headers=UA,timeout=timeout)
   if r.status_code in (429,500,502,503,504):
    r.raise_for_status()
   r.raise_for_status();return r
  except (requests.exceptions.Timeout,requests.exceptions.ConnectionError,requests.exceptions.HTTPError) as exc:
   last=exc
   if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None and exc.response.status_code not in (429,500,502,503,504):raise
   if i+1<attempts:time.sleep(min(2**i,4)+random.uniform(0,.2))
 raise last

def arcgis(con,session,sid,url,stamp,limit=None):
 # Keyset pagination: a persisted cursor means every run CONTINUES, rather than restarting at OBJECTID 1.
 # Never infer deleted records from a partial scan. Only move cursor in the same transaction as page inserts.
 limit=int(limit if limit is not None else os.getenv('BRAMPTON_ARCGIS_ROWS_PER_RUN','10000'))
 limit=max(1,min(limit,100000))
 meta=get(session,url,{'f':'json'},timeout=(8,15),attempts=2).json()
 if 'error' in meta:raise ValueError(str(meta['error']))
 oid=meta.get('objectIdField') or next((f['name'] for f in meta.get('fields',[]) if f.get('type')=='esriFieldTypeOID'),None)
 if not oid or not re.fullmatch(r'[A-Za-z][A-Za-z_0-9]*',oid):raise ValueError('No safe stable object ID')
 qurl=url+'/query'
 count=get(session,qurl,{'where':'1=1','returnCountOnly':'true','f':'json'},timeout=(8,20),attempts=2).json()
 if 'error' in count:raise ValueError(str(count['error']))
 total=int(count['count'])
 row=con.execute('SELECT last_oid,backfilled FROM arcgis_progress WHERE source_id=?',(sid,)).fetchone()
 cursor=int(row[0]) if row else -1
 # Restart only AFTER a complete baseline has been scanned, to spot changed rows.
 # Refresh is bounded and resumes across runs as well; no removal inference.
 restarting=bool(row and row[1])
 if restarting:cursor=-1
 page=min(int(meta.get('maxRecordCount') or 1000),25 if 'inspections' in sid else 500)
 seen=created=changed=0; end=False; max_oid=cursor
 while seen<limit:
  args={'where':f'{oid} > {cursor}','outFields':'*','returnGeometry':'false','orderByFields':f'{oid} ASC','resultRecordCount':min(page,limit-seen),'f':'json'}
  body=get(session,qurl,args,timeout=(10,60) if 'inspections' in sid else (8,30),attempts=4 if 'inspections' in sid else 3).json()
  if 'error' in body:raise ValueError(str(body['error']))
  batch=body.get('features') or []
  if not batch:end=True;break
  for f in batch:
   attrs=f.get('attributes') or {}
   number=attrs.get(oid)
   if number is None or int(number)<=cursor:raise ValueError('Non-increasing or missing OBJECTID')
   cursor=int(number)
   a,b=put(con,sid,str(number),attrs,stamp);created+=a;changed+=b;seen+=1
  # Atomic page write and checkpoint; interruption never skips records.
  con.execute('INSERT INTO arcgis_progress(source_id,last_oid,total_estimate,backfilled,updated_at,notes) VALUES(?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET last_oid=excluded.last_oid,total_estimate=excluded.total_estimate,backfilled=excluded.backfilled,updated_at=excluded.updated_at,notes=excluded.notes',(sid,cursor,total,0,utc(),'backfill in progress'))
  con.commit()
  if len(batch)<args['resultRecordCount']:end=True;break
  time.sleep(.15)
 if end:
  con.execute('UPDATE arcgis_progress SET backfilled=1,notes=?,updated_at=? WHERE source_id=?',('full ID-range scanned; next run refreshes changed records',utc(),sid));con.commit()
 return ('OK' if end else 'PARTIAL'),seen,created,changed,f'{seen} in this run; source has ~{total} rows; checkpoint {oid}={cursor}; '+('full pass complete' if end else 'resumes next run')+'; no removals inferred'

def arcgis_small_by_ids(con,session,sid,url,stamp,limit=1000):
 # Small public layers can expose duplicate/missing OBJECTID attributes in features.
 # Query an explicit ID list and retrieve each ID with objectIds; only checkpoint
 # identifiers we actually received. Never infer removals from an incomplete read.
 meta=get(session,url,{'f':'json'},timeout=(10,25)).json()
 if 'error' in meta:raise ValueError(str(meta['error']))
 oid=meta.get('objectIdField') or next((f.get('name') for f in meta.get('fields',[]) if f.get('type')=='esriFieldTypeOID'),None)
 if not oid:raise ValueError('No official ArcGIS object ID field')
 qurl=url+'/query'
 index=get(session,qurl,{'where':'1=1','returnIdsOnly':'true','f':'json'},timeout=(10,40)).json()
 if 'error' in index:raise ValueError(str(index['error']))
 ids=sorted(set(int(x) for x in (index.get('objectIds') or [])))
 previous=con.execute('SELECT last_oid,backfilled FROM arcgis_progress WHERE source_id=?',(sid,)).fetchone()
 cursor=(-1 if previous and previous[1] else int(previous[0]) if previous else -1)
 pending=[x for x in ids if x>cursor][:max(1,limit)]
 seen=created=changed=0
 batch_size=max(1,min(50,int(meta.get('maxRecordCount') or 50)))
 for pos in range(0,len(pending),batch_size):
  chunk=pending[pos:pos+batch_size]
  body=get(session,qurl,{'objectIds':','.join(map(str,chunk)),'outFields':'*','returnGeometry':'false','f':'json'},timeout=(12,45)).json()
  if 'error' in body:raise ValueError(str(body['error']))
  keyed={}
  for ft in body.get('features') or []:
   attrs=ft.get('attributes') or {}
   val=attrs.get(oid)
   if val is not None and str(val).lstrip('-').isdigit():keyed[int(val)]=attrs
  if set(chunk)-set(keyed):raise ValueError('ArcGIS incomplete ID response; checkpoint unchanged for current page')
  for number in chunk:
   a,b=put(con,sid,str(number),keyed[number],stamp)
   seen+=1;created+=a;changed+=b
  cursor=chunk[-1]
  con.execute('INSERT INTO arcgis_progress(source_id,last_oid,total_estimate,backfilled,updated_at,notes) VALUES(?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET last_oid=excluded.last_oid,total_estimate=excluded.total_estimate,backfilled=excluded.backfilled,updated_at=excluded.updated_at,notes=excluded.notes',(sid,cursor,len(ids),0,utc(),'ID-list checkpoint'))
  con.commit()
  time.sleep(.2)
 complete=(not pending or cursor>=ids[-1] if ids else True)
 if complete:
  con.execute('INSERT INTO arcgis_progress(source_id,last_oid,total_estimate,backfilled,updated_at,notes) VALUES(?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET last_oid=excluded.last_oid,total_estimate=excluded.total_estimate,backfilled=excluded.backfilled,updated_at=excluded.updated_at,notes=excluded.notes',(sid,cursor,len(ids),1,utc(),'ID-list full pass completed'))
  con.commit()
 return ('OK' if complete else 'PARTIAL'),seen,created,changed,f'{seen} records retrieved by explicit IDs; source has {len(ids)} IDs; checkpoint={cursor}; no removals inferred'

LIC_FIELDS=['organization_name','operating_name','business_address','expiry_date','file_number']
LIC_HEADERS=('organization name','contractor operating name','business address','expiry date','file number')
def parse_licence_table(table):
 """Reject malformed rows, rather than putting a combined header into the database."""
 rows=[]
 for tr in table.find_all('tr'):
  cells=[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'],recursive=False)]
  if cells:rows.append(cells)
 if not rows:return []
 header_index=next((i for i,row in enumerate(rows) if all(x in ' '.join(row).lower() for x in ('organization name','file number'))),None)
 if header_index is None:return []
 header=rows[header_index]
 # Some Brampton pages display a single header cell containing all labels.
 results=[]
 for cells in rows[header_index+1:]:
  if len(cells)!=5:continue
  company,operating,address,expires,file_no=[re.sub(r'\s+',' ',c).strip() for c in cells]
  if not file_no or not address or not re.search(r'\d',address):continue
  results.append(dict(zip(LIC_FIELDS,(company,operating,address,expires,file_no))))
 return results

def webtable(con,session,sid,url,stamp):
 resp=get(session,url,timeout=(10,35));soup=BeautifulSoup(resp.text,'html.parser')
 found=[]
 for table in soup.find_all('table'):
  parsed=parse_licence_table(table)
  if len(parsed)>len(found):found=parsed
 if not found:raise ValueError('Could not find valid 5-column licence rows; saved records unchanged')
 seen=created=changed=0
 for fields in found:
  obj={'fields':fields,'source_url':url}
  key=fields['file_number']
  a,b=put(con,sid,key,obj,stamp);created+=a;changed+=b;seen+=1
 con.commit()
 # Many pages use DataTables with only a subset of total rows in initial HTML.
 # Do not claim full coverage without verified pagination/server data source.
 return 'PARTIAL',seen,created,changed,f'{seen} correctly split licence rows (5 fields); pagination not yet proved exhaustive; no removals inferred'
def parse_extended_table(table):
 """Use actual DOM header positions; do not presume every licence list shares a schema."""
 trs=table.find_all('tr')
 header=None; parsed=[]
 for i,tr in enumerate(trs):
  cells=tr.find_all(['th','td'],recursive=False)
  labels=[re.sub(r'\s+',' ',x.get_text(' ',strip=True)).strip().lower() for x in cells]
  if any('organization name' in x for x in labels) and any('file number' in x for x in labels):
   header=(i,labels);break
 if header is None:return []
 idx,labels=header
 keys=[]
 for label in labels:
  if 'file number' in label:keys.append('file_number')
  elif 'organization name' in label:keys.append('organization_name')
  elif 'contractor operating name' in label or 'operating name' in label:keys.append('operating_name')
  elif 'business address' in label:keys.append('business_address')
  elif 'expiry date' in label:keys.append('expiry_date')
  elif 'classification' in label:keys.append('classification')
  else:keys.append('other')
 if 'file_number' not in keys:return []
 for tr in trs[idx+1:]:
  cells=tr.find_all('td',recursive=False)
  if len(cells)!=len(keys):continue
  values=[re.sub(r'\s+',' ',c.get_text(' ',strip=True)).strip() for c in cells]
  obj={k:v for k,v in zip(keys,values) if k!='other'}
  if obj.get('file_number') and (obj.get('organization_name') or obj.get('operating_name')):parsed.append(obj)
 return parsed

def webtable_extended(con,session,sid,url,stamp):
 """Bounded SharePoint next-page traversal; PARTIAL unless exhaustiveness is clear."""
 seen=created=changed=0;next_url=url;visited=set();pages=0;cap=20;repeated=False;fingerprints=set()
 while next_url and next_url not in visited and pages<cap:
  visited.add(next_url)
  response=get(session,next_url,timeout=(8,30),attempts=2)
  soup=BeautifulSoup(response.text,'html.parser')
  candidates=[parse_extended_table(t) for t in soup.find_all('table')]
  batch=max(candidates,key=len,default=[])
  if not batch:
   if pages==0:raise ValueError('No well-structured licence rows found; nothing modified')
   break
  fingerprint=digest([row.get('file_number') for row in batch])
  if fingerprint in fingerprints:
   repeated=True;break
  fingerprints.add(fingerprint)
  for fields in batch:
   key=fields['file_number']
   a,b=put(con,sid,key,{'fields':fields,'source_url':response.url},stamp)
   created+=a;changed+=b;seen+=1
  con.commit();pages+=1
  # Only follow explicit navigation links. Never fabricate server page tokens.
  nxt=None
  for anchor in soup.find_all('a',href=True):
   title=' '.join((anchor.get_text(' ',strip=True),anchor.get('title',''),anchor.get('aria-label',''), ' '.join(anchor.get('rel',[])))).lower()
   href=anchor['href']
   backward='pagedprev' in href.lower() or 'previous' in title or 'prev' in title
   forward=('next' in title or 'pagefirstrow' in href.lower() and 'paged=true' in href.lower())
   if not forward or backward:continue
   target=urljoin(response.url,href)
   from urllib.parse import urlsplit
   parsed=urlsplit(target)
   if parsed.scheme=='https' and parsed.hostname in ('www.brampton.ca','www1.brampton.ca') and target not in visited:
    nxt=target;break
  next_url=nxt
  if nxt:time.sleep(.3)
 status='PARTIAL' if next_url or pages==1 else 'PARTIAL'
 return status,seen,created,changed,f'{seen} parsed rows across {pages} pages; repeated_page={repeated}; completeness not established; no removals inferred'

def content_monitor(con,session,sid,url,stamp):
 """Archive page text, linked-document metadata, and bounded public PDF text.

 PDFs remain source-specific documents; failure to extract leaves an auditable
 link entry and a PARTIAL status, not an invented document or silent success.
 """
 from urllib.parse import urlsplit
 from io import BytesIO
 response=get(session,url,timeout=(8,25),attempts=2)
 soup=BeautifulSoup(response.text,'html.parser')
 for node in soup(['script','style','nav','footer','header']):node.decompose()
 main=soup.find('main') or soup.find(id='content') or soup.body or soup
 page_text=re.sub(r'\s+',' ',main.get_text(' ',strip=True))[:250000]
 if len(page_text)<50:raise ValueError('Little public text, likely JS-only content; not a structured feed')
 created=changed=0
 a,b=put(con,sid,'PAGE',{'url':response.url,'text':page_text},stamp);created+=a;changed+=b
 links=[];pdf_links=[];errors=[]
 allowed={'www.brampton.ca','www1.brampton.ca','brampton.ca','pub-brampton.escribemeetings.com'}
 for anchor in main.find_all('a',href=True):
  link=urljoin(response.url,anchor['href'].strip())
  parts=urlsplit(link)
  if parts.scheme!='https' or parts.hostname not in allowed:continue
  if any(x in link.lower() for x in ('login.aspx','signin','logout')):continue
  title=anchor.get_text(' ',strip=True)[:250]
  if not title:continue
  is_pdf=parts.path.lower().endswith('.pdf')
  if not (is_pdf or parts.path.lower().endswith(('.doc','.docx','.xlsx','.csv')) or any(x in title.lower() for x in ('agenda','minutes','report','project','contract','tender','budget','application','plan','notice'))):continue
  links.append((link,title))
  aa,bb=put(con,sid,'LINK:'+digest(link),{'url':link,'label':title,'parent_url':response.url},stamp)
  created+=aa;changed+=bb
  if is_pdf:pdf_links.append((link,title))
 con.commit()
 # Bound document downloads to keep ordinary daily jobs predictable.
 max_docs=max(0,min(8,int(os.getenv('BRAMPTON_PDFS_PER_SOURCE','3'))))
 for link,title in pdf_links[:max_docs]:
  try:
   doc=get(session,link,timeout=(8,30),attempts=2)
   data=doc.content
   if len(data)>8*1024*1024:raise ValueError('Document above safe 8 MiB bound')
   if not data.startswith(b'%PDF-'):raise ValueError('Not a PDF response')
   from pypdf import PdfReader
   reader=PdfReader(BytesIO(data))
   if len(reader.pages)>120:raise ValueError('Document above safe 120-page bound')
   extracted=' '.join((page.extract_text() or '') for page in reader.pages)
   extracted=re.sub(r'\\s+',' ',extracted).strip()[:200000]
   if not extracted:raise ValueError('No extractable PDF text (possibly scanned)')
   aa,bb=put(con,sid,'DOCUMENT:'+digest(link),{'url':link,'label':title,'parent_url':response.url,'text':extracted,'pages':len(reader.pages),'sha256':hashlib.sha256(data).hexdigest()},stamp)
   created+=aa;changed+=bb
  except Exception as exc:
   errors.append(title[:60]+': '+str(exc)[:100])
 con.commit()
 partial=bool(errors or len(pdf_links)>max_docs)
 status='PARTIAL' if partial else 'MONITOR'
 return status,len(links)+1,created,changed,f'{len(links)} links; {min(max_docs,len(pdf_links))-len(errors)} PDFs text-extracted; {len(errors)} PDF failures; {max(0,len(pdf_links)-max_docs)} deferred; no removals inferred'+('; '+errors[0] if errors else '')

def discover(con,session,sid,url,stamp):
 response=get(session,url);soup=BeautifulSoup(response.text,'html.parser');count=0
 for a in soup.find_all('a',href=True):
  full=urljoin(response.url,a['href'].strip());label=a.get_text(' ',strip=True)[:180]
  if not full.startswith(('https://www.brampton.ca/','https://www1.brampton.ca/','https://geohub.brampton.ca/')):continue
  if not label:continue
  con.execute('INSERT INTO discoveries(source_id,url,anchor,first_seen,last_seen) VALUES(?,?,?,?,?) ON CONFLICT(source_id,url) DO UPDATE SET anchor=excluded.anchor,last_seen=excluded.last_seen',(sid,full,label,stamp,stamp));count+=1
 con.commit();return 'DISCOVERY',count,0,0,'Public page links indexed for manual source qualification; no bulk data inferred'
def report(con):
 dest=DATA/'brampton_collection_report.html'
 css='body{font:15px Segoe UI,Arial;max-width:1150px;margin:35px auto;color:#243246}table{border-collapse:collapse;width:100%}td,th{padding:9px;text-align:left;border-bottom:1px solid #ddd}small{color:#555}'
 parts=['<!doctype html><meta charset="utf-8"><title>Brampton Source Audit</title><style>'+css+'</style><h1>Brampton — Department Source Collection</h1><p>Separate, additive source archive. PARTIAL means limited webpage rows or capped API retrieval. Baselines are not fresh events. No deletions inferred.</p><table><tr><th>Department</th><th>Source</th><th>Status</th><th>Stored records</th><th>Latest change</th><th>Details</th></tr>']
 for dept,title,sid,url,status,count,detail in con.execute('''SELECT s.department,s.title,s.id,s.url,COALESCE(r.status,'NOT RUN'),(SELECT COUNT(*) FROM records WHERE source_id=s.id),COALESCE(r.detail,'') FROM sources s LEFT JOIN runs r ON r.id=(SELECT MAX(id) FROM runs WHERE source_id=s.id) ORDER BY s.department,s.id'''):
  parts.append('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in (dept,title,status,count,detail[:240]))+'</tr>')
 parts.append('</table><p>Source discovery links are stored in brampton_sources.sqlite. Existing Radar databases are unchanged.</p>')
 dest.write_text(''.join(parts),encoding='utf-8');return dest
def main(argv=None):
 parser=argparse.ArgumentParser(description='Collect Brampton government data')
 parser.add_argument('--activities-only',action='store_true',help='Only resume permit-activity backfill')
 parser.add_argument('--activity-limit',type=int,default=10000,help='Maximum activity rows in this run (up to 50000)')
 args=parser.parse_args(argv)
 DATA.mkdir(exist_ok=True);con=sqlite3.connect(DB);setup(con);session=requests.Session()
 try:official_licences=resolve_licence_urls(session)
 except Exception as exc:
  print('Licensing navigation discovery unavailable; using configured URLs:',str(exc)[:150],flush=True)
  official_licences={}

 for sid,dept,title,url,adapter,freq in SOURCES:
  if args.activities_only and sid!='brampton_permit_activity':continue
  if adapter=='html_table_extended':
   lookup=re.sub(r'[^a-z0-9]','',title.lower()).replace('or','')
   resolved=official_licences.get(lookup)
   if resolved and resolved!=url:
    url=resolved
    con.execute('UPDATE sources SET url=? WHERE id=?',(url,sid));con.commit()
  stamp=utc();cur=con.execute('INSERT INTO runs(source_id,started,status) VALUES(?,?,?)',(sid,stamp,'RUNNING'));rid=cur.lastrowid;con.commit()
  print(f'Brampton: {title} ...',flush=True)
  try:
   if adapter=='arcgis_small':status,n,a,b,detail=arcgis_small_by_ids(con,session,sid,url,stamp)
   elif adapter=='arcgis':status,n,a,b,detail=arcgis(con,session,sid,url,stamp,limit=75 if 'inspections' in sid else (min(50000,max(1,args.activity_limit)) if sid=='brampton_permit_activity' else None))
   elif adapter=='html_table':status,n,a,b,detail=webtable(con,session,sid,url,stamp)
   elif adapter=='html_table_extended':status,n,a,b,detail=webtable_extended(con,session,sid,url,stamp)
   elif adapter=='content_monitor':status,n,a,b,detail=content_monitor(con,session,sid,url,stamp)
   else:status,n,a,b,detail=discover(con,session,sid,url,stamp)
  except Exception as e:status,n,a,b,detail='ERROR',0,0,0,str(e)[:400]
  con.execute('UPDATE runs SET ended=?,status=?,seen=?,created=?,changed=?,detail=? WHERE id=?',(utc(),status,n,a,b,detail,rid))
  con.execute('UPDATE sources SET access_status=?,last_checked=?,notes=? WHERE id=?',(status,utc(),detail,sid));con.commit()
  print(f'  {status}: seen={n} first_seen={a} updated={b} {detail}',flush=True)
 result=report(con);con.close();print('Brampton report:',result)
 return 0
if __name__=='__main__':sys.exit(main())
