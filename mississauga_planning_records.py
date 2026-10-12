"""Separate, additive Mississauga planning archive for two staged official GIS layers.

Does not enable staged sources in the main Radar database. Records only complete
official full snapshots with stable APP_FILE_NO identity. No removal inference.
Uses the shared proven version/observation archive schema.
"""
from __future__ import annotations
import csv, json, sqlite3, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse
from radar import Http, collect_arcgis
from toronto_public_records import setup, persist, identify

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
DB=DATA/'mississauga_planning_sources.sqlite'
IDS=('mississauga_site_plan_applications','mississauga_rezoning_applications')
HOST='services6.arcgis.com'
ACCOUNT='hM5ymMLbxIyWTjn2'
MAX_ROWS=30000

def load_sources():
 configs=json.loads((ROOT/'config'/'sources.json').read_text(encoding='utf-8'))
 matched={s['id']:s for s in configs if s.get('id') in IDS}
 if set(matched)!=set(IDS):raise ValueError('Missing staged Mississauga planning source')
 return [matched[key] for key in IDS]

def validate_location(source):
 url=str(source.get('url') or '')
 p=urlparse(url)
 if p.scheme!='https' or p.hostname!=HOST or p.username or p.password:
  raise ValueError('Unexpected Mississauga ArcGIS host')
 if not p.path.lower().startswith('/'+ACCOUNT.lower()+'/arcgis/rest/services/'):
  raise ValueError('Unexpected Mississauga ArcGIS account')
 if not p.path.lower().endswith('/featureserver/0'):
  raise ValueError('Expected FeatureServer layer zero')
 if str(source.get('query_url') or '').lower().split('?')[0]!=url.lower()+'/query':
  raise ValueError('Query URL does not match the configured layer')

def application_key_quality(rows, key):
 """Count missing and repeated application IDs without exposing any record values."""
 seen=set()
 missing=repeated=0
 for row in rows:
  value=str(row.get(key) or '').strip()
  if not value:
   missing+=1
  elif value in seen:
   repeated+=1
  else:
   seen.add(value)
 return missing,repeated

def fetch(http,source,preferred_identity=None):
 validate_location(source)
 layer=source['url']
 response=http.get(layer,params={'f':'json'},timeout=(10,35))
 metadata=response.json()
 if 'error' in metadata:raise ValueError('ArcGIS layer metadata error: '+str(metadata['error']))
 fieldnames={str(f.get('name') or '').upper() for f in metadata.get('fields',[])}
 if 'APP_FILE_NO' not in fieldnames and 'PLNG_APP_ID' not in fieldnames:
  raise ValueError('No application ID field present in official layer')
 oid=metadata.get('objectIdField')
 if not oid or str(oid).upper() not in fieldnames:raise ValueError('ArcGIS ObjectID metadata missing')
 counter=http.get(source['query_url'],params={'where':source.get('server_where','1=1'),
                    'returnCountOnly':'true','f':'json'},timeout=(10,45)).json()
 if 'error' in counter:raise ValueError('ArcGIS record count query failed')
 count=int(counter['count'])
 if count<0 or count>MAX_ROWS:raise ValueError('ArcGIS record count out of approved bounds')
 if count==0:raise ValueError('Empty planning source requires review; no overwrite')
 snapshot=collect_arcgis({**source,'page_size':min(int(source.get('page_size') or 1000),1000)},
                          http,progress=False,smart=False,force_full=True)
 if not snapshot.is_complete or len(snapshot.rows)!=count:
  raise ValueError('Mississauga planning snapshot incomplete')
 # A site plan may have an incomplete/repeated public file number. A second
 # city-published application ID is allowed ONLY when complete and unique.
 # Preserve the previously stored identity strategy on later weekly refreshes.
 candidates=('APP_FILE_NO','PLNG_APP_ID')
 if preferred_identity=='APPLICATION_COMPOSITE_ID':
  candidates=()
 elif preferred_identity in candidates:
  candidates=(preferred_identity,)+tuple(x for x in candidates if x!=preferred_identity)
 quality=[]
 chosen=None
 for key in candidates:
  if key not in fieldnames:
   quality.append(key+' absent')
   continue
  missing,repeated=application_key_quality(snapshot.rows,key)
  quality.append(key+' missing='+str(missing)+' repeated='+str(repeated))
  if missing==0 and repeated==0:
   chosen=key
   break
 if not chosen and all(k in fieldnames for k in ('APP_FILE_NO','PLNG_APP_ID')):
  # A compound identity is safe only if both fields are present on every row
  # and each PAIR is unique. Do not use ArcGIS OBJECTID as a business identity.
  pairs=[(str(row.get('APP_FILE_NO') or '').strip(),
          str(row.get('PLNG_APP_ID') or '').strip()) for row in snapshot.rows]
  if all(left and right for left,right in pairs) and len(set(pairs))==len(pairs):
   chosen='APPLICATION_COMPOSITE_ID'
   # Deterministic, unambiguous JSON encoding avoids separator collisions.
   for row,(left,right) in zip(snapshot.rows,pairs):
    row[chosen]=json.dumps([left,right],separators=(',',':'),ensure_ascii=False)
 if not chosen:
  raise ValueError('Planning application IDs missing or repeated; '+
                   '; '.join(quality)+'; no complete unique composite ID; snapshot rejected')
 spec={'id':source['id'],'department':'City Planning','keys':(chosen,)}
 evidence={'package_id':layer,'resource_id':layer,
           'resource_url':layer+'/query',
           'source_url':layer,
           'reported_count':count}
 return snapshot.rows,evidence,spec

