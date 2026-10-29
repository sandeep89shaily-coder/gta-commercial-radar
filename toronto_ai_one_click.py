"""Single-command Toronto PDF -> AI review, using already saved documents.

No downloads, no production edits. Shared ledger enforced by existing
municipal_ai_document_review. Prints actionable block reasons and preserves
the original PDF; creates a small HTML review of successful AI evidence.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,html,json
from pathlib import Path
from toronto_ai_document_batch import process
from municipal_ai_budget_diagnostic import diagnose

def discover(home):
    home=Path(home)
    roots=[home/"Desktop"/"GTA_RADAR_INSTALL",home/"OneDrive"/"Desktop"/"GTA_RADAR_INSTALL"]
    items=[]
    for root in roots:
        if root.is_dir():
            items.extend(root.glob("*/TORONTO_VERIFIED_REPORTS/VERIFIED_REPORT_FETCH_AUDIT.csv"))
    return max(items,key=lambda p:p.stat().st_mtime) if items else None

def make_review(out):
    out=Path(out)
    audit=out/"TORONTO_AI_DOCUMENT_BATCH_AUDIT.csv"
    if not audit.exists():return
    with audit.open(encoding="utf-8-sig",newline="") as f:rows=list(csv.DictReader(f))
    rendered=["<!DOCTYPE html><html><head><meta charset='utf-8'><title>Toronto AI report review</title>",
              "<style>body{font:16px system-ui;max-width:1050px;margin:45px auto;padding:0 20px}section{border:1px solid #bbb;border-radius:10px;padding:16px;margin:18px 0}pre{white-space:pre-wrap}code{overflow-wrap:anywhere}</style></head><body>",
              "<h1>Toronto municipal AI report review</h1><p>All findings are unverified; no sale-ready leads.</p>"]
    for row in rows:
        rendered.append("<section><h2>"+html.escape(row["status"])+"</h2><p><code>"+
                        html.escape(row["source_url"])+"</code></p>")
        path=Path(row.get("result_file") or "")
        if path.is_file():
            try:
                result=json.loads(path.read_text(encoding="utf-8"))
                rendered.append("<h3>AI suggestions — not verified</h3><pre>"+
                                html.escape(json.dumps(result.get("model_output",{}),indent=2,ensure_ascii=False))+
                                "</pre><h3>Quotes found on cited pages</h3><pre>"+
                                html.escape(json.dumps(result.get("supported_claims",[]),indent=2,ensure_ascii=False))+"</pre>")
            except (OSError,ValueError) as e:
                rendered.append("<p>Result could not be read: "+html.escape(str(e))+"</p>")
        else:rendered.append("<p>"+html.escape(row.get("detail","No review result"))+"</p>")
        rendered.append("</section>")
    rendered.append("</body></html>")
    path=out/"TORONTO_AI_REVIEW.html"
    path.write_text("".join(rendered),encoding="utf-8")
    return path

def run(home,results,*,paid=False,day=None,audit=None):
    audit=Path(audit) if audit else discover(home)
    if audit is None or not audit.is_file():
        return {"status":"NO_SAVED_DOCUMENT_AUDIT","next":"Keep previous PDF folder. No redownload required."}
    results=Path(results)
    if not results.is_dir():return {"status":"MISSING_EXISTING_RESULTS"}
    status=diagnose(results,day)
    out=audit.parent.parent/"TORONTO_AI_SINGLE_REPORT"
    if not paid:
        result=process(audit,out,results,limit=1,paid=False)
        return {"status":"NO_COST_READY","ledger":status,"batch":result}
    if status.get("status")!="READ_ONLY_DIAGNOSTIC":
        return {"status":"MISSING_SHARED_LEDGER_STOPPED","ledger":status}
    if not status.get("budget_allows_new_request"):
        return {"status":"LOCAL_BUDGET_HOLD_STOPPED","ledger":status}
    import hashlib
    with audit.open(encoding="utf-8-sig",newline="") as handle:
        first=next((row for row in csv.DictReader(handle) if row.get("status")=="CAPTURED"),None)
    if first:
        digest=first.get("sha256","")
        url=first.get("attachment_url") or first.get("url") or ""
        attempt="municipal_report_compact_v2_"+hashlib.sha256((digest+url).encode()).hexdigest()[:24]
        for entry in status.get("municipal_attempts",[]):
            if entry.get("id")==attempt:
                return {"status":"DUPLICATE_ATTEMPT_BLOCKED_BEFORE_API",
                        "prior_status":entry.get("status"),"paid_ai_calls":0,
                        "next":"No retry today. Preserve earlier reservations and check next budget day."}
    batch=process(audit,out,results,limit=1,paid=True)
    review=make_review(out)
    with (out/"TORONTO_AI_DOCUMENT_BATCH_AUDIT.csv").open(encoding="utf-8-sig") as f:
        record=next(csv.DictReader(f),{})
    return {"status":record.get("status","NO_RECORD"),"batch":batch,
            "review_html":str(review) if review else None,
            "detail":record.get("detail",""),
            "message":"No V8 production files were changed."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--home",type=Path,default=Path.home())
    p.add_argument("--results",type=Path,required=True)
    p.add_argument("--audit",type=Path)
    p.add_argument("--paid",action="store_true")
    args=p.parse_args()
    print(json.dumps(run(args.home,args.results,paid=args.paid,audit=args.audit),indent=2,default=str))
if __name__=="__main__":main()
