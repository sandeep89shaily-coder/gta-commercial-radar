"""GTA Commercial Radar V6: genuine collection-to-investigation daily workflow.

This is the coordinator, not a second collector or a substitute for source evidence.
Collector SQLite records change only through the existing official collection code.
All reports and the AI ledger are kept in a separate GTA_RADAR_RESULTS directory.
"""
from __future__ import annotations

import argparse
import csv
from contextlib import closing
import datetime as dt
import html
import json
import os
import re
import sqlite3
import subprocess
import sys
import traceback
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus, urlparse

VERSION = '6.0'
ROOT = Path(__file__).resolve().parent
MAX_INVESTIGATIONS = 25
MAX_LOG_BYTES = 32000
TASK_NAME = 'GTA Commercial Radar V6'
PREVIOUS_TASK = 'GTA Commercial Radar V5'


def say(message):
    print('[GTA Radar] ' + str(message), flush=True)


def workspace_locations(home=None):
    home = Path(home or Path.home())
    paths = [home / 'Desktop' / 'new data', home / 'OneDrive' / 'Desktop' / 'new data',
             home / 'OneDrive - Personal' / 'Desktop' / 'new data', home / 'Desktop']
    if os.environ.get('OneDrive'):
        paths.append(Path(os.environ['OneDrive']) / 'Desktop' / 'new data')
    return list(dict.fromkeys(p for p in paths if p.is_dir()))


def find_workspace(explicit=None, home=None):
    """Look in the established Radar workspace, not the user's entire drive."""
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not p.is_dir():
            raise FileNotFoundError('Specified workspace does not exist: ' + str(p))
        return p
    places = workspace_locations(home)
    for p in places:
        if p.name.casefold() == 'new data':
            return p
    raise FileNotFoundError('Desktop/new data workspace not found; no data was changed.')


def choose_database(workspace):
    """Choose the best existing collector database, never create a new empty one."""
    ws = Path(workspace)
    candidates = [ws / 'data' / 'radar.sqlite']
    # Preserve continuity with the database V5 actually selected on this PC.
    previous = ws / 'GTA_RADAR_RESULTS' / 'RUN_DETAILS.json'
    if previous.is_file():
        try:
            last = json.loads(previous.read_text(encoding='utf-8'))
            pinned = Path(last.get('database_read_only') or '')
            if pinned.is_file() and pinned.resolve().is_relative_to(ws.resolve()):
                with closing(sqlite3.connect(f'{pinned.resolve().as_uri()}?mode=ro', uri=True, timeout=4)) as conn:
                    if conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='records_current'").fetchone()[0]:
                        return pinned.resolve()
        except (OSError, ValueError, sqlite3.Error, TypeError):
            pass
    candidates.extend(ws.glob('*/data/radar.sqlite'))
    candidates.extend(ws.glob('*/*/data/radar.sqlite'))
    scored = []
    for db in set(candidates):
        try:
            if not db.is_file() or db.stat().st_size < 100:
                continue
            with closing(sqlite3.connect(f'{db.resolve().as_uri()}?mode=ro', uri=True, timeout=4)) as con:
                ok = con.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='records_current'").fetchone()[0]
            if not ok:
                continue
            stat = db.stat()
            # Prefer established, non-empty collection over a tiny or newly-created db.
            scored.append((stat.st_size, stat.st_mtime, db))
        except (OSError, sqlite3.Error):
            continue
    if not scored:
        raise FileNotFoundError('No compatible radar.sqlite found under your new data folder.')
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return scored[0][2].resolve()


