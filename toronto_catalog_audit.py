"""Read-only Toronto CKAN department/feed inventory; does not ingest source records.

Run: python toronto_catalog_audit.py
Output: data/toronto_catalog_inventory.csv and .json
Only replaces outputs after an entire successful catalogue scan.
"""
from __future__ import annotations
import csv, io, json, re, sys, hashlib
from datetime import timedelta
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parent
API='https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/package_search'
PRIORITIES=(
 ('construction_development',r'building permit|development application|site plan|rezoning|zoning by.law|subdivision|development pipeline|planning application'),
 ('business_licensing',r'business licen|municipal licen|establishment|dinesafe|inspection'),
 ('procurement_finance',r'procurement|purchase order|tender|contract|non.competitive|capital budget|financial plan|vendor'),
 ('infrastructure_transport',r'road closure|road restriction|construction project|traffic restriction|capital project|right.of.way|roadwork'),
 ('land_property',r'address point|parcel|property|land use|assessment'),
 ('council_governance',r'council|committee|agenda|by.law|decision'),
)
def classify(package):
    haystack=' '.join(str(package.get(k) or '') for k in ('title','notes','name')).lower()
    return [family for family,pattern in PRIORITIES if re.search(pattern,haystack)]

def fetch_catalog(session=None, *, rows=100):
    session=session or requests.Session()
    start=0;packages=[];total=None;seen=set()
    while total is None or start<total:
        response=session.get(API,params={'rows':rows,'start':start},timeout=(10,60))
        response.raise_for_status()
        payload=response.json()
        if not payload.get('success') or not isinstance(payload.get('result'),dict):
            raise ValueError('Toronto CKAN returned an unsuccessful response')
        result=payload['result']
        count=result.get('count')
        items=result.get('results')
        if not isinstance(count,int) or count<0 or not isinstance(items,list):
            raise ValueError('Invalid Toronto CKAN pagination structure')
        if total is None:total=count
        elif total!=count:
            raise ValueError('CKAN package count changed during scan; retry to avoid partial inventory')
        if not items and start<total:
            raise ValueError('CKAN ended before package count was reached')
        for package in items:
            pid=package.get('id')
            if not pid or pid in seen:raise ValueError('Missing or repeated CKAN package id')
            seen.add(pid);packages.append(package)
        start+=len(items)
    if len(packages)!=total:raise ValueError('Incomplete CKAN catalogue')
    return packages

def normalize_title(text):
    return ' '.join(re.findall(r'[a-z0-9]+',str(text or '').lower()))

def audit(packages,sources):
    configured=[s for s in sources if str(s.get('jurisdiction','')).lower()=='toronto']
    rows=[]
    for package in packages:
        resources=package.get('resources') or []
        name=str(package.get('name') or '')
        title=str(package.get('title') or '')
        match=[s['id'] for s in configured if
               (s.get('package_id') and s['package_id']==package.get('id'))
               or (s.get('package_slug') and s['package_slug']==name)
               or (s.get('package_name') and s['package_name']==name)]
        # Search-based configuration is only a title candidate, not an ID check.
        possible=[s['id'] for s in configured if s['id'] not in match
                  and s.get('collector')=='ckan'
                  and s.get('package_query')
                  and normalize_title(s['package_query'])==normalize_title(title)]
        enabled=[s['id'] for s in configured if s['id'] in match and s.get('enabled')]
        rows.append({
            'package_id':package.get('id',''),
            'package_name':name,'title':title,
            'organization':(package.get('organization') or {}).get('title',''),
            'maintainer':package.get('maintainer',''),
            'modified':package.get('metadata_modified',''),
            'licence_id':package.get('license_id',''),
            'url':'https://open.toronto.ca/dataset/'+name+'/' if name else '',
            'resource_count':len(resources),
            'resource_formats':','.join(sorted({str(x.get('format') or '').upper() for x in resources if x.get('format')})),
            'resource_ids':','.join(sorted(str(x['id']) for x in resources if x.get('id'))),
            'priority_families':','.join(classify(package)),
            'configured_exact_ids':','.join(match),
            'configured_enabled_ids':','.join(enabled),
            'possible_query_matches':','.join(possible),
            'collector_alignment':'EXACT_CONFIGURED' if match else 'TITLE_SEARCH_POSSIBLE' if possible else 'NOT_CONFIGURED',
        })
    return rows

PROVIDER_FIELDS = ('title', 'organization', 'modified', 'licence_id',
                   'resource_ids', 'resource_formats', 'resource_count')

