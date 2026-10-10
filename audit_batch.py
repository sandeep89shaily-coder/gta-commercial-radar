"""Read-only, multi-source ArcGIS readiness audit. Does not open or alter radar.sqlite.

Usage: python audit_batch.py
       python audit_batch.py --all-arcgis
"""
from __future__ import annotations
import argparse, csv, json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from radar import Http

ROOT=Path(__file__).resolve().parent
DATE_TYPES={'esriFieldTypeDate','esriFieldTypeDateOnly','esriFieldTypeTimestampOffset'}

def assess_schema(source, metadata):
    remote={f.get('name','').upper():f for f in metadata.get('fields',[])}
    if not remote:
        return ['No field schema returned'],[],[]
    missing=[]
    for group in ('key_fields','address_fields','description_fields','date_fields','incremental_fields'):
        for name in source.get(group,[]):
            if name.upper() not in remote:
                missing.append(f'{group}:{name}')
    inc=source.get('incremental_fields') or source.get('freshness_fields') or []
    text_dates=[name for name in inc if name.upper() in remote and remote[name.upper()].get('type') not in DATE_TYPES]
    return missing,text_dates,list(remote)

def audit_one(source, http):
    out={'id':source['id'],'region':source.get('region',''),'enabled':source.get('enabled',False),
         'result':'BLOCKED','full_count':'','recent_count':'','issues':'','timestamp':datetime.now(timezone.utc).isoformat()}
    try:
        metadata=http.get(source['url'],params={'f':'json'},timeout=(8,30)).json()
        if metadata.get('error'):raise ValueError(f"Metadata: {metadata['error']}")
        missing,nondate,remote=assess_schema(source,metadata)
        issues=[]
        if missing:issues.append('Missing fields: '+', '.join(missing))
        if nondate:issues.append('Incremental fields not ArcGIS date type: '+', '.join(nondate))
        where=source.get('server_where') or '1=1'
        q=http.get(source['query_url'],params={'f':'json','where':where,'returnCountOnly':'true'},timeout=(8,30)).json()
        if q.get('error'):issues.append('Server filter failed: '+str(q['error']))
        else:out['full_count']=q.get('count','')
        inc=source.get('incremental_fields') or source.get('freshness_fields') or []
        eligible=[f for f in inc if f.upper() in {a.upper() for a in remote} and f not in nondate]
        if eligible:
            since=(datetime.now(timezone.utc)-timedelta(days=30)).date().isoformat()
            clause=' OR '.join(f"{f} >= DATE '{since}'" for f in eligible)
            window=f'({where}) AND ({clause})'
            q=http.get(source['query_url'],params={'f':'json','where':window,'returnCountOnly':'true'},timeout=(8,30)).json()
            if q.get('error'):issues.append('Recent query rejected: '+str(q['error']))
            else:out['recent_count']=q.get('count','')
        else:issues.append('No verified ArcGIS date field for incremental polling')
        if out['full_count']!='' and out['recent_count']==0:
            issues.append('Zero recent records: investigate publication freshness before enabling')
        out['result']='REVIEW' if issues else 'TECHNICAL_CHECK_PASSED'
        out['issues']=' | '.join(issues)
    except Exception as exc:
        out['issues']=f'{type(exc).__name__}: {exc}'
    return out

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all-arcgis',action='store_true',help='Include already-enabled ArcGIS sources')
    parser.add_argument('--source',action='append',help='Audit specific configured source IDs')
    args=parser.parse_args(argv)
    sources=json.loads((ROOT/'config/sources.json').read_text(encoding='utf-8'))
    chosen=[s for s in sources if s.get('collector')=='arcgis' and (args.all_arcgis or not s.get('enabled'))]
    if args.source:
        chosen=[s for s in sources if s.get('id') in args.source and s.get('collector')=='arcgis']
    http=Http(); outputs=[]
    for i,s in enumerate(chosen,1):
        print(f'[{i}/{len(chosen)}] {s["id"]} ...',flush=True)
        row=audit_one(s,http);outputs.append(row)
        print(f'  {row["result"]} full={row["full_count"]} last30d={row["recent_count"]} {row["issues"]}',flush=True)
    dest=ROOT/'SOUTHERN_ONTARIO_LIVE_AUDIT.csv'
    with dest.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=['id','region','enabled','result','full_count','recent_count','issues','timestamp']);w.writeheader();w.writerows(outputs)
    print(f'\nSaved: {dest}\nNo database changes were made.')
    return 0 if all(r['result']!='BLOCKED' for r in outputs) else 1

if __name__=='__main__':sys.exit(main())