def due(db,sid,now=None):
 now=now or datetime.now(timezone.utc)
 r=db.execute('SELECT last_success FROM sources WHERE source_id=?',(sid,)).fetchone()
 if not r or not r[0]:return True
 try:return now-datetime.fromisoformat(r[0].replace('Z','+00:00'))>=timedelta(days=7)
 except (ValueError,TypeError):return True

def export_changes(db):
 output=DATA/'mississauga_planning_changes_REVIEW_ONLY.csv'
 columns=('source_id','record_key','observed_at','change_type','source_url')
 records=db.execute('SELECT source_id,record_key,observed_at,change_type,source_url '
                    'FROM changes ORDER BY id DESC LIMIT 5000').fetchall()
 temp=output.with_suffix('.csv.tmp')
 with temp.open('w',newline='',encoding='utf-8-sig') as handle:
  writer=csv.writer(handle);writer.writerow(columns);writer.writerows(records)
 temp.replace(output)

def run():
 DATA.mkdir(exist_ok=True)
 db=sqlite3.connect(DB)
 setup(db)
 failures=0
 try:
  http=Http()
  for source in load_sources():
   sid=source['id']
   if not due(db,sid):
    print('Mississauga planning: weekly refresh not yet due:',sid,flush=True)
    continue
   timestamp=datetime.now(timezone.utc).isoformat(timespec='seconds')
   try:
    prior=db.execute('SELECT identity_field FROM sources WHERE source_id=?',
                     (sid,)).fetchone()
    records,meta,spec=fetch(http,source,preferred_identity=prior[0] if prior else None)
    result=persist(db,spec,records,meta,timestamp)
    print('Mississauga planning:',json.dumps(result),flush=True)
   except Exception as exc:
    failures+=1
    with db:
     db.execute('INSERT INTO runs(source_id,observed_at,status,fetched,created,updated,detail) '
                'VALUES(?,?,?,?,?,?,?)',(sid,timestamp,'ERROR',0,0,0,str(exc)[:500]))
    print('Mississauga planning ERROR:',sid,str(exc)[:300],file=sys.stderr,flush=True)
  export_changes(db)
 finally:db.close()
 return 1 if failures else 0

if __name__=='__main__':raise SystemExit(run())
