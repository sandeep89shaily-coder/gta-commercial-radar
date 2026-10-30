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
    record={"started":dt.datetime.now().astimezone().isoformat(),"stages":[],"completed":False,"production_accepted":False}
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
        # Datum-style municipal meeting discovery, procurement and bounded
        # policy-checked document retrieval are separate audited stages.
        for city in ("Toronto","Brampton"):
            run("meeting_"+city.lower(),["RUN_MEETING_BUYER_PIPELINE.py",
                "--city",city,"--out",str(review/"MEETINGS"/city),
                "--include-procurement"],False)
        run("toronto_meeting_documents",["toronto_meeting_pdf_pipeline.py",
            "--meetings",str(ROOT/"config"/"toronto_verified_meeting_seeds.csv"),
            "--out",str(review/"MEETING_DOCUMENTS"/"Toronto"),"--fetch",
            "--max-agendas","4","--max-pdfs","6"],False)

        # Independently observed Toronto report links are a second bounded path.
        # This does not assume the meeting video/index discovery yielded agenda PDFs.
        run("verified_toronto_reports",["toronto_verified_report_queue.py",
            "--queue",str(ROOT/"config"/"toronto_verified_report_queue.csv"),
            "--out",str(review/"MEETING_DOCUMENTS"/"Toronto"),"--fetch",
            "--max-files","4"],False)
        pdf_audit=review/"MEETING_DOCUMENTS"/"Toronto"/"TORONTO_PDF_FETCH_AUDIT.csv"
        # Merge captured PDFs from both official paths into a single AI audit.
        from gta_document_audit_union import union
        combined = review/"MEETING_DOCUMENTS"/"Toronto"/"COMBINED_PDF_FETCH_AUDIT.csv"
        union([pdf_audit,review/"MEETING_DOCUMENTS"/"Toronto"/"VERIFIED_REPORT_FETCH_AUDIT.csv"],combined)
        run("document_deepseek_analysis",["toronto_ai_document_batch.py",
            "--audit",str(combined),"--out",str(review/"DOCUMENT_AI"),
            "--results",str(results),"--limit","4","--paid"],False)
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
        # Exit status is only execution health. Evidence gates are independent.
        from gta_integrated_run_gates import evaluate, write_report
        gates=evaluate(review,results)
        write_report(review,gates)
        record["execution_completed"]=not any(s["exit_code"] for s in record["stages"])
        record["production_accepted"]=gates["production_accepted"] and record["execution_completed"]
        record["completed"]=record["execution_completed"]
        record["evidence_gate_report"]=str(review/"UNIFIED_EVIDENCE_GATES.json")
        record["blockers"]=gates["blockers"]
        record["status"]=("PRODUCTION_ACCEPTED" if record["production_accepted"] else
                          "COMPLETED_WITH_EVIDENCE_BLOCKERS" if record["execution_completed"] else
                          "COMPLETED_WITH_ERRORS")
        return 0 if record["production_accepted"] else 2
    finally:
        record["finished"]=dt.datetime.now().astimezone().isoformat()
        save()
        print("\nRUN MANIFEST: "+str(target),flush=True)
        print("REVIEW: "+str(review/"COMMERCIAL_REVIEW.html"),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--workspace")
    args=p.parse_args();raise SystemExit(execute(args.workspace))
