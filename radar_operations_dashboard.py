"""One offline operations dashboard for both V8 and early-source histories.

No web server, no DeepSeek, no invented open-purchase or buyer assertions.
Regenerated after collection; browser reloads the HTML file every five minutes.
"""
import csv
import html
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.parse import urlparse

import radar_workspace as rw

PAGE="GTA_RADAR_OPERATIONS.html"


def esc(x):
    return html.escape(str(x if x is not None else ""),quote=True)


def safeurl(x):
    value=str(x or "").strip()
    p=urlparse(value)
    return value if p.scheme in ("https","http") and p.netloc else ""


def build(home):
    home=Path(home).resolve()
    master=rw.setup(home)
    results=home/"Results"
    statefile=results/"RADAR_PRODUCTION_RUN.json"
    try:
        state=json.loads(statefile.read_text(encoding="utf-8")) if statefile.exists() else {}
    except (OSError,ValueError):
        state={"status":"RUN_REPORT_UNREADABLE"}
    with closing(sqlite3.connect(master)) as db:
        db.row_factory=sqlite3.Row
        count=lambda table:db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        totals={x:count(x) for x in
                ("records","record_versions","historical_events","source_runs")}
        totals["feeds"]=db.execute("SELECT COUNT(DISTINCT source_id) FROM records").fetchone()[0]
        changes=[dict(r) for r in db.execute(
            "SELECT source_id,record_id,event_type,event_at,payload_json "
            "FROM historical_events ORDER BY event_at DESC LIMIT 100")]
        v8=[dict(r) for r in db.execute(
            "SELECT source_id,finished_at,success,record_count,error,latest_source_date "
            "FROM source_runs WHERE source_id IS NOT NULL "
            "ORDER BY COALESCE(finished_at,started_at) DESC,run_id DESC")]
        latest={}
        for row in v8:
            latest.setdefault(row["source_id"],row)
        imported=db.execute("SELECT import_id,completed_at FROM import_runs "
                            "ORDER BY rowid DESC LIMIT 1").fetchone()
        early=[]
        if imported:
            early=[dict(r) for r in db.execute(
                "SELECT source_id,reported_status,detail_json FROM feed_health "
                "WHERE import_id=? ORDER BY source_id",(imported["import_id"],))]
    def table(headers,rows):
        return "<div class='scroll'><table><thead><tr>"+ "".join(
            "<th>"+esc(h)+"</th>" for h in headers)+"</tr></thead><tbody>"+ "".join(
            "<tr>"+"".join("<td>"+str(c)+"</td>" for c in row)+"</tr>" for row in rows
        )+"</tbody></table></div>"
    health=[]
    for s in latest.values():
        health.append((esc(s["source_id"]),"V8","SUCCESS" if s["success"]==1 else "FAILED",
                       esc(s["finished_at"]),esc(s["record_count"]),esc(s["error"])))
    for s in early:
        try: detail=json.loads(s["detail_json"])
        except (ValueError,TypeError):detail={}
        health.append((esc(s["source_id"]),"EARLY",esc(s["reported_status"]),
                       "Last imported report",esc(detail.get("fetched") or
                        detail.get("reports_indexed") or ""),
                       esc(detail.get("error") or detail.get("warning") or "")))
    activity=[]
    for c in changes:
        try: info=json.loads(c["payload_json"])
        except (ValueError,TypeError):info={}
        title=esc(str(info.get("title") or info.get("description") or c["record_id"])[:140])
        url=safeurl(info.get("source_url") or info.get("official_page"))
        if url:title="<a rel='noopener noreferrer' href='"+esc(url)+"'>"+title+"</a>"
        activity.append((esc(c["event_at"]),esc(c["source_id"]),esc(c["event_type"]),
                         title,esc(info.get("site") or info.get("address") or "")))
    candidates=[]
    file=results/"GTA_RADAR_EARLY_PURCHASE_CANDIDATES.csv"
    if file.exists():
        try:
            with file.open(encoding="utf-8-sig",newline="") as f:
                for c in csv.DictReader(f):
                    candidates.append((
                        esc(c.get("company_name") or c.get("address") or "Unknown"),
                        esc(str(c.get("description") or "")[:180]),
                        esc(c.get("event_date") or ""),"RESEARCH ONLY"))
                    if len(candidates)>=35:break
        except (OSError,csv.Error,UnicodeError):pass
    runstate=esc(state.get("status") or "NEVER_RUN")
    status=("<b>Last run: "+runstate+"</b> · "+esc(state.get("finished_at") or "")+
            " · V8 "+esc(state.get("v8_status") or "NOT_RUN")+
            " · Early "+esc(state.get("early_status") or "NOT_RUN")+
            " · Import errors "+esc(state.get("import_errors",0))+
            " · DeepSeek OFF")
    metrics="".join("<div class='metric'><small>"+esc(label)+"</small><b>"+esc(f"{val:,}")+"</b></div>"
                    for label,val in (("Stored records",totals["records"]),
                         ("Feeds with records",totals["feeds"]),
                         ("Historical changes",totals["historical_events"]),
                         ("Record revisions",totals["record_versions"]),
                         ("V8 source runs",totals["source_runs"])))
    css="""<style>body{font:15px Segoe UI,Arial,sans-serif;color:#1a2938;background:#f4f6fa;margin:0}
      main{max-width:1220px;margin:32px auto;padding:0 18px}
      .panel,.metric{border:1px solid #dce2e9;background:#fff;border-radius:10px;padding:17px;margin:12px 0}
      .stats{display:flex;gap:12px;flex-wrap:wrap}.metric{min-width:155px;flex:1}
      .metric small{display:block;color:#566b81}.metric b{font-size:23px}
      .scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:13px}
      th,td{border-bottom:1px solid #e1e7ed;padding:9px;text-align:left;vertical-align:top}
      th{background:#f5f7f9}a{color:#14649c}
      .muted{color:#617184}input{padding:9px;border:1px solid #ccd5df;border-radius:6px}
      </style>"""
    body=["<!doctype html><html><head><meta charset='utf-8'>",
        "<meta http-equiv='refresh' content='300'><title>GTA Radar Operations</title>",css,
        "</head><body><main><h1>GTA Radar — Operations</h1>",
        "<p class='muted'>One persistent V8 + early-source evidence view. Reopens updated "
        "data after each completed scheduled run; this is not a live-server feed.</p>",
        "<div class='panel'>",status,"<p class='muted'>Latest import: ",
        esc(imported["completed_at"] if imported else "NONE"),"</p></div>",
        "<div class='stats'>",metrics,"</div>",
        "<div class='panel'><h2>Source health</h2>",
        "<p class='muted'>Last reported source statuses, not proof of present availability.</p>",
        "<input id='filter' placeholder='Filter sources by name or status' "
        "aria-label='Filter source health'>",
        table(("Source","Family","Last status","Last check","Records","Issue"),
              health or [("No source statuses imported yet","","","","","")]),
        "</div><div class='panel'><h2>Recent evidence changes</h2>",
        table(("Observed","Source","Change","Title","Site"),
              activity or [("No post-baseline changes","","","","")]),"</div>",
        "<div class='panel'><h2>Commercial research candidates</h2>",
        "<p class='muted'>Purchasing categories are hypotheses. No buyer or unawarded "
        "contract is verified by appearing in this table.</p>",
        table(("Company/site","Description","Public date","Disposition"),
              candidates or [("No qualifying candidates yet","","","")]),"</div>",
        "<p class='muted'>Historical imports are not fresh leads. Source posting date and "
        "Radar first observation are distinct. Research, company identity and procurement "
        "status require separate verification.</p>",
        """<script>document.getElementById('filter').addEventListener('input',function(){
        const t=this.value.toLowerCase();const table=document.querySelectorAll('table')[0];
        for(const r of table.tBodies[0].rows){r.hidden=!r.textContent.toLowerCase().includes(t)}
        });</script>""","</main></body></html>"]
    target=results/PAGE
    tmp=target.with_name(target.name+".tmp")
    tmp.write_text("".join(body),encoding="utf-8")
    os.replace(tmp,target)
    return target
