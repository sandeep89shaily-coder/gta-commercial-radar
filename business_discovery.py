'''GTA Radar v0.8 business-discovery companion. Does not write radar.sqlite.

Provides opt-in federal CSV + official GIS sources, fresh observations, qualification
review, and an Ontario registration manual verification queue. First collection of
any source is baseline-only. No unauthorized automated Ontario registry scraping.
'''
from __future__ import annotations
import argparse,csv,hashlib,html,io,json,re,sqlite3,time
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import urlparse
import requests

ROOT=Path(__file__).resolve().parent
CFG=ROOT/'config'/'business_sources.json'
FIELDS=['source_id','source_key','company_name','address','city','province','industry','website','event_date','event_type','observed_at','confidence','local_verified','evidence_url','verification','buyer_categories','notes']
SCHEMA='''
CREATE TABLE IF NOT EXISTS observations(source_id TEXT NOT NULL,source_key TEXT NOT NULL,company_name TEXT,address TEXT,city TEXT,province TEXT,industry TEXT,website TEXT,event_date TEXT,event_type TEXT,observed_at TEXT,record_hash TEXT,raw_json TEXT, PRIMARY KEY(source_id,source_key));
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,source_id TEXT,source_key TEXT,observed_at TEXT,event_type TEXT,event_date TEXT,company_name TEXT,address TEXT,city TEXT,industry TEXT,evidence_url TEXT);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(observed_at);
CREATE TABLE IF NOT EXISTS runs(source_id TEXT PRIMARY KEY,last_checked TEXT,last_success TEXT,record_count INTEGER,etag TEXT,last_modified TEXT,status TEXT,error TEXT);
CREATE TABLE IF NOT EXISTS verification_queue(queue_key TEXT PRIMARY KEY,company_name TEXT,address TEXT,source_id TEXT,source_key TEXT,created_at TEXT,last_seen TEXT,status TEXT,reason TEXT,registry_url TEXT);
'''
REGISTRY='https://www.ontario.ca/page/ontario-business-registry'
USER_AGENT='GTACommercialRadar/0.8 (public open-data research; contact: local operator)'

def now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def norm(x):return re.sub(r'\s+',' ',str(x or '').strip())
def lowkey(x):return re.sub(r'[^a-z0-9]','',norm(x).lower())
def sha(x):return hashlib.sha256(x.encode('utf-8')).hexdigest()
def pick(d,keys):
    upper={k.upper():v for k,v in d.items()}
    return next((norm(upper[k.upper()]) for k in keys if norm(upper.get(k.upper()))),'')
def database(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path)
    db.row_factory=sqlite3.Row;db.executescript(SCHEMA);return db

def federal_rows(response):
    # stream large file without loading 100+ MB into RAM
    lines=(s.decode('utf-8-sig',errors='replace') if isinstance(s,bytes) else s for s in response.iter_lines() if s)
    reader=csv.DictReader(lines)
    if not reader.fieldnames or not {'Corporation number','Corporate name - form 1'}.issubset(set(reader.fieldnames)):
        raise ValueError('Federal CSV headers differ from supported schema; refusing to accept snapshot')
    for r in reader:
        prov=pick(r,['Province/territory','Province/Territory','Province'])
        if prov.upper() not in ('ON','ONTARIO'):continue
        name=pick(r,['Corporate name - form 1','Corporate name - form 2'])
        number=pick(r,['Corporation number'])
        if not name or not number:continue
        yield {'source_key':number,'company_name':name,'address':pick(r,['Street','Street 2']),
          'city':pick(r,['City/town']),'province':'ON','industry':'','website':'',
          'event_date':pick(r,['Date of incorporation','Incorporation date','Incorporation Date']),
          'event_type':'FEDERAL_INCORPORATION_RECORD','raw':r}

