"""Unified evidence acceptance: process success must never imply commercially valid output.

Uses only on-disk reports; does not invent documents, buyers, or dates.
"""
from __future__ import annotations
import csv
import json
from pathlib import Path

def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}

def read_rows(path):
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file))
    except (OSError, ValueError):
        return []

def evaluate(review, results=None):
    review = Path(review)
    results = Path(results) if results else review.parent
    # Count actual unique captured source records, not separate overlapping queue totals.
    combined = read_rows(review/"MEETING_DOCUMENTS"/"Toronto"/"COMBINED_PDF_FETCH_AUDIT.csv")
    if not combined:
        # Standalone/legacy audit acceptance where the union stage was not run.
        meeting = read_rows(review/"MEETING_DOCUMENTS"/"Toronto"/"TORONTO_PDF_FETCH_AUDIT.csv")
        verified = read_rows(review/"MEETING_DOCUMENTS"/"Toronto"/"VERIFIED_REPORT_FETCH_AUDIT.csv")
        combined = meeting + [{**row, "url":row.get("attachment_url") or row.get("url")} for row in verified]
    unique = {row.get("url"):row for row in combined if row.get("url")}
    documents = sum(row.get("status")=="CAPTURED" for row in unique.values())
    if not unique:
        # Legacy isolated test audits can omit URLs; retain their diagnostic count.
        legacy = read_rows(review/"MEETING_DOCUMENTS"/"Toronto"/"VERIFIED_REPORT_FETCH_AUDIT.csv")
        summary = read_json(review/"MEETING_DOCUMENTS"/"Toronto"/"VERIFIED_REPORT_FETCH_SUMMARY.json")
        documents = min(sum(row.get("status")=="CAPTURED" for row in legacy), int(summary.get("captured") or 0))
    analyzed = read_rows(review/"DOCUMENT_AI"/"TORONTO_AI_DOCUMENT_BATCH_AUDIT.csv")
    completed_urls = {row.get("source_url") for row in analyzed
                      if row.get("source_url") and row.get("result_file")
                      and row.get("status") not in ("ERROR","MISSING_PDF","CHECKSUM_MISMATCH","READY_NOT_SENT")}
    ai_completed = len(completed_urls)
    buyers = read_json(review/"BUYER_RESEARCH_STATUS.json")
    buyer_count = int(buyers.get("verified_buyers") or buyers.get("buying_decision_makers_verified") or 0)
    releases = read_json(review/"RELEASE_ACCEPTANCE.json")
    unawarded = int(releases.get("verified_unawarded_packages") or 0)
    proof = read_json(results/"EARLY_DISCOVERY_PROOF.json")
    measured = int(proof.get("measurable") or 0)
    stage_success = bool(releases.get("production_acceptance") is True)
    checks = {
        "official_documents_captured": documents > 0,
        "document_ai_completed": ai_completed > 0,
        "verified_buyer_authorities": buyer_count > 0 and int(releases.get("verified_buying_authorities") or 0)>0,
        "unawarded_private_work_packages_verified": unawarded > 0,
        "early_discovery_pair_measured": measured > 0,
        "release_acceptance_confirmed": stage_success,
    }
    return {
        "production_accepted": all(checks.values()),
        "checks": checks,
        "blockers": [key.upper() for key, passed in checks.items() if not passed],
        "counts": {"captured_documents": documents, "ai_analyzed_documents": ai_completed,
                   "buyer_authorities": buyer_count, "unawarded_packages": unawarded,
                   "measurable_discovery_pairs": measured},
        "note": "Zero observations are evidence gaps, not success. Early-discovery comparisons require independently verified matching events."
    }

def write_report(review, report):
    target = Path(review)/"UNIFIED_EVIDENCE_GATES.json"
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2),encoding="utf-8")
    return target
