"""Evaluate DeepSeek report claims against human-reviewed fact fixtures.

This is an offline evaluation harness: NO API requests, cost, or changes to
production. A claim is grounded only if the cited quote occurs on its page.
Grounding != factual correctness; gold comparisons check correctness.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

def norm(value):
    return " ".join(str(value or "").casefold().split())

def evaluate(result, gold):
    supported=result.get("supported_claims",[])
    expected=gold.get("expected",[])
    pages=gold.get("pages",[])
    page_text={p["page"]:p["text"] for p in pages}
    expected_pairs={(norm(c["field"]),norm(c["value"])) for c in expected}
    predictions={(norm(c.get("field")),norm(c.get("value"))) for c in supported}
    quote_valid=sum(
        isinstance(c.get("page"),int)
        and c.get("evidence_excerpt","") in page_text.get(c.get("page"),"")
        and bool(c.get("evidence_excerpt",""))
        for c in supported)
    matched=len(expected_pairs & predictions)
    return {
        "status":"OFFLINE_EVALUATION",
        "expected_count":len(expected_pairs),
        "predicted_count":len(predictions),
        "matched_count":matched,
        "precision":matched/len(predictions) if predictions else (1.0 if not expected else 0.0),
        "recall":matched/len(expected_pairs) if expected_pairs else (1.0 if not predictions else 0.0),
        "quotes_on_cited_page":quote_valid,
        "quotes_submitted":len(supported),
        "false_positive_fields":sorted([list(p) for p in predictions-expected_pairs]),
        "missed_fields":sorted([list(p) for p in expected_pairs-predictions]),
        "real_document_validated":bool(gold.get("verified_real_pdf")),
        "supplier_selected_evidence_checked":False,
        "buyer_verified":False
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--result",required=True)
    p.add_argument("--gold",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    result=json.loads(Path(a.result).read_text(encoding="utf-8"))
    gold=json.loads(Path(a.gold).read_text(encoding="utf-8"))
    report=evaluate(result,gold)
    target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    main()
