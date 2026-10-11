"""Additive Toronto public-record archive for verified Toronto Open Data datasets.

Separate SQLite database; does not mutate main Radar records or claim removals.
The first successful snapshot is a baseline. Later new/changed content is evidence
of a change in the published DATASET, not necessarily a fresh business event.
Official catalogue pages: open.toronto.ca/dataset/<slug>/
"""
from __future__ import annotations
import csv, hashlib, json, sqlite3, sys
from collections import Counter
from xml.etree import ElementTree
from datetime import datetime, timezone
from pathlib import Path
from radar import Http, choose_ckan_resource, normalize_row, parse_tabular_bytes, resolve_ckan_package

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
DB=DATA/'toronto_priority_sources.sqlite'
API='https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action'
MAX_BYTES=35*1024*1024
SPECS=(
 {'id':'toronto_open_solicitations','department':'Purchasing & Finance',
  'slug':'tobids-all-open-solicitations','resource_hint':'All Solicitations',
  'keys':('SOLICITATION_ID','CALL_NUMBER','CALL_NO','REQUEST_NUMBER','SOLICITATION_NUMBER','ID')},
 {'id':'toronto_awarded_contracts','department':'Purchasing & Finance',
  'slug':'tobids-awarded-contracts','resource_hint':'Awarded Contracts',
  'keys':('AWARD_ID','CONTRACT_ID','CALL_NUMBER','CALL_NO','REQUEST_NUMBER','CONTRACT_NUMBER','ID')},
 {'id':'toronto_noncompetitive_contracts','department':'Purchasing & Finance',
  'slug':'tobids-non-competitive-contracts','resource_hint':'Non-Competitive Contracts',
  'keys':('CONTRACT_ID','CONTRACT_NUMBER','REFERENCE_NUMBER','SOLICITATION_NUMBER','ID')},
 {'id':'toronto_road_restrictions','department':'Transportation Services',
  'slug':'road-restrictions','resource_hint':'Road Restrictions',
  'keys':('RESTRICTION_ID','EVENT_ID','OBJECTID','ID')},
 {'id':'toronto_development_pipeline','department':'City Planning',
  'slug':'development-pipeline','resource_hint':'Development Pipeline',
  'keys':('PROJECT_ID','PROJECT_NUMBER','PROJECT_NO','DEVELOPMENT_ID','ID')},
 {'id':'toronto_development_application_history','department':'City Planning',
  'slug':'development-applications','resource_hint':'Development Applications',
  'keys':('APPLICATION_NUMBER','APPLICATION_NO','APPLICATION_NUM','FOLDER_NUMBER','ID')},
 {'id':'toronto_council_meeting_schedule','department':"City Clerk's Office",
  'slug':'3bfab808-105b-45ab-8d92-cf1916594653',
  'resource_hint':'meeting-schedule-all-committees-2022-2026',
  'keys':('MEETING_ID','EVENT_ID','ID')},
)

def now():
 return datetime.now(timezone.utc).isoformat(timespec='seconds')

def canonical(item):
 return json.dumps(item,sort_keys=True,ensure_ascii=False,default=str,separators=(',',':'))

def checksum(item):
 return hashlib.sha256(canonical(item).encode('utf-8')).hexdigest()

def setup(db):
 db.executescript("""CREATE TABLE IF NOT EXISTS sources(
   source_id TEXT PRIMARY KEY,department TEXT,package_id TEXT,resource_id TEXT,
   identity_field TEXT,last_success TEXT);
 CREATE TABLE IF NOT EXISTS runs(
   id INTEGER PRIMARY KEY,source_id TEXT,observed_at TEXT,status TEXT,
   fetched INTEGER,created INTEGER,updated INTEGER,detail TEXT);
 CREATE TABLE IF NOT EXISTS records(
   source_id TEXT,record_key TEXT,first_seen TEXT,last_seen TEXT,hash TEXT,json TEXT,
   PRIMARY KEY(source_id,record_key));
 CREATE TABLE IF NOT EXISTS versions(
   id INTEGER PRIMARY KEY,source_id TEXT,record_key TEXT,observed_at TEXT,hash TEXT,json TEXT);
 CREATE TABLE IF NOT EXISTS changes(
   id INTEGER PRIMARY KEY,source_id TEXT,record_key TEXT,observed_at TEXT,
   change_type TEXT,source_url TEXT,old_hash TEXT,new_hash TEXT);
 CREATE INDEX IF NOT EXISTS ix_toronto_versions ON versions(source_id,record_key);
 CREATE INDEX IF NOT EXISTS ix_toronto_changes ON changes(observed_at);""")
 db.commit()

