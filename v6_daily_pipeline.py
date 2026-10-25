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
from radar_run_lock import once_lock

VERSION = '6.0'
ROOT = Path(__file__).resolve().parent
MAX_INVESTIGATIONS = 0  # 0 means process every queued project until time or $1/day budget stops the run
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
    # AI searches are hints, never verified claims.
    suggestions=list(row.get('_deepseek_queries') or [])[:2]
    attempts=0;queries=list(dict.fromkeys(suggestions+evidence_queries(row)))
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
    """One meaningful DeepSeek call per project, with or without web evidence.

    No paid search plans. Source-only model output is explicitly unverified.
    """
    import v8_deepseek_native as researcher
    results = Path(results_dir)
    return researcher.run(results / 'CANDIDATES_V4_ALL_REVIEW_ONLY.csv',
                          results, legacy_data_dir=data_dir,
                          key=None if enable_ai else '',
                          max_projects=max_projects)

def render_dashboard(results, state):
    """User-facing report must reveal when collectors failed or when no fresh events exist."""
    rdir = Path(results)
    file = rdir / 'GTA_RADAR_V6_DASHBOARD.html'
    def esc(s): return html.escape(str(s if s is not None else ''), quote=True)
    def safe_link(s):
        s = str(s or '').strip()
        return s if urlparse(s).scheme == 'https' and urlparse(s).hostname else ''
    investigations = []
    history = rdir / 'GTA_RADAR_V6_LATEST_INVESTIGATIONS.csv'
    # Compatibility with historical manually generated reports. Production
    # always emits the latest-run file above, preventing same-day overcounting.
    if not history.exists():
        history = rdir / 'GTA_RADAR_V5_INVESTIGATIONS.csv'
    if history.exists():
        with history.open('r', newline='', encoding='utf-8-sig') as inp:
            investigations = list(csv.DictReader(inp))
    if state.get('ai_mode')=='OFF':
        # This run generated NO AI investigations; never misrepresent an older
        # paid research export as newly investigated this morning.
        investigations=[]
    current = state.get('investigation_date', '')
    new = investigations
    # Deferred and source-only records stay in the automated research CSV queue,
    # never in the evidence-backed lead list.
    pending = [r for r in new if r.get('status') in
               ('AI_BUDGET_DEFERRED','NO_DEEPSEEK_KEY','INSUFFICIENT_SOURCE_RECORD')
               or r.get('lead_maturity')=='SOURCE_RECORD_OBSERVED']
    visible = [r for r in new if r not in pending]
    visible.sort(key=lambda x: (
        x.get('lead_maturity')!='PUBLIC_OPERATOR_CONTACT_IDENTIFIED',
        x.get('lead_maturity')!='PROJECT_AND_OPERATOR_IDENTIFIED',
        x.get('status')!='AI_EVIDENCE_REVIEW', x.get('address') or ''))
    status = state.get('status') or 'UNKNOWN'
    css = ('body{font:15px Segoe UI,Arial,sans-serif;background:#f5f7fa;color:#1d2939;max-width:1100px;margin:35px auto;padding:0 20px}'
           'article{background:#fff;border:1px solid #dfe5ed;border-radius:9px;padding:18px;margin:14px 0}'
           '.muted{color:#526171}.mono{font-family:Consolas,monospace}a{color:#145a9c}'
           '.pill{font-size:12px;border:1px solid #9ca3af;border-radius:40px;padding:3px 8px}')
    page = [f'<!doctype html><html><head><meta charset="utf-8"><title>GTA Radar V6</title><style>{css}</style></head><body>',
            '<h1>GTA Commercial Radar — daily intelligence</h1>',
            f'<p><b>Run state: {esc(status)}</b> · {esc(state.get("started_local", ""))}</p>',
            '<p><b>Research only:</b> an application or AI suggestion is not proof of purchasing intent. No unverified project is sale-ready.</p>',
             '<p><b>DAILY PUBLIC RECORD WATCH:</b> <a href="GTA_RADAR_DAILY_NEW_DEVELOPMENTS.html">Newly observed and changed municipal projects</a> · '+
             '<a href="GTA_RADAR_DAILY_PUBLIC_RECORDS.csv">Full public-record collection</a>. Selective DeepSeek uses a separate $0.25 daily ceiling.</p>',
             '<p><b>INVESTIGATE NEXT:</b> <a href="GTA_RADAR_SHORTLIST.html">Open high-confidence commercial opportunities</a> · '+
             '<a href="GTA_RADAR_QUALIFIED_OPPORTUNITY_SHORTLIST.csv">Download qualified shortlist</a> · '+
             '<a href="GTA_RADAR_OPPORTUNITY_RESEARCH_GAPS.csv">Records awaiting verification</a>.</p>',
             '<p><b>Commercial intelligence:</b> <a href="GTA_RADAR_LEAD_INTELLIGENCE.html">Open all classified opportunities and contact dashboard</a>.</p>',
            '<h2>One collection system — source health</h2>',
            '<p><b>Unified source inventory:</b> <a href="GTA_RADAR_ALL_SOURCE_STATUS.csv">View status of every core, disabled, and independent collector</a>. '
            'Review-only feeds are visible, but do not automatically trigger paid research.</p>',
            '<p>All early collectors run under the same daily pipeline. An unsuccessful or review-only source is not a verified buying signal.</p>',
            '<ul>'+''.join('<li>'+esc(s.get('step'))+': <b>'+esc(s.get('status'))+'</b></li>'
                  for s in state.get('early_pilot_results',[]))+'</ul>',
            f'<p><b>Early post-baseline changes passed to the common opportunity engine:</b> {esc(state.get("early_pilot_changes_accepted",0))}. '
            f'<b>Disabled main sources (not activated):</b> {esc(state.get("disabled_source_count",14))}.</p>',
            f'<p><b>Collector database:</b> <span class="mono">{esc(state.get("database", ""))}</span></p>',
            f'<p><b>Window:</b> most recent 48 hours by source event/change date. <b>Projects this run:</b> {esc(state.get("projects",0))}. '
            f'<b>Projects investigated:</b> {esc(state.get("investigated",0))}. '
            f'<b>Projects with corroborated pages:</b> {esc(state.get("with_public_pages",0))}. '
            f'<b>Source-backed projects:</b> {esc(state.get("source_backed_projects",0))}; '
            f'<b>Public operator contacts identified:</b> {esc(state.get("publicly_contactable",0))}. '
            f'<b>Native DeepSeek Search requests:</b> {esc(state.get("native_searches",0))}; '
            f'<b>Native DeepSeek Fetch requests:</b> {esc(state.get("native_fetches",0))}; '
             f'<b>Exact official permit/status matches:</b> {esc(state.get("official_live_matches",0))}; '
             f'<b>Local source-only exact matches:</b> {esc(state.get("official_local_matches",0))}; '
             f'<b>Company contact searches:</b> {esc(state.get("company_contact_searches",0))}; '
             f'<b>Public company channels found:</b> {esc(state.get("company_contacts_discovered",0))}; '
            f'<b>Flash analyses attempted:</b> {esc(state.get("ai_calls_attempted",0))}; '
            f'<b>Duplicate AI requests safely skipped:</b> {esc(state.get("duplicate_model_skipped",0))}; '
            f'<b>DeepSeek analyses completed:</b> {esc(state.get("ai_calls_succeeded",0))}; '
            f'<b>Source-record-only analyses (unverified):</b> {esc(state.get("source_only_ai_calls",0))}; '
            f'<b>Still awaiting first AI analysis:</b> {esc(state.get("queue_initial_uninvestigated",0))}; '
            f'<b>Total persistent research queue:</b> {esc(state.get("queue_total",0))}; '
            f'<b>Ready for the next run:</b> {esc(state.get("queue_due",0))}; '
            f'<b>Current AI stop reason:</b> {esc(state.get("queue_stop_reason","NOT_RUN"))}; '
            f'<b>Without corroborated evidence:</b> {esc(state.get("no_corroboration",0))}. '
            f'<b>DeepSeek daily budget used (completed-token estimates + unknown holds):</b> US${esc(state.get("reserved_usd",0))} / $1.00. '
            f'<b>Completed API-call cost estimate:</b> US${esc(state.get("charged_estimate_usd",0))}; '
            f'<b>Uncertain charges still reserved:</b> US${esc(state.get("unresolved_reservations_usd",0))}. '
            f'These are local estimates, not DeepSeek account billing.</p>']
    if status != 'SUCCESS':
        incomplete_collector=any(step.get('status')!='SUCCESS' for step in state.get('steps',[]))
        heading='Collection attention needed' if incomplete_collector else 'Run attention needed'
        page.append('<article><h2>'+heading+'</h2><p>Some processing did not finish. '
                    'A completed collection step is not the same as completed AI research.</p>')
        if state.get('error'):
            page.append('<p><b>Failure stage:</b> '+esc(state.get('error_stage','UNKNOWN'))+
                        ' · <b>Error:</b> '+esc(state['error'])+'</p>')
            if state.get('error_log'):
                page.append('<p><b>Diagnostic file:</b> <code>'+
                            esc(state['error_log'])+'</code></p>')
        if state.get('checkpointed_investigations_today') is not None:
            page.append('<p><b>Research records checkpointed for this date:</b> '+
                        esc(state['checkpointed_investigations_today'])+
                        '. This is not necessarily the count from this run.</p>')
        page.append('</article>')
    if state.get('regional_regions_represented') is not None:
        page.append('<p><b>Regional archive supplement:</b> '+
                    esc(state.get('regional_source_records_added',0))+
                    ' distinct source-dated records outside/alongside the rolling 48h feed. '+
                    '<b>Regions represented:</b> '+
                    esc(', '.join(state.get('regional_regions_represented') or []) or 'None')+
                    '. These are NOT newly issued permits. '+
                    '<a href="GTA_RADAR_REGIONAL_COVERAGE.csv">Regional collection gaps and coverage</a>.</p>')
        if state.get('regional_passed_selector') is not None:
            page.append('<p><b>Regional source records passing commercial filter:</b> '+
                        esc(state['regional_passed_selector'])+
                        '. <a href="GTA_RADAR_REGIONAL_SELECTION_OUTCOMES.csv">Per-region selection outcomes</a>.</p>')
    if state.get('regional_bridge_error'):
        page.append('<p><b>Regional supplement unavailable:</b> '+
                    esc(state['regional_bridge_error'])+'. Other collectors continue.</p>')
    page.append('<h2>Collection steps</h2>')
    for step in state.get('steps', []):
        page.append(f'<p><b>{esc(step["step"])}</b>: {esc(step["status"])} '
                    f'<span class="muted">({esc(step.get("detail", ""))})</span></p>')
    if state.get('lead_reports'):
        reports=state['lead_reports']
        page.append('<p><b>Researched commercial prospect records (not necessarily current jobs):</b> '+
                    esc(reports.get('project_opportunities',0))+
                    ' · <b>Public company contact channels:</b> '+esc(reports.get('public_company_contacts',0))+
                    ' · <b>Company-only enrichment records (not sales triggers):</b> '+
                    esc(reports.get('company_enrichment',0))+'</p>')
        page.append('<p><b>Automatic qualification:</b> '+
                    esc(reports.get('qualified_investigation_candidates',0))+
                    ' high-confidence projects to investigate (unlimited count); '+
                    esc(reports.get('opportunity_research_gaps',0))+
                    ' others retained for rechecking or historical context. '
                    'Not proof of unawarded contracts.</p>')
        page.append('<p><b>Genuine-opportunity review:</b> '+
                    esc(reports.get('early_stage_review',0))+' early-stage · '+
                    esc(reports.get('issued_stage_review',0))+' issued-permit timing checks · '+
                    esc(reports.get('historical_or_inactive',0))+' historical/inactive · '+
                    esc(reports.get('exact_project_verification_needed',0))+' exact-ID verification required. '+
                    '<a href="GTA_RADAR_GENUINE_OPPORTUNITY_REVIEW.csv">Open full lifecycle review</a>. '+
                    'No listed project is automatically an open supplier contract.</p>')
    if state.get('free_daily_watch'):
        free=state['free_daily_watch']
        page.append('<p><b>FREE municipal development watch:</b> '+
                    esc(free.get('first_observed',0))+' newly observed records · '+
                    esc(free.get('record_changed',0))+' records changed · '+
                    esc(free.get('initial_baseline',0))+' initial baseline records · '+
                    esc(free.get('archive_context',0))+' archived regional source records indexed. '+
                    '<b>Free collection stage costs $0 DeepSeek.</b> '+
                    '<a href="GTA_RADAR_DAILY_NEW_DEVELOPMENTS.html">Open this run\'s source-event report</a>.</p>')
    if state.get('selective_ai'):
        ai=state['selective_ai']
        page.append('<p><b>Selective DeepSeek (US$0.25/day maximum):</b> '+
                    esc(ai.get('new_eligible',0))+' newly eligible · '+
                    esc(ai.get('pending_before',0))+' eligible pending · '+
                    esc(ai.get('paid_research_attempts',0))+' model calls attempted · '+
                    esc(ai.get('actual_daily_ledger_estimate_usd',0))+
                    ' USD total estimated ledger use today · '+
                    esc(ai.get('status','UNKNOWN'))+
                    '. Unchanged historic queue projects were not authorized for AI.</p>')
    page.append('<h2>Evidence-backed commercial intelligence</h2>')
    page.append('<p>Project evidence is assessed automatically. A project does not imply '
                'that a supplier purchase is underway.</p>')
    if state.get('queue_total',0):
        page.append('<p><b>'+esc(state.get('queue_total'))+
                    '</b> projects remain in the persistent research backlog, including '+
                    esc(state.get('queue_initial_uninvestigated',0))+
                    ' awaiting their first successful AI analysis. They will survive '+
                    'the 48-hour source window and resume automatically on later days. '+
                    'No manual verification is required to keep them queued.</p>')
    if state.get('queue_stop_reason') in ('DAILY_USD_LIMIT','RUNTIME_WINDOW','OPTIONAL_RUN_LIMIT'):
        page.append('<p><b>Collection succeeded; AI research remains incomplete.</b> '+
                    'Further investigations will continue automatically within the US$1 daily budget.</p>')
    if not visible:
        page.append('<p>No additional evidence-backed project was established in this run. '
                    'Unresolved records remain queued for later automated discovery.</p>')
    for v in visible:
        page.append(f'<article><h3>{esc(v.get("address") or v.get("project_id"))}</h3>'
                    f'<p><span class="pill">{esc(v.get("status"))}</span> — {esc(v.get("project_stage"))}</p>'
                    f'<p><b>Company/operator:</b> {esc(v.get("operator")) or "Unknown"} '
                    f'· <b>Developer:</b> {esc(v.get("developer")) or "Unknown"}</p>'
                    f'<p><b>Possible services:</b> {esc(v.get("buyer_fit")) or "Unverified"}</p>'
                    f'<p><b>Public contact:</b> {esc(v.get("contact")) or "Not identified"}</p>'
                    f'<p><b>Research maturity:</b> {esc(v.get("lead_maturity")) or "Prior-version record"}</p>'
                    f'<p><b>Next system action:</b> {esc(v.get("next_system_action") or v.get("next_verification")) or "Continue scheduled research"}</p>'
                    f'<p class="muted">{esc(v.get("caveats"))}</p>')
        for url in str(v.get('source_urls') or '').split(' | '):
            if safe_link(url):
                page.append(f'<a href="{esc(url)}" rel="noopener noreferrer">Supporting public page</a> · ')
        page.append('</article>')
    page.append('</body></html>')
    file.write_text(''.join(page), encoding='utf-8')
    return file


