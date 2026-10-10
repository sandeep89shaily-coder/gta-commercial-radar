from __future__ import annotations
import argparse, json, sys, shutil, sqlite3, os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from lead_candidates import export_candidates
from commercial_engine import write_opportunity_outputs
from radar import (Http, collect_source, latest_changes, open_db, process_snapshot, record_failed_run,
                   register_sources, source_status, write_csv, write_dashboard, clear_source_current,
                   set_source_state, source_universe_hash, previous_run_metadata, current_active_count,
                   last_successful_run)

ROOT=Path(__file__).resolve().parent
DEFAULT_DATA=ROOT/"data"

def load_sources():
    return json.loads((ROOT/"config"/"sources.json").read_text(encoding="utf-8"))

def selected_sources(all_sources,args):
    if args.source:
        wanted=set(args.source)
        unknown=wanted-{s['id'] for s in all_sources}
        if unknown: raise SystemExit("Unknown source(s): "+", ".join(sorted(unknown)))
        return [s for s in all_sources if s['id'] in wanted]
    if args.command=='backfill':
        return [s for s in all_sources if s.get('mode')=='backfill']
    return [s for s in all_sources if s.get('enabled') and s.get('mode') in ('daily','monthly')]

def smart_since_date(con, source):
    r=last_successful_run(con,source["id"])
    if not r: return None
    stamp=r["finished_at"] or r["started_at"]
    if not stamp: return None
    try:
        dt=datetime.fromisoformat(str(stamp).replace("Z","+00:00"))
    except Exception:
        return None
    overlap=int(source.get("incremental_overlap_days",3))
    return (dt.astimezone(timezone.utc)-timedelta(days=overlap)).date().isoformat()


def collection_plan(con, source, *, force_full=False, now=None):
    """Select existing collector's full/incremental mode without rewriting history.

    Snapshot sources run only at configured intervals unless explicitly reconciled;
    no empty snapshot is written when deferred. Live schema/licence validation is
    still mandatory before enabling staged feeds in normal unattended polling.
    """
    if force_full or current_active_count(con, source['id']) == 0:
        return 'full'
    policy=source.get('collection_policy','incremental')
    if policy=='incremental':return 'incremental'
    if policy!='snapshot':raise ValueError('Unknown collection policy: '+str(policy))
    last=last_successful_run(con,source['id'])
    if not last:return 'full'
    stamp=last['finished_at'] or last['started_at']
    if not stamp:return 'full'
    try:
        last_dt=datetime.fromisoformat(str(stamp).replace('Z','+00:00'))
        if last_dt.tzinfo is None:last_dt=last_dt.replace(tzinfo=timezone.utc)
    except (ValueError,TypeError):return 'full'
    now=now or datetime.now(timezone.utc)
    return 'skip' if now-last_dt<timedelta(days=int(source.get('snapshot_interval_days',7))) else 'full'

def do_poll(args, *, force_full=False):
    data=Path(args.data_dir)
    con=open_db(data/"radar.sqlite")
    try:
        all_sources=load_sources(); register_sources(con,all_sources)
        sources=selected_sources(all_sources,args)
        http=Http(); results=[]; failures=0
        label="FULL RECONCILIATION" if force_full else "SMART DAILY POLL"
        print(f"{label}: {len(sources)} source(s). One failure will not stop the others.\n")
        for i,s in enumerate(sources,1):
            print(f"[{i}/{len(sources)}] {s['name']}",flush=True)
            try:
                count=current_active_count(con,s['id'])
                plan=collection_plan(con,s,force_full=force_full)
                if plan=='skip':
                    print(f"  -> SKIPPED: scheduled snapshot not yet due ({s.get('snapshot_interval_days',7)}-day cadence); existing records preserved\n",flush=True)
                    continue
                must_full=(plan=='full')
                since=None if must_full else smart_since_date(con,s)
                prev={} if must_full else previous_run_metadata(con,s['id'])
                snap=collect_source(s,http,progress=True,smart=not must_full,since_date=since,previous_metadata=prev,force_full=must_full)
                r=process_snapshot(con,snap,data/"raw_deltas",emit_baseline=args.emit_baseline)
                results.append(r)
                state="BASELINE" if r['baseline'] and not args.emit_baseline else "DIFF"
                print(f"  -> {state}/{r['mode']}: fetched={r['records']:,}; current={r['current']:,}; new={r['new']:,} updated={r['updated']:,} removed={r['removed']:,}\n",flush=True)
            except Exception as e:
                failures+=1
                record_failed_run(con,s,e)
                print(f"  !! FAILED: {e}\n",file=sys.stderr,flush=True)
        export_outputs(con,data,args.hours)
        print("Finished. Open:",data/"dashboard.html")
        return (1 if failures else 0) if results else 2
    finally:
        con.close()