def parse_public_xml(content):
 """Strict XML row parser for bounded, official Toronto procurement tables."""
 if b'<!DOCTYPE' in content.upper() or b'<!ENTITY' in content.upper():
  raise ValueError('XML entity/DTD declarations are not accepted')
 root=ElementTree.fromstring(content)
 def tag(el):
  return str(el.tag).rsplit('}',1)[-1]
 def fields(el):
  attrs=dict(el.attrib)
  if len(el):
   # Select data records with scalar fields, never flatten structured reports silently.
   if any(len(child) for child in el):return {}
   for child in el:
    key=tag(child)
    if key in attrs:return {}
    attrs[key]=(child.text or '').strip()
  return attrs if len(attrs)>=2 else {}
 choices=[]
 for parent in root.iter():
  group={}
  for child in parent:
   record=fields(child)
   if record:group.setdefault(tag(child),[]).append(record)
  for name,records in group.items():
   if len(records)>=2:
    choices.append((len(records),name,records))
 if not choices:
  record=fields(root)
  if not record:raise ValueError('XML has no recognizable tabular records')
  choices=[(1,tag(root),[record])]
 choices.sort(key=lambda x:x[0],reverse=True)
 if len(choices)>1 and choices[1][0]==choices[0][0]:
  raise ValueError('Ambiguous XML record groups')
 result=[normalize_row(r) for r in choices[0][2]]
 if any(not r for r in result):raise ValueError('XML row missing scalar fields')
 return result

def fetch(http,spec):
 """Fetch one complete, parseable CKAN resource by exact published package slug/ID."""
 cfg={'id':spec['id'],'name':spec['id'],'collector':'ckan','api_base':API,
      'package_slug':spec['slug'],
      'preferred_resource_names':[spec['resource_hint']],
      'preferred_formats':['CSV','JSON','GEOJSON','XLSX','ZIP','XLS','XML']}
 package=resolve_ckan_package(cfg,http)
 resource=choose_ckan_resource(package,cfg)
 name=str(resource.get('name') or '')
 if spec['resource_hint'].lower() not in name.lower():
  raise ValueError('Expected named resource was not selected: '+name[:100])
 fmt=str(resource.get('format') or '').upper()
 if fmt not in ('CSV','JSON','GEOJSON','XLSX','ZIP','XLS','XML'):
  raise ValueError('Unsupported resource format: '+fmt)
 size=resource.get('size')
 if size is not None and str(size).isdigit() and int(size)>MAX_BYTES:
  raise ValueError('Resource too large for bounded daily collector')
 url=str(resource.get('url') or '')
 if not url.lower().startswith('https://'):
  raise ValueError('Resource download URL must use HTTPS')
 response=http.get(url,timeout=(20,180),retries=3)
 if len(response.content)>MAX_BYTES:
  raise ValueError('Resource exceeded download size budget')
 if not response.content:
  raise ValueError('Empty downloaded resource')
 rows=parse_public_xml(response.content) if fmt=='XML' else parse_tabular_bytes(response.content,url,fmt)
 return [normalize_row(r) for r in rows],{'package_id':package['id'],'resource_id':resource['id'],
     'source_url':'https://open.toronto.ca/dataset/'+str(package.get('name') or spec['slug'])+'/',
     'resource_url':url,'format':fmt}

def identify(rows,spec):
 """Only use an ID field if it is complete AND unique throughout this snapshot."""
 for field in spec['keys']:
  values=[str(r.get(field) or '').strip() for r in rows]
  if values and all(values) and len(set(values))==len(values):
   return field,[str(v) for v in values]
 # Snapshot-hash identities are explicitly labelled: content revisions look NEW.
 hashes=[checksum(r) for r in rows]
 if len(set(hashes))!=len(hashes):
  raise ValueError('Duplicate rows without stable IDs; refuse to silently collapse')
 return 'ROW_HASH',[h for h in hashes]

