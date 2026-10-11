"""Read-only, evidence-first GTA Radar operations and intelligence dashboard."""
from __future__ import annotations
import argparse,csv,html,json,sqlite3
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parent
def esc(x):return html.escape(str(x if x is not None else ''),quote=True)
def connection(path):
 if not path.is_file():return None
 return sqlite3.connect('file:'+path.resolve().as_posix()+'?mode=ro',uri=True)
def rows(db,sql,args=()):
 try:
  return [dict(zip([x[0] for x in cur.description],r)) for cur in [db.execute(sql,args)] for r in cur.fetchall()]
 except sqlite3.DatabaseError:return []
def safe_url(url):
 from urllib.parse import urlsplit
 u=str(url or '')
 try:
  p=urlsplit(u)
  return u if p.scheme in ('https','http') and p.hostname and not p.username and not p.password else ''
 except ValueError:return ''
def brampton(data):
 db=connection(data/'brampton_sources.sqlite')
 if db is None:return {'available':False,'sources':[],'changes':[],'progress':[],'links':[]}
 try:
  sources=rows(db,"""SELECT s.id,s.department,s.title,s.url,s.access_status,
   COALESCE((SELECT COUNT(*) FROM records x WHERE x.source_id=s.id),0) AS records,
   (SELECT ended FROM runs r WHERE r.source_id=s.id ORDER BY id DESC LIMIT 1) AS last_run,
   (SELECT detail FROM runs r WHERE r.source_id=s.id ORDER BY id DESC LIMIT 1) AS detail
   FROM sources s ORDER BY s.department,s.title""")
  changes=rows(db,"""SELECT v.source_id,v.record_id,v.observed_at,v.json
    FROM versions v ORDER BY v.id DESC LIMIT 120""")
  progress=rows(db,"SELECT source_id,last_oid,total_estimate,backfilled,updated_at FROM arcgis_progress ORDER BY source_id")
  evidence=[]
  for r in changes:
   try: obj=json.loads(r.pop('json') or '{}')
   except (TypeError,ValueError):obj={}
   if not isinstance(obj,dict):obj={}
   r['evidence_url']=safe_url(obj.get('source_url') or obj.get('url') or obj.get('parent_url'))
   r['title']=str(obj.get('label') or obj.get('text') or obj.get('fields',{}).get('organization_name') if isinstance(obj.get('fields',{}),dict) else obj.get('label') or '')[:110]
  for r in rows(db,"SELECT source_id,record_id,json FROM records WHERE record_id LIKE 'LINK:%' OR record_id LIKE 'DOCUMENT:%' ORDER BY last_seen DESC LIMIT 150"):
   try:o=json.loads(r['json'])
   except (TypeError,ValueError):continue
   if isinstance(o,dict) and safe_url(o.get('url')):evidence.append({'source_id':r['source_id'],'url':o['url'],'label':str(o.get('label') or r['record_id'])[:150]})
  return {'available':True,'sources':sources,'changes':changes,'progress':progress,'links':evidence}
 finally:db.close()
def business(data):
 db=connection(data/'business_discovery.sqlite')
 if db is None:return {'available':False,'runs':[],'changes':[]}
 try:
  return {'available':True,'runs':rows(db,'SELECT source_id,last_checked,last_success,record_count,status,error FROM runs ORDER BY source_id'),
    'changes':rows(db,'SELECT source_id,source_key,observed_at,event_type,event_date,company_name,address,city,evidence_url FROM events ORDER BY id DESC LIMIT 100')}
 finally:db.close()
def municipal(data):
 db=connection(data/'radar.sqlite')
 if db is None:return {'available':False,'counts':[]}
 try:
  return {'available':True,'counts':rows(db,'SELECT source_id,COUNT(*) AS records FROM records_current WHERE active=1 GROUP BY source_id ORDER BY records DESC LIMIT 100')}
 finally:db.close()
def inferred_relationships(data,limit=50):
 """Identity candidates only; exact normalized address match is NOT a verified relationship."""
 b=connection(data/'business_discovery.sqlite')
 m=connection(data/'brampton_sources.sqlite')
 if b is None or m is None:
  if b:b.close()
  if m:m.close()
  return []
 try:
  businesses=rows(b,'SELECT source_id,source_key,company_name,address,city FROM observations WHERE address IS NOT NULL AND TRIM(address)<>\'\' LIMIT 10000')
  targets=rows(m,"SELECT source_id,record_id,json FROM records WHERE source_id LIKE 'brampton_lic_%' LIMIT 10000")
  import re
  norm=lambda a:re.sub(r'[^a-z0-9]','',str(a or '').lower())
  by_address={}
  for o in businesses:
   addr=norm(o['address'])
   if len(addr)>=12:by_address.setdefault(addr,[]).append(o)
  result=[]
  for t in targets:
   try:payload=json.loads(t['json'] or '{}')
   except (ValueError,TypeError):continue
   if not isinstance(payload,dict):continue
   fields=payload.get('fields',{})
   if not isinstance(fields,dict):continue
   addr=norm(fields.get('business_address'))
   if addr not in by_address:continue
   for o in by_address[addr][:2]:
    result.append({'business':o['company_name'],'licence':fields.get('organization_name') or fields.get('operating_name'),'address':fields.get('business_address'),'left_source':o['source_id'],'right_source':t['source_id'],'classification':'UNVERIFIED CANDIDATE: exact normalized address; may be shared premises'})
    if len(result)>=limit:return result
  return result
 finally:b.close();m.close()