def export_outputs(con,data,hours):
    changes=latest_changes(con,hours=hours,only_commercial=True)
    status=source_status(con)
    write_csv(data/"feed.csv",changes)
    export_candidates(data/"lead_candidates_REVIEW_ONLY.csv",changes)
    write_opportunity_outputs(data,changes)
    write_csv(data/"source_status.csv",status)
    write_dashboard(data/"dashboard.html",changes,status)

def do_status(args):
    data=Path(args.data_dir); con=open_db(data/"radar.sqlite")
    try:
        register_sources(con,load_sources()); st=source_status(con)
        for x in st:
            health="OK" if x.get('success')==1 else ("NEVER" if x.get('success')=='' else "FAIL")
            print(f"{health:5} {x['source_id']:<38} mode={str(x.get('snapshot_mode','')):<20} current={str(x.get('current_count','')):<8} fetched={str(x.get('record_count','')):<8} latest={x.get('latest_source_date','')} poll={x.get('poll_health','')} publication={x.get('source_freshness','')} {x.get('error','')}")
        export_outputs(con,data,args.hours)
    finally:
        con.close()

def do_doctor(args):
    all_sources=load_sources(); sources=selected_sources(all_sources,args); http=Http(); bad=0
    for s in sources:
        print(f"Checking {s['id']} ...",end=" ",flush=True)
        try:
            if s['collector']=='arcgis':
                r=http.get(s['url'],params={'f':'json'},timeout=(8,30)); j=r.json()
                if 'error' in j: raise RuntimeError(j['error'])
                where=str(s.get('server_where') or '1=1')
                c=http.get(s['query_url'],params={'f':'json','where':where,'returnCountOnly':'true'},timeout=(8,30)).json()
                if 'error' in c: raise RuntimeError(f"configured source filter rejected: {c['error']}")
                from datetime import datetime, timezone, timedelta
                fields=s.get('incremental_fields') or s.get('freshness_fields') or s.get('date_fields') or []
                since=(datetime.now(timezone.utc)-timedelta(days=int(s.get('incremental_overlap_days',3)))).date().isoformat()
                recent=" OR ".join(f"{f} >= DATE '{since}'" for f in fields)
                iw=f"({where}) AND ({recent})" if recent else where
                ic=http.get(s['query_url'],params={'f':'json','where':iw,'returnCountOnly':'true'},timeout=(8,30)).json()
                inc=(f"; recent-window count={int(ic.get('count',0)):,}" if 'error' not in ic else "; incremental filter FAILED")
                print(f"OK ({j.get('name','ArcGIS')}; full filtered count={int(c.get('count',0)):,}{inc})")
            elif s['collector']=='ckan':
                from radar import resolve_ckan_package, choose_ckan_resource
                p=resolve_ckan_package(s,http); r=choose_ckan_resource(p,s)
                ds="yes" if r.get('datastore_active') else "no"
                print(f"OK ({p.get('title')} -> {r.get('name')} [{r.get('format')}]; datastore={ds}; smart polling=metadata-check{' + datastore incremental' if r.get('datastore_active') else ''})")
            elif s['collector']=='html_csv_link':
                from radar import _agco_resolve_download
                page=http.get(s['url'],timeout=(10,40)); dl,updated=_agco_resolve_download(s['url'],page.text)
                stale=""
                if updated and s.get('stale_after_days'):
                    try:
                        age=(datetime.now(timezone.utc).date()-datetime.fromisoformat(updated).date()).days
                        if age>int(s['stale_after_days']): stale=f"; WARNING source-reported update is {age} days old"
                    except Exception: pass
                print(f"OK (CSV link resolved; page last updated={updated or 'unknown'}{stale})")
            elif s['collector']=='web_table':
                from web_collectors import collect_web_table
                snap=collect_web_table(s,http,progress=False,force_full=True)
                print(f"OK ({snap.metadata['delivery']}; filtered={len(snap.rows):,}; publication={snap.metadata.get('source_updated_at') or 'unknown'})")
            elif s['collector']=='peel_health':
                from web_collectors import _peel_page
                from bs4 import BeautifulSoup
                start=http.get(s['url'],timeout=(10,40))
                if BeautifulSoup(start.text,'html.parser').find('input',attrs={'name':'AcceptDisclaimerButton'}):
                    http.post(s['url'],data={'AcceptDisclaimerButton':'Accept'},timeout=(10,40))
                page=http.get(s['table_url'],params={'FacilityCountLimit':0,'ProgramAreaName':s['program_area'],'SortBy':'MostRecentlyInspected','pageNumber':1},timeout=(10,60))
                rows,pages,_=_peel_page(page.text,s['table_url'])
                print(f"OK (first page={len(rows)} facilities; directory={pages} pages; daily=recent inspection window)")
            elif s['collector']=='ero_search':
                from radar import _parse_ero_search_cards
                r=http.get(s['url'],params={'date[min]':(datetime.now(timezone.utc)-timedelta(days=7)).date().isoformat(),'date[max]':datetime.now(timezone.utc).date().isoformat(),'search':'','page':0},timeout=(10,60))
                rows=_parse_ero_search_cards(r.text)
                print(f"OK (recent search parsed {len(rows)} notice card(s); daily query uses date window)")
        except Exception as e:
            bad+=1; print("FAIL:",e)
    raise SystemExit(1 if bad else 0)

