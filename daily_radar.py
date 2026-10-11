"""Unattended daily collection with per-step outcomes and honest failure status."""
from __future__ import annotations
import json,subprocess,sys,traceback
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
def stamp():return datetime.now(timezone.utc).isoformat(timespec='seconds')
STEPS=[
 ('municipal_poll',('main.py','poll'),True),
 ('toronto_catalog_discovery',('toronto_catalog_audit.py',),False),
 ('toronto_coverage_report',('toronto_coverage.py',),False),
 ('toronto_schema_validation',('toronto_source_validator.py',),False),
 ('toronto_public_records',('toronto_public_records.py',),False),
 ('toronto_research_signals',('toronto_signals.py',),False),
 ('mississauga_catalog_discovery',('mississauga_catalog_audit.py',),False),
 ('mississauga_planning_archive',('mississauga_planning_records.py',),False),
 ('mississauga_procurement_public',('mississauga_procurement.py',),False),
 ('brampton',('brampton_network.py',),True),
 ('peel',('peel_pilot.py',),True),
 ('business_collection',('business_discovery.py','run'),True),
 ('business_export',('business_discovery.py','export'),False),
 ('opportunity_engine',('opportunity_engine.py','--days','2'),False),
 ('lead_maturation',('lead_maturation.py',),False),
 ('lead_research',('lead_research.py',),False),
 ('optional_deepseek',('deepseek_daily.py',),False),
 ('intelligence_dashboard',('intelligence_dashboard.py',),True),
 ('readiness_report',('production_readiness.py',),False),
 ('health_report',('radar_health.py',),True),
 ('relationship_candidates',('entity_intelligence.py',),False),
]
def main():
 DATA.mkdir(exist_ok=True)
 manifest={'started_at':stamp(),'finished_at':None,'status':'RUNNING','steps':[]}
 destination=DATA/'daily_run_manifest.json'
 def save():
  temp=destination.with_suffix('.json.tmp')
  temp.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
  temp.replace(destination)
 save()
 if not (DATA/'radar.sqlite').is_file():
  manifest['status']='FAILED';manifest['finished_at']=stamp()
  manifest['steps'].append({'step':'preflight','status':'FAILED','exit_code':1,'detail':'radar.sqlite missing'})
  save();print('Radar database missing; no collectors started',flush=True);return 1
 failed_required=False
 for name,args,required in STEPS:
  print('Radar:',name,flush=True);began=stamp()
  try:
   exit_code=subprocess.run([sys.executable,*args],cwd=ROOT,check=False).returncode
  except Exception as exc:
   exit_code=1;print('Step failed:',name,str(exc),flush=True)
  manifest['steps'].append({'step':name,'started_at':began,'finished_at':stamp(),'status':'SUCCESS' if exit_code==0 else 'FAILED','exit_code':exit_code,'required':required})
  if required and exit_code:failed_required=True
  save()
 manifest['finished_at']=stamp()
 manifest['status']='FAILED' if failed_required else ('PARTIAL' if any(x['exit_code'] for x in manifest['steps']) else 'SUCCESS')
 save()
 print('Radar daily run:',manifest['status'],'|',destination,flush=True)
 return 1 if failed_required else 0
if __name__=='__main__':raise SystemExit(main())
