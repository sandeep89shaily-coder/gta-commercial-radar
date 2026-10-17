@python -x "%~f0" %* & pause & exit /b
"""GTA Radar: single-file Windows launcher. Python 3, standard library only.

Run by double-clicking this BAT file. The Python -x flag skips the first BAT line.
No installation, no GitHub download, no paid AI, no data/database writes.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import html
import json
import os
import sqlite3
import sys
import traceback
import types
import zlib
import base64
from pathlib import Path

VERSION = '2026-10-17-v1'
SELECTOR_B64 = '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'
CSV_FIELDS = ['opportunity_id','source_id','source_key','company_name','address','city',
              'description','event_date','event_type','event_date_basis','source_group',
              'evidence_url','buyer_categories']


def print_step(message):
    print('[GTA Radar] ' + message, flush=True)


def candidate_roots(script_path):
    home = Path(os.environ.get('USERPROFILE') or str(Path.home()))
    possibles = [home/'Desktop'/'new data',
                 home/'OneDrive'/'Desktop'/'new data',
                 home/'OneDrive - Personal'/'Desktop'/'new data',
                 Path(os.environ.get('OneDrive',''))/'Desktop'/'new data' if os.environ.get('OneDrive') else None,
                 script_path.parent, Path.cwd(), home/'Desktop', home/'Downloads']
    seen = set()
    for p in possibles:
        if p is None:
            continue
        try:
            p=p.resolve()
        except OSError:
            continue
        if p.is_dir() and str(p).casefold() not in seen:
            seen.add(str(p).casefold())
            yield p


def candidate_databases(root):
    paths = [root/'data'/'radar.sqlite', root/'radar.sqlite']
    try:
        paths += list(root.glob('*/data/radar.sqlite'))
        paths += list(root.glob('*/*/data/radar.sqlite'))
    except OSError:
        pass
    for db in paths:
        try:
            if db.is_file() and db.stat().st_size > 0:
                yield db
        except OSError:
            continue


def locate(root_override, script_path):
    # Do not scan the entire PC or modify the Windows Task Scheduler.
    roots = [root_override.resolve()] if root_override else list(candidate_roots(script_path))
    found=[]
    for root in roots:
        for db in candidate_databases(root):
            try:
                stat=db.stat()
                csv_source=db.parent/'opportunities_ALL_REVIEW_ONLY.csv'
                has_export=csv_source.is_file() and csv_source.stat().st_size > 100
                # Prefer the largest existing collector database; an export is a tiebreaker.
                score=(stat.st_size, int(has_export), stat.st_mtime)
                found.append((score,root,db,csv_source if has_export else None))
            except OSError:
                pass
    if not found:
        raise RuntimeError('Could not find your existing radar.sqlite in the new data folders. Please send a screenshot of this message.')
    found.sort(key=lambda entry: entry[0],reverse=True)
    _, root, db, csv_source=found[0]
    # Reports stay in a new, clearly named results folder, never inside the database folder.
    # Prefer the actual "new data" parent when the launcher is in Downloads.
    place=next((p for p in [root,*db.parents] if p.name.lower()=='new data'),root)
    return place,db,csv_source


def table_exists(db,name):
    try:
        return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None
    except sqlite3.Error:
        return False


def read_only(dbfile):
    return sqlite3.connect('file:' + dbfile.resolve().as_posix() + '?mode=ro',uri=True,timeout=30)


def to_row(source_id,key,source_date,info,group,observed_date=''):
    try:
        if not isinstance(info,dict): info={}
        description=str(info.get('description') or info.get('work_description') or '')
        return dict(
            opportunity_id=f'{source_id}:{key}',source_id=source_id,source_key=key,
            company_name=str(info.get('entity_name') or info.get('business_name') or ''),
            address=str(info.get('address') or info.get('site_address') or ''),
            city=str(info.get('region') or info.get('jurisdiction') or ''),
            description=description,event_date=observed_date or source_date or '',
            event_type=str(info.get('event_type') or ''),
            event_date_basis=('CHANGE_DETECTED_NOT_PERMIT_ISSUED' if group=='MUNICIPAL_CHANGE'
                              else 'COLLECTOR_DATE_NOT_VERIFIED_ISSUANCE'),
            source_group=group,
            evidence_url=str(info.get('evidence_url') or ''),
            buyer_categories='')
    except Exception:
        return None


def export_from_existing_db(dbfile, destination, days=90):
    """Read-only, event-date-bounded review export; not live data collection."""
    today=dt.date.today()
    cutoff=(today-dt.timedelta(days=days)).isoformat()
    upper=today.isoformat()+'T23:59:59'
    count=0
    stats={'current_rows':0,'change_rows':0,'database':'','lookback_days':days}
    destination.parent.mkdir(parents=True,exist_ok=True)
    # Write a separate CSV, never touch collected database or existing export.
    with read_only(dbfile) as conn, destination.open('w',encoding='utf-8-sig',newline='') as target:
        writer=csv.DictWriter(target,fieldnames=CSV_FIELDS)
        writer.writeheader()
        if not table_exists(conn,'records_current'):
            raise RuntimeError('This folder does not contain a compatible collector database.')
        # Prefer true change-detection provenance if the same record is in both tables.
        changed_keys=set()
        if table_exists(conn,'changes'):
            try:
                query="""SELECT source_id,record_key,observed_at,normalized_json
                         FROM changes WHERE change_type='UPDATED'
                         AND observed_at>=? AND observed_at<=?
                         ORDER BY observed_at DESC"""
                for sid,key,observed,raw in conn.execute(query,(cutoff,upper)):
                    ident=(sid,key)
                    if ident in changed_keys:continue
                    changed_keys.add(ident)
                    try:info=json.loads(raw or '{}')
                    except (TypeError,ValueError):continue
                    row=to_row(sid,key,'',info,'MUNICIPAL_CHANGE',observed)
                    if row:
                        writer.writerow(row);count+=1;stats['change_rows']+=1
            except sqlite3.OperationalError:
                print_step('Change history unavailable; reading current source records only.')
        query="""SELECT source_id,record_key,source_date,normalized_json
                 FROM records_current WHERE active=1
                 AND source_date>=? AND source_date<=?
                 ORDER BY source_date DESC"""
        for sid,key,date,raw in conn.execute(query,(cutoff,upper)):
            # An UPDATED record is not independently a newly issued permit.
            if (sid,key) in changed_keys:continue
            try:info=json.loads(raw or '{}')
            except (TypeError,ValueError):continue
            row=to_row(sid,key,date,info,'MUNICIPAL')
            if row:
                writer.writerow(row);count+=1;stats['current_rows']+=1
            if count and count % 20000 == 0:
                print_step(f'Read {count:,} dated records...')
    stats['total_rows']=count
    return stats


def embedded_v4():
    # Versioned V4 selector source is bundled offline; no network dependency.
    source=zlib.decompress(base64.b64decode(SELECTOR_B64)).decode('utf-8')
    module=types.ModuleType('gta_radAR_bundled_v4')
    module.__file__='<self-contained-one-click-selector>'
    exec(compile(source,module.__file__,'exec'),module.__dict__)
    return module


def show_report(report):
    if os.name=='nt':
        os.startfile(str(report))
    else:
        import webbrowser
        webbrowser.open_new_tab(report.resolve().as_uri())


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=None,help='Developer/test override for workspace search')
    parser.add_argument('--no-open',action='store_true',help='Developer/test flag to skip opening browser')
    parser.add_argument('--days',type=int,default=90,help='Review lookback in days for fallback export')
    args=parser.parse_args()
    if not 1<=args.days<=365:
        parser.error('--days must be between 1 and 365')
    print_step('Looking for your existing Radar data automatically...')
    root,db,existing=locate(args.root,Path(__file__).resolve())
    print_step('Found collector database: '+str(db))
    output=root/'GTA_RADAR_RESULTS'
    output.mkdir(parents=True,exist_ok=True)
    if existing:
        source=existing
        stats={'input':'Existing opportunity export','lookback_days':'As exported',
               'source_rows':'Existing export was used without editing'}
        print_step('Found previous opportunity export. Using it as-is.')
    else:
        source=output/'opportunities_AUTO_REVIEW_ONLY.csv'
        print_step('Missing opportunity export. Building a read-only review from the database...')
        stats=export_from_existing_db(db,source,args.days)
        stats['input']='Read-only SQLite review export'
        print_step(f"Generated {stats['total_rows']:,} dated source/change rows from the last {args.days} days.")
    print_step('Grouping and filtering projects using bundled V4...')
    selector=embedded_v4()
    projects=selector.run(source,output,db)
    report=output/'commercial_candidates_v4.html'
    if not report.is_file():
        raise RuntimeError('The report could not be generated.')
    # Make staleness unmistakable in the report itself.
    last_local=dt.datetime.fromtimestamp(db.stat().st_mtime).astimezone().strftime('%Y-%m-%d %H:%M')
    banner=('<div style="padding:14px;background:#fff4db;border:1px solid #e5d39b;border-radius:8px">'
            '<b>OFFLINE, UNVERIFIED REVIEW</b> — This launcher does not refresh data from government sites. '
            'Selected database last modified: '+html.escape(last_local)+'. '
            'Dates are collector/status dates or detected updates, not proven permit issue dates. '
            'No projects are ready for sale without independent verification.</div>')
    page=report.read_text(encoding='utf-8')
    report.write_text(page.replace('<body>','<body>'+banner,1),encoding='utf-8')
    manifest={'launcher_version':VERSION,'database_read_only':str(db),'source_export':str(source),
              'created_local':dt.datetime.now().astimezone().isoformat(timespec='seconds'),
              'source_stats':stats,'projects_for_research':len(projects),
              'disclaimer':'Source dates are not verified permit issue dates. Report is research-only, not sale-ready. No source polling or paid AI performed.'}
    (output/'RUN_DETAILS.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print_step('Finished. Found '+str(len(projects))+' research projects (NOT verified sales leads).')
    print_step('Report saved: '+str(report))
    if not args.no_open:
        show_report(report)
    print_step('Done. No original database files were changed.')
    return 0


if __name__=='__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('\n[GTA Radar] Could not finish: '+str(exc))
        print('[GTA Radar] Nothing in your existing database has been deleted or overwritten.')
        if '--debug' in sys.argv:
            traceback.print_exc()
        sys.exit(1)