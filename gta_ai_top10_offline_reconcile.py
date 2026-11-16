"""Reconcile an already paid, rejected Top-10 model result without another call.

Rechecks the original model response against original saved independent source
excerpts using the same _validate function as production. Unsupported model
citations are explicitly REJECTED and review downgraded, never accepted.
Does not modify the customer Top 10, reserve budget or request new data.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from gta_ai_top10_reranker import _validate, ATTEMPT


def run(results):
    root = Path(results)
    attempt_path = root / ATTEMPT
    if not attempt_path.is_file():
        raise FileNotFoundError("ORIGINAL_PAID_TOP10_ATTEMPT_MISSING")
    state = json.loads(attempt_path.read_text(encoding="utf-8"))
    record_id = str(state.get("failed_project_id") or "")
    raw = Path(str(state.get("failed_response_file") or "")).name
    if not record_id or not raw.endswith(".raw_response.json"):
        raise ValueError("NO_PRESERVED_INVALID_MODEL_AND_PROJECT")
    source = root / "AI_TOP10_REVIEW_BATCHES" / raw
    if not source.is_file():
        raise FileNotFoundError("PRESERVED_MODEL_RESPONSE_NOT_FOUND")
    response = json.loads(source.read_text(encoding="utf-8"))
    date = str(state.get("recheck_date") or "")
    files = sorted((root / "AI_TOP10_LIVE_SOURCE_CHECKS").glob("LIVE_*.json"))
    matches = []
    for path in files:
        try:
            check = json.loads(path.read_text(encoding="utf-8"))
            if check.get("record_id") == record_id and check.get("checked_on") == date:
                matches.append(check)
        except (ValueError, OSError):
            pass
    if len(matches) != 1:
        raise ValueError("EXACT_ORIGINAL_LIVE_SOURCE_SNAPSHOT_NOT_UNIQUE")
    check = matches[0]
    row = {"city": check["city"], "record_id": record_id}
    accepted = _validate(
        response, 1, batch=[row],
        live_checks={(check["city"].casefold(), record_id): check})
    review = accepted[0]
    result = {
        "status": "OFFLINE_SOURCE_VALIDATED_RESEARCH_ONLY",
        "project_id": record_id,
        "city": check["city"],
        "recheck_date": date,
        "original_model_response": raw,
        "decision": review["decision"],
        "unsupported_live_citation_rejected": review["rejected_live_citation"],
        "source_citation_status": review["source_citation_status"],
        "cited_source": review["cited_source"],
        "role_claims": review["role_candidates"],
        "site_mentions": review["site_company_candidates"],
        "buyer_hypothesis": review["buyer_function_hypothesis"],
        "next_check": review["next_check"],
        "paid_model_calls": 0, "paid_search_calls": 0, "paid_fetch_calls": 0,
        "customer_top10_edited": False, "verified_buyer": False,
        "verified_open_supplier_package": False,
        "original_incomplete_aggregate_preserved": True,
    }
    out = root / "GTA_RADAR_AI_TOP10_OFFLINE_RECONCILED.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", required=True)
    a = p.parse_args()
    print(json.dumps(run(a.results), indent=2))


if __name__ == "__main__":
    main()
