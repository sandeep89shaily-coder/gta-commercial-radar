"""Exactly one same-day opt-in DeepSeek recovery using existing local PDF.
No repeat downloads or ledger clearing; previous UNKNOWN holds count fully.
"""
import argparse,csv,hashlib,json,datetime as dt
from pathlib import Path
from municipal_ai_document_review import run as analyze
from municipal_ai_budget_diagnostic import diagnose
from toronto_ai_one_click import discover,make_review
from v8_deepseek_native import MODEL_RESERVE

def recover(home,results,*,audit=None,paid=False):
    audit=Path(audit) if audit else discover(home)
    if not audit or not audit.is_file():return {"status":"SAVED_PDF_AUDIT_NOT_FOUND","calls":0}
    results=Path(results)
    if not results.is_dir():return {"status":"SHARED_RESULTS_NOT_FOUND","calls":0}
    with audit.open(encoding="utf-8-sig",newline="") as h:
        rows=list(csv.DictReader(h))
    row=next((r for r in rows if r.get("status")=="CAPTURED"),None)
    if not row:return {"status":"NO_CAPTURED_REPORT","calls":0}
    pdf=Path(row.get("saved_path") or "")
    url=row.get("attachment_url") or row.get("url") or ""
    sha=row.get("sha256") or ""
    if not pdf.is_file() or hashlib.sha256(pdf.read_bytes()).hexdigest()!=sha:
        return {"status":"PDF_MISSING_OR_CHECKSUM_MISMATCH","calls":0}
    ledger=diagnose(results)
    if ledger.get("status")!="READ_ONLY_DIAGNOSTIC":
        return {"status":"SHARED_LEDGER_NOT_VERIFIED","calls":0}
    fingerprint=hashlib.sha256((sha+url).encode()).hexdigest()[:24]
    existing={a["id"]:a["status"] for a in ledger.get("municipal_attempts",[])}
    recovery_id="municipal_report_nonthinking_v4_"+fingerprint
    if recovery_id in existing:
        return {"status":"SAME_DAY_RECOVERY_ALREADY_ATTEMPTED","prior_status":existing[recovery_id],"calls":0}
    if not ledger.get("budget_allows_new_request"):
        return {"status":"SHARED_DAILY_LIMIT_BLOCKED","calls":0,"budget":ledger.get("budget_remaining_for_new_reservation_usd")}
    if not paid:return {"status":"READY_FOR_ONE_RECOVERY","calls":0,"prior_unknown_preserved":True,
                          "new_max_reservation_usd":MODEL_RESERVE}
    out=audit.parent.parent/"TORONTO_AI_SAME_DAY_RECOVERY"
    out.mkdir(parents=True,exist_ok=True)
    target=out/(sha[:24]+"_AI_REVIEW_ONLY.json")
    try:
        result=analyze(pdf,target,url,paid=True,results=results,retry_version="one_approved_nonthinking_v4")
        status=result.get("status","UNKNOWN")
        summary={"status":status,"calls_reported":result.get("paid_ai_calls",0),
                 "supported_claims":result.get("supported_claims",0),
                 "prior_unknown_preserved":True}
    except Exception as exc:
        # Core analyzer conservatively retains FULL reservation on unknown response
        summary={"status":"AI_REQUEST_FAILED","reason":type(exc).__name__+": "+str(exc)[:240],
                 "prior_unknown_preserved":True,"calls_reported":"UNKNOWN_see_shared_ledger"}
    if target.is_file():
        with (out/"TORONTO_AI_DOCUMENT_BATCH_AUDIT.csv").open("w",encoding="utf-8-sig",newline="") as h:
            w=csv.DictWriter(h,fieldnames=["source_url","status","detail","result_file"])
            w.writeheader();w.writerow(dict(source_url=url,status=summary["status"],detail="",result_file=str(target)))
        summary["result_file"]=str(target)
        summary["review_html"]=str(make_review(out))
    (out/"RECOVERY_RESULT.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--results",required=True)
    p.add_argument("--home",default=str(Path.home()))
    p.add_argument("--audit")
    p.add_argument("--paid",action="store_true")
    a=p.parse_args()
    print(json.dumps(recover(a.home,a.results,audit=a.audit,paid=a.paid),indent=2))

if __name__=="__main__":main()