def persist(db,spec,rows,meta,stamp):
 """Store an entirely parsed snapshot atomically, without removal inferences."""
 field,keys=identify(rows,spec)
 sid=spec['id']
 if not meta.get('package_id') or not meta.get('resource_id'):
  raise ValueError('Missing official package/resource provenance')
 prior=db.execute('SELECT identity_field FROM sources WHERE source_id=?',(sid,)).fetchone()
 if prior and prior[0]!=field and db.execute(
     'SELECT EXISTS(SELECT 1 FROM records WHERE source_id=?)',(sid,)).fetchone()[0]:
  raise ValueError('Stable key strategy changed; manual baseline migration required')
 baseline=not db.execute('SELECT EXISTS(SELECT 1 FROM records WHERE source_id=?)',(sid,)).fetchone()[0]
 created=updated=0
 with db:
  for key,row in zip(keys,rows):
   digest=checksum(row)
   previous=db.execute('SELECT hash FROM records WHERE source_id=? AND record_key=?',
                       (sid,key)).fetchone()
   if previous and previous[0]==digest:
    db.execute('UPDATE records SET last_seen=? WHERE source_id=? AND record_key=?',
               (stamp,sid,key))
    continue
   if previous:updated+=1
   else:created+=1
   serialized=canonical(row)
   db.execute('INSERT INTO versions(source_id,record_key,observed_at,hash,json) VALUES(?,?,?,?,?)',
              (sid,key,stamp,digest,serialized))
   db.execute("""INSERT INTO records(source_id,record_key,first_seen,last_seen,hash,json)
     VALUES(?,?,?,?,?,?) ON CONFLICT(source_id,record_key) DO UPDATE SET
     last_seen=excluded.last_seen,hash=excluded.hash,json=excluded.json""",
     (sid,key,stamp,stamp,digest,serialized))
   if not baseline:
    db.execute('INSERT INTO changes(source_id,record_key,observed_at,change_type,source_url,old_hash,new_hash) VALUES(?,?,?,?,?,?,?)',
               (sid,key,stamp,'DATASET_ROW_UPDATED' if previous else 'DATASET_ROW_FIRST_SEEN',
                meta['source_url'],previous[0] if previous else '',digest))
  db.execute("""INSERT INTO sources(source_id,department,package_id,resource_id,identity_field,last_success)
      VALUES(?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET
      department=excluded.department,package_id=excluded.package_id,
      resource_id=excluded.resource_id,identity_field=excluded.identity_field,
      last_success=excluded.last_success""",
      (sid,spec['department'],meta['package_id'],meta['resource_id'],field,stamp))
  db.execute('INSERT INTO runs(source_id,observed_at,status,fetched,created,updated,detail) VALUES(?,?,?,?,?,?,?)',
             (sid,stamp,'BASELINE' if baseline else 'OK',len(rows),created,updated,
              'Identity='+field+'; no removals inferred; '+meta['resource_url']))
 return {'source':sid,'status':'BASELINE' if baseline else 'OK','fetched':len(rows),
         'new_observations':created,'modified_observations':updated,'identity':field}

def report(db):
 DATA.mkdir(exist_ok=True)
 path=DATA/'toronto_priority_changes_REVIEW_ONLY.csv'
 fields=['source_id','record_key','observed_at','change_type','source_url']
 records=db.execute("""SELECT source_id,record_key,observed_at,change_type,source_url
                       FROM changes ORDER BY id DESC LIMIT 5000""").fetchall()
 tmp=path.with_suffix('.csv.tmp')
 with tmp.open('w',encoding='utf-8-sig',newline='') as out:
  w=csv.writer(out);w.writerow(fields);w.writerows(records)
 tmp.replace(path)

def run():
 DATA.mkdir(exist_ok=True)
 db=sqlite3.connect(DB)
 setup(db)
 http=Http()
 failures=[]
 try:
  for spec in SPECS:
   stamp=now()
   try:
    rows,meta=fetch(http,spec)
    result=persist(db,spec,rows,meta,stamp)
    print('Toronto public record:',json.dumps(result),flush=True)
   except Exception as exc:
    failures.append(spec['id'])
    with db:
     db.execute('INSERT INTO runs(source_id,observed_at,status,fetched,created,updated,detail) VALUES(?,?,?,?,?,?,?)',
                (spec['id'],stamp,'ERROR',0,0,0,str(exc)[:500]))
    print('Toronto public record ERROR:',spec['id'],str(exc)[:250],file=sys.stderr,flush=True)
  report(db)
 finally:db.close()
 print('Toronto sources:',len(SPECS)-len(failures),'successful;',len(failures),'failed')
 return 1 if failures else 0

if __name__=='__main__':
 raise SystemExit(run())
