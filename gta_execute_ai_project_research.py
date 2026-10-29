"""Execute DeepSeek research on sourced GTA projects, not another task planner.

Uses the existing native search/fetch/analyze implementation, the SAME shared
V5 budget ledger, and review-only output files outside production V8 queues.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,json
from pathlib import Path
import v5_investigator as v5
import v8_deepseek_native as native

def read_candidates(path):
    with Path(path).open(encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    required=("project_id","address","source_id","source_keys",
              "record_source_url","description")
    missing=[name for name in required if not rows or name not in rows[0]]
    if missing:raise ValueError("Missing canonical project fields: "+", ".join(missing))
    seen=set();valid=[]
    for row in rows:
        pid=str(row["project_id"]).strip()
        if not pid or pid in seen:continue
        seen.add(pid)
        if not native.safe_url(row.get("record_source_url")):continue
        if not str(row.get("address") or row.get("source_keys") or "").strip():continue
        valid.append(row)
    return valid

def execute(candidate_file,shared_results,out,*,paid=False,max_projects=3,
            key=None,transport=None,today=None):
    projects=read_candidates(candidate_file)
    dest=Path(out);dest.mkdir(parents=True,exist_ok=True)
    state={"status":"PREFLIGHT","candidates":len(projects),"attempted":0,
           "completed":0,"verified_private_leads":0,"deepseek_budget_limit_usd":0.25}
    manifest=dest/"AI_PROJECT_RESEARCH_MANIFEST.json"
    if not paid:
        manifest.write_text(json.dumps(state,indent=2),encoding="utf-8")
        return state
    root=Path(shared_results)
    if not root.is_dir():raise ValueError("Existing shared results folder required")
    key=v5.key_from_windows() if key is None else key
    if not key:return {**state,"status":"MISSING_API_KEY"}
    db=v5._ledger(root/"v5_ai_budget.sqlite")
    day=(today or dt.date.today()).isoformat()
    legacy=v5._legacy_reserved(root/"deepseek_budget.sqlite",day)
    audit=[]
    try:
        limit=max(0,min(int(max_projects),10))
        for row in projects:
            if state["attempted"]>=limit:break
            rid=row["project_id"]
            identity=hashlib.sha256(json.dumps(
                {k:row.get(k) for k in sorted(row)},sort_keys=True).encode()).hexdigest()
            filename=dest/("AI_PROJECT_"+hashlib.sha256(rid.encode()).hexdigest()[:16]+".json")
            if filename.exists():
                previous=json.loads(filename.read_text(encoding="utf-8"))
                if previous.get("input_hash")==identity:
                    audit.append({"project_id":rid,"status":"ALREADY_REVIEWED"});continue
                raise ValueError("Project changed; use a new output folder to preserve history")
            # Existing V8 implements conservative native search/fetch billing.
            state["attempted"]+=1
            evidence,stats=native.fetch_native(row,key,db,day,legacy,transport,daily_limit=0.25)
            reservation="project_ai_v1_"+hashlib.sha256((rid+identity).encode()).hexdigest()[:24]
            if not native.ledger_claim(db,day,reservation,native.MODEL_RESERVE,legacy,daily_limit=0.25):
                audit.append({"project_id":rid,"status":"BUDGET_OR_PRIOR_REQUEST"});break
            try:
                answer,cost=native.analyze(row,evidence,key,transport)
                native.ledger_finish(db,day,reservation,"DONE",cost)
                # Model claims stay review-only; roles and unawarded packages
                # require independent confirmation before promotion.
                output={"project_id":rid,"input_hash":identity,
                    "source_url":row["record_source_url"],"address":row["address"],
                    "research_status":"AI_REVIEW_ONLY","native_searches":stats["search"],
                    "native_fetches":stats["fetch"],"sources":evidence,
                    "model_suggestions":answer,"verified_buying_authority":False,
                    "verified_supplier_unselected":False,"sale_ready":False}
                filename.write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding="utf-8")
                state["completed"]+=1
                audit.append({"project_id":rid,"status":"AI_REVIEW_SAVED",
                              "fetched_sources":len(evidence)})
            except Exception as exc:
                native.ledger_finish(db,day,reservation,"UNKNOWN")
                audit.append({"project_id":rid,"status":"MODEL_FAILURE",
                              "error_type":type(exc).__name__})
                break
    finally:db.close()
    state["status"]="REVIEW_ONLY_RESULTS" if state["completed"] else "NO_COMPLETED_AI_REVIEWS"
    state["audit"]=audit
    manifest.write_text(json.dumps(state,indent=2),encoding="utf-8")
    return state

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--candidates",required=True);p.add_argument("--results",required=True)
    p.add_argument("--out",required=True);p.add_argument("--paid",action="store_true")
    p.add_argument("--max-projects",type=int,default=3)
    a=p.parse_args()
    print(json.dumps(execute(a.candidates,a.results,a.out,paid=a.paid,
                             max_projects=a.max_projects),indent=2))
if __name__=="__main__":main()
