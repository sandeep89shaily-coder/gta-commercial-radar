"""Zero-cost bounded validation of two existing Radar candidate records.

Probes live sources and tests truthful excerpts, fabricated claims, and the
reviewed-evidence release gate. Never writes the production results directory.
"""
import argparse, datetime as dt, json
from pathlib import Path
import auto_verify
import reviewed_evidence
from gta_live_source_validation import run as brampton_probe

GAY_SPEC=Path(__file__).parent/"config"/"first_claims.json"
FALSE_CLAIM="All mechanical contracts are confirmed open and every supplier has not been selected"

def gay_lea_probe(fetcher):
    spec=json.loads(GAY_SPEC.read_text(encoding="utf-8"))["projects"][0]
    claims=spec["claims"]
    urls=sorted({v["official_url"] for v in claims.values()})
    fetched={u:fetcher(u) for u in urls}
    review,fields=auto_verify.build_review(spec,lambda u:fetched[u])
    verdict=reviewed_evidence.evaluate_review(review)
    negative=[]
    for url in urls:
        if not fetched[url].get("ok"):
            negative.append({"source_url":url,"status":"INCONCLUSIVE_SOURCE_UNAVAILABLE",
                             "reason":fetched[url].get("reason")})
            continue
        _,why,accepted=auto_verify.verify_claim("project_source",
            {"official_url":url,"excerpt":FALSE_CLAIM},spec["organization"],lambda u:fetched[u])
        negative.append({"source_url":url,"status":"REJECTED" if not accepted else "UNSAFE_ACCEPTED",
                         "reasons":why})
    verified=sum(x["status"]=="AUTO_VERIFIED" for x in fields.values())
    if verdict["sale_ready"] or any(x["status"]=="UNSAFE_ACCEPTED" for x in negative):
        outcome="FAIL"
    elif not verified and all(not f.get("ok") for f in fetched.values()):
        outcome="INCONCLUSIVE_SOURCE_UNAVAILABLE"
    elif all(x["status"]!="UNSAFE_ACCEPTED" for x in negative):
        outcome="PASS_PARTIAL_EVIDENCE"
    else:
        outcome="FAIL"
    return {"project_id":spec["project_id"],"address":spec["address"],
            "source_urls":urls,"source_status":{u:{"ok":x.get("ok"),"reason":x.get("reason")} for u,x in fetched.items()},
            "milestone_checks":fields,"auto_verified_milestones":verified,
            "fabricated_claim_checks":negative,"sale_ready":verdict["sale_ready"],
            "missing":verdict["missing"],"outcome":outcome}

def run(fetcher=auto_verify.fetch_page):
    a=brampton_probe(fetcher)
    b=gay_lea_probe(fetcher)
    outcomes=[a["outcome"],b["outcome"]]
    if "FAIL" in outcomes:status="FAIL"
    elif all(x.startswith("INCONCLUSIVE") for x in outcomes):status="INCONCLUSIVE"
    elif any(x.startswith("INCONCLUSIVE") for x in outcomes):status="PARTIAL_PASS"
    else:status="PASS"
    return {"run_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "mode":"LIVE_ZERO_PAID_AI","projects_checked":2,
            "deepseek_calls":0,"writes_to_production_results":False,
            "overall":status,"results":[a,b]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True)
    args=p.parse_args()
    result=run()
    Path(args.out).write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))
    return 1 if result["overall"]=="FAIL" else 0

if __name__=="__main__":raise SystemExit(main())
