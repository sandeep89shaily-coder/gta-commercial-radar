"""Execute DeepSeek research on sourced GTA projects, best candidates first.

Uses the existing native search/fetch/analyze implementation, the SAME shared
budget ledger (limit from radar_config), and review-only output files outside
production V8 queues.

Spend discipline
  1. Projects are ranked by deterministic commercial significance BEFORE any
     paid call (candidate_scoring). Public bodies and projects below the
     threshold get no paid AI.
  2. Paid search/fetch evidence is saved BEFORE the model is called, so a model
     failure never throws away evidence that was already paid for.
  3. A failed model call is recorded with its failure class and a bounded raw
     reply, and its real cost when the provider reported usage.
  4. Nothing is overwritten: changed inputs are stored under versioned names.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,json
from pathlib import Path
import v5_investigator as v5
import v8_deepseek_native as native
import candidate_scoring as scoring
import source_dates
from radar_config import DEEPSEEK_DAILY_LIMIT_USD as DAILY_CAP

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

def locate_candidates(results,explicit=None):
    """Find V8 queue across normal and legacy result layouts; verify content."""
    root=Path(results)
    locations=[root,root/"results",root/"RESULTS",root.parent,root.parent/"GTA_RADAR_RESULTS"]
    names=("GTA_RADAR_V8_PENDING_QUEUE.csv","GTA_RADAR_V8_PROJECTS.csv",
           "GTA_RADAR_V8_AI_CANDIDATES.csv","GTA_RADAR_V4_PROJECTS_FOR_AI.csv")
    checked=[]
    paths=[Path(explicit)] if explicit else [folder/name for folder in locations for name in names]
    for path in paths:
        if not path.is_file():continue
        try:
            rows=read_candidates(path)
        except (ValueError,OSError,UnicodeError) as exc:
            checked.append({"path":str(path),"reason":type(exc).__name__})
            continue
        if rows:return path,rows
        checked.append({"path":str(path),"reason":"NO_ELIGIBLE_SOURCED_PROJECTS"})
    raise ValueError("No eligible V8 sourced project queue found; checked: "+json.dumps(checked)[:900])

def select_projects(projects):
    """Rank candidates by commercial significance; return (eligible, summary).

    eligible is [(row, score_result)] best first. Public bodies and projects
    under the threshold are never researched with paid AI.
    """
    ranked=scoring.rank(projects)
    eligible=[(r,s) for r,s in ranked if not s["excluded"] and s["score"]>=scoring.MIN_SELECTION_SCORE]
    summary={"candidates":len(projects),"eligible_for_paid_ai":len(eligible),
             "excluded_public_body":sum(1 for _,s in ranked if s["excluded"]),
             "below_threshold":sum(1 for _,s in ranked if not s["excluded"] and s["score"]<scoring.MIN_SELECTION_SCORE),
             "min_score":scoring.MIN_SELECTION_SCORE,
             "top":[{"project_id":r["project_id"],"address":r.get("address",""),
                     "score":s["score"],"tier":s["tier"],"reasons":s["reasons"][:5]}
                    for r,s in eligible[:10]]}
    return eligible,summary

def _write_new(path,obj):
    """Write JSON without ever overwriting an existing file."""
    path=Path(path)
    if path.exists():return False
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding="utf-8")
    return True

def _failure_reason(exc):
    if isinstance(exc,native.ModelResponseError):return str(exc)[:200]
    if isinstance(exc,ValueError):return str(exc)[:200]
    code=getattr(exc,"code",None)
    return "MODEL_REQUEST_FAILED:"+type(exc).__name__+(":HTTP_"+str(code) if code else "")

def execute(candidate_file,shared_results,out,*,paid=False,max_projects=3,
            key=None,transport=None,today=None):
    candidate_file,projects=locate_candidates(shared_results,candidate_file)
    dest=Path(out);dest.mkdir(parents=True,exist_ok=True)
    eligible,selection=select_projects(projects)
    state={"status":"PREFLIGHT","candidates":len(projects),"attempted":0,
           "completed":0,"candidate_source":str(candidate_file),
           "verified_private_leads":0,"deepseek_budget_limit_usd":DAILY_CAP,
           "selection":selection}
    manifest=dest/"AI_PROJECT_RESEARCH_MANIFEST.json"
    if not paid:
        preview=dest/"AI_PROJECT_PREFLIGHT.json"
        preview.write_text(json.dumps(state,indent=2),encoding="utf-8")
        return state
    root=Path(shared_results)
    if not root.is_dir():raise ValueError("Existing shared results folder required")
    key=v5.key_from_windows() if key is None else key
    if not key:
        state["status"]="MISSING_API_KEY"
        manifest.write_text(json.dumps(state,indent=2),encoding="utf-8")
        return state
    db=v5._ledger(root/"v5_ai_budget.sqlite")
    day=(today or dt.date.today()).isoformat()
    legacy=v5._legacy_reserved(root/"deepseek_budget.sqlite",day)
    audit=[]
    state["skipped_previous_requests"]=0
    state["budget_remaining_usd"]=None
    state["status"]="INTERRUPTED_BY_ERROR"   # replaced below if the loop finishes
    try:
        limit=max(0,min(int(max_projects),10))
        for row,pick in eligible:
            if state["attempted"]>=limit:break
            rid=row["project_id"]
            identity=hashlib.sha256(json.dumps(
                {k:row.get(k) for k in sorted(row)},sort_keys=True).encode()).hexdigest()
            stem="AI_PROJECT_"+hashlib.sha256(rid.encode()).hexdigest()[:16]
            filename=dest/(stem+".json")
            if filename.exists():
                previous=json.loads(filename.read_text(encoding="utf-8"))
                if previous.get("input_hash")==identity:
                    audit.append({"project_id":rid,"status":"ALREADY_REVIEWED"});continue
                # Keep the original immutable; store changed inputs under a versioned name.
                filename=dest/(stem+"_"+identity[:12]+".json")
                if filename.exists():
                    version=json.loads(filename.read_text(encoding="utf-8"))
                    if version.get("input_hash")==identity:
                        audit.append({"project_id":rid,"status":"ALREADY_REVIEWED_VERSION"});continue
                    raise ValueError("Version filename collision; refusing overwrite")
                audit.append({"project_id":rid,"status":"CHANGED_PROJECT_VERSION_PRESERVED"})
            reservation="project_ai_v1_"+hashlib.sha256((rid+identity).encode()).hexdigest()[:24]
            prior=db.execute("SELECT status FROM spends WHERE day=? AND candidate=?",(day,reservation)).fetchone()
            if prior:
                state["skipped_previous_requests"]+=1
                audit.append({"project_id":rid,"status":"ALREADY_ATTEMPTED_TODAY","ledger_status":prior[0]})
                continue
            used=native.effective_spend(db,day)[0]
            remaining=max(0.0,DAILY_CAP-used-legacy)
            state["budget_remaining_usd"]=round(remaining,6)
            # Reserve space for discovery and the model before paid discovery.
            max_job=native.MODEL_RESERVE+native.MAX_SEARCHES*native.SEARCH_COST+native.MAX_FETCHES*native.FETCH_COST
            if remaining+1e-9<max_job:
                state["stop_reason"]="DAILY_BUDGET_EXHAUSTED_OR_HELD"
                break
            state["attempted"]+=1
            selection_info={"selection_score":pick["score"],"selection_tier":pick["tier"],
                            "selection_reasons":pick["reasons"]}
            try:
                from gta_adaptive_deepseek_planner import plan
                investigation_plan=plan(row,key,db,day,legacy,transport,daily_limit=DAILY_CAP)
                planned_row={**row,"_adaptive_query_order":investigation_plan["queries"]}
                evidence,stats=native.fetch_native(planned_row,key,db,day,legacy,transport,daily_limit=DAILY_CAP)
            except Exception as exc:
                audit.append({"project_id":rid,"status":"DISCOVERY_FAILURE",
                              "error_type":type(exc).__name__,"error_reason":_failure_reason(exc)})
                continue
            rejected=[e for e in evidence if e.get("page_identity")=="ADDRESS_CONTEXT_UNCONFIRMED"]
            evidence=[e for e in evidence if e.get("page_identity")!="ADDRESS_CONTEXT_UNCONFIRMED"]
            # Paid evidence is saved BEFORE the model call so a model failure never loses it.
            evidence_file=dest/(stem+"_EVIDENCE_"+identity[:12]+".json")
            _write_new(evidence_file,{"project_id":rid,"input_hash":identity,
                "address":row["address"],"source_url":row["record_source_url"],
                "investigation_plan":investigation_plan,"native_searches":stats["search"],
                "native_fetches":stats["fetch"],"sources":evidence,
                "rejected_address_only_sources":[{"url":e.get("url"),"reason":"ADDRESS_CONTEXT_UNCONFIRMED"} for e in rejected],
                "source_dates":source_dates.verified_dates(row,evidence),**selection_info,
                "saved_at":dt.datetime.now(dt.timezone.utc).isoformat()})
            if not native.ledger_claim(db,day,reservation,native.MODEL_RESERVE,legacy,daily_limit=DAILY_CAP):
                audit.append({"project_id":rid,"status":"MODEL_BUDGET_OR_CONCURRENT_REQUEST",
                              "evidence_file":evidence_file.name})
                state["stop_reason"]="BUDGET_OR_CONCURRENT_REQUEST"
                break
            try:
                answer,cost=native.analyze(row,evidence,key,transport)
                native.ledger_finish(db,day,reservation,"DONE",cost)
                # Model claims stay review-only; roles and unawarded packages
                # require independent confirmation before promotion.
                output={"project_id":rid,"input_hash":identity,
                    "source_url":row["record_source_url"],"address":row["address"],
                    "research_status":"AI_REVIEW_ONLY","investigation_plan":investigation_plan,"native_searches":stats["search"],
                    "native_fetches":stats["fetch"],"sources":evidence,
                    "rejected_address_only_sources":[{"url":e.get("url"),"reason":"ADDRESS_CONTEXT_UNCONFIRMED"} for e in rejected],
                    "model_suggestions":answer,"source_dates":answer.get("source_dates",[]),
                    "evidence_file":evidence_file.name,**selection_info,
                    "verified_buying_authority":False,
                    "verified_supplier_unselected":False,"sale_ready":False,
                    "qualification_status":"RESEARCH_ONLY",
                    "missing_commercial_proof":["Purchasing authority linked to project",
                        "Official unawarded work package confirmation",
                        "Current procurement status"]}
                filename.write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding="utf-8")
                state["completed"]+=1
                audit.append({"project_id":rid,"status":"AI_REVIEW_SAVED",
                              "fetched_sources":len(evidence),"selection_score":pick["score"],
                              "model_dates_removed":answer.get("model_dates_removed",0)})
            except Exception as exc:
                cost=getattr(exc,"cost",None)
                if cost is not None:native.ledger_finish(db,day,reservation,"DONE",cost)
                else:native.ledger_finish(db,day,reservation,"UNKNOWN")
                failure_class=getattr(exc,"failure_class","REQUEST_FAILED")
                stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                failure_file=dest/(stem+"_FAILURE_"+stamp+".json")
                _write_new(failure_file,{"project_id":rid,"input_hash":identity,
                    "failure_class":failure_class,"error_type":type(exc).__name__,
                    "error_reason":_failure_reason(exc),
                    "raw_reply_excerpt":getattr(exc,"raw","") or "",
                    "cost_usd":cost,"evidence_file":evidence_file.name,
                    "saved_at":dt.datetime.now(dt.timezone.utc).isoformat()})
                audit.append({"project_id":rid,"status":"MODEL_FAILURE",
                              "error_type":type(exc).__name__,"failure_class":failure_class,
                              "error_reason":_failure_reason(exc),
                              "failure_file":failure_file.name,"evidence_file":evidence_file.name,
                              "cost_usd":cost})
                continue
        state["status"]=("REVIEW_ONLY_RESULTS" if state["completed"] else
            "BUDGET_EXHAUSTED" if state.get("stop_reason")=="DAILY_BUDGET_EXHAUSTED_OR_HELD" else
            "ALREADY_PROCESSED_TODAY" if state["skipped_previous_requests"] and not state["attempted"] else
            "NO_ELIGIBLE_PROJECTS_ABOVE_THRESHOLD" if not eligible else
            "NO_COMPLETED_AI_REVIEWS")
    finally:
        state["budget_used_or_held_usd"]=round(native.effective_spend(db,day)[0]+legacy,6)
        state["budget_remaining_usd"]=round(max(0,DAILY_CAP-state["budget_used_or_held_usd"]),6)
        db.close()
        state["audit"]=audit
        manifest.write_text(json.dumps(state,indent=2),encoding="utf-8")
    return state

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--candidates");p.add_argument("--results",required=True)
    p.add_argument("--out",required=True);p.add_argument("--paid",action="store_true")
    p.add_argument("--max-projects",type=int,default=3)
    a=p.parse_args()
    print(json.dumps(execute(a.candidates,a.results,a.out,paid=a.paid,
                             max_projects=a.max_projects),indent=2))
if __name__=="__main__":main()
