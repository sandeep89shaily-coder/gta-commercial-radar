"""Early-cue-only execution of the existing GTA Radar pilot collectors.

No original V8 municipal/business collector, no permit ranking, DeepSeek,
scheduled task, source configuration change, or production data writes.
"""
from __future__ import annotations

import csv
import datetime as dt
import html
import json
from pathlib import Path

from integrated_early_events import FIELDS as BRIDGE_FIELDS, merge
from radar_run_lock import once_lock
from unified_collector_inventory import PILOT_GROUPS, build as source_inventory
from v6_daily_pipeline import ROOT, run_step

RUNNERS = (
    ("early_planning_pilot", "early_signal_watch.py", 1800),
    ("early_industrial_cues", "early_cue_watch.py", 900),
    ("early_agendas", "early_discovery_watch.py", 900),
    ("early_hamilton", "early_hamilton_watch.py", 900),
    ("early_notices", "early_public_notices.py", 900),
    ("early_ajax", "early_ajax_watch.py", 900),
    ("early_oakville", "early_oakville_watch.py", 900),
    ("early_markham", "early_markham_circulation.py", 900),
    ("early_investment_tenders", "early_investment_tenders.py", 900),
)

if {name for name, _, _ in RUNNERS} != set(PILOT_GROUPS):
    raise RuntimeError("Early runner list and source inventory disagree")

REPORT = "GTA_RADAR_EARLY_ONLY.html"
SOURCES_CSV = "GTA_RADAR_EARLY_ONLY_SOURCES.csv"
RUN_JSON = "GTA_RADAR_EARLY_ONLY_RUN.json"


def csv_read(path):
    if not Path(path).exists():
        return []
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def present(out, state, rows):
    escape=lambda value: html.escape(str(value if value is not None else ""),quote=True)
    seen=csv_read(out/"GTA_RADAR_EARLY_CUES_REVIEW.csv")
    preview=sorted(seen,key=lambda item:(item["pipeline_disposition"]!="EARLY_SELECTOR_CANDIDATE",
                                        item.get("source_id","")))
    def link(filename, label):
        return '<a href="'+escape(filename)+'">'+escape(label)+'</a>'
    incomplete=[r for r in rows if not r["execution_status"].startswith("SUCCESS")]
    page=[
        '<!doctype html><html><head><meta charset="utf-8"><title>GTA Radar Early Cues</title>',
        '<style>body{font:15px Segoe UI,Arial;max-width:1000px;margin:30px auto;padding:0 15px;'
        'background:#f6f8fa;color:#182436}article{background:white;border:1px solid #dce3ea;'
        'border-radius:8px;padding:15px;margin:12px 0}a{color:#175d9e}small{color:#5b697b}'
        'table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;'
        'padding:8px;text-align:left;vertical-align:top}</style></head><body>',
        '<h1>GTA Radar — Early Investment Cues</h1>',
        '<p><strong>Early collectors only.</strong> Original V8 municipal and business collectors '
        'were not run. DeepSeek calls: <strong>0</strong>. Scheduled tasks unchanged.</p>',
        '<article><b>Runner status:</b> '+escape(state["status"])+
        ' · <b>Unique additional feeds:</b> 17 · <b>Pilot definitions:</b> 21 across 9 runners'
        ' · <b>Fresh post-baseline signals reviewed:</b> '+escape(len(seen))+
        ' · <b>Passed initial filter:</b> '+escape(state["early_pilot_changes_accepted"])+
        ' · <b>Unqualified / review only:</b> '+escape(state["early_cues_review_only"])+
        '</article>',
        '<p>'+link(SOURCES_CSV,"Source-by-source health (21 pilot definitions)")+' · '+
        link("GTA_RADAR_EARLY_CUES_REVIEW.csv","All newly detected early cues")+' · '+
        link("GTA_RADAR_EARLY_QUALIFIED_CANDIDATES.csv","Candidates for further buyer research")+'</p>',
        '<p><small>New means first seen since this source baseline, not proof of first public '
        'posting, unawarded work, or permit status. An initial baseline produces no new cues.</small></p>',
    ]
    if incomplete:
        page.append('<article><h2>Feeds needing attention</h2><table>'
                    '<tr><th>Source</th><th>Reported status</th></tr>'+
                    ''.join('<tr><td>'+escape(r["source_id"])+'</td><td>'+
                            escape(r["execution_status"])+'</td></tr>' for r in incomplete)+
                    '</table></article>')
    page.append('<h2>Newly observed cues (not verified sales leads)</h2>')
    if not preview:
        page.append('<article>No post-baseline changes from successfully reporting '
                    'pilot sources this run. See source health for failures and partial feeds.'
                    '</article>')
    else:
        for item in preview[:100]:
            page.append('<article><b>'+escape(item.get("description") or "Unnamed signal")+
                        '</b> · '+escape(item.get("pipeline_disposition"))+
                        '<p>Source: '+escape(item.get("source_id"))+
                        ' · Stage: '+escape(item.get("stage") or "Not reported")+
                        ' · Site: '+escape(item.get("site") or "Unverified")+
                        '</p><small>Observed: '+escape(item.get("observed_at"))+
                        ' · Contract selection: '+escape(item.get("procurement_status"))+
                        ' · Permit status: not verified</small></article>')
    page.append('</body></html>')
    target=out/REPORT
    target.write_text("".join(page),encoding="utf-8")
    return target