def do_adopt(args):
    src=Path(args.from_data).resolve()
    if not src.exists(): raise SystemExit(f"Source data folder not found: {src}")
    dst=Path(args.data_dir).resolve()
    if src==dst: raise SystemExit("Source and destination data folders are the same")
    if not (src/'radar.sqlite').is_file(): raise SystemExit("Source folder has no radar.sqlite database")
    if (dst/'radar.sqlite').exists():
        raise SystemExit("Target already contains radar.sqlite; adoption refused to protect accumulated history. Use --data-dir to point to that database.")
    dst.mkdir(parents=True,exist_ok=True)
    # Copy a consistent SQLite view, including committed WAL transactions.
    # The prior daily task must be stopped so there are no competing pollers.
    staging=dst/'radar.sqlite.adopting'
    if staging.exists(): raise SystemExit("An interrupted adoption left radar.sqlite.adopting; move it aside before retrying")
    original=sqlite3.connect(str(src/'radar.sqlite'))
    target=sqlite3.connect(str(staging))
    try:
        original.backup(target)
        if target.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise RuntimeError("Copied database failed SQLite integrity check")
    finally:
        target.close(); original.close()
    shutil.copytree(src,dst,dirs_exist_ok=True,ignore=shutil.ignore_patterns('radar.sqlite','radar.sqlite-wal','radar.sqlite-shm'))
    os.replace(staging,dst/'radar.sqlite')

    # Preserve the source-universe fingerprint that produced the adopted rows.
    # Never rewrite an old fingerprint to the new code's definition: doing so
    # would make a collector/config change look like genuine NEW/REMOVED data.
    con=open_db(dst/"radar.sqlite")
    try:
        sources=load_sources()
        register_sources(con,sources)
        known_legacy_universe={
            "brampton_building_permits":"LEGACY_UNFILTERED_BASELINE",
            "mississauga_issued_building_permits":"LEGACY_UNFILTERED_BASELINE",
        }
        needs=[]
        for s in sources:
            n=con.execute("SELECT COUNT(*) FROM records_current WHERE source_id=?",(s["id"],)).fetchone()[0]
            if not n:
                continue
            row=con.execute("SELECT universe_hash FROM source_state WHERE source_id=?",(s["id"],)).fetchone()
            current=source_universe_hash(s)
            if row is None:
                marker=known_legacy_universe.get(s["id"],"LEGACY_UNKNOWN_BASELINE")
                con.execute(
                    "INSERT OR REPLACE INTO source_state(source_id,universe_hash,updated_at) VALUES(?,?,datetime('now'))",
                    (s["id"],marker)
                )
                needs.append(s["id"])
            elif row["universe_hash"] != current:
                # Keep the old hash exactly as adopted; process_snapshot will refuse
                # to diff it against the new universe until rebaseline is explicit.
                needs.append(s["id"])
        con.commit()
    finally:
        con.close()
    print(f"Adopted persistent radar data from {src} -> {dst}")
    if needs:
        print("Sources whose comparison universe changed and require rebaseline:")
        for sid in needs:
            print(f"  - {sid}")
        print("Rebaseline these sources before polling them.")


