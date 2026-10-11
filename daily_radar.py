"""Unattended daily run; optional DeepSeek no other paid API."""
import subprocess,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def cmd(*args):
    p=subprocess.run([sys.executable,*args],cwd=ROOT,check=False)
    return p.returncode

def main():
    (ROOT/'data').mkdir(exist_ok=True)
    # Existing database only; schedule does not re-run first-time backup or open browsers.
    if not (ROOT/'data'/'radar.sqlite').is_file():
        print('First-time setup required. Run START_RADAR.bat once.');return 1
    print('Daily collector poll...')
    cmd('main.py','poll')
    print('Brampton departmental sources (separate evidence history)...')
    cmd('brampton_network.py')
    print('Peel pilot public project sources (separate history)...')
    cmd('peel_pilot.py')
    print('Daily business discovery...')
    cmd('business_discovery.py','run')
    cmd('business_discovery.py','export')
    cmd('opportunity_engine.py','--days','2')
    cmd('lead_maturation.py')
    cmd('lead_research.py')
    # Search API disabled: no Brave/OpenAI requirements.
    # DeepSeek processes only locally available evidence and never invents contacts.
    ai_result=cmd('deepseek_daily.py')
    # Reporting is offline/read-only and must run even if optional AI fails.
    dashboard_result=cmd('intelligence_dashboard.py')
    readiness_result=cmd('production_readiness.py')
    if dashboard_result: print('WARNING: consolidated dashboard generation failed')
    if readiness_result: print('WARNING: readiness report found a database failure')
    return ai_result or dashboard_result or readiness_result
if __name__=='__main__':raise SystemExit(main())
