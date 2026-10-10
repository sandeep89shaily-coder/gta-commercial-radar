"""Read-only parallel technical acceptance testing for *all* staged ArcGIS feeds.

Does not import records, edit source enablement, or touch radar.sqlite.
"""
from __future__ import annotations
import argparse, concurrent.futures, csv, html, json, time
from pathlib import Path
from audit_batch import audit_one
from radar import Http
ROOT=Path(__file__).resolve().parent
FIELDS=['id','region','enabled','result','full_count','recent_count','issues','timestamp','sample_count','sample_issue','licence_clearance']

def assess_record_sample(source,http):
    """Probe 3 actual records using the configured filter, without a bulk download."""
    try:
        where=source.get('server_where') or '1=1'
        obj=http.get(source['query_url'],params={'f':'json','where':where,'outFields':'*','returnGeometry':'false','resultRecordCount':3},timeout=(8,30)).json()
        if obj.get('error'):
            return 0,'Sample query rejected: '+str(obj['error'])[:200]
        records=obj.get('features',[])
        if not isinstance(records,list):return 0,'Missing features array'
        keys=source.get('key_fields') or []
        if records and not any(any(str((x.get('attributes') or {}).get(k) or '').strip() for k in keys) for x in records):
            return len(records),'Configured record key is absent/empty in sample'
        return len(records),''
    except Exception as exc:
        return 0,type(exc).__name__+': '+str(exc)[:180]

def inspect(source):
    http=Http()
    row=audit_one(source,http)
    n,problem=assess_record_sample(source,http) if row['result']!='BLOCKED' else (0,'Skipped after metadata/query failure')
    row['sample_count']=n;row['sample_issue']=problem
    row['licence_clearance']='NOT_VERIFIED_FOR_COMMERCIAL_REDISTRIBUTION'
    if problem and row['result']=='TECHNICAL_CHECK_PASSED':row['result']='REVIEW'
    return row

def make_html(rows,path):
    css="body{font:14px system-ui,Segoe UI,sans-serif;margin:30px auto;max-width:1250px;line-height:1.55;color:#243045;padding:0 16px}table{border-collapse:collapse;width:100%;font-size:12px}td,th{padding:9px;text-align:left;border-bottom:1px solid #dde1e8;vertical-align:top}th{background:#f0f3f8} .ok{color:#087a53;font-weight:bold}.review{color:#875600;font-weight:bold}.bad{color:#b32424;font-weight:bold} .note{background:#f3f5f8;padding:12px;border-radius:6px}"
    escape=lambda x:html.escape(str(x or ''))
    body=[]
    for row in rows:
        state=row['result']; cl='ok' if state=='TECHNICAL_CHECK_PASSED' else 'bad' if state=='BLOCKED' else 'review'
        cells=[row['region'],row['id'],row['result'],row['full_count'],row['recent_count'],row['sample_count'],row['issues'],row['sample_issue']]
        body.append('<tr>'+''.join('<td class="'+cl+'">'+escape(v)+'</td>' if i==2 else '<td>'+escape(v)+'</td>' for i,v in enumerate(cells))+'</tr>')
    labels=['Region','Source','Technical status','Records','Last 30d','Sample','Issues','Sample check']
    page='<!doctype html><meta charset="utf-8"><title>Southern Ontario Collector Audit</title><style>'+css+'</style><h1>Southern Ontario batch readiness</h1><p class="note">Read-only diagnostics. Technical pass is NOT permission to redistribute. No data source was enabled, no full import was run, and the working database was not modified. Check licensing before commercial sale.</p><p>'+str(len(rows))+' staged ArcGIS sources checked.</p><table><thead><tr>'+''.join('<th>'+x+'</th>' for x in labels)+'</tr></thead><tbody>'+''.join(body)+'</tbody></table>'
    path.write_text(page,encoding='utf-8')

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workers',type=int,default=4,help='Concurrent independent source probes (default 4)')
    p.add_argument('--source',action='append',help='Limit to a configured source ID')
    args=p.parse_args(argv)
    all_sources=json.loads((ROOT/'config'/'sources.json').read_text(encoding='utf-8'))
    sources=[s for s in all_sources if s.get('collector')=='arcgis' and not s.get('enabled') and s.get('mode')!='backfill']
    if args.source:
        unknown=set(args.source)-{s['id'] for s in sources}
        if unknown:p.error('Unknown or nonstaged ArcGIS source(s): '+', '.join(sorted(unknown)))
        sources=[s for s in sources if s['id'] in args.source]
    print(f'Checking {len(sources)} staged sources in parallel (read-only).',flush=True)
    results={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,min(args.workers,8))) as pool:
        futures={pool.submit(inspect,s):s['id'] for s in sources}
        for fut in concurrent.futures.as_completed(futures):
            sid=futures[fut]
            try:row=fut.result()
            except Exception as exc:
                row={'id':sid,'region':'','enabled':False,'result':'BLOCKED','full_count':'','recent_count':'','issues':str(exc),'timestamp':'','sample_count':0,'sample_issue':'','licence_clearance':'NOT_VERIFIED'}
            results[sid]=row
            print(f'[{len(results)}/{len(sources)}] {sid}: {row["result"]} count={row["full_count"]} recent={row["recent_count"]} {row["issues"]}',flush=True)
    rows=[results[s['id']] for s in sources]
    with (ROOT/'SOUTHERN_ONTARIO_LIVE_AUDIT.csv').open('w',newline='',encoding='utf-8-sig') as handle:
        writer=csv.DictWriter(handle,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
    make_html(rows,ROOT/'SOUTHERN_ONTARIO_LIVE_AUDIT.html')
    summary={x:sum(r['result']==x for r in rows) for x in ('TECHNICAL_CHECK_PASSED','REVIEW','BLOCKED')}
    print('\nAudit complete:',summary,'\nOpen SOUTHERN_ONTARIO_LIVE_AUDIT.html',flush=True)
    return 0 # Source failures appear in report; do not prevent other sources finishing.

if __name__=='__main__':raise SystemExit(main())
