"""Offline production readiness audit. Does not poll or mutate collection databases."""
import argparse,json,sqlite3,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
from intelligence_dashboard import connection,rows,brampton,business,municipal

ROOT=Path(__file__).resolve().parent
def audit(data):
 report={'checked_at':datetime.now(timezone.utc).isoformat(),'data_directory':str(data),
         'checks':[],'production_verified':False}
 def check(name,status,detail):
  report['checks'].append({'check':name,'status':status,'detail':detail})
 for name in ('radar.sqlite','brampton_sources.sqlite','business_discovery.sqlite'):
  path=data/name
  if not path.is_file():
   check(name,'MISSING','No local database; source is not verified');continue
  db=None
  try:
   db=connection(path)
   # sqlite integrity quick_check is read-only and runs without creating checkpoints.
   result=db.execute('PRAGMA quick_check(1)').fetchone()[0]
   check(name,'PASS' if result=='ok' else 'FAIL',result)
  except (sqlite3.DatabaseError,OSError) as exc:check(name,'FAIL',str(exc)[:250])
  finally:
   if db:db.close()
 b=brampton(data)
 if b['available']:
  sources=b['sources']
  failures=[x['id'] for x in sources if x['access_status']=='ERROR']
  check('brampton_source_health','WARN' if failures else 'PASS',
        str(len(sources))+' configured entries; '+str(len(failures))+' latest ERROR statuses')
  stamps=[x['last_run'] for x in sources if x.get('last_run')]
  newest=max(stamps) if stamps else None
  check('brampton_run_history','PASS' if newest else 'WARN','Most recent recorded run: '+str(newest or 'none'))
 else:check('brampton_source_health','MISSING','No Brampton source archive')
 c=business(data)
 if c['available']:
  check('business_discovery_health','WARN' if not c['runs'] else 'PASS',str(len(c['runs']))+' sources have run metadata')
 else:check('business_discovery_health','MISSING','No business archive')
 m=municipal(data)
 if m['available']:
  check('municipal_active_records','PASS' if m['counts'] else 'WARN',str(sum(r['records'] for r in m['counts']))+' active records across reported groups')
 else:check('municipal_active_records','MISSING','No municipal archive')
 # Snapshot validation cannot prove unattended scheduler execution or public endpoint coverage.
 check('scheduled_task_execution','UNVERIFIED','Requires Windows Task Scheduler last execution and live collector logs')
 check('live_official_sources','UNVERIFIED','Repository tests cannot validate public endpoint responses or coverage')
 return report
def main(argv=None):
 p=argparse.ArgumentParser()
 p.add_argument('--data-dir',type=Path,default=ROOT/'data')
 p.add_argument('--output',type=Path)
 a=p.parse_args(argv);report=audit(a.data_dir)
 dest=a.output or a.data_dir/'radar_readiness.json'
 dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps(report,indent=2))
 return 0 if not any(c['status']=='FAIL' for c in report['checks']) else 1
if __name__=='__main__':sys.exit(main())
