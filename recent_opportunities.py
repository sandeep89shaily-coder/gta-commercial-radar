"""Find genuinely recent dated business records even on initial database baseline.

Read-only toward existing Radar databases. Deduped follow-up queue is persisted
separately so daily overlapping windows do not repeatedly trigger investigations.
"""
import csv, json, sqlite3, hashlib, re
from pathlib import Path
from datetime import datetime, timezone, timedelta, date

ROOT=Path(__file__).resolve().parent
COLUMNS=['source_id','source_key','company_name','entity_name','address','city','industry','event_date','event_type','observed_at','buyer_categories','evidence_url','description','review_status','selection_reason']
EXCLUDED={'','unknown','none','n/a','not available','anonymous'}

def parse_date(raw):
    if raw is None:return None
    raw=str(raw).strip()
    if not raw:return None
    if raw.isdigit() and len(raw)>=12:
        try:return datetime.fromtimestamp(int(raw)/1000,timezone.utc).date()
        except (ValueError,OverflowError):return None
    try:return date.fromisoformat(raw[:10])
    except ValueError:return None

def identity(row):
    return hashlib.sha256('|'.join(str(row.get(k,'')).strip().lower() for k in ('source_id','source_key','event_date')).encode()).hexdigest()[:24]

def valid_name(name):
    return bool(name and str(name).strip().lower() not in EXCLUDED)

def collect(data,days=2,today=None,limit=250):
    today=today or datetime.now().astimezone().date()
    cutoff=today-timedelta(days=days)
    results=[]
    business=data/'business_discovery.sqlite'
    if business.exists():
        with sqlite3.connect(f'file:{business.as_posix()}?mode=ro',uri=True) as db:
            db.row_factory=sqlite3.Row
            try:
                for raw in db.execute('SELECT source_id,source_key,company_name,address,city,industry,event_date,event_type,observed_at FROM observations WHERE event_date IS NOT NULL AND event_date != ""'):
                    r=dict(raw);d=parse_date(r['event_date'])
                    if d is None or not cutoff<=d<=today or not valid_name(r['company_name']):continue
                    r.update(entity_name=r['company_name'],buyer_categories='commercial_insurance;accounting_payroll;it_telecom',evidence_url='',description=r.get('industry',''),review_status='UNVERIFIED_NOT_FOR_SALE',selection_reason='RECENT_SOURCE_DATE_FROM_BASELINE_OR_LATER')
                    results.append(r)
            except sqlite3.DatabaseError:pass
    radar=data/'radar.sqlite'
    if radar.exists():
        with sqlite3.connect(f'file:{radar.as_posix()}?mode=ro',uri=True) as db:
            db.row_factory=sqlite3.Row
            try:
                for raw in db.execute('SELECT source_id,record_key,source_date,normalized_json FROM records_current WHERE active=1 AND source_date IS NOT NULL AND source_date != "" AND source_date>=?',(cutoff.isoformat(),)):
                    d=parse_date(raw['source_date'])
                    if d is None or not cutoff<=d<=today:continue
                    try:p=json.loads(raw['normalized_json'])
                    except (ValueError,TypeError):continue
                    if p.get('commercial_relevance')=='LOW':continue
                    name=p.get('entity_name','');addr=p.get('address','')
                    if not valid_name(name) or not addr:continue
                    results.append(dict(source_id=raw['source_id'],source_key=raw['record_key'],company_name=name,entity_name=name,address=addr,city=p.get('region',''),industry='',event_date=d.isoformat(),event_type=p.get('event_type',''),observed_at='',buyer_categories='commercial_insurance;commercial_hvac;security_access',evidence_url=p.get('evidence_url',''),description=p.get('description',''),review_status='UNVERIFIED_NOT_FOR_SALE',selection_reason='RECENT_SOURCE_DATE_FROM_BASELINE_OR_LATER'))
            except sqlite3.DatabaseError:pass
    unique={identity(r):r for r in results}
    return sorted(unique.values(),key=lambda r:(r['event_date'],r['source_id'],r['source_key']),reverse=True)[:limit]

def export(data,days=2,today=None,limit=250):
    data.mkdir(parents=True,exist_ok=True)
    matches=collect(data,days,today,limit)
    path=data/'recent_opportunities_REVIEW_ONLY.csv'
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=COLUMNS,extrasaction='ignore');w.writeheader();w.writerows(matches)
    queue_db=sqlite3.connect(data/'recent_selection_history.sqlite')
    try:
        queue_db.execute('CREATE TABLE IF NOT EXISTS queued (fingerprint TEXT PRIMARY KEY, queued_at TEXT NOT NULL)')
        fresh=[]
        with queue_db:
            for r in matches:
                token=identity(r)
                exists=queue_db.execute('SELECT 1 FROM queued WHERE fingerprint=?',(token,)).fetchone()
                if exists:continue
                queue_db.execute('INSERT INTO queued VALUES (?,?)',(token,datetime.now(timezone.utc).isoformat()))
                fresh.append(r)
        # Persist backlog so no opportunity disappears if DeepSeek has no key or budget.
        backlog=data/'recent_queue_pending.csv'
        old=[]
        if backlog.exists():
            with backlog.open(encoding='utf-8-sig',newline='') as f:old=list(csv.DictReader(f))
        merged={identity(r):r for r in old}
        merged.update({identity(r):r for r in fresh})
        with backlog.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=COLUMNS,extrasaction='ignore');w.writeheader();w.writerows(merged.values())
        # research queue currently reads business_leads_REVIEW_ONLY.csv. Preserve that
        # original report; give the researcher an explicit recent queue to prefer.
        print(f'Recent dated records in last {days} days: {len(matches)}; newly queued: {len(fresh)}; pending total: {len(merged)}')
        return len(matches),len(fresh),len(merged)
    finally:queue_db.close()

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--days',type=int,default=2);p.add_argument('--data-dir',default=str(ROOT/'data'));a=p.parse_args()
    if not 1<=a.days<=90:raise SystemExit('Days must be 1..90')
    export(Path(a.data_dir),a.days)
