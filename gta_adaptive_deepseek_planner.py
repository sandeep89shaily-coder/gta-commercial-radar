"""DeepSeek investigation planner with bounded, auditable research actions.

The model may select only a topic and one of the project's predefined search
queries. Python retains control over network access, budgets and claims.
"""
import hashlib,json
import v8_deepseek_native as native

TOPICS=("project_identity","buyer_organization","supplier_award","project_timing")

def plan(row,key,db,day,legacy,transport=None,*,daily_limit=.49):
    queries=native.queries(row)[:3]
    fallback={"topic":"project_identity","queries":queries,
              "status":"DETERMINISTIC_FALLBACK","model_cost_usd":0.0}
    if not queries:return fallback
    identity=str(row.get("project_id") or "")
    claim="adaptive_plan_v1_"+hashlib.sha256((identity+json.dumps(queries)).encode()).hexdigest()[:22]
    if not native.ledger_claim(db,day,claim,native.MODEL_RESERVE,legacy,daily_limit=daily_limit):
        return {**fallback,"status":"PLANNER_BUDGET_OR_PRIOR_REQUEST"}
    try:
        system=("You are a cautious GTA development-research planner. Decide the "
                "single most useful research topic for this specific project. "
                "Choose integer query indices from the provided candidate queries "
                "ONLY. Return JSON keys topic and query_indices. Topics allowed: "
                "project_identity, buyer_organization, supplier_award, project_timing. "
                "Do not invent project facts or new URLs.")
        payload={"project_id":identity,"description":str(row.get("description") or "")[:500],
                 "status":str(row.get("current_source_status") or "")[:100],
                 "queries":[{"index":i,"query":q} for i,q in enumerate(queries)]}
        answer=native.request("/chat/completions",{"model":native.MODEL,
            "thinking":{"type":"disabled"},"response_format":{"type":"json_object"},
            "messages":[{"role":"system","content":system},
                        {"role":"user","content":json.dumps(payload)}],
            "max_tokens":200,"stream":False},key,transport)
        values=json.loads(answer["choices"][0]["message"]["content"])
        topic=values.get("topic")
        if topic not in TOPICS:topic="project_identity"
        indices=values.get("query_indices",[])
        valid=[]
        if isinstance(indices,list):
            for i in indices:
                if type(i) is int and 0<=i<len(queries) and i not in valid:valid.append(i)
        order=valid+[i for i in range(len(queries)) if i not in valid]
        cost=native.model_usage_cost(answer.get("usage",{}))
        native.ledger_finish(db,day,claim,"DONE" if cost is not None else "UNKNOWN",cost)
        return {"topic":topic,"queries":[queries[i] for i in order],
                "status":"AI_PLANNED","model_cost_usd":cost}
    except Exception:
        native.ledger_finish(db,day,claim,"UNKNOWN")
        return {**fallback,"status":"PLANNER_ERROR_RESERVATION_HELD"}
