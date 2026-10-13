"""Safe one-click setup and orchestration for nontechnical Windows users.
Only creates files under this version's data directory; never modifies old versions.
"""
from pathlib import Path
from contextlib import closing
import csv, os, shutil, sqlite3, subprocess, sys, webbrowser
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
OLD_NAMES=('GTA_RADAR_SMART_PRIORITY','GTA_RADAR_LEAD_MATURATION','GTA_RADAR_PEEL_INTEGRATED','GTA_RADAR_INTELLIGENCE_ONE_CLICK','gta_commercial_radar_v07_integrated_candidate','gta_commercial_radar_v07_rollout_corrected','gta_commercial_radar_v06_easy_setup','gta_commercial_radar_v06_integrated')

def find_old():
    roots=[ROOT.parent,ROOT.parent.parent,Path.home()/'Desktop'/'new data',Path.home()/'OneDrive'/'Desktop'/'new data']
    found=[]
    for base in roots:
        for name in OLD_NAMES:
            for p in (base/name/'data'/'radar.sqlite',base/name/'radar.sqlite'):
                if p.is_file() and p.resolve()!= (DATA/'radar.sqlite').resolve():
                    found.append(p)
    # Prefer existing integrated v07 over dated older versions; skip incomplete databases
    return found[0] if found else None

def safe_backup(source,dest):
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():
        print('Previously prepared Radar data found. Leaving it unchanged.');return True
    temp=dest.with_suffix('.sqlite.incomplete')
    if temp.exists():
        # Only remove this launcher's own unfinished temporary file, never an old database.
        try:
            temp.unlink()
            print('Cleared a previous unfinished temporary copy automatically.')
        except OSError as e:
            print('Temporary copy is busy. Close any other Radar window and try again:',e)
            return False
    print('Found your previous database:',source.parent.parent.name)
    print('Making a SAFE COPY. The original will not be modified...')
    try:
        # sqlite3.Connection context managers commit/rollback but DO NOT close files.
        # Windows refuses the final rename while either connection holds the file open.
        with closing(sqlite3.connect(f'file:{source.as_posix()}?mode=ro',uri=True)) as a:
            with closing(sqlite3.connect(temp)) as b:
                a.backup(b)
                if b.execute('PRAGMA quick_check').fetchone()[0]!='ok':
                    raise ValueError('Database integrity check failed')
        # At this point both SQLite connections are actually closed.
        temp.replace(dest)
        print('Database copy completed.')
        return True
    except Exception as e:
        print('Database copy did not complete:',e)
        try:
            temp.unlink(missing_ok=True)
        except PermissionError:
            print('Temporary file is still locked. Close other Radar windows and retry.')
        return False

def command(*args):
    result=subprocess.run([sys.executable,*args],cwd=ROOT,check=False)
    return result.returncode==0

def main():
    print('\n===== GTA COMMERCIAL RADAR - EASY START =====\n')
    DATA.mkdir(exist_ok=True)
    if not (DATA/'radar.sqlite').exists():
        old=find_old()
        if old:
            if not safe_backup(old,DATA/'radar.sqlite'):return 1
        else:
            print('Could not find a previously collected Radar database automatically.')
            print('Your original files are safe. Please share a screenshot of this message.')
            return 2
    if not (DATA/'business_discovery.sqlite').exists():
        print('\nBusiness discovery has not run in this folder yet.')
        print('The first run establishes historical baselines, not fresh leads.')
        print('Starting business discovery; large federal files can take time...')
        if not command('business_discovery.py','run'):
            print('One or more business sources may need attention; continuing with available data.')
    print('\nCollecting additional Brampton official sources...')
    command('brampton_network.py')
    print('\nChecking Peel development and infrastructure pilot feeds...')
    command('peel_pilot.py')
    print('\nPreparing leads and investigating queue...')
    command('business_discovery.py','export')
    command('opportunity_engine.py','--days','2')
    command('lead_maturation.py')
    command('first_ten_leads.py')
    print('Checking evidence readiness for the first 3 opportunities (free dry run)...')
    command('pilot_evidence.py')
    command('lead_research.py')
    queue=DATA/'lead_research_REVIEW_ONLY.csv'
    with queue.open(encoding='utf-8-sig',newline='') as f:
        count=sum(1 for _ in csv.DictReader(f))
    print('Lead candidates queued:',count)
    if count==0:
        print('No sufficiently recent dated records are in the queue. Old records remain archived.')
        print('No paid search requests were made.')
    else:
        print('Candidate queue is ready. Only DeepSeek will be used for paid AI analysis.')
        print('To enable automatic DeepSeek analysis, run INSTALL_DAILY.bat once.')
    for output in ('first_10_leads_dashboard.html','brampton_collection_report.html','investigation_dashboard.html','opportunity_dashboard.html','lead_research_dashboard.html','business_dashboard.html'):
        p=DATA/output
        if p.exists():
            print('Results:',p)
            if p.suffix=='.html':webbrowser.open(p.as_uri());break
    print('\nFinished. The old Radar folders and databases were not changed.')
    return 0
if __name__=='__main__':raise SystemExit(main())