def run(data_dir, results_dir, collector=run_step):
    """Run nine existing pilot programs only, preserving the first-seen baselines."""
    data=Path(data_dir).resolve()
    out=Path(results_dir).resolve()
    data.mkdir(parents=True,exist_ok=True)
    out.mkdir(parents=True,exist_ok=True)
    lock=once_lock(out)
    state=dict(started_local=dt.datetime.now().astimezone().isoformat(timespec="seconds"),
               status="RUNNING",mode="EARLY_ONLY_NO_AI",
               steps=[],deepseek_calls=0,disabled_source_changes=0)
    manifest=out/RUN_JSON
    try:
        for name,script,timeout in RUNNERS:
            result=collector(name,[script,"--data-dir",str(data),"--output-dir",str(out)],
                             out/"V6_LOGS",timeout=timeout)
            state["steps"].append(result)
            manifest.write_text(json.dumps(state,indent=2),encoding="utf-8")
        inventory_path,count=source_inventory(out,ROOT/"config"/"sources.json",
                            state["steps"],run_started=state["started_local"])
        state.update(count)
        all_rows=csv_read(inventory_path)
        pilot=[r for r in all_rows if r.get("group")!="CORE_CONFIG"]
        if len(pilot)!=21:
            raise RuntimeError("Expected 21 pilot source definitions")
        with (out/SOURCES_CSV).open("w",encoding="utf-8-sig",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=pilot[0].keys())
            writer.writeheader();writer.writerows(pilot)
        empty=out/"EARLY_ONLY_EMPTY_INPUT.csv"
        with empty.open("w",encoding="utf-8-sig",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=BRIDGE_FIELDS)
            writer.writeheader()
        successful={item["step"] for item in state["steps"]
                    if item.get("status")=="SUCCESS"}
        accepted,summary=merge(empty,out,out/"GTA_RADAR_EARLY_QUALIFIED_CANDIDATES.csv",
                               successful_steps=successful,
                               run_started=state["started_local"])
        state.update(summary)
        core_failures=sum(step.get("status")!="SUCCESS" for step in state["steps"])
        feed_issues=sum(not r["execution_status"].startswith("SUCCESS") for r in pilot)
        state["runner_failures"]=core_failures
        state["source_attention_count"]=feed_issues
        state["status"]="PARTIAL" if core_failures or feed_issues else "SUCCESS"
        state["early_only_report"]=str(present(out,state,pilot))
        return state
    except Exception as exc:
        state["status"]="FAILED"
        state["error"]=type(exc).__name__+": "+str(exc)[:300]
        return state
    finally:
        state["finished_local"]=dt.datetime.now().astimezone().isoformat(timespec="seconds")
        manifest.write_text(json.dumps(state,indent=2),encoding="utf-8")
        lock.unlink(missing_ok=True)