def schedule_daily(script_path, workspace, at='08:30', *, no_ai=False, selective_ai=False):
    if os.name != 'nt':
        return 'NOT_WINDOWS'
    # Do not replace previous schedule until the new task is successfully created.
    runner = Path(script_path).resolve()
    if no_ai and selective_ai:raise ValueError('Conflicting task modes')
    option=' --selective-ai' if selective_ai else (' --no-ai' if no_ai else '')
    command = f'cmd.exe /c ""{runner}" --unattended{option}"'
    proc = subprocess.run(['schtasks.exe','/Create','/F','/SC','DAILY','/ST',at,
                           '/TN',TASK_NAME,'/TR',command], capture_output=True, text=True, timeout=30)
    if proc.returncode:
        return 'FAILED: ' + str(proc.stderr or proc.stdout)[:240]
    if no_ai or selective_ai:
        # The user disabled the prior V6 task. Overwriting a disabled task can
        # leave it disabled, so explicitly enable the free-only schedule.
        enabled=subprocess.run(['schtasks.exe','/Change','/TN',TASK_NAME,'/ENABLE'],
                               capture_output=True,text=True,timeout=30)
        if enabled.returncode:
            return 'FAILED_TO_ENABLE_FREE_TASK: '+str(enabled.stderr or enabled.stdout)[:240]
    # Avoid two daily collectors or divergent budget ledgers running together.
    old = subprocess.run(['schtasks.exe','/Delete','/F','/TN',PREVIOUS_TASK],
                         capture_output=True, text=True, timeout=20)
    return 'SUCCESS' if old.returncode == 0 else 'SUCCESS_NEW_TASK; REVIEW_OLD_V5_TASK'