CSS="""body{font:14px system-ui,Segoe UI,Arial;margin:28px auto;padding:0 18px;max-width:1350px;color:#172736;background:#f6f8fa}h1{margin-bottom:4px}h2{margin-top:32px}small,.muted{color:#627386}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:20px 0}.metric{background:white;border:1px solid #dbe1e8;border-radius:10px;padding:18px}.metric strong{display:block;font-size:24px}table{border-collapse:collapse;width:100%;background:white;font-size:12px}td,th{padding:9px 8px;border-bottom:1px solid #edf0f3;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#eaf0f4}a{color:#14548c}.note{padding:12px;border-left:4px solid #bb8740;background:#fff7e8}.scroll{overflow-x:auto}"""
def table(columns,items):
 out=['<div class="scroll"><table><tr>']+['<th>'+esc(label)+'</th>' for key,label in columns]+['</tr>']
 for row in items:
  out.append('<tr>')
  for key,label in columns:
   val=row.get(key,'')
   if key in ('url','evidence_url'):
    url=safe_url(val);val='<a href="'+esc(url)+'" rel="noopener noreferrer" target="_blank">Official evidence</a>' if url else '—'
   else:val=esc(str(val)[:280])
   out.append('<td>'+val+'</td>')
  out.append('</tr>')
 return ''.join(out)+'</table></div>'
