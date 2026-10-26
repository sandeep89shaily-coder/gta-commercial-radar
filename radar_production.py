"""Permanent consolidated V8 + early collection and explicit Windows scheduler.

Collection runs are serialized, operate only on an adopted V8 database,
save source logs and publish one operations dashboard. No paid DeepSeek.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import radar_workspace as ws
import radar_v8_migration as v8
import radar_operations_dashboard as dashboard

ROOT=Path(__file__).resolve().parent
TASK="GTA_Radar_Consolidated"
RUNFILE="RADAR_PRODUCTION_RUN.json"


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save(path,obj):
    target=Path(path);temporary=target.with_name(target.name+".tmp")
    temporary.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding="utf-8")
    os.replace(temporary,target)


def preflight(home):
    home=Path(home).resolve()
    ws.setup(home)
    active=home/"Data"/"radar.sqlite"
    if not active.is_file():
        raise FileNotFoundError(
            "V8 database not adopted. Run radar_workspace.py --home HOME adopt-v8 "
            "PATH_TO_OLD/radar.sqlite first.")
    with closing(sqlite3.connect(active.as_uri()+"?mode=ro",uri=True)) as db:
        if not v8.supported(db,ws._has_fields):
            raise ValueError("Active V8 DB is missing its normal records/history tables")
    return active


def run(home, core=None, early=None):
    """Run V8 then early-source collection; even partial runs publish diagnostics."""
    home=Path(home).expanduser().resolve()
    preflight(home)
    lock=home/"Data"/"production.lock"
    try:
        fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError as exc:
        raise RuntimeError("Collection already running or prior lock not cleared: "+str(lock)) from exc
    with os.fdopen(fd,"w",encoding="utf-8") as f:
        f.write("pid="+str(os.getpid())+" started="+stamp()+"\n")
    id=uuid.uuid4().hex
    state={"run_id":id,"started_at":stamp(),"status":"RUNNING",
           "v8_status":"NOT_RUN","early_status":"NOT_RUN","deepseek_calls":0}
    manifest=home/"Results"/RUNFILE
    save(manifest,state)
    try:
        if core is None:
            log=home/"Logs"/("v8_"+id[:12]+".log")
            with log.open("w",encoding="utf-8") as f:
                result=subprocess.run(
                    [sys.executable,str(ROOT/"main.py"),"poll","--data-dir",
                     str(home/"Data")],
                    cwd=str(ROOT),stdout=f,stderr=subprocess.STDOUT,
                    timeout=7200,check=False)
            code=result.returncode
            state["v8_log"]=str(log)
        else:
            code=int(core(home))
        state["v8_status"]="SUCCESS" if code==0 else "PARTIAL_OR_FAILED"
        state["v8_exit_code"]=code
        try:
            if early is None:
                from early_investment_radar import run as collect_early
                early_state=collect_early(home/"Data",home/"Results",paid=False)
            else:
                early_state=early(home)
            state["early_status"]=early_state.get("status","UNKNOWN")
            state["early_source_issues"]=early_state.get("source_issues")
        except Exception as exc:
            state["early_status"]="FAILED"
            state["early_error"]=type(exc).__name__+": "+str(exc)[:240]
        imported=ws.import_history(home,[home])
        state["master_new_records"]=imported["new_records"]
        state["master_new_change_events"]=imported["added_events"]
        state["master_v8_source_runs"]=imported["source_runs_imported"]
        state["import_errors"]=len(imported["read_errors"])
        state["unsupported_databases"]=imported["unsupported_databases"]
        state["status"]="SUCCESS" if (
            code==0 and state["early_status"]=="SUCCESS" and not imported["read_errors"]
        ) else "PARTIAL"
    except Exception as exc:
        state["status"]="FAILED"
        state["error"]=type(exc).__name__+": "+str(exc)[:240]
    finally:
        state["finished_at"]=stamp()
        save(manifest,state)
        try:
            state["dashboard"]=str(dashboard.build(home))
        except Exception as exc:
            state["status"]="FAILED"
            state["dashboard_error"]=type(exc).__name__+": "+str(exc)[:160]
        finally:
            save(manifest,state)
            lock.unlink(missing_ok=True)
    return state


def install_schedule(home, *, daily_at="08:30", every_hours=None,
                     operating_system=None, execute=None):
    """Only explicit CLI install writes a Windows Task Scheduler entry."""
    operating_system=operating_system or os.name
    if operating_system!="nt":
        raise RuntimeError("Task Scheduler setup requires Windows")
    home=Path(home).expanduser().resolve()
    preflight(home)
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d",daily_at):
        raise ValueError("daily_at must be HH:MM")
    if every_hours is not None and every_hours not in (2,4,6,12):
        raise ValueError("Allowed interval hours: 2, 4, 6, or 12")
    launcher=home/"RUN_GTA_RADAR_CONSOLIDATED.bat"
    # Uses this stable repo's Python and full script paths; no Downloads ZIP.
    lines=("@echo off\r\nsetlocal\r\n"+
           '"'+str(sys.executable)+'" -u "'+str(ROOT/"radar_production.py")+
           '" --home "'+str(home)+'" run >> "'+
           str(home/"Logs"/"scheduled.log")+'" 2>&1\r\nexit /b %ERRORLEVEL%\r\n')
    launcher.write_text(lines,encoding="utf-8")
    args=["schtasks.exe","/Create","/F","/TN",TASK,
          "/TR",'"'+str(launcher)+'"']
    if every_hours is not None:
        args.extend(["/SC","HOURLY","/MO",str(every_hours)])
    else:
        args.extend(["/SC","DAILY","/ST",daily_at])
    caller=execute or subprocess.run
    r=caller(args,capture_output=True,text=True,check=False)
    if r.returncode!=0:
        raise RuntimeError("Task creation failed: "+str(r.stderr)[:250])
    check=caller(["schtasks.exe","/Query","/TN",TASK],
                 capture_output=True,text=True,check=False)
    if check.returncode:
        raise RuntimeError("Task created but failed verification query")
    return {"task":TASK,"launcher":str(launcher),
            "schedule":("every "+str(every_hours)+" hours" if every_hours
                        else "daily at "+daily_at),
            "status":"INSTALLED_NOT_EXECUTED","deepseek":"OFF"}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home",help="Permanent Radar home; default Documents/GTA_Radar")
    sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("run",help="Collect adopted V8 + early sources then publish report")
    sub.add_parser("dashboard",help="Regenerate one report from stored evidence without collecting")
    sched=sub.add_parser("install-schedule",help="Explicit Windows Task Scheduler setup")
    sched.add_argument("--daily-at",default="08:30")
    sched.add_argument("--every-hours",type=int)
    args=parser.parse_args(argv)
    home=ws.home_path(args.home)
    if args.command=="run":
        result=run(home)
        print(json.dumps(result,indent=2))
        return 0 if result["status"]=="SUCCESS" else 1
    if args.command=="dashboard":
        print(str(dashboard.build(home)))
        return 0
    print(json.dumps(install_schedule(home,daily_at=args.daily_at,
                                      every_hours=args.every_hours),indent=2))
    return 0


if __name__=="__main__":
    try:sys.exit(main())
    except (RuntimeError,OSError,ValueError,sqlite3.Error) as exc:
        print("GTA Radar production:",type(exc).__name__,str(exc),file=sys.stderr)
        sys.exit(1)
