"""Bounded zero-cost live public-record acceptance probe.

This makes actual HTTP requests through the existing robots-checked verifier.
Network refusal is INCONCLUSIVE, never a pass. Buyer / procurement remain false.
No source databases or human-reviewed evidence files are written.
"""
import argparse, datetime as dt, json, pathlib
import auto_verify
import reviewed_evidence

URL=("https://planning.brampton.ca/CitizenAccess/Cap/CapDetail.aspx?"
     "Module=Planning&TabName=Planning&agencyCode=BRAMPTON"
     "&capID1=REC21&capID2=00000&capID3=000LB")
PROJECT="Brampton SPA-2021-0209 (5515 and 5525 Countryside Drive)"
EXPECTED=("SPA-2021-0209","5515 and 5525 Countryside Drive",
          "2 industrial buildings")
FALSE="the municipality confirms every HVAC contract is unawarded and ready to bid"

def run(fetcher=auto_verify.fetch_page):
    report={"tested_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "project":PROJECT,"source_url":URL,"network_cost_usd":0,
        "paid_ai_calls":0,"buyer_authority_verified":False,
        "supplier_unselected_verified":False}
    page=fetcher(URL)
    if not page.get("ok"):
        report.update(outcome="INCONCLUSIVE_SOURCE_UNAVAILABLE",
                      reason=page.get("reason","UNKNOWN"))
        return report
    # Require both an exact file identity and project scope, not just generic HTML.
    verified={}
    for label in EXPECTED:
        claim={"official_url":URL,"excerpt":label}
        verified[label]=auto_verify.excerpt_present(page.get("text",""),label)
    fake=auto_verify.excerpt_present(page.get("text",""),FALSE)
    report["expected_text_matches"]=verified
    report["fabricated_quote_rejected"]=not fake
    # Directly exercise the production validator with a page-backed positive
    # excerpt, and a deliberately fabricated negative quote.
    actual="5515 and 5525 Countryside Drive To permit the construction of 2 industrial buildings"
    fetch=lambda url:page
    pos,issues,allowed=auto_verify.verify_claim(
        "project_source",{"official_url":URL,"excerpt":actual},"",fetch)
    neg,neg_issues,neg_allowed=auto_verify.verify_claim(
        "project_source",{"official_url":URL,"excerpt":FALSE},"",fetch)
    report.update(positive_production_verification=allowed,
                  positive_problems=issues,
                  false_claim_blocked=(not neg_allowed and bool(neg_issues)),
                  false_claim_problems=neg_issues)
    # A verified source is NOT a sale-ready opportunity: no purchasing proof.
    review={"project_id":"brampton:SPA-2021-0209","supplier_status":"UNKNOWN",
            "evidence":{"project_source":pos} if pos else {}}
    decision=reviewed_evidence.evaluate_review(review)
    report["sale_ready"]=decision["sale_ready"]
    report["missing_milestones"]=decision["missing"]
    checks=(verified.get(EXPECTED[0],False) and
            verified.get(EXPECTED[1],False) and
            verified.get(EXPECTED[2],False) and
            report["fabricated_quote_rejected"] and
            report["positive_production_verification"] and
            report["false_claim_blocked"] and not report["sale_ready"])
    report["outcome"]="PASS" if checks else "FAIL"
    return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",default="live_source_validation.json")
    args=ap.parse_args()
    result=run()
    pathlib.Path(args.out).write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))
    return 0 if result["outcome"]=="PASS" else (2 if result["outcome"].startswith("INCONCLUSIVE") else 1)

if __name__=="__main__":raise SystemExit(main())
