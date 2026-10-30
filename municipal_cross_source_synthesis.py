"""Review-only DeepSeek synthesis of cited PDF/meeting observations.

Links source evidence IDs across materials without auto-merging ambiguous
projects or inferring purchasing authority. Shared ledger enforces $0.25/day.
"""
from __future__ import annotations
import argparse,datetime as dt,hashlib,json
from pathlib import Path
import v5_investigator as v5
import v8_deepseek_native as native

STAGE="municipal_cross_source_synthesis_v1"
RESERVE_USD=0.025
PROMPT="""You analyze untrusted municipal project observations extracted from
official documents and meeting recordings. Return compact JSON with keys:
project_candidates, corroborations, novel_audio_claims, conflicts, summary.
Each project_candidates item: name, address, event_type, organizations,
source_evidence_ids, unresolved_questions. Each corroboration or audio claim
has source_evidence_ids and an explanation. Never invent missing addresses,
developers, purchasing contacts, construction plans, or unawarded tenders.
Distinct sites are distinct until evidence proves an identity match.
Audio-only statements are UNCONFIRMED until the recording is listened to.
Each source_evidence_ids entry MUST match an ID provided in input.
Tax agreements and existing operations are not available work packages.
Return JSON only. Keep brief; do not assert verified commercial opportunities."""

def observations(review_files,max_evidence=24):
    sources=[];items=[]
    for name in review_files:
        obj=json.loads(Path(name).read_text(encoding="utf-8"))
        if not obj.get("source_sha256") or not obj.get("source_url"):
            raise ValueError("Missing provenance in evidence review")
        sources.append({"url":obj["source_url"],"sha256":obj["source_sha256"],
                        "completed_chunks":obj.get("completed_chunks",[])})
        for item in obj.get("mentions",[]):
            if not (item.get("quote_present") and item.get("marker_correct")
                    and item.get("evidence_check_passed")):continue
            if len(items)>=max_evidence:break
            tag="E"+str(len(items)+1)
            items.append({"id":tag,"source_url":obj["source_url"],
                          "kind":item.get("source_kind"),
                          "page_or_second":item.get("source_marker_expected"),
                          "address":item.get("address",""),
                          "organization":item.get("organization",""),
                          "role":item.get("role",""),
                          "stage":item.get("stage",""),
                          "quote":str(item.get("exact_quote") or "")[:180]})
    return {"sources":sources,"evidence":items}

def synthesize(review_files,results,out,*,paid=False,key=None,transport=None):
    if not 1<=len(review_files)<=4:raise ValueError("Supply 1-4 review files")
    found=observations(review_files)
    encoded=json.dumps(found,ensure_ascii=True)
    if len(encoded.encode("ascii"))>native.MODEL_INPUT_BYTES*2:
        raise ValueError("Too much evidence for a single synthesis; split reviews")
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    state={"status":"NO_PAID_SYNTHESIS","source_count":len(found["sources"]),
           "grounded_evidence_count":len(found["evidence"]),"paid_model_calls":0,
           "sale_ready_leads":0}
    if not found["evidence"]:
        return {**state,"status":"NO_GROUNDED_EVIDENCE_FOR_SYNTHESIS"}
    if not paid:
        out.write_text(json.dumps({**state,"source_evidence":found},indent=2),encoding="utf-8")
        return state
    root=Path(results)
    if not root.is_dir():raise ValueError("Existing shared results folder required")
    key=v5.key_from_windows() if key is None else key
    if not key:return {**state,"status":"MISSING_API_KEY"}
    day=dt.date.today().isoformat()
    source_hash=hashlib.sha256(encoded.encode("ascii")).hexdigest()
    reservation="municipal_synthesis_"+hashlib.sha256((STAGE+source_hash).encode()).hexdigest()[:24]
    db=v5._ledger(root/"v5_ai_budget.sqlite")
    try:
        legacy=v5._legacy_reserved(root/"deepseek_budget.sqlite",day)
        if not native.ledger_claim(db,day,reservation,RESERVE_USD,legacy,daily_limit=0.25):
            return {**state,"status":"SHARED_BUDGET_OR_DUPLICATE_BLOCKED"}
        try:
            response=native.request("/chat/completions",{
                "model":native.MODEL,"thinking":{"type":"disabled"},
                "messages":[{"role":"system","content":PROMPT},
                            {"role":"user","content":encoded}],
                "response_format":{"type":"json_object"},
                "max_tokens":2200,"stream":False},key,transport=transport)
            choice=response["choices"][0]
            if choice.get("finish_reason")=="length":
                raise ValueError("Cross-source synthesis truncated")
            model=json.loads(choice["message"]["content"])
            if not isinstance(model,dict):raise ValueError("Synthesis must be JSON object")
            native.ledger_finish(db,day,reservation,"UNKNOWN")
        except Exception:
            native.ledger_finish(db,day,reservation,"UNKNOWN")
            raise
    finally:db.close()
    known={x["id"] for x in found["evidence"]}
    rejected=[]
    for field in ("project_candidates","corroborations","novel_audio_claims"):
        cleaned=[]
        for entry in model.get(field,[]) if isinstance(model.get(field),list) else []:
            if not isinstance(entry,dict):continue
            refs=entry.get("source_evidence_ids",[])
            if not isinstance(refs,list) or not refs or any(r not in known for r in refs):
                rejected.append({"field":field,"reason":"MISSING_OR_INVALID_EVIDENCE_ID"})
                continue
            cleaned.append({**entry,"review_required":True})
        model[field]=cleaned
    state.update({"status":"SYNTHESIS_REVIEW_ONLY","paid_model_calls":1,
                  "candidate_project_groups":len(model.get("project_candidates",[])),
                  "invalid_citations_rejected":len(rejected)})
    out.write_text(json.dumps({"summary":state,"source_evidence":found,
            "ai_suggestions":model,"rejected_claims":rejected,
            "warning":"AI grouped observations are unverified. No buyer, award, procurement or project matches automatically approved."},
            indent=2,ensure_ascii=False),encoding="utf-8")
    return state

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--reviews",nargs="+",required=True)
    p.add_argument("--results",required=True);p.add_argument("--out",required=True)
    p.add_argument("--paid",action="store_true")
    a=p.parse_args()
    print(json.dumps(synthesize(a.reviews,a.results,a.out,paid=a.paid),indent=2))
if __name__=="__main__":main()
