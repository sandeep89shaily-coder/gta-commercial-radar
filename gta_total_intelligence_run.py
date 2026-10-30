"""One-shot desktop intelligence orchestration. No new collector database or credentials."""
from __future__ import annotations
import argparse,json,subprocess,sys,datetime as dt
from pathlib import Path
from v6_daily_pipeline import find_workspace
ROOT=Path(__file__).resolve().parent
def execute(workspace=None):
    ws=find_workspace(workspace)
    results=ws/"GTA_RADAR_RESULTS"
    results.mkdir(exist_ok=True)
    review=results/"TOTAL_INTELLIGENCE_REVIEW"
    review.mkdir(exist_ok=True)
    record={"started":dt.datetime.now().astimezone().isoformat(),"stages":[],"completed":False}
    target=review/"TOTAL_RUN_STATUS.json"
    def save():target.write_text(json.dumps(record,indent=2),encoding="utf-8")
    def run(name,arguments,critical=True):
        print("\n=== "+name+" ===",flush=True)
        cmd=[sys.executable,str(ROOT/arguments[0]),*arguments[1:]]
        with (review/(name.replace(" ","_")+".log")).open("w",encoding="utf-8") as log:
            result=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        record["stages"].append({"name":name,"exit_code":result.returncode})
        save()
        print(name+(" COMPLETE" if result.returncode==0 else " FAILED")+"; see log in "+str(review),flush=True)
        if critical and result.returncode:return False
        return True
    save()
    try:
        # Collect and selectively investigate within the V6 shared DeepSeek cap.
        if not run("daily_collection",["v6_daily_pipeline.py","--workspace",str(ws),
                                      "--results-dir",str(results),"--selective-ai",
                                      "--no-schedule","--unattended"],True):
            record["status"]="COLLECTION_FAILED";return 1
        run("early_source_monitor",["gta_early_signal_feed_monitor.py","--out",str(results)],False)
        queue=results/"GTA_RADAR_V8_PENDING_QUEUE.csv"
        if queue.exists():
            run("first_seen_ledger",["gta_discovery_tracking.py","--queue",str(queue),
                                     "--folder",str(results)],False)
        run("deepseek_project_investigations",["gta_execute_ai_project_research.py",
            "--results",str(results),"--out",str(review),"--paid","--max-projects","10"],False)
        run("buyer_research",["gta_integrated_buyer_investigation.py","--folder",
                              str(review),"--results",str(results),"--paid"],False)
        run("commercial_review",["gta_commercial_review_html.py","--folder",str(review)],False)
        run("intelligence_graph",["gta_unified_intelligence.py","--results",str(results),
                                  "--review",str(review)],False)
        run("release_quality",["gta_release_acceptance.py","--folder",str(review)],False)
        record["completed"]=True
        record["status"]="COMPLETED_WITH_ERRORS" if any(s["exit_code"] for s in record["stages"]) else "COMPLETED"
        return 0 if record["status"]=="COMPLETED" else 1
    finally:
        record["finished"]=dt.datetime.now().astimezone().isoformat()
        save()
        print("\nRUN MANIFEST: "+str(target),flush=True)
        print("REVIEW: "+str(review/"COMMERCIAL_REVIEW.html"),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--workspace")
    args=p.parse_args();raise SystemExit(execute(args.workspace))