def arcgis_rows(session,source):
    url=source['url'];headers={'User-Agent':USER_AGENT}
    info=session.get(url,params={'f':'json'},timeout=(12,40),headers=headers);info.raise_for_status()
    layer=info.json(); fields={x['name'] for x in layer.get('fields',[])}
    if 'error' in layer or not fields:raise RuntimeError('ArcGIS metadata unavailable or missing field definitions: '+str(layer.get('error','')))
    key_field=next((k for k in source.get('key_fields',[]) if k in fields),None) or layer.get('objectIdField')
    if not key_field or key_field not in fields:raise RuntimeError('Source has no stable record key')
    batch=min(1000,int(layer.get('maxRecordCount',1000)))
    offset=0; seen=set()
    while True:
        q=session.get(url+'/query',params={'f':'json','where':'1=1','outFields':'*','returnGeometry':'false','orderByFields':key_field+' ASC','resultOffset':offset,'resultRecordCount':batch},headers=headers,timeout=(12,70))
        q.raise_for_status();obj=q.json()
        if 'error' in obj:raise RuntimeError('ArcGIS query failed '+str(obj['error']))
        features=obj.get('features')
        if not isinstance(features,list):raise RuntimeError('Invalid ArcGIS features array')
        for item in features:
            r=item.get('attributes') or {}; key=norm(r.get(key_field))
            if not key or key in seen:continue
            seen.add(key)
            name=pick(r,source.get('name_fields',[]))
            if not name:continue
            address=pick(r,source.get('address_fields',[]))
            if source['id']=='niagara_employment_inventory':
                address=' '.join(x for x in (pick(r,['businessstreetnumber']),address,pick(r,['businessunit'])) if x)
            yield {'source_key':key,'company_name':name,'address':address,
                 'city':pick(r,source.get('city_fields',[])) or ('Kitchener' if source['id']=='kitchener_business_licences' else ''),
                 'province':'ON','industry':pick(r,source.get('industry_fields',[])),
                 'website':pick(r,source.get('website_fields',[])),
                 'event_date':pick(r,source.get('date_fields',[])),
                 'event_type':'BUSINESS_DIRECTORY_OBSERVATION' if 'directory' in source['id'] else 'BUSINESS_LICENCE_OBSERVATION','raw':r}
        if len(features)<batch:break
        offset+=len(features)
        if offset>500000:raise RuntimeError('Refusing unexpected >500k row layer')

def is_local(record,source):
    # Federal Ontario registration is NOT proof of physical GTA/Southern Ontario presence.
    return source['kind']=='arcgis' and bool(record.get('address'))
def eligible_categories(row):
    w=(row['industry']+' '+row['event_type']).lower()
    out=['commercial_insurance','accounting_payroll','it_telecom']
    if any(x in w for x in ('restaurant','food','retail','store','licence')):out+=['security_access','signage_graphics','payment_pos']
    if any(x in w for x in ('manufactur','warehouse','industrial')):out+=['hvac_mechanical','fire_life_safety','equipment_furnishing']
    return ';'.join(dict.fromkeys(out))

def queue_ontario(db,record,source_id,reason):
    name=norm(record.get('company_name'))
    if not name:return
    addr=norm(record.get('address'))
    key=sha(lowkey(name)+'|'+lowkey(addr))[:24]
    date=now()
    db.execute('''INSERT INTO verification_queue VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(queue_key) DO UPDATE SET last_seen=excluded.last_seen''',
        (key,name,addr,source_id,norm(record.get('source_key')),date,date,'NEEDS_MANUAL_REGISTRY_CHECK',reason,REGISTRY))

