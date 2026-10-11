"""Read-only local daily health and verified-delta summary.
No inference of source publication date from first observation.
"""
import argparse,json,sqlite3
from pathlib import Path
from datetime import datetime,timezone,timedelta
from intelligence_dashboard import connection,rows
ROOT=Path(__file__).resolve().parent
def dt(s):
 try:
  v=datetime.fromisoformat(str(s).replace('Z','+00:00'))
  return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)
 except (ValueError,TypeError):return None
def health(data,now=None):
 now=now or datetime.now(timezone.utc)
 result={'generated_at':now.isoformat(),'status':'OK','issues':[],'brampton':{},'fresh_changes':[],'historical_observations':0}
 def issue(kind,message):
  result['issues'].append({'type':kind,'message':message})
 b=connection(data/'brampton_sources.sqlite')
 if b is None:issue('MISSING','Brampton database unavailable')
 else:
  try:
   sources=rows(b,'SELECT id,department,access_status,last_checked,frequency FROM sources')
   last=rows(b,'SELECT source_id,MAX(ended) AS ended FROM runs GROUP BY source_id')
   latest={r['source_id']:dt(r['ended']) for r in last}
   for s in sources:
    st=s['access_status'] or 'UNKNOWN'
    if st=='ERROR':issue('SOURCE_ERROR',s['id'])
    t=latest.get(s['id'])
    # Only flag stale when the source has completed a run before.
    hours=48 if s['frequency']=='daily' else 240
    if t and now-t>timedelta(hours=hours):issue('STALE_SOURCE',s['id']+' last run '+t.isoformat())
   result['brampton']={'sources':len(sources),'errors':sum(s['access_status']=='ERROR' for s in sources),'last_run':max((t for t in latest.values() if t),default=None)}
   if result['brampton']['last_run']:result['brampton']['last_run']=result['brampton']['last_run'].isoformat()
   # Version count is historical state, not necessarily a public event.
   from_time=(now-timedelta(days=1)).isoformat()
   result['historical_observations']=rows(b,'SELECT COUNT(*) AS n FROM versions WHERE observed_at>=?',(from_time,))[0]['n']
   # A version is an independently observed change only when it has a previous version.
   # New records are excluded here because their publication date is not verified.
   candidates=rows(b,"""SELECT v.source_id,v.record_id,v.observed_at,v.json
      FROM versions v WHERE v.observed_at>=?
      AND EXISTS(SELECT 1 FROM versions earlier
                 WHERE earlier.source_id=v.source_id AND earlier.record_id=v.record_id
                   AND earlier.id<v.id) ORDER BY v.id DESC LIMIT 100""",(from_time,))
   for v in candidates:
    try:o=json.loads(v['json'])
    except (ValueError,TypeError):o={}
    result['fresh_changes'].append({'source_id':v['source_id'],'record_id':v['record_id'],
       'detected_at':v['observed_at'],'classification':'RECORD_CHANGED_NOT_PUBLICATION_DATE',
       'evidence_url':o.get('source_url') or o.get('url') or '' if isinstance(o,dict) else ''})
  finally:b.close()
 if result['issues']:result['status']='ATTENTION'
 return result
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument('--data-dir',type=Path,default=ROOT/'data')
 a=p.parse_args(argv);report=health(a.data_dir)
 output=a.data_dir/'radar_health.json';output.parent.mkdir(parents=True,exist_ok=True)
 output.write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
 print('Radar health:',report['status'],'| issues:',len(report['issues']),
       '| detected record changes:',len(report['fresh_changes']))
 print('Report:',output)
 return 0
if __name__=='__main__':raise SystemExit(main())