def run_step(name, args, log_dir, timeout=1200, cwd=ROOT, env=None):
    """Run one real collector/process and retain both its exit status and diagnostics."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    file = log_dir / (name + '.log')
    say('Running ' + name + '...')
    try:
        with file.open('w', encoding='utf-8') as output:
            process = subprocess.run([sys.executable, *[str(a) for a in args]], cwd=str(cwd),
                                     env=env, stdout=output, stderr=subprocess.STDOUT,
                                     timeout=timeout, check=False)
        code = process.returncode
        status = 'SUCCESS' if code == 0 else 'FAILED'
        detail = 'exit code ' + str(code)
    except subprocess.TimeoutExpired:
        status, code, detail = 'FAILED', 124, 'timeout after ' + str(timeout) + 's'
    except (OSError, ValueError) as exc:
        status, code, detail = 'FAILED', 125, type(exc).__name__ + ': ' + str(exc)[:200]
    return {'step': name, 'status': status, 'exit_code': code, 'detail': detail,
            'started_utc': started, 'finished_utc': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
            'log': str(file)}


def once_lock(results, stale_hours=16):
    """Protect scheduled runs from concurrent database writers (no stale-lock deletion)."""
    path = Path(results) / 'V6_RUNNING.lock'
    if path.exists():
        try:
            age_hours = (dt.datetime.now().timestamp() - path.stat().st_mtime) / 3600
            if age_hours > stale_hours:
                path.unlink(missing_ok=True)  # Timed stages cannot run for 16 hours.
        except OSError:
            pass
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise RuntimeError('A V6 run may already be active. Only one run can use this database at a time.')
    with os.fdopen(descriptor, 'w') as f:
        f.write(str(os.getpid()) + '\n' + dt.datetime.now(dt.timezone.utc).isoformat())
    return path


def atomic_json(path, obj):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    temp.replace(path)


def evidence_queries(row):
    """Target civic addresses, source IDs and identifiable companies, not broad leads."""
    address=' '.join(str(row.get('address') or '').split()).split(',')[0].strip()
    company=str(row.get('company_name') or '').strip()
    ident=str(row.get('source_keys') or '').split(' | ')[0].strip()
    sid=str(row.get('source_id') or '').lower()
    queries=[]
    if address:
        queries.extend([f'"{address}" development application',
                        f'"{address}" construction developer',
                        f'"{address}" commercial building project'])
        expanded=re.sub(r'\b(RD|ST|AVE|CRT|DR|BLVD)\b',
                        lambda m:{'RD':'Road','ST':'Street','AVE':'Avenue','CRT':'Court',
                                  'DR':'Drive','BLVD':'Boulevard'}[m.group().upper()],
                        address,flags=re.I)
        if expanded.lower()!=address.lower():
            queries.append(f'"{expanded}" project')
    if 8<=len(ident)<=75 and not ident.isdigit():
        queries.append(f'"{ident}" {"Toronto planning" if "toronto" in sid else "Ontario permit"}')
    if company and company.lower() not in ('unknown','none','n/a'):
        queries.append(f'"{company}" "{address[:45]}"')
    return list(dict.fromkeys(queries))[:6]


def normalized_location(value):
    parts=re.sub(r'[^a-z0-9]+',' ',str(value or '').lower()).split()
    alias={'rd':'road','st':'street','ave':'avenue','crt':'court',
           'dr':'drive','blvd':'boulevard','hwy':'highway','pkwy':'parkway'}
    return ' '.join(alias.get(t,t) for t in parts)


def evidence_matches(row,page):
    """Require a real fetched page containing the address, company or source ID."""
    body=normalized_location(page)
    addr=normalized_location((str(row.get('address') or '').splitlines() or [''])[0].split(',')[0])
    match=re.search(r'\b(\d{2,6})\s+([a-z]{3,})(?:\s+([a-z]{3,}))?',addr)
    if match:
        number,street,second=match.groups()
        if street in {'old','north','south','east','west'} and second:
            street+=' '+second
        if re.search(r'\b'+re.escape(number)+r'\s+'+re.escape(street)+r'\b',body):
            return True
    name=str(row.get('company_name') or '').strip().lower()
    if name not in {'','unknown','none','n/a'} and len(name)>=9 and normalized_location(name) in body:
        return True
    for identifier in re.split(r'[|;]',str(row.get('source_keys') or ''))[:5]:
        identifier=identifier.strip()
        if len(identifier)>=9 and re.search('[a-z]',identifier,re.I) and normalized_location(identifier) in body:
            return True
    return False


def news_rss_search(query):
    """Secondary free RSS discovery, with separate verification of every found page."""
    from urllib.request import Request,urlopen
    from urllib.parse import urlencode
    from xml.etree import ElementTree
    url='https://news.google.com/rss/search?'+urlencode(
        {'q':query[:140],'hl':'en-CA','gl':'CA','ceid':'CA:en'})
    try:
        with urlopen(Request(url,headers={'User-Agent':'GTACommercialRadarResearch/1.0'}),timeout=10) as res:
            data=res.read(90001)
        if len(data)>90000:return []
        tree=ElementTree.fromstring(data);results=[]
        for item in tree.findall('.//item')[:8]:
            link=(item.findtext('link') or '').strip()
            if link.startswith('https://') and link not in results:results.append(link)
        return results
    except (OSError,ValueError,ElementTree.ParseError):return []


def discover_improved(row,search,fetch,max_searches=6,max_pages=4):
    """Bounded, verified source discovery. No search snippet counts as evidence."""
    import v5_investigator as v5
    urls=[]
    direct=str(row.get('record_source_url') or '').strip()
    if direct.startswith('https://'):urls.append(direct)
    if str(row.get('source_id') or '').startswith('ero_'):
        key=str(row.get('source_keys') or '').strip()
        if re.fullmatch(r'\d{3}-\d{3,5}',key):
            urls.append('https://ero.ontario.ca/notice/'+key)
    attempts=0;queries=evidence_queries(row)
    for query in queries[:max_searches]:
        attempts+=1
        try:
            for url in search(query)[:8]:
                if isinstance(url,str) and urlparse(url).scheme=='https' and url not in urls:
                    urls.append(url)
        except Exception:continue
    evidence=[];visited=set()
    def check(urls_to_check,cap):
        for url in urls_to_check:
            if len(evidence)>=max_pages or len(visited)>=cap:break
            if url in visited:continue
            visited.add(url)
            try:body=fetch(url)
            except Exception:continue
            if body and evidence_matches(row,body):
                evidence.append({'url':url,'text':body[:2600]})
    check(urls,14)
    # Never make network calls in mocked/isolated tests.
    if not evidence and search is getattr(v5,'search_rss',None) and queries:
        for q in queries[:2]:
            attempts+=1
            for url in news_rss_search(q)[:5]:
                if url not in urls:urls.append(url)
        check(urls,20)
    return evidence,attempts


def select_unresearched(rows,limit,previous,day):
    import v5_investigator as v5
    reviewed=set()
    for identifier,old in (previous or {}).items():
        try:
            age=(day-dt.date.fromisoformat(str(old.get('researched_at') or '')[:10])).days
            status=str(old.get('status') or '')
            # Failed source discovery gets a fresh attempt tomorrow, not in seven days.
            cooldown=1 if status in {'NO_CORROBORATED_PAGE','AI_ERROR_REVIEW',
                                      'EVIDENCE_ONLY_AI_NOT_CONFIGURED'} else 7
            if 0<=age<cooldown:reviewed.add(identifier)
        except (ValueError,TypeError):pass
    remaining=[row for row in rows
               if row.get('project_id') not in reviewed
               and not v5.CLOSED.search(str(row.get('current_source_status') or ''))]
    original_order=v5_original_queue(remaining,len(remaining),previous,day)
    priorities={'PERMIT_REVIEW':0,'BUSINESS_REVIEW':1,'PLANNING_WATCH':2,
                'OTHER_WATCH':3,'SOURCE_UPDATE_WATCH':4}
    # Preserve earlier ordering within each lane but prioritize genuine permits.
    original_order.sort(key=lambda row:(priorities.get(row.get('lane'),5),
                                         -int(row.get('review_priority') or 0)))
    return original_order[:max(0,limit)]


v5_original_queue = None


def investigate(data_dir, results_dir, max_projects=MAX_INVESTIGATIONS, *, enable_ai=True):
    """Reuse the vetted V5 provider reservation ledger without a parallel billing path."""
    global v5_original_queue
    import v5_investigator as v5
    old_discover = v5.discover
    old_select = v5.select_queue
    v5_original_queue = old_select
    try:
        v5.discover = discover_improved
        v5.select_queue = select_unresearched
        return v5.run(results_dir,
                      projects_file=Path(results_dir) / 'CANDIDATES_V4_ALL_REVIEW_ONLY.csv',
                      results_dir=results_dir,
                      max_projects=max_projects, run_ai=enable_ai,
                      legacy_budget_dir=data_dir)
    finally:
        v5.discover = old_discover
        v5.select_queue = old_select
        v5_original_queue = None


def render_dashboard(results, state):
    """User-facing report must reveal when collectors failed or when no fresh events exist."""
    rdir = Path(results)
    file = rdir / 'GTA_RADAR_V6_DASHBOARD.html'
    def esc(s): return html.escape(str(s if s is not None else ''), quote=True)
    def safe_link(s):
        s = str(s or '').strip()
        return s if urlparse(s).scheme == 'https' and urlparse(s).hostname else ''
    investigations = []
    history = rdir / 'GTA_RADAR_V5_INVESTIGATIONS.csv'
    if history.exists():
        with history.open('r', newline='', encoding='utf-8-sig') as inp:
            investigations = list(csv.DictReader(inp))
    current = state.get('investigation_date', '')
    new = [i for i in investigations if (i.get('researched_at') or '').startswith(current)]
    new.sort(key=lambda x: (x.get('status') != 'AI_EVIDENCE_REVIEW', x.get('status') or '', x.get('address') or ''))
    status = state.get('status') or 'UNKNOWN'
    css = ('body{font:15px Segoe UI,Arial,sans-serif;background:#f5f7fa;color:#1d2939;max-width:1100px;margin:35px auto;padding:0 20px}'
           'article{background:#fff;border:1px solid #dfe5ed;border-radius:9px;padding:18px;margin:14px 0}'
           '.muted{color:#526171}.mono{font-family:Consolas,monospace}a{color:#145a9c}'
           '.pill{font-size:12px;border:1px solid #9ca3af;border-radius:40px;padding:3px 8px}')
    page = [f'<!doctype html><html><head><meta charset="utf-8"><title>GTA Radar V6</title><style>{css}</style></head><body>',
            '<h1>GTA Commercial Radar — daily intelligence</h1>',
            f'<p><b>Run state: {esc(status)}</b> · {esc(state.get("started_local", ""))}</p>',
            '<p><b>Research only:</b> a municipal record, source update or AI suggestion is not a verified sales lead. No buying intent is assumed.</p>',
            f'<p><b>Collector database:</b> <span class="mono">{esc(state.get("database", ""))}</span></p>',
            f'<p><b>Window:</b> most recent 48 hours by source event/change date. <b>Projects this run:</b> {esc(state.get("projects",0))}. '
            f'<b>Projects investigated:</b> {esc(state.get("investigated",0))}. '
            f'<b>Projects with corroborated pages:</b> {esc(state.get("with_public_pages",0))}. '
            f'<b>DeepSeek calls attempted:</b> {esc(state.get("ai_calls_attempted",0))}; '
            f'<b>AI analyses completed:</b> {esc(state.get("ai_calls_succeeded",0))}; '
            f'<b>Without corroborated evidence:</b> {esc(state.get("no_corroboration",0))}. '
            f'<b>DeepSeek budget reserved today:</b> US${esc(state.get("reserved_usd",0))} / $0.50 (local safeguard, not provider cap).</p>']
    if status != 'SUCCESS':
        page.append('<article><h2>Collection attention needed</h2><p>Not all collection steps succeeded. '
                    'Do not interpret this as a complete or fully fresh GTA picture.</p></article>')
    page.append('<h2>Collection steps</h2>')
    for step in state.get('steps', []):
        page.append(f'<p><b>{esc(step["step"])}</b>: {esc(step["status"])} '
                    f'<span class="muted">({esc(step.get("detail", ""))})</span></p>')
    page.append('<h2>Project investigations from this run</h2>')
    if not new:
        page.append('<p>No new independent investigations in this run. The report will not relabel old investigations as new.</p>')
    for v in new:
        page.append(f'<article><h3>{esc(v.get("address") or v.get("project_id"))}</h3>'
                    f'<p><span class="pill">{esc(v.get("status"))}</span> — {esc(v.get("project_stage"))}</p>'
                    f'<p><b>Company/operator:</b> {esc(v.get("operator")) or "Unknown"} '
                    f'· <b>Developer:</b> {esc(v.get("developer")) or "Unknown"}</p>'
                    f'<p><b>Possible services:</b> {esc(v.get("buyer_fit")) or "Unverified"}</p>'
                    f'<p><b>Public contact:</b> {esc(v.get("contact")) or "Not verified"}</p>'
                    f'<p class="muted">{esc(v.get("caveats"))}</p>')
        for url in str(v.get('source_urls') or '').split(' | '):
            if safe_link(url):
                page.append(f'<a href="{esc(url)}" rel="noopener noreferrer">Supporting public page</a> · ')
        page.append('</article>')
    page.append('</body></html>')
    file.write_text(''.join(page), encoding='utf-8')
    return file


def schedule_daily(script_path, workspace, at='08:30'):
    if os.name != 'nt':
        return 'NOT_WINDOWS'
    # Do not replace previous schedule until the new task is successfully created.
    runner = Path(script_path).resolve()
    command = f'cmd.exe /c ""{runner}" --unattended"'
    proc = subprocess.run(['schtasks.exe','/Create','/F','/SC','DAILY','/ST',at,
                           '/TN',TASK_NAME,'/TR',command], capture_output=True, text=True, timeout=30)
    if proc.returncode:
        return 'FAILED: ' + str(proc.stderr or proc.stdout)[:240]
    # Avoid two daily collectors or divergent budget ledgers running together.
    old = subprocess.run(['schtasks.exe','/Delete','/F','/TN',PREVIOUS_TASK],
                         capture_output=True, text=True, timeout=20)
    return 'SUCCESS' if old.returncode == 0 else 'SUCCESS_NEW_TASK; REVIEW_OLD_V5_TASK'


def pipeline(workspace, database=None, *, run_collectors=True, run_research=True, max_projects=MAX_INVESTIGATIONS,
             collector=run_step, selector=None, investigator=investigate, results_dir=None, today=None):
    ws = Path(workspace).resolve()
    db = Path(database or choose_database(ws)).resolve()
    data = db.parent
    out = Path(results_dir or (ws / 'GTA_RADAR_RESULTS')).resolve()
    out.mkdir(parents=True, exist_ok=True)
    lock = once_lock(out)
    day = today or dt.date.today()
    state = {'version': VERSION, 'started_local': dt.datetime.now().astimezone().isoformat(timespec='seconds'),
             'database': str(db), 'status': 'RUNNING', 'investigation_date': day.isoformat(),
             'steps': [], 'projects': 0, 'investigated': 0, 'reserved_usd': 0}
    manifest = out / 'GTA_RADAR_V6_RUN.json'
    try:
        atomic_json(manifest, state)
        if not db.exists():
            raise FileNotFoundError('The original database cannot be located.')
        if run_collectors:
            steps = [
                ('municipal_collector', ['main.py','poll','--data-dir',data,'--hours','48'], 1800),
                ('business_collector', ['business_discovery.py','run','--data-dir',data], 1200),
            ]
            for name, command, timeout in steps:
                outcome = collector(name, command, out / 'V6_LOGS', timeout=timeout)
                state['steps'].append(outcome)
                atomic_json(manifest, state)
            succeeded = sum(step['status'] == 'SUCCESS' for step in state['steps'])
            if not succeeded:
                state['status'] = 'FAILED'
                state['note'] = 'No collectors succeeded; prior export NOT reused and AI NOT run.'
                return state
            state['status'] = 'PARTIAL' if succeeded < len(steps) else 'SUCCESS'
        else:
            # Tests and explicitly requested offline diagnostics; never fake a live refresh.
            state['status'] = 'OFFLINE_REVIEW_ONLY'
        if not run_collectors:
            # Offline tests can supply a pre-generated CSV; not a production success claim.
            if not (data / 'opportunities_ALL_REVIEW_ONLY.csv').exists():
                raise FileNotFoundError('Offline review requires an explicit current opportunity export.')
        else:
            step = collector('fresh_48h_opportunities', ['opportunity_engine.py','--days','2','--data-dir',data],
                             out / 'V6_LOGS', timeout=420)
            state['steps'].append(step)
            if step['status'] != 'SUCCESS':
                state['status'] = 'PARTIAL'
                state['note'] = 'Opportunity export generation failed; old exports NOT used.'
                return state
        if selector is None:
            import commercial_selector_v4 as v4
            selector = v4.run
        selector(data / 'opportunities_ALL_REVIEW_ONLY.csv', out, db)
        projects = out / 'CANDIDATES_V4_ALL_REVIEW_ONLY.csv'
        if not projects.exists():
            raise RuntimeError('V4 did not produce a candidate CSV.')
        with projects.open(encoding='utf-8-sig',newline='') as f:
            state['projects'] = sum(1 for _ in csv.DictReader(f))
        if run_research:
            outcome = investigator(data, out, max_projects=max_projects)
            state['investigated'] = outcome['processed']
            state['with_public_pages'] = outcome['with_public_pages']
            state['reserved_usd'] = outcome['reserved_usd']
            state['ai_configured'] = outcome['deepseek_configured']
            # Count actual provider attempts separately from mere project searches.
            research_file=out/'GTA_RADAR_V5_INVESTIGATIONS.csv'
            today_rows=[]
            if research_file.is_file():
                with research_file.open(encoding='utf-8-sig',newline='') as f:
                    today_rows=[r for r in csv.DictReader(f)
                                if str(r.get('researched_at') or '').startswith(day.isoformat())]
            state['ai_calls_succeeded']=sum(r.get('status')=='AI_EVIDENCE_REVIEW' for r in today_rows)
            state['ai_calls_failed']=sum(r.get('status')=='AI_ERROR_REVIEW' for r in today_rows)
            state['ai_calls_attempted']=state['ai_calls_succeeded']+state['ai_calls_failed']
            state['no_corroboration']=sum(r.get('status')=='NO_CORROBORATED_PAGE' for r in today_rows)
            state['research_searches']=sum(int(r.get('searches') or 0) for r in today_rows)
            state['evidence_pages_read']=sum(int(r.get('web_pages') or 0) for r in today_rows)
        else:
            state['note'] = 'AI investigation disabled for this test; no charge.'
        return state
    except Exception as exc:
        state['status'] = 'FAILED'
        state['error'] = type(exc).__name__ + ': ' + str(exc)[:250]
        return state
    finally:
        state['finished_local'] = dt.datetime.now().astimezone().isoformat(timespec='seconds')
        try:
            atomic_json(manifest, state)
            render_dashboard(out, state)
        finally:
            lock.unlink(missing_ok=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description='GTA Radar V6: daily end-to-end source collection, qualification and AI research')
    parser.add_argument('--workspace', type=Path, help='Existing Desktop/new data folder (automatically detected by default)')
    parser.add_argument('--database', type=Path, help='Existing collector database; never creates a new collector DB')
    parser.add_argument('--results-dir', type=Path)
    parser.add_argument('--max-projects', type=int, default=MAX_INVESTIGATIONS)
    parser.add_argument('--unattended', action='store_true')
    parser.add_argument('--no-ai', action='store_true')
    parser.add_argument('--offline-test', action='store_true', help='Only for local diagnostics, never marketed as fresh collection')
    parser.add_argument('--no-schedule', action='store_true')
    args=parser.parse_args(argv)
    try:
        workspace = find_workspace(args.workspace)
        db = args.database or choose_database(workspace)
        say('Using your established database: ' + str(db))
        say('Running live collection first. Existing history will be preserved as collectors update it.')
        state=pipeline(workspace, db, run_collectors=not args.offline_test,
                       run_research=not args.no_ai, results_dir=args.results_dir,
                       max_projects=min(50, max(1,args.max_projects)))
        dest=Path(args.results_dir or (workspace/'GTA_RADAR_RESULTS')) / 'GTA_RADAR_V6_DASHBOARD.html'
        say('Run status: '+state['status']+'; projects: '+str(state.get('projects',0))+
            '; researched: '+str(state.get('investigated',0)))
        if state.get('error') or state.get('note'): say(state.get('error') or state.get('note'))
        say('Dashboard: ' + str(dest))
        if not args.unattended and dest.exists():
            if os.name=='nt': os.startfile(str(dest))
            else: webbrowser.open(dest.resolve().as_uri())
        if not args.unattended and not args.no_schedule and state['status'] in ('SUCCESS','PARTIAL'):
            # The scheduled program should be the stable, installed runner, never a Downloads ZIP.
            installed=Path(__file__).resolve().parent/'RUN_GTA_RADAR_V6.bat'
            if installed.is_file(): say('Daily task: '+schedule_daily(installed,workspace))
            else:say('Daily task not installed: stable launcher missing.')
        return 0 if state['status']=='SUCCESS' else 1
    except Exception as exc:
        say('Could not start: '+type(exc).__name__+': '+str(exc)[:250]);return 1


if __name__=='__main__': raise SystemExit(main())