def pipeline(workspace, database=None, *, run_collectors=True, run_research=True, selective_ai=False,
             max_projects=MAX_INVESTIGATIONS,collector=run_step,selector=None,
             investigator=investigate,results_dir=None,today=None):
    ws = Path(workspace).resolve()
    db = Path(database or choose_database(ws)).resolve()
    data = db.parent
    out = Path(results_dir or (ws / 'GTA_RADAR_RESULTS')).resolve()
    out.mkdir(parents=True, exist_ok=True)
    lock = once_lock(out)
    day = today or dt.date.today()
    # Disabled sources remain accounted for in the unified report, not silently enabled.
    try:
        with (ROOT / 'config' / 'sources.json').open(encoding='utf-8') as source_file:
            disabled_count=sum(not item.get('enabled',False) for item in json.load(source_file))
    except (OSError,ValueError):
        disabled_count='UNVERIFIED'
    state = {'version': VERSION, 'started_local': dt.datetime.now().astimezone().isoformat(timespec='seconds'),
             'database': str(db), 'status': 'RUNNING', 'investigation_date': day.isoformat(),
             'steps': [], 'projects': 0, 'investigated': 0, 'reserved_usd': 0,
             'disabled_source_count': disabled_count}
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
            # Keep independent source histories and only ingest verified changes.
            steps.extend([
                ('early_planning_pilot',['early_signal_watch.py','--data-dir',data,'--output-dir',out],1800),
                ('early_industrial_cues',['early_cue_watch.py','--data-dir',data,'--output-dir',out],900),
                ('early_agendas',['early_discovery_watch.py','--data-dir',data,'--output-dir',out],900),
                ('early_hamilton',['early_hamilton_watch.py','--data-dir',data,'--output-dir',out],900),
                ('early_notices',['early_public_notices.py','--data-dir',data,'--output-dir',out],900),
                # Discovery-only pilot outputs: not forwarded to paid research.
                ('early_ajax',['early_ajax_watch.py','--data-dir',data,'--output-dir',out],900),
                ('early_oakville',['early_oakville_watch.py','--data-dir',data,'--output-dir',out],900),
                ('early_markham',['early_markham_circulation.py','--data-dir',data,'--output-dir',out],900),
                ('early_investment_tenders',['early_investment_tenders.py','--data-dir',data,'--output-dir',out],900),
            ])
            for name, command, timeout in steps:
                outcome = collector(name, command, out / 'V6_LOGS', timeout=timeout)
                state['steps'].append(outcome)
                atomic_json(manifest, state)
            # Optional early pilots are independently reported; do not convert a
            # healthy core refresh into PARTIAL and suppress its selective AI.
            core_steps = [step for step in state['steps']
                          if step['step'] in ('municipal_collector','business_collector')]
            core_succeeded = sum(step['status'] == 'SUCCESS' for step in core_steps)
            state['early_pilot_results'] = [
                {'step':step['step'],'status':step['status']}
                for step in state['steps'] if step['step'].startswith('early_')]
            # A single status inventory covers every configured and independent source.
            try:
                from unified_collector_inventory import build
                _,inventory=build(out,ROOT/'config'/'sources.json',state['steps'])
                state.update(inventory)
            except (OSError,ValueError,csv.Error) as exc:
                state['collector_inventory_error']=str(exc)[:200]
            if not core_succeeded:
                state['status'] = 'FAILED'
                state['note'] = 'No core collectors succeeded; prior export NOT reused and AI NOT run.'
                return state
            state['status'] = 'PARTIAL' if core_succeeded < len(core_steps) else 'SUCCESS'
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
        state['active_stage']='COMMERCIAL_SELECTION'
        use_default_selector = selector is None
        if use_default_selector:
            import commercial_selector_v4 as v4
            selector = v4.run
        selection_file=data / 'opportunities_ALL_REVIEW_ONLY.csv'
        if use_default_selector and db.is_file():
            try:
                from regional_candidate_bridge import selection_input
                selection_file,regional_summary=selection_input(selection_file,db,out,today=day)
                state.update(regional_summary)
            except (OSError,ValueError,sqlite3.DatabaseError) as exc:
                # Never misrepresent uncollected regions as successfully covered,
                # and never damage the primary 48-hour collector output.
                state['regional_bridge_error']=type(exc).__name__+': '+str(exc)[:180]
        if use_default_selector and run_collectors:
            try:
                from integrated_early_events import merge
                # Fail closed: previous status/CSV files may remain after a crash.
                # Only use pilot outputs from collector steps successful THIS run.
                successful_pilots={
                    step['step'] for step in state['steps']
                    if step.get('status')=='SUCCESS'
                }
                selection_file, integration=merge(
                    selection_file,out,out/'GTA_RADAR_INTEGRATED_EARLY_EVENTS.csv',
                    successful_steps=successful_pilots)
                state.update(integration)
            except (OSError,ValueError,csv.Error) as exc:
                state['early_integration_error']=str(exc)[:180]
        selector(selection_file, out, db)
        if use_default_selector and not state.get('regional_bridge_error'):
            from regional_candidate_bridge import selection_outcomes
            state.update(selection_outcomes(out))
        projects = out / 'CANDIDATES_V4_ALL_REVIEW_ONLY.csv'
        if not projects.exists():
            raise RuntimeError('V4 did not produce a candidate CSV.')
        with projects.open(encoding='utf-8-sig',newline='') as f:
            state['projects'] = sum(1 for _ in csv.DictReader(f))
        if run_research:
            state['active_stage']='DEEPSEEK_RESEARCH'
            outcome = investigator(data, out, max_projects=max_projects)
            state['investigated'] = outcome['processed']
            state['with_public_pages'] = outcome['with_public_pages']
            state['source_backed_projects']=outcome.get('source_backed_projects',0)
            state['publicly_contactable']=outcome.get('publicly_contactable',0)
            state['reserved_usd'] = outcome['reserved_usd']
            state['charged_estimate_usd'] = outcome.get('charged_estimate_usd',0)
            state['unresolved_reservations_usd'] = outcome.get('unresolved_reservations_usd',0)
            state['ai_configured'] = outcome['deepseek_configured']
            state['native_searches']=outcome.get('native_searches',0)
            state['native_fetches']=outcome.get('native_fetches',0)
            state['official_queries']=outcome.get('official_queries',0)
            state['official_live_matches']=outcome.get('official_live_matches',0)
            state['official_local_matches']=outcome.get('official_local_matches',0)
            state['ai_plans_attempted']=outcome.get('ai_plans_attempted',0)
            state['ai_plans_completed']=outcome.get('ai_plans_completed',0)
            state['ai_plans_failed']=outcome.get('ai_plans_failed',0)
            state['ai_plans_deferred']=outcome.get('ai_plans_deferred',0)
            state['ai_calls_attempted']=outcome.get('ai_calls_attempted',0)
            state['company_contact_searches']=outcome.get('company_contact_searches',0)
            state['company_contacts_discovered']=outcome.get('company_contacts_discovered',0)
            state['duplicate_model_skipped']=outcome.get('duplicate_model_skipped',0)
            state['ai_calls_succeeded']=outcome.get('ai_calls_succeeded',0)
            state['source_only_ai_calls']=outcome.get('source_only_ai_calls',0)
            state['ai_budget_deferred']=outcome.get('ai_budget_deferred',0)
            state['queue_total']=outcome.get('queue_total',0)
            state['queue_due']=outcome.get('queue_due',0)
            state['queue_initial_uninvestigated']=outcome.get('queue_initial_uninvestigated',0)
            state['queue_stop_reason']=outcome.get('queue_stop_reason','UNKNOWN')
            state['no_corroboration']=outcome.get('no_corroboration',0)
            state['investigated']=outcome.get('current_invocations',outcome['processed'])
            state['active_stage']='COMMERCIAL_REPORTING'
            from commercial_lead_reports import build as build_commercial_reports
            state['lead_reports']=build_commercial_reports(out)
        else:
            state['ai_mode']='SELECTIVE_USD_0_25' if selective_ai else 'OFF'
            state['active_stage']='FREE_DAILY_RECORD_WATCH'
            from free_daily_report import build as build_free_daily, CSV_NAME
            state['free_daily_watch']=build_free_daily(projects,out,today=day)
            state['note']='Free municipal watch completed without DeepSeek calls.'
            if selective_ai:
                state['active_stage']='SELECTIVE_DEEPSEEK_USD_0_25'
                from selective_daily_ai import run as selective_run
                if state['status']=='PARTIAL':
                    state['selective_ai']={'status':'COLLECTOR_PARTIAL_SKIP_PAID_AI',
                                           'daily_ceiling_usd':0.25,
                                           'paid_research_attempts':0}
                else:
                    state['selective_ai']=selective_run(
                        projects,out/CSV_NAME,out,data,today=day)
                state['investigated']=state['selective_ai'].get('investigated',0)
                state['reserved_usd']=state['selective_ai'].get(
                    'actual_daily_ledger_estimate_usd',0)
                state['queue_stop_reason']=state['selective_ai'].get('status','UNKNOWN')
                state['active_stage']='COMMERCIAL_REPORTING'
                from commercial_lead_reports import build as build_commercial_reports
                state['lead_reports']=build_commercial_reports(out)
                state['note']='Selective AI limited to eligible new/changed projects; daily ceiling US$0.25.'
        return state
    except Exception as exc:
        state['status'] = 'FAILED'
        state['error'] = type(exc).__name__ + ': ' + str(exc)[:250]
        diagnostic=traceback.format_exc(limit=18)[-6000:]
        state['error_stage']=state.get('active_stage','UNKNOWN')
        # Preserve enough detail to identify the exact crashing line next time,
        # without retaining API keys, HTTP headers, or municipal input payloads.
        # Format traceback stack + exception only; do not log API responses.
        log=out/'V6_LOGS'/'pipeline_error.log'
        try:
            log.parent.mkdir(parents=True,exist_ok=True)
            log.write_text(diagnostic,encoding='utf-8')
            state['error_log']=str(log)
        except OSError:
            state['error_log']='COULD_NOT_WRITE_DIAGNOSTIC'
        # V8 checkpoints its investigation history before every next project.
        # A top-level failure should not imply AI accomplished nothing; show
        # how many completed/reviewed records were checkpointed today.
        checkpoint=out/'GTA_RADAR_V6_LATEST_INVESTIGATIONS.csv'
        try:
            if checkpoint.is_file():
                with checkpoint.open(encoding='utf-8-sig',newline='') as handle:
                    state['checkpointed_investigations_today']=sum(
                        1 for rec in csv.DictReader(handle)
                        if rec.get('investigated_local_date')==day.isoformat())
        except (OSError,csv.Error):
            pass
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
    parser.add_argument('--selective-ai',action='store_true',
                        help='New and changed commercial project AI, max USD 0.25/day')
    parser.add_argument('--install-selective-schedule',action='store_true',
                        help='Set 08:30 selective USD 0.25 task without running AI')
    parser.add_argument('--install-free-schedule',action='store_true',
                        help='Only schedule the 08:30 daily free-data run; do not run collectors or DeepSeek')
    parser.add_argument('--offline-test', action='store_true', help='Only for local diagnostics, never marketed as fresh collection')
    parser.add_argument('--no-schedule', action='store_true')
    args=parser.parse_args(argv)
    try:
        workspace = find_workspace(args.workspace)
        db = args.database or choose_database(workspace)
        say('Using your established database: ' + str(db))
        if args.install_free_schedule and args.install_selective_schedule:
            say('Only one schedule mode can be selected.');return 1
        if args.no_ai and args.selective_ai:
            say('Cannot combine --no-ai with --selective-ai.');return 1
        if args.install_selective_schedule:
            installed=ROOT/'RUN_GTA_RADAR_V6.bat'
            if not installed.is_file():
                say('Selective schedule NOT installed: stable runner missing.');return 1
            status=schedule_daily(installed,workspace,selective_ai=True)
            say('Daily 08:30 selective (US$0.25) task: '+status)
            say('Setup made NO DeepSeek requests and did not run collectors.')
            return 0 if status.startswith('SUCCESS') else 1
        if args.install_free_schedule:
            installed=ROOT/'RUN_GTA_RADAR_V6.bat'
            if not installed.is_file():
                say('Free schedule NOT installed: stable runner missing.');return 1
            status=schedule_daily(installed,workspace,no_ai=True)
            say('Daily 08:30 free collection task: '+status)
            say('This setup made no DeepSeek requests and did not run collectors.')
            return 0 if status.startswith('SUCCESS') else 1
        say('Running live collection first. Existing history will be preserved as collectors update it.')
        state=pipeline(workspace, db, run_collectors=not args.offline_test,
                       run_research=not (args.no_ai or args.selective_ai),
                       selective_ai=args.selective_ai,results_dir=args.results_dir,
                       max_projects=min(5000, max(0,args.max_projects)))
        dest=Path(args.results_dir or (workspace/'GTA_RADAR_RESULTS')) / 'GTA_RADAR_V6_DASHBOARD.html'
        say('Run status: '+state['status']+'; projects: '+str(state.get('projects',0))+
            '; AI researched now: '+str(state.get('investigated',0))+
            '; persistent queue: '+str(state.get('queue_total',0))+
            '; stop reason: '+str(state.get('queue_stop_reason','NOT_RUN')))
        if state.get('error') or state.get('note'): say(state.get('error') or state.get('note'))
        say('Dashboard: ' + str(dest))
        if not args.unattended and dest.exists():
            if os.name=='nt': os.startfile(str(dest))
            else: webbrowser.open(dest.resolve().as_uri())
        if not args.unattended and not args.no_schedule and state['status'] in ('SUCCESS','PARTIAL'):
            # The scheduled program should be the stable, installed runner, never a Downloads ZIP.
            installed=Path(__file__).resolve().parent/'RUN_GTA_RADAR_V6.bat'
            if installed.is_file(): say('Daily task: '+schedule_daily(installed,workspace,no_ai=args.no_ai,selective_ai=args.selective_ai))
            else:say('Daily task not installed: stable launcher missing.')
        return 0 if state['status']=='SUCCESS' else 1
    except Exception as exc:
        say('Could not start: '+type(exc).__name__+': '+str(exc)[:250]);return 1


if __name__=='__main__': raise SystemExit(main())