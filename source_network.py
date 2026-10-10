"""v0.9 source intelligence: count actual collectors separately from candidate URLs.

No network traffic unless the user explicitly runs `probe`. Probes request only
source metadata (ArcGIS layer metadata or ordinary page HEAD/GET), not datasets.
This does not infer scraping or commercial-use permission from HTTP availability.
"""
from __future__ import annotations
import argparse,csv,json,re,datetime
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parent
CONFIG=ROOT/'config'
FIELDS=['source_id','name','region','category','url','record_kind','implementation','enabled','access_status','live_import','reuse_review','last_audited','notes']

def today():return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def unique_id(s):return re.sub('[^a-z0-9]+','_',s.lower()).strip('_')
def base_rows():
    out=[]
    for o in json.loads((CONFIG/'sources.json').read_text(encoding='utf8')):
        out.append(dict(source_id=o['id'],name=o['name'],region=o.get('region',''),category=o.get('family',''),url=o.get('url') or o.get('official_page') or '',record_kind='legacy_radar',implementation='configured',enabled=str(o.get('enabled',False)).lower(),access_status='configured_not_probed',live_import='not_verified_in_this_release',reuse_review='review_source_terms',last_audited='',notes='Original v0.8 collector. Check local data/status for actual operational state.'))
    v8=json.loads((CONFIG/'business_sources.json').read_text(encoding='utf8'))
    for o in v8['sources']:
        out.append(dict(source_id=o['id'],name=o['name'],region='Ontario/Southern Ontario',category='business_identity',url=o['url'],record_kind=o['kind'],implementation='configured',enabled=str(o['enabled']).lower(),access_status='configured_not_probed',live_import='not_verified_in_this_release',reuse_review=o.get('commercial_reuse','review_source_terms'),last_audited='',notes='v0.8 source; first run historical baseline only.'))
    for o in v8.get('optional_sources',[]):
        out.append(dict(source_id=o['id'],name=o['id'].replace('_',' ').title(),region='Ontario',category='business_identity',url='',record_kind=o['kind'],implementation='research_only',enabled='false',access_status='not_validated',live_import='not_tested',reuse_review='review_source_terms',last_audited='',notes=o.get('reason','')))
    # Research queue contains useful leads, not implemented collectors. Distinguish carefully.
    with (CONFIG/'free_feed_pipeline.csv').open(newline='',encoding='utf-8-sig') as f:
        for o in csv.DictReader(f):
            name=o['candidate'].strip()
            if not name:continue
            out.append(dict(source_id='candidate_'+unique_id(name),name=name,region=o['region'],category=o['source_family'],url='',record_kind='unknown',implementation='research_only',enabled='false',access_status='research_only',live_import='not_tested',reuse_review='review_source_terms',last_audited='',notes=(o['next_validation']+'; '+o['commercial_use_case'])[:500]))
    with (CONFIG/'southern_ontario_feed_queue.csv').open(newline='',encoding='utf-8-sig') as f:
        for o in csv.DictReader(f):
            name=o.get('source','').strip();url=o.get('url','').strip()
            if not name:continue
            out.append(dict(source_id='candidate_'+unique_id(name),name=name,region=o.get('region',''),category=o.get('kind',''),url=url,record_kind='candidate',implementation='research_only',enabled='false',access_status='research_only',live_import='not_tested',reuse_review='review_source_terms',last_audited='',notes=o.get('verification','')))
    # Conservative deduplication: never count identical normalized source name twice.
    dedup={}
    for o in out:
        key=unique_id(o['name'])
        if key in dedup:
            prior=dedup[key]
            if prior['implementation']=='research_only' and o['implementation']=='configured':
                dedup[key]=o
            elif not prior['url'] and o['url']:prior['url']=o['url']
        else:dedup[key]=o
    return list(dedup.values())

def save(rows,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS,extrasaction='ignore');w.writeheader();w.writerows(rows)

def load(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def init(path):
    # Preserve previous research and live probe statuses when rebuilding catalog.
    previous={r['source_id']:r for r in load(path)} if path.exists() else {}
    rows=base_rows()
    for r in rows:
        old=previous.get(r['source_id'])
        if old:
            for k in ('last_audited','access_status','live_import','notes'):
                if old.get(k) and (k=='notes' or old[k] not in ('not_tested','configured_not_probed','research_only')):r[k]=old[k]
    save(rows,path);return rows

def summarize(rows):
    return {'unique_listed_sources':len(rows),'configured_collectors':sum(r['implementation']=='configured' for r in rows),'research_candidates':sum(r['implementation']=='research_only' for r in rows),'enabled_configuration':sum(r['enabled']=='true' for r in rows),'live_import_verified_in_v09':sum(r['live_import']=='verified' for r in rows),'access_probed':sum(r['access_status'] in ('reachable','unreachable','error','auth_required') for r in rows)}

def probe_one(row,session):
    url=row.get('url','');parts=urlsplit(url)
    if parts.scheme!='https' or not parts.hostname:return 'no_valid_https_url'
    # Limit probing to known public endpoints; no registry scraping.
    if 'business-registry' in parts.path.lower() or 'cbr-rec' in parts.hostname.lower():return 'manual_only'
    try:
        if '/FeatureServer/' in parts.path or '/MapServer/' in parts.path:
            response=session.get(url,params={'f':'json'},timeout=(6,15));response.raise_for_status()
            d=response.json();return 'reachable' if isinstance(d,dict) and isinstance(d.get('fields'),list) and not d.get('error') else 'error'
        response=session.head(url,allow_redirects=True,timeout=(6,12))
        if response.status_code in (401,403):return 'auth_required'
        if response.status_code==405:return 'method_not_allowed'
        return 'reachable' if response.ok else 'unreachable'
    except Exception:return 'error'

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('action',choices=('init','status','probe'));p.add_argument('--file',default=str(ROOT/'data'/'source_network.csv'));p.add_argument('--max-probes',type=int,default=10);args=p.parse_args(argv)
    path=Path(args.file)
    rows=init(path) if args.action=='init' or not path.exists() else load(path)
    if args.action=='probe':
        import requests
        session=requests.Session();session.headers['User-Agent']='GTACommercialRadar/0.9 (source metadata audit)'
        count=0
        for r in rows:
            if count>=max(0,args.max_probes):break
            if not r['url'] or r['access_status'] not in ('configured_not_probed','research_only'):continue
            r['access_status']=probe_one(r,session);r['last_audited']=today();count+=1
            print(r['source_id']+': '+r['access_status'])
        save(rows,path)
    print(json.dumps(summarize(rows),indent=2));print('Source catalog:',path)
    print('WARNING: Endpoint reachability is not proof of collector success or commercial reuse rights.')
if __name__=='__main__':main()
