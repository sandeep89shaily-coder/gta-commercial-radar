"""AI-first work allocation for commercial Radar intelligence.

This planner never spends money or makes claims itself. It picks AI tasks where
source-supported uncertainty could change a lead's commercial viability.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path

STAGES=("SOURCE_EXTRACTION","PROJECT_RESOLUTION","BUYER_RELATIONSHIP",
        "PROCUREMENT_REVIEW","CONTRADICTION_CHECK")
def plan(candidate):
    sources=candidate.get("sources",[])
    if not isinstance(sources,list):sources=[]
    tasks=[]
    def add(stage,reason,need):
        tasks.append({"stage":stage,"reason":reason,"required_evidence":need,
                      "model_role":"PROPOSE_WITH_QUOTES_NOT_VERIFY",
                      "paid":False,"approval_required":True})
    if any(s.get("type") in ("pdf","meeting_transcript","ocr") and not s.get("analyzed") for s in sources if isinstance(s,dict)):
        add("SOURCE_EXTRACTION","Uninterpreted official document or transcript","Source page or timestamp + exact quote")
    if len(sources)>1 and not candidate.get("project_identity_confirmed"):
        add("PROJECT_RESOLUTION","Potential cross-source duplicates","Independent IDs and matching address/parcel evidence")
    if not candidate.get("buying_authority_verified"):
        add("BUYER_RELATIONSHIP","Owner, operator and purchasing authority not established","Official organization-role evidence and public business contact route")
    if not candidate.get("supplier_selection_verified"):
        add("PROCUREMENT_REVIEW","Cannot assume an unawarded trade opportunity","Original official tender/award or direct confirmed source")
    if candidate.get("conflicting_claims"):
        add("CONTRADICTION_CHECK","Conflicting dates, roles or stages","Independent dated source quotations")
    return {"project_id":candidate.get("project_id"),"tasks":tasks,
            "ai_calls_executed":0,"verified_leads_created":0,
            "budget_cap_usd_per_day":0.25,"production_promotion":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--candidate",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    result=plan(json.loads(Path(a.candidate).read_text(encoding="utf-8")))
    output=Path(a.out);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({"tasks":len(result["tasks"]),"paid_requests":0},indent=2))
if __name__=="__main__":main()
