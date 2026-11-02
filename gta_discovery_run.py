"""GTA Radar's default stage: find new/changed projects and make a human review list.

Default integrated workflow: live V6 collection, selective DeepSeek, municipal
meetings, verified official PDFs, bounded source-backed document/project/buyer
research, one merged human review list. All paid stages share US$0.25/day.
"""
from __future__ import annotations
import argparse,datetime as dt,json,subprocess,sys
from pathlib import Path
import desktop_update
from v6_daily_pipeline import find_workspace
from gta_manual_project_list import build as build_manual_list
from gta_daily_intelligence import integrate as run_integrated_intelligence

ROOT=Path(__file__).resolve().parent
WATCH="GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv"

def execute(workspace=None,*,runner=None,preflight=None,list_builder=None,integrator=None):
    ws=find_workspace(workspace)
    results=ws/"GTA_RADAR_RESULTS"
    results.mkdir(parents=True,exist_ok=True)
    report=results/"GTA_RADAR_DISCOVERY_RUN_STATUS.json"
    record={"mode":"INTEGRATED_DAILY_INTELLIGENCE",
            "started":dt.datetime.now().astimezone().isoformat(),
            "completed":False,"commercial_qualification_automated":False,
            "supplier_or_procurement_investigation_automated":True,
            "daily_deepseek_cap_usd":0.25}
    def save():
        report.write_text(json.dumps(record,indent=2),encoding="utf-8")
    check=(preflight or desktop_update.preflight)(ROOT,results,apply_update=False)
    record["code_check_status"]=check.get("status","UNKNOWN")
    record["installed_commit"]=check.get("installed_commit")
    if not check.get("ok"):
        record["status"]="CODE_PREFLIGHT_REFUSED"
        save()
        print("Release check refused: "+str(check.get("message","unknown")),flush=True)
        return 3
    # Require a new export from this run, not a file left from yesterday.
    output=results/WATCH
    previous_mtime=output.stat().st_mtime_ns if output.is_file() else -1
    cmd=[sys.executable,str(ROOT/"v6_daily_pipeline.py"),
         "--workspace",str(ws),"--results-dir",str(results),
         "--selective-ai","--no-schedule","--unattended"]
    record["collector_command"]="V6 LIVE COLLECTION + SELECTIVE DEEPSEEK"
    print("Running daily discovery, evidence-backed meeting/document intelligence and bounded DeepSeek investigations.",flush=True)
    print("Buyer research is automatic; purchasing authority, supplier awards and outreach require manual verification.",flush=True)
    log=results/"GTA_RADAR_DISCOVERY_COLLECTION.log"
    with log.open("w",encoding="utf-8") as handle:
        outcome=(runner or subprocess.run)(cmd,cwd=ROOT,stdout=handle,stderr=subprocess.STDOUT)
    record["collection_exit_code"]=outcome.returncode
    record["collection_log"]=str(log)
    try:
        v6=json.loads((results/"GTA_RADAR_V6_RUN.json").read_text(encoding="utf-8"))
        record["collector_status"]=v6.get("status","UNKNOWN")
        record["initial_deepseek"]=v6.get("selective_ai",{})
    except (OSError,ValueError,TypeError):
        record["collector_status"]="UNKNOWN"
        record["initial_deepseek"]={}
    if not output.is_file() or output.stat().st_mtime_ns==previous_mtime:
        record["status"]="NO_FRESH_PROJECT_LIST"
        save()
        print("No fresh daily project export; refusing to report old data as today's results.",flush=True)
        return 2
    try:
        listing=(list_builder or build_manual_list)(results)
    except (OSError,ValueError,TypeError) as exc:
        record["status"]="MANUAL_PROJECT_LIST_FAILED"
        record["error"]=type(exc).__name__+": "+str(exc)[:240]
        save()
        raise
    record["manual_list"]=listing
    # The integrated stage is part of EVERY normal run, not a --full-intelligence
    # opt-in. If V6 partially failed, allow free review but no additional paid AI.
    try:
        unified=(integrator or run_integrated_intelligence)(
            results,allow_paid=outcome.returncode==0)
        record["integrated_intelligence"]={
            k:unified.get(k) for k in ("status","failed_stages","combined_records",
               "combined_csv","combined_html","pdfs_captured_in_union",
               "new_source_dated_project_candidates","deepseek_shared_ceiling_usd")}
        record["meeting_document_pipeline_complete"]=unified.get("status")=="INTEGRATED_REVIEW_READY"
    except Exception as exc:
        record["meeting_document_pipeline_complete"]=False
        record["integrated_intelligence"]={"status":"FAILED",
            "error":type(exc).__name__+": "+str(exc)[:250]}
    record["completed"]=outcome.returncode==0 and record["meeting_document_pipeline_complete"]
    record["status"]=("INTEGRATED_INTELLIGENCE_READY" if record["completed"] else
                      "INTEGRATED_PARTIAL_REVIEW_REQUIRED")
    record["finished"]=dt.datetime.now().astimezone().isoformat()
    save()
    print("PROJECTS TO REVIEW:",listing["new_or_changed_source_records"],flush=True)
    print("INITIAL CONTACT HINTS:",listing["initial_public_contact_hints"],flush=True)
    print("CSV:",listing["manual_review_csv"],flush=True)
    print("HTML:",listing["manual_review_html"],flush=True)
    print("INTEGRATED:",record["integrated_intelligence"].get("combined_html","see status JSON"),flush=True)
    print("RUN STATUS:",record["status"],flush=True)
    return 0 if record["completed"] else 2

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--workspace")
    args=p.parse_args()
    raise SystemExit(execute(args.workspace))