def catalog_changes(previous, current, stamp):
    """Observe published catalogue metadata; never assert record changes or deletion."""
    if previous is None:
        return []
    old={p['package_id']:p for p in previous if p.get('package_id')}
    new={p['package_id']:p for p in current if p.get('package_id')}
    events=[]
    for pid,now in new.items():
        before=old.get(pid)
        if before is None:
            events.append({'observed_at':stamp, 'package_id':pid,
                           'title':now.get('title',''), 'source_url':now.get('url',''),
                           'event_type':'NEW_CATALOGUE_ENTRY',
                           'details':{'note':'Publication listing discovered; not a new business or permit'}})
            continue
        changes={k:{'before':before.get(k,''),'after':now.get(k,'')}
                 for k in PROVIDER_FIELDS if before.get(k,'')!=now.get(k,'')}
        if changes:
            events.append({'observed_at':stamp,'package_id':pid,
                           'title':now.get('title',''), 'source_url':now.get('url',''),
                           'event_type':'CATALOGUE_METADATA_CHANGED','details':changes})
    for pid,before in old.items():
        if pid not in new:
            events.append({'observed_at':stamp,'package_id':pid,
                           'title':before.get('title',''),'source_url':before.get('url',''),
                           'event_type':'NOT_LISTED_IN_CURRENT_CATALOGUE',
                           'details':{'note':'No deletion, unpublishing or business closure inferred'}})
    return events

def store_history(path, events):
    """Deduplicate journal events by content, so interrupted audit retries are safe."""
    existing=path.read_text(encoding='utf-8') if path.is_file() else ''
    hashes=set()
    for line in existing.splitlines():
        if not line.strip():continue
        obj=json.loads(line)  # Corrupted history must not be silently replaced.
        hashes.add(str(obj.get('event_key') or ''))
    written=[]
    for e in events:
        identity={k:v for k,v in e.items() if k!='observed_at'}
        key=hashlib.sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()
        if key in hashes:continue
        written.append({**e,'event_key':key})
        hashes.add(key)
    updated=existing
    if updated and not updated.endswith('\n'):updated+='\n'
    updated+=''.join(json.dumps(x,sort_keys=True,ensure_ascii=False)+'\n' for x in written)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(updated,encoding='utf-8')
    temp.replace(path)
    return len(written)

def due(path, *, now=None, interval_days=7):
    now=now or datetime.now(timezone.utc)
    if not path.exists():return True
    try:
        metadata=json.loads(path.read_text(encoding='utf-8'))
        at=datetime.fromisoformat(metadata['observed_at'].replace('Z','+00:00'))
        return at.tzinfo is None or now-at>=timedelta(days=interval_days)
    except (ValueError,KeyError,TypeError,OSError,json.JSONDecodeError):return True

def run(*,force=False):
    dest=ROOT/'data';dest.mkdir(exist_ok=True)
    if not force and not due(dest/'toronto_catalog_inventory.json'):
        print('Toronto catalogue: weekly audit not due; existing inventory retained')
        return
    packages=fetch_catalog()
    sources=json.loads((ROOT/'config'/'sources.json').read_text(encoding='utf-8'))
    rows=audit(packages,sources)
    previous_path=dest/'toronto_catalog_inventory.json'
    previous=None
    if previous_path.exists():
        old_report=json.loads(previous_path.read_text(encoding='utf-8'))
        previous=old_report['packages']
        if len(previous)!=old_report['package_count']:
            raise RuntimeError('Previous Toronto inventory incomplete; history not modified')
    observed_at=datetime.now(timezone.utc).isoformat()
    changes=catalog_changes(previous,rows,observed_at)
    history_written=store_history(dest/'toronto_catalog_change_history.jsonl',changes)
    names=list(rows[0]) if rows else ['package_id','package_name','title']
    buffer=io.StringIO();writer=csv.DictWriter(buffer,fieldnames=names);writer.writeheader();writer.writerows(rows)
    summary={'observed_at':observed_at,
             'first_catalog_baseline':previous is None,
             'catalogue_metadata_changes_observed':len(changes),
             'catalogue_history_events_written':history_written,
             'source':'Toronto Open Data CKAN package_search','package_count':len(rows),
             'Toronto_existing_configured_sources':len([s for s in sources if str(s.get('jurisdiction','')).lower()=='toronto']),
             'priority_candidates':sum(bool(r['priority_families']) for r in rows),
             'packages':rows,
             'caveat':'Discovery only. EXACT_CONFIGURED means identity pinned in code, not proof of current successful ingestion. TITLE_SEARCH_POSSIBLE is not verified. No licence, schema, or live ingestion validated.'}
    for filename,text in [('toronto_catalog_inventory.csv',buffer.getvalue()),
                          ('toronto_catalog_inventory.json',json.dumps(summary,indent=2,ensure_ascii=False))]:
        output=dest/filename;temp=dest/(filename+'.tmp')
        temp.write_text(text,encoding='utf-8');temp.replace(output)
    print('Toronto catalogue inventory:',len(rows),'packages;',
          summary['priority_candidates'],'priority candidates;',
          len(changes),'catalogue metadata observations; outputs in',dest)
if __name__=='__main__':run(force='--force' in sys.argv[1:])