def upsert_source(db,source,rows,*,etag='',modified=''):
    sid=source['id'];date=now(); old=db.execute('SELECT COUNT(*) FROM observations WHERE source_id=?',(sid,)).fetchone()[0];baseline=old==0
    new=changed=0;seen=set()
    # Atomic transaction prevents partial snapshots being interpreted as success.
    with db:
        for r in rows:
            key=str(r['source_key']);seen.add(key)
            payload={k:r.get(k,'') for k in ('company_name','address','city','province','industry','website','event_date','event_type')}
            h=sha(json.dumps(payload,sort_keys=True,ensure_ascii=False))
            prev=db.execute('SELECT record_hash FROM observations WHERE source_id=? AND source_key=?',(sid,key)).fetchone()
            if prev is None:new+=1
            elif prev['record_hash']!=h:changed+=1
            db.execute('''INSERT INTO observations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
              ON CONFLICT(source_id,source_key) DO UPDATE SET company_name=excluded.company_name,address=excluded.address,city=excluded.city,province=excluded.province,industry=excluded.industry,website=excluded.website,event_date=excluded.event_date,event_type=excluded.event_type,observed_at=excluded.observed_at,record_hash=excluded.record_hash,raw_json=excluded.raw_json''',
              (sid,key,r['company_name'],r['address'],r['city'],r['province'],r['industry'],r['website'],r['event_date'],r['event_type'],date,h,json.dumps(r.get('raw',{}),ensure_ascii=False,default=str)))
            if not baseline and (prev is None or prev['record_hash']!=h):
                event='NEWLY_OBSERVED' if prev is None else 'RECORD_UPDATED'
                db.execute('INSERT INTO events(source_id,source_key,observed_at,event_type,event_date,company_name,address,city,industry,evidence_url) VALUES(?,?,?,?,?,?,?,?,?,?)',
                  (sid,key,date,event,r['event_date'],r['company_name'],r['address'],r['city'],r['industry'],source['url']))
                queue_ontario(db,r,sid,'New or changed official business record; verify legal identity manually')
        if not seen:raise ValueError('Empty collection: not storing empty baseline/snapshot')
        # Never infer business closure from absence: source survey/layer coverage can change.
        db.execute('''INSERT INTO runs(source_id,last_checked,last_success,record_count,etag,last_modified,status,error) VALUES(?,?,?,?,?,?,?,?)
                     ON CONFLICT(source_id) DO UPDATE SET last_checked=excluded.last_checked,last_success=excluded.last_success,record_count=excluded.record_count,etag=excluded.etag,last_modified=excluded.last_modified,status=excluded.status,error='' ''',
                  (sid,date,date,len(seen),etag,modified,'BASELINE' if baseline else 'OK',''))
    return {'source':sid,'baseline':baseline,'rows':len(seen),'new':0 if baseline else new,'updated':0 if baseline else changed}

def run_source(db,source,session,force=False):
    r=db.execute('SELECT * FROM runs WHERE source_id=?',(source['id'],)).fetchone()
    if r and not force and r['last_success']:
        try:
            delta=datetime.now(timezone.utc)-datetime.fromisoformat(r['last_success'])
            if delta<timedelta(days=source.get('cadence_days',1)):return {'source':source['id'],'skipped':'NOT_DUE'}
        except ValueError:pass
    try:
        if source['kind']=='federal_csv':
            headers={'User-Agent':USER_AGENT}
            if r and r['etag'] and not force:headers['If-None-Match']=r['etag']
            if r and r['last_modified'] and not force:headers['If-Modified-Since']=r['last_modified']
            resp=session.get(source['url'],headers=headers,stream=True,timeout=(15,180))
            if resp.status_code==304:
                with db:db.execute('UPDATE runs SET last_checked=?,last_success=?,status=? WHERE source_id=?',(now(),now(),'UNCHANGED',source['id']))
                return {'source':source['id'],'skipped':'NOT_MODIFIED'}
            resp.raise_for_status()
            result=upsert_source(db,source,federal_rows(resp),etag=resp.headers.get('ETag',''),modified=resp.headers.get('Last-Modified',''))
            resp.close()
        elif source['kind']=='arcgis':result=upsert_source(db,source,arcgis_rows(session,source))
        else:raise ValueError('Unimplemented or unauthorized source kind '+source['kind'])
        return result
    except Exception as e:
        with db:
            db.execute('''INSERT INTO runs(source_id,last_checked,status,error) VALUES(?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET last_checked=excluded.last_checked,status=excluded.status,error=excluded.error''',(source['id'],now(),'FAILED',str(e)[:500]))
        return {'source':source['id'],'error':str(e)}

def import_radar_events(db,legacy_db,limit=10000):
    if not legacy_db.exists():return 0
    conn=sqlite3.connect('file:'+str(legacy_db.resolve())+'?mode=ro',uri=True)
    conn.row_factory=sqlite3.Row;added=0
    try:
        # Only actually logged NEW/UPDATED events; existing baselines are deliberately excluded.
        query='''SELECT c.source_id,c.record_key,c.normalized_json,c.observed_at FROM changes c WHERE c.change_type IN ('NEW','UPDATED') ORDER BY c.id DESC LIMIT ?'''
        try:rows=conn.execute(query,(limit,)).fetchall()
        except sqlite3.DatabaseError:return 0
        with db:
            for item in rows:
                try:details=json.loads(item['normalized_json'])
                except (ValueError,TypeError):continue
                name=norm(details.get('entity_name') or details.get('entity') or '')
                if not name or name.lower() in ('unknown','none','n/a'):continue
                record={'company_name':name,'address':details.get('address',''),'source_key':item['record_key']}
                before=db.total_changes
                queue_ontario(db,record,item['source_id'],'Existing Radar event suggests a named Ontario company; verify identity')
                added+=int(db.total_changes>before)
    finally:conn.close()
    return added