def do_rebaseline(args):
    if not args.source:
        raise SystemExit("rebaseline requires at least one --source SOURCE_ID")
    data=Path(args.data_dir)
    con=open_db(data/"radar.sqlite")
    try:
        all_sources=load_sources()
        by_id={s["id"]:s for s in all_sources}
        for sid in args.source:
            if sid not in by_id:
                raise SystemExit(f"Unknown source: {sid}")
            n=clear_source_current(con,sid)
            print(f"Rebaseline prepared for {sid}: cleared {n:,} current comparison rows. "
                  "Historical runs/versions were retained. The next poll for this source will be a baseline.")
    finally:
        con.close()

def do_audit(args):
    p=ROOT/"config"/"source_audit.csv"
    print(p.read_text(encoding="utf-8"))

p=argparse.ArgumentParser(description="GTA Commercial Radar - desktop-first public-source snapshot/diff engine")
p.add_argument("command",choices=["doctor","poll","reconcile","backfill","status","audit","adopt","rebaseline","leads"],help="doctor=endpoint/capability check; poll=smart daily incremental; reconcile=full snapshot reconciliation; backfill=history-only feeds; status=health; audit=GTA coverage plan; rebaseline=safely reset one source comparison universe")
p.add_argument("--data-dir",default=str(DEFAULT_DATA),help="Persistent local data directory")
p.add_argument("--from-data",help="For adopt: prior version data directory to copy")
p.add_argument("--force",action="store_true",help="Reserved for compatibility; adoption never overwrites an existing database")
p.add_argument("--source",action="append",help="Run only one source id; repeat for several")
p.add_argument("--emit-baseline",action="store_true",help="Emit every row as NEW on a source's first run (normally suppressed)")
p.add_argument("--hours",type=int,default=72,help="Dashboard/feed lookback")
args=p.parse_args()
if args.command=="poll": raise SystemExit(do_poll(args,force_full=False))
if args.command in ("reconcile","backfill"): raise SystemExit(do_poll(args,force_full=True))
if args.command=="adopt":
    if not args.from_data: raise SystemExit("adopt requires --from-data PATH")
    do_adopt(args); raise SystemExit(0)
if args.command=="status": do_status(args)
if args.command=="leads":
    data=Path(args.data_dir); con=open_db(data/"radar.sqlite")
    try:
        changes=latest_changes(con,hours=args.hours,only_commercial=True)
        opportunities,routes=write_opportunity_outputs(data,changes)
        print(f"Review-only: {opportunities} distinct location groups, {routes} buyer-category candidate rows (lookback={args.hours}h)")
        print("Outputs:",data/"opportunities_REVIEW_ONLY.csv", "and",data/"buyer_leads_REVIEW_ONLY")
    finally: con.close()
elif args.command=="doctor": do_doctor(args)
elif args.command=="rebaseline": do_rebaseline(args)
elif args.command=="audit": do_audit(args)
