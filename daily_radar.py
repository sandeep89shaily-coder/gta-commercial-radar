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
    return cmd('deepseek_daily.py')
if __name__=='__main__':raise SystemExit(main())