def output(db,data):
    data.mkdir(parents=True,exist_ok=True)
    events=db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 10000').fetchall()
    source_cfg={x['id']:x for x in json.loads(CFG.read_text())['sources']}
    out=[]
    for ev in events:
        r=dict(ev);s=source_cfg[r['source_id']]
        r.update({'province':'ON','website':'','confidence':'REVIEW_REQUIRED','local_verified':'YES_DIRECTORY_ADDRESS' if r['address'] and s['kind']=='arcgis' else 'NO',
           'verification':'NOT_VERIFIED','buyer_categories':eligible_categories(r),
           'notes':'Observation event, NOT verified incorporation/opening or consent to contact'})
        out.append(r)
    path=data/'business_leads_REVIEW_ONLY.csv'
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS,extrasaction='ignore');writer.writeheader();writer.writerows(out)
    qcols=['company_name','address','source_id','source_key','created_at','status','reason','registry_url']
    pending=db.execute('SELECT * FROM verification_queue ORDER BY created_at DESC').fetchall()
    with (data/'ontario_registry_MANUAL_QUEUE.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=qcols,extrasaction='ignore');writer.writeheader();writer.writerows([dict(r) for r in pending])
    statuses=[dict(r) for r in db.execute('SELECT * FROM runs ORDER BY source_id')]
    with (data/'business_source_status.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=['source_id','last_checked','last_success','record_count','status','error'],extrasaction='ignore');writer.writeheader();writer.writerows(statuses)
    table=''.join('<tr>'+''.join('<td>'+html.escape(str(r.get(k,'')))+'</td>' for k in ['source_id','record_count','status','last_success','error'])+'</tr>' for r in statuses)
    (data/'business_dashboard.html').write_text('<!doctype html><meta charset="utf-8"><title>GTA Business Discovery</title><style>body{font:15px Segoe UI,Arial;max-width:1050px;margin:35px auto;color:#253145;padding:0 20px}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}.note{background:#f1f4f9;padding:14px;border-radius:8px}</style><h1>GTA Radar — Business Discovery</h1><p class="note">'+str(len(out))+' review-only new/updated observations; '+str(len(pending))+' Ontario registry manual verification candidates. Baseline data is excluded. No automatic registry scraping or sales outreach.</p><table><tr><th>Source</th><th>Rows</th><th>Status</th><th>Last success</th><th>Error</th></tr>'+table+'</table><p>See business_leads_REVIEW_ONLY.csv and ontario_registry_MANUAL_QUEUE.csv.</p>',encoding='utf-8')
    return len(out),len(pending)

def main(argv=None):
    p=argparse.ArgumentParser(description='Non-destructive business discovery extension to v0.7')
    p.add_argument('command',choices=['run','status','export','queue'])
    p.add_argument('--data-dir',default=str(ROOT/'data'))
    p.add_argument('--source',action='append')
    p.add_argument('--force',action='store_true',help='Ignore cadence; never alters legacy database')
    args=p.parse_args(argv);data=Path(args.data_dir)
    db=database(data/'business_discovery.sqlite')
    config=json.loads(CFG.read_text());sources=[s for s in config['sources'] if s.get('enabled')]
    if args.source:
        unknown=set(args.source)-{s['id'] for s in sources}
        if unknown:p.error('Unknown or disabled source '+str(unknown))
        sources=[s for s in sources if s['id'] in args.source]
    failed=0
    if args.command=='run':
        with requests.Session() as session:
            for source in sources:
                print('Collecting:',source['name'],flush=True)
                result=run_source(db,source,session,force=args.force)
                print(' ->',result,flush=True);failed+=bool(result.get('error'))
    if args.command in ('run','queue'):
        n=import_radar_events(db,data/'radar.sqlite')
        print('Existing Radar event records considered for Ontario verification:',n)
    events,pending=output(db,data)
    print('Review-only business events:',events,'Ontario verification candidates:',pending)
    print('Open:',data/'business_dashboard.html')
    db.close();return 1 if failed else 0
if __name__=='__main__':raise SystemExit(main())