def render(data,out):
 B=brampton(data);C=business(data);M=municipal(data)
 relations=inferred_relationships(data)
 statuses={}
 for r in B['sources']:statuses[r['access_status'] or 'UNKNOWN']=statuses.get(r['access_status'] or 'UNKNOWN',0)+1
 count=sum(r['records'] for r in B['sources'])
 total=sum(r.get('records',0) for r in M['counts'])
 metrics=[('Brampton tracked sources',len(B['sources'])),('Brampton stored records',count),('Other active municipal records*',total),('Brampton source errors',statuses.get('ERROR',0)),('Unverified address matches',len(relations))]
 parts=['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GTA Radar — Operations and Evidence</title><style>',CSS,'</style></head><body><h1>GTA Radar — Operations &amp; Evidence</h1><p class="muted">Generated ',esc(datetime.now(timezone.utc).isoformat(timespec='seconds')),' UTC · Offline, read-only database snapshot</p><div class="note">Public records and document observations are <b>evidence</b>. Address matches are <b>UNVERIFIED research candidates</b>, never proof of common ownership or a commercial opportunity. Source availability does not establish reuse rights. Counts do not imply unique entities or newly published events.</div><div class="grid">']
 for label,value in metrics:parts.extend(['<div class="metric"><span>',esc(label),'</span><strong>',esc(value),'</strong></div>'])
 parts.append('</div><h2>Daily collection execution</h2>')
 manifest=data/'daily_run_manifest.json'
 if manifest.is_file():
  try:
   latest=json.loads(manifest.read_text(encoding='utf-8'))
   parts.append('<p>Last run: '+esc(latest.get('started_at'))+' · Status: <strong>'+esc(latest.get('status'))+'</strong></p>')
   parts.append(table([('step','Step'),('status','Result'),('finished_at','Finished'),('exit_code','Exit code')],latest.get('steps',[])))
  except (ValueError,OSError,TypeError):parts.append('<p>Run manifest unreadable; validate scheduled collection.</p>')
 else:parts.append('<p>No completed daily run manifest yet. Scheduled execution unverified.</p>')
 if (data/'toronto_department_coverage.html').is_file():
  parts.append('<h2>Toronto — Department and Source Coverage</h2>')
  parts.append('<p><a href="toronto_department_coverage.html">Open Toronto department and source audit</a> — identify missing priority CKAN feeds, publishing divisions, and configured collector health. <a href="toronto_gap_queue.csv">CSV research queue</a>. These are candidates, not confirmed records or opportunities.</p>')
  if (data/'toronto_candidate_validation.json').is_file():
   parts.append('<p><a href="toronto_candidate_validation.json">Latest Toronto priority-source schema probes (JSON)</a> — metadata and field names only; not confirmation of a working collector.</p>')
  if (data/'toronto_catalog_change_history.jsonl').is_file():
   parts.append('<p><a href="toronto_catalog_change_history.jsonl">Toronto CKAN catalogue publication history (JSONL)</a> — newly listed packages and metadata changes, not new businesses or permits.</p>')
 if (data/'toronto_priority_sources.sqlite').is_file():
  tdb=connection(data/'toronto_priority_sources.sqlite')
  if tdb:
   try:
    parts.append('<h2>Toronto — Procurement, Roads and Council Record Archive</h2>')
    parts.append('<p>Complete public dataset snapshots and version observations are stored separately. Baselines are not new business events; absent rows are not interpreted as deletions.</p>')
    parts.append(table([('source_id','Source'),('observed_at','Latest check'),('status','Result'),('fetched','Records checked'),('created','New observations'),('updated','Modified')],rows(tdb,'SELECT source_id,observed_at,status,fetched,created,updated FROM runs ORDER BY id DESC LIMIT 20')))
    if (data/'toronto_priority_changes_REVIEW_ONLY.csv').is_file():
     parts.append('<p><a href="toronto_priority_changes_REVIEW_ONLY.csv">Dataset-level changes (review only)</a> — not yet independently qualified commercial opportunities.</p>')
    if (data/'toronto_service_provider_signals_REVIEW_ONLY.csv').is_file():
     parts.append('<p><a href="toronto_service_provider_signals_REVIEW_ONLY.csv">Toronto provider-category research signals</a> — based only on post-baseline changes, with source evidence, commercial tags and independent qualification required.</p>')
   finally:tdb.close()
 if (data/'mississauga_planning_sources.sqlite').is_file():
  mdb=connection(data/'mississauga_planning_sources.sqlite')
  if mdb:
   try:
    parts.append('<h2>Mississauga — Site Plans and Rezoning Applications</h2>')
    parts.append('<p>Separate weekly planning archive. First observations are baselines; subsequent changes are research-only. Incomplete GIS downloads are never treated as deletions.</p>')
    parts.append(table([('source_id','Source'),('observed_at','Checked'),('status','Result'),('fetched','Fetched'),('created','First-seen records'),('updated','Modified records')],rows(mdb,'SELECT source_id,observed_at,status,fetched,created,updated FROM runs ORDER BY id DESC LIMIT 20')))
    if (data/'mississauga_planning_changes_REVIEW_ONLY.csv').is_file():
     parts.append('<p><a href="mississauga_planning_changes_REVIEW_ONLY.csv">Planning record changes — research only</a></p>')
   finally:mdb.close()
 parts.append('<h2>1 · Source health — Brampton</h2>')
 parts.append(table([('department','Department'),('title','Source'),('access_status','Status'),('records','Stored'),('last_run','Last run'),('detail','Last result'),('url','Official source')],B['sources']))
 parts.append('<h2>2 · Collection checkpoints</h2>')
 parts.append(table([('source_id','Source'),('last_oid','Last ID'),('total_estimate','Estimated total'),('backfilled','Full pass done'),('updated_at','Checkpoint time')],B['progress']))
 parts.append('<h2>3 · Recorded changes and versions (not necessarily fresh events)</h2>')
 parts.append(table([('observed_at','Observed at'),('source_id','Source'),('record_id','Record'),('title','Extract'),('evidence_url','Evidence')],B['changes'][:80]))
 parts.append('<h2>4 · Public documents &amp; provenance</h2>')
 parts.append(table([('source_id','Source'),('label','Linked publication'),('url','Source link')],B['links'][:100]))
 parts.append('<h2>5 · Business source health</h2>')
 parts.append(table([('source_id','Source'),('status','Status'),('record_count','Records'),('last_success','Last success'),('error','Error')],C['runs']))
 parts.append('<h2>6 · Reported business events</h2>')
 parts.append(table([('observed_at','Observed'),('company_name','Entity'),('event_type','Event'),('event_date','Event date'),('source_id','Source'),('evidence_url','Evidence')],C['changes'][:60]))
 parts.append('<h2>7 · Experimental relationship candidates — NOT verified</h2>')
 parts.append(table([('business','Business record'),('licence','Licence record'),('address','Shared address'),('classification','Confidence statement'),('left_source','Record source'),('right_source','Licence source')],relations))
 parts.append('<h2>8 · Information product development</h2><p>Collection outputs are evidence, not an automatically sellable product. Derived products require entity resolution, timestamps, source licensing review, provenance, uncertainty, and customer-specific validation. No revenue or verified customer value is asserted here.</p>')
 parts.append('<p class="muted">*Municipal summary covers up to 100 grouped sources, not every possible source. Empty sections indicate missing or unsupported local data. No SQLite database was modified.</p></body></html>')
 out.parent.mkdir(parents=True,exist_ok=True);out.write_text(''.join(parts),encoding='utf-8')
 return {'output':str(out),'brampton_sources':len(B['sources']),'brampton_records':count,'candidate_links':len(relations)}
def main(argv=None):
 parser=argparse.ArgumentParser();parser.add_argument('--data-dir',type=Path,default=ROOT/'data');parser.add_argument('--output',type=Path)
 args=parser.parse_args(argv);output=args.output or args.data_dir/'radar_intelligence_dashboard.html'
 print(json.dumps(render(args.data_dir,output),indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
