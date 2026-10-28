"""Review-only batch AI interpretation of PDFs already captured in Toronto audit.

Uses existing DeepSeek shared budget. Runs no calls unless --paid is explicitly
supplied. No V8 update. Writes per-document error/status and citations.
"""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
from municipal_ai_document_review import run as analyze_one

FIELDS=("source_url","pdf_path","sha256_download","status","ai_calls","supported_claims","rejected_claims","detail","result_file")

def process(audit_csv,out,results,*,paid=False,limit=4,analyzer=analyze_one):
    audit_csv=Path(audit_csv)
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    with audit_csv.open(encoding="utf-8-sig",newline="") as h:
        rows=list(csv.DictReader(h))
    records=[]
    seen=set()
    for row in rows:
        url=str(row.get("attachment_url") or row.get("url") or "").strip()
        if not url or url in seen or row.get("status")!="CAPTURED":
            continue
        seen.add(url)
        if len(records)>=max(0,min(20,int(limit))):
            break
        local=Path(row.get("saved_path") or "")
        digest=str(row.get("sha256") or "").lower()
        record=dict(source_url=url,pdf_path=str(local),sha256_download=digest,status="",
                    ai_calls=0,supported_claims=0,rejected_claims=0,detail="",result_file="")
        if not local.is_file():
            record.update(status="MISSING_PDF",detail="Saved PDF path missing")
        elif not digest or hashlib.sha256(local.read_bytes()).hexdigest()!=digest:
            record.update(status="CHECKSUM_MISMATCH",detail="PDF bytes differ from download audit")
        elif not paid:
            record.update(status="READY_NOT_SENT",detail="Explicit --paid required")
        else:
            target=out/(digest[:24]+"_AI_REVIEW_ONLY.json")
            try:
                result=analyzer(local,target,url,paid=True,results=results)
                record.update(status=result.get("status","UNKNOWN"),
                              ai_calls=int(result.get("paid_ai_calls",0)),
                              supported_claims=int(result.get("supported_claims",0)),
                              rejected_claims=int(result.get("rejected_claims",0)),
                              result_file=str(target) if target.is_file() else "")
            except Exception as exc:
                record.update(status="ERROR",detail=type(exc).__name__+": "+str(exc)[:250])
        records.append(record)
    file=out/"TORONTO_AI_DOCUMENT_BATCH_AUDIT.csv"
    with file.open("w",encoding="utf-8-sig",newline="") as h:
        w=csv.DictWriter(h,fieldnames=FIELDS);w.writeheader();w.writerows(records)
    summary={"captured_pdf_records_checked":len(records),
             "ai_calls_reported":sum(r["ai_calls"] for r in records),
             "review_outputs":sum(bool(r["result_file"]) for r in records),
             "errors":sum(r["status"] in ("ERROR","CHECKSUM_MISMATCH","MISSING_PDF") for r in records),
             "sale_ready":0,"production_database_modified":False,"audit":str(file.resolve())}
    (out/"TORONTO_AI_DOCUMENT_BATCH_SUMMARY.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--results",required=True)
    p.add_argument("--paid",action="store_true")
    p.add_argument("--limit",type=int,default=4)
    a=p.parse_args()
    print(json.dumps(process(a.audit,a.out,a.results,paid=a.paid,limit=a.limit),indent=2))
if __name__=="__main__":main()
