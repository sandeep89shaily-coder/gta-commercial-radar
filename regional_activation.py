"""One-click isolated regional rollout. Never modifies the previous installation.
Runs source-limited baseline collection in a SQLite backup; produces per-source outcomes.
Operational state is pilot/review only until source licences and freshness are approved.
"""
from pathlib import Path
import csv, json, os, sqlite3, subprocess, sys, datetime

HERE=Path(__file__).resolve().parent
SOURCE_FILE=HERE/'config'/'sources.json'
DATA=HERE/'data'
REPORT=HERE/'REGIONAL_IMPORT_REPORT.csv'


def integrity(db):
    c=sqlite3.connect('file:'+db.resolve().as_posix()+'?mode=ro',uri=True)
    try:
        check=c.execute('PRAGMA quick_check').fetchone()[0]
        count=c.execute('SELECT COUNT(DISTINCT source_id) FROM records_current WHERE active=1').fetchone()[0]
        return check,count
    finally:c.close()


def find_source():
    root=HERE.parent
    names=['gta_commercial_radar_v06_easy_setup','gta_commercial_radar_v06_integrated','gta_commercial_radar_v06_multifeed_merged']
    options=[]
    for name in names:
        db=root/name/'data'/'radar.sqlite'
        if db.exists():
            try:
                check,n=integrity(db)
                if check=='ok' and n>=8:options.append((n,db))
            except sqlite3.Error:pass
    return max(options,default=(0,None))[1]


def safe_copy(db):
    DATA.mkdir(exist_ok=True)
    target=DATA/'radar.sqlite'
    if target.exists():
        check,n=integrity(target)
        if check!='ok' or n<8:raise RuntimeError('Existing destination database needs manual review; no overwrite performed')
        print('Using existing, intact isolated database, sources=',n,flush=True)
        return
    tmp=DATA/'radar.sqlite.copying'
    if tmp.exists():raise RuntimeError('Unfinished database copy found; no overwrite performed')
    print('Creating separate SQLite backup; original stays untouched.',flush=True)
    try:
        source=sqlite3.connect('file:'+db.resolve().as_posix()+'?mode=ro',uri=True)
        try:
            dest=sqlite3.connect(tmp)
            try:source.backup(dest)
            finally:dest.close()
        finally:source.close()
        check,n=integrity(tmp)
        if check!='ok' or n<8:raise RuntimeError('Copied database did not pass integrity/population check')
        tmp.rename(target)
    finally:
        if tmp.exists():tmp.unlink()


def classify_result(exit_code, log_text):
    """Use the collector's actual outcome, not its exit status alone.

    main.py currently returns code 2 for a not-due scheduled snapshot. That
    is expected and must not be counted as an import failure.
    """
    import re
    if re.search(r'SKIPPED: scheduled snapshot not yet due', log_text, re.I):
        return 'SKIPPED_NOT_DUE', 'Scheduled snapshot not due; existing records preserved'
    if exit_code == 0 and 'Finished. Open:' in log_text and re.search(r'->\s*(?:BASELINE|DIFF)/', log_text):
        return 'IMPORTED', 'Source poll completed and records reconciled'
    return 'FAILED', 'Collector returned code '+str(exit_code)+'; review source log'


def summarize(records):
    from collections import Counter
    c=Counter(r['result'] for r in records)
    return c


def run():
    print('Southern Ontario regional batch: isolated installation',flush=True)
    if not (DATA/'radar.sqlite').exists():
        db=find_source()
        if not db:raise RuntimeError('Could not find intact v06_easy_setup database beside this folder. Original folders untouched.')
        print('Established database:',db.parent.parent.name,flush=True)
        safe_copy(db)
    else:
        safe_copy(None)
    sources=json.loads(SOURCE_FILE.read_text('utf-8'))
    staged=[s for s in sources if s.get('collector')=='arcgis' and not s.get('enabled') and s.get('mode')!='backfill']
    print('Testing',len(staged),'regional sources against isolated database. This may take time.',flush=True)
    old={}
    if REPORT.exists():
        with REPORT.open(newline='',encoding='utf-8-sig') as f:
            old={r['source_id']:r for r in csv.DictReader(f)}
    records=[]
    for i,s in enumerate(staged,1):
        sid=s['id']
        if old.get(sid,{}).get('result') in ('IMPORTED','SKIPPED_NOT_DUE'):
            records.append(old[sid]);print(f'[{i}/{len(staged)}] {sid}: previously imported',flush=True);continue
        print(f'[{i}/{len(staged)}] {sid}: querying municipal source...',flush=True)
        logpath=HERE/'logs'/f'{sid}.log';logpath.parent.mkdir(exist_ok=True)
        with logpath.open('w',encoding='utf-8') as log:
            try:
                p=subprocess.run([sys.executable,'main.py','poll','--source',sid],cwd=HERE,stdout=log,stderr=subprocess.STDOUT,timeout=2400)
                result, detail = classify_result(p.returncode, logpath.read_text(encoding='utf-8', errors='replace'))
            except subprocess.TimeoutExpired:
                result='FAILED';detail='Time limit exceeded; see log; source not enabled'
        r={'source_id':sid,'region':s.get('region',''),'result':result,'detail':detail,'log_file':str(logpath.relative_to(HERE)), 'commercial_reuse':'NOT_YET_VERIFIED'}
        records.append(r)
        with REPORT.open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=['source_id','region','result','detail','log_file','commercial_reuse'])
            writer.writeheader();writer.writerows(records)
        print(' ',result,'(log:',logpath.name,')',flush=True)
    counts=summarize(records)
    print(f"Complete: {counts['IMPORTED']} imported, {counts['SKIPPED_NOT_DUE']} safely skipped, {counts['FAILED']} failed (of {len(staged)}). Report: {REPORT.name}",flush=True)
    print('New feeds remain separate from unattended polling until freshness and licensing are checked.',flush=True)
    print('Original v0.6 database has not been changed.',flush=True)
    return 0

if __name__=='__main__':
    try:raise SystemExit(run())
    except Exception as exc:
        print('SAFE STOP:',str(exc),flush=True)
        raise SystemExit(2)
