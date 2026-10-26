"""Single free early-cue workflow + optional capped DeepSeek research.

Runs only the nine original early pilots and four new investment sources.
Never runs core V8 municipal/permit/business collectors or a scheduled task.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import html
import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

from desktop_v8_early_preview import prepare
from early_purchase_queue import compile_sources,export
from radar_run_lock import once_lock

RUNNERS=(
 ('early_planning_pilot','early_signal_watch.py',1800),
 ('early_industrial_cues','early_cue_watch.py',900),
 ('early_agendas','early_discovery_watch.py',900),
 ('early_hamilton','early_hamilton_watch.py',900),
 ('early_notices','early_public_notices.py',900),
 ('early_ajax','early_ajax_watch.py',900),
 ('early_oakville','early_oakville_watch.py',900),
 ('early_markham','early_markham_circulation.py',900),
 ('early_investment_tenders','early_investment_tenders.py',900),
 ('investment_cues','investment_cue_watch.py',900),
)
SOURCES={
 'early_planning_pilot':('EARLY_SIGNALS_SOURCES_STATUS.csv','status',7),
 'early_industrial_cues':('EARLY_CUES_SOURCE_STATUS.csv','state',2),
 'early_agendas':('EARLY_DISCOVERY_SOURCE_STATUS.csv','status',2),
 'early_hamilton':('EARLY_HAMILTON_SOURCE_STATUS.csv','status',2),
 'early_notices':('EARLY_PUBLIC_NOTICES_SOURCE_STATUS.csv','status',3),
 'early_ajax':('EARLY_AJAX_SOURCE_STATUS.csv','status',1),
 'early_oakville':('EARLY_OAKVILLE_SOURCE_STATUS.csv','status',1),
 'early_markham':('EARLY_MARKHAM_REPORT_SOURCE_STATUS.csv','status',1),
 'early_investment_tenders':('EARLY_INVESTMENT_TENDERS_STATUS.csv','status',2),
 'investment_cues':('EARLY_INVESTMENT_SOURCE_STATUS.csv','status',4),
}
REPORT='GTA_RADAR_EARLY_INVESTMENT.html'

def read(path):
    if not path.is_file():return []
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def run(data,results,*,paid=False,collector=None,researcher=None):
    data=Path(data);results=Path(results)
    data.mkdir(parents=True,exist_ok=True);results.mkdir(parents=True,exist_ok=True)
    lock=once_lock(results)
    now=dt.datetime.now().astimezone().isoformat(timespec='seconds')
    state={'started_local':now,'status':'RUNNING','paid_ai_requested':bool(paid),
           'deepseek_budget_cap_usd':0.25,'steps':[]}
    manifest=results/'GTA_RADAR_EARLY_INVESTMENT_RUN.json'
    try:
        good=set()
        for name,script,timeout in RUNNERS:
            print('Collecting:',name,flush=True)
            if collector:
                result=collector(name,[script,'--data-dir',str(data),'--output-dir',str(results)])
                code=result.get('exit_code',0 if result.get('status')=='SUCCESS' else 1)
            else:
                log=results/'EARLY_LOGS';log.mkdir(exist_ok=True)
                with (log/(name+'.log')).open('w',encoding='utf-8') as f:
                    try:code=subprocess.run([sys.executable,str(Path(__file__).with_name(script)),
                        '--data-dir',str(data),'--output-dir',str(results)],
                        stdout=f,stderr=subprocess.STDOUT,timeout=timeout,check=False).returncode
                    except (OSError,subprocess.TimeoutExpired) as exc:
                        code=124;f.write(str(exc))
                result=dict(step=name,status='SUCCESS' if code==0 else 'FAILED',exit_code=code)
            state['steps'].append(result)
            if code==0:good.add(name)
            manifest.write_text(json.dumps(state,indent=2),encoding='utf-8')
        src=[]
        for runner,(filename,column,expected) in SOURCES.items():
            rows=read(results/filename) if runner in good or runner=='investment_cues' else []
            for row in rows:
                status=(row.get(column) or 'UNREPORTED') if runner in good or runner=='investment_cues' else 'RUNNER_FAILED'
                src.append(dict(source_id=row.get('source_id'),runner=runner,status=status,
                    fetched=row.get('fetched') or row.get('reports_indexed') or '',
                    new=row.get('new') or '',updated=row.get('updated') or '',
                    error=row.get('error') or row.get('warning') or ''))
            if len(rows)<expected:
                src.append(dict(source_id='MISSING_SOURCE_STATUS',runner=runner,
                    status='SOURCE_REPORT_MISSING',fetched='',new='',updated='',error=''))
        with (results/'GTA_RADAR_EARLY_SOURCES.csv').open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=('source_id','runner','status','fetched','new','updated','error'))
            w.writeheader();w.writerows(src)
        candidates,gaps=compile_sources(results,good,now)
        csv_file=export(results,candidates,gaps)
        state.update(eligible_early_cues=len(candidates),held_for_research=len(gaps),
                     source_issues=sum(r['status'] not in ('SUCCESS','SUCCESS_INDEX_ONLY','SUCCESS_REPORT_INDEX') for r in src))
        state['status']='PARTIAL' if state['source_issues'] else 'SUCCESS'
        state['ai_status']='DISABLED_FREE_RUN'
        if paid and candidates:
            # Exact whitelist: never pay on the historical pilot backlog.
            # Uses V8's already implemented shared ledger and USD 0.25 cap.
            ids={r['project_id'] for r in candidates}
            if researcher:
                ans=researcher(csv_file,results,legacy_data_dir=data,budget_cap_usd=.25,
                               eligible_project_ids=ids)
            else:
                import v8_deepseek_native
                ans=v8_deepseek_native.run(csv_file,results,legacy_data_dir=data,
                         budget_cap_usd=.25,eligible_project_ids=ids,max_runtime_seconds=600)
            state['ai_status']=ans.get('queue_stop_reason','FINISHED')
            state['ai_results']=ans.get('processed',0)
            state['ai_budget_reserved_usd']=ans.get('reserved_usd',0)
        report(results,state,src,candidates,gaps)
        return state
    except Exception as exc:
        state['status']='FAILED'
        state['error']=type(exc).__name__+': '+str(exc)[:350]
        report(results,state,[],[],[])
        return state
    finally:
        state['finished_local']=dt.datetime.now().astimezone().isoformat(timespec='seconds')
        manifest.write_text(json.dumps(state,indent=2),encoding='utf-8')
        lock.unlink(missing_ok=True)

def report(root,state,sources,candidates,gaps):
    esc=lambda x:html.escape(str(x if x is not None else ''),quote=True)
    def link(file,name):return '<a href="'+esc(file)+'">'+esc(name)+'</a>'
    page=['<!doctype html><html><head><meta charset="utf-8"><title>GTA Radar: Investment Cues</title>',
      '<style>body{font:15px Segoe UI,Arial;max-width:1050px;margin:35px auto;padding:0 18px;background:#f5f7fa;color:#182536}'
      'article{background:white;border:1px solid #dfe4ea;border-radius:9px;padding:16px;margin:12px 0}'
      'table{border-collapse:collapse;width:100%;background:white}td,th{border-bottom:1px solid #e0e0e0;padding:9px;text-align:left}'
      'a{color:#2266a3}small{color:#566}</style></head><body>',
      '<h1>GTA Radar — Early investment signals</h1>',
      '<p>Only early public investment and planning sources. No core V8 permit/business collection.</p>',
      '<article><b>Run:</b> '+esc(state.get('status'))+' · <b>Fresh qualified research cues:</b> '+esc(len(candidates))+
      ' · <b>Held as incomplete or context:</b> '+esc(len(gaps))+' · <b>Source issues:</b> '+esc(state.get('source_issues'))+
      ' · <b>DeepSeek:</b> '+esc(state.get('ai_status') or 'OFF')+' · <b>Software cap:</b> US$0.25/day</article>',
      '<p>'+link('GTA_RADAR_EARLY_SOURCES.csv','Source health')+' · '+
      link('GTA_RADAR_EARLY_PURCHASE_CANDIDATES.csv','Research candidates')+' · '+
      link('GTA_RADAR_EARLY_PURCHASE_RESEARCH_GAPS.csv','Not qualified')+' · '+
      link('EARLY_INVESTMENT_RESEARCH_QUEUE.csv','Investment announcements and context')+'</p>',
      '<small>Dates are source publication dates only where explicitly supplied. First observed is a Radar observation, not proof of discovery lead time. Likely purchases are hypotheses; procurement remains UNKNOWN without independent evidence. An initial baseline generates no new research cues.</small>',
      '<h2>Signals needing buyer and purchasing-window research</h2>']
    if not candidates:page.append('<article>No eligible post-baseline project changes in this run. This does NOT mean there are no investments.</article>')
    for x in candidates[:40]:
        page.append('<article><b>'+esc(x['company_name'] or x['address'] or x['source_id'])+
         '</b><p>'+esc(x['description'])+'</p><small>'+esc(x['source_id'])+' · '+
         esc(x['event_date'])+' · Buyer not verified · Procurement UNKNOWN</small></article>')
    page.append('<h2>Source health</h2><table><tr><th>Feed</th><th>Status</th><th>Records</th><th>Error / limitation</th></tr>')
    for x in sources:
        page.append('<tr><td>'+esc(x['source_id'])+'</td><td>'+esc(x['status'])+'</td><td>'+esc(x['fetched'])+'</td><td>'+esc(x['error'])+'</td></tr>')
    page.append('</table></body></html>')
    (root/REPORT).write_text(''.join(page),encoding='utf-8')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--paid-ai',action='store_true',help='Opt in to DeepSeek (max USD 0.25 per local day)')
    args=p.parse_args(argv)
    _,db,out=prepare()
    print('EARLY INVESTMENT RADAR: safe isolated desktop test',flush=True)
    print('History:',db.parent,' | Results:',out,flush=True)
    state=run(db.parent,out,paid=args.paid_ai)
    file=out/REPORT
    if file.is_file():
        try:
            if os.name=='nt':os.startfile(str(file))
            else:webbrowser.open(file.resolve().as_uri())
        except OSError:print('Open report at:',file,flush=True)
    print('Status',state['status'],'qualified cues',state.get('eligible_early_cues',0),
          'DeepSeek',state.get('ai_status'),flush=True)
    return 0 if state['status']=='SUCCESS' else 1

if __name__=='__main__':raise SystemExit(main())
