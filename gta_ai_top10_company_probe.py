"""Direct, opt-in DeepSeek company/contact investigation of CURRENT Top 10 CSV.

This deliberately skips the 24-record preselection and municipal collection.
It uses the existing shared $1/day ledger and immutable paid checkpoints.
AI narratives are unverified research hints. Independently fetched pages are
retained separately; co-location is not proof of purchasing or a contract.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path

import v5_investigator as v5
from radar_run_lock import once_lock
from gta_top10_live_source_recheck import model_directed_company_search

INPUT = "GTA_RADAR_COMMERCIAL_TOP10_ANALYST_REVIEW.csv"
OUT_PREFIX = "GTA_RADAR_TOP10_DEEPSEEK_COMPANY_PROBE_"


def _rows(root):
    source = root / INPUT
    if not source.is_file():
        raise FileNotFoundError("CURRENT_TOP10_CSV_MISSING: " + str(source))
    with source.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    if not rows:
        raise ValueError("TOP10_CSV_EMPTY")
    required = ("record_id", "city", "address", "application_id",
                "project_description", "source_url")
    if any(key not in rows[0] for key in required):
        raise ValueError("TOP10_CSV_MISSING_REQUIRED_FIELDS")
    selected = []
    for data in rows[:10]:
        if not data["record_id"].strip() or not data["address"].strip():
            continue
        selected.append({key: str(data.get(key) or "").strip() for key in required})
    if not selected:
        raise ValueError("TOP10_NO_USABLE_RECORDS")
    return selected


def _output(root, day):
    return root / (OUT_PREFIX + day.isoformat() + ".json")


def _save(path, report):
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    temp.replace(path)


def run(root, *, paid=False, token=None, today=None, transport=None):
    root = Path(root)
    rows = _rows(root)
    day = today or dt.date.today()
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    path = _output(root, day)
    report = {"status": "PREFLIGHT_ONLY", "date": day.isoformat(),
              "input": INPUT, "input_fingerprint": digest,
              "selected_count": len(rows), "attempted_count": 0,
              "completed_fetch_evidence": 0, "verified_buyers": 0,
              "contact_verification": "NONE_AUTOMATED",
              "not_authorized_for_outreach": True,
              "reviews": [], "report_path": str(path)}
    if not paid:
        return report
    key = v5.key_from_windows() if token is None else token
    if not key:
        report["status"] = "MISSING_DEEPSEEK_API_KEY"
        return report
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            old = {}
        if old.get("input_fingerprint") != digest:
            report["status"] = "TOP10_CHANGED_SAME_DAY_REVIEW_EXISTING_FILE_FIRST"
            return report
    with once_lock(root):
        db = v5._ledger(root / "v5_ai_budget.sqlite")
        try:
            legacy = v5._legacy_reserved(root / "deepseek_budget.sqlite",
                                          day.isoformat())
            for row in rows:
                checked = model_directed_company_search(
                    root, row, key, db, day, legacy, transport=transport)
                sources = []
                for src in checked.get("sources") or []:
                    sources.append({
                        "url": src.get("url", ""),
                        "identity": src.get("identity", ""),
                        "excerpt": src.get("excerpt", ""),
                        "role_excerpt": src.get("role_excerpt", ""),
                        "retrieved_on": src.get("retrieved_on", ""),
                        "project_role_verified": False,
                    })
                item = {
                    "record_id": row["record_id"], "city": row["city"],
                    "address": row["address"], "application_id": row["application_id"],
                    "project_description": row["project_description"],
                    "research_status": checked.get("status", "UNKNOWN"),
                    "model_summary_research_hint_not_verified":
                        checked.get("model_research_summary", ""),
                    "discovered_urls_unverified": checked.get("discovered_urls", []),
                    "independently_fetched_context": sources,
                    "company_and_contact_verification": "PENDING",
                    "purchasing_authority_verified": False,
                    "procurement_award_verified": False,
                    "issues": checked.get("issues", []),
                }
                report["reviews"].append(item)
                report["attempted_count"] += 1
                report["completed_fetch_evidence"] += len(sources)
                report["status"] = "PARTIAL_SAVED"
                _save(path, report)
                if checked.get("status") in (
                    "BUDGET_OR_ALREADY_CLAIMED", "UNKNOWN_CHARGE_NO_RETRY",
                    "UNKNOWN_PROVIDER_USAGE_NO_RETRY", "HTTP_402"):
                    report["status"] = "STOPPED_" + checked.get("status")
                    break
            else:
                report["status"] = "ALL_TOP10_RESEARCH_ATTEMPTED"
        finally:
            db.close()
    _save(path, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    parser.add_argument("--paid", action="store_true",
                        help="Allow paid DeepSeek research under shared daily budget")
    args = parser.parse_args()
    result = run(args.results, paid=args.paid)
    print(json.dumps({k: v for k, v in result.items() if k != "reviews"},
                     indent=2))
