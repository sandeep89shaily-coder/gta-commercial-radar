"""Persistent review-only industrial lifecycle tracking using the shared AI ledger."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path

import v5_investigator as v5
import v8_deepseek_native as native
from radar_config import DEEPSEEK_DAILY_LIMIT_USD

ROOT = Path(__file__).resolve().parent
FOLDER = "PROJECT_LIFECYCLE_REVIEW"
STATUS = "GTA_RADAR_PROJECT_LIFECYCLE_STATUS.json"
CSV = "GTA_RADAR_PROJECT_LIFECYCLE_50.csv"
MODEL_RESERVE = 0.018
STAGES = {"UNKNOWN", "ANNOUNCED", "APPROVALS", "DESIGN", "PROCUREMENT",
          "CONSTRUCTION", "COMMISSIONING", "OPERATIONS", "MAINTENANCE",
          "ON_HOLD", "CANCELLED", "COMPLETED"}
CHANGES = {"NEW_EVIDENCE", "CHANGED", "NO_NEW_EVIDENCE", "CONFLICT", "INSUFFICIENT_EVIDENCE"}


def atomic_json(path, value):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def load_seeds():
    seeds = json.loads((ROOT / "config/lifecycle_50.json").read_text(encoding="utf-8"))
    if len(seeds) != 50 or len({p["project_id"] for p in seeds}) != 50:
        raise ValueError("Lifecycle register must contain 50 unique projects")
    if not all(re.fullmatch(r"LC-\d{3}", p["project_id"]) for p in seeds):
        raise ValueError("Invalid lifecycle project ID")
    return seeds


def queries(p, day):
    name, location = p["search_name"], p["location"]
    return [f'"{name}" {location} Ontario {p["scope_hint"]} update {day[:4]}',
            f'"{name}" {location} Ontario equipment procurement tender award approval expansion']


def evidence_hash(pages):
    return hashlib.sha256(json.dumps(pages, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def verified_review(raw, pages):
    """Citation and quotation validation, not independent factual verification."""
    if not isinstance(raw, dict):
        raise ValueError("Model did not return an object")
    indexed = {p["id"]: p["text"] for p in pages}
    def ids_ok(ids):
        return isinstance(ids, list) and bool(ids) and all(type(i) is int and i in indexed for i in ids)
    def quote_ok(item):
        ids, quote = item.get("evidence_ids"), item.get("quote")
        return ids_ok(ids) and isinstance(quote, str) and bool(quote.strip()) and any(
            quote in indexed[i] for i in ids)
    identity = raw.get("identity")
    matched = isinstance(identity, dict) and identity.get("status") == "MATCHED" and ids_ok(identity.get("evidence_ids"))
    stage = raw.get("stage")
    stage = stage if matched and stage in STAGES and ids_ok(raw.get("stage_evidence_ids")) else "UNKNOWN"
    out = {"identity": identity if matched else {"status": "UNCERTAIN"},
           "stage": stage, "stage_evidence_ids": raw.get("stage_evidence_ids", []) if stage != "UNKNOWN" else [],
           "change_status": raw.get("change_status") if matched and raw.get("change_status") in CHANGES else "INSUFFICIENT_EVIDENCE"}
    for field, limit in (("changes", 5), ("packages", 6), ("participants", 5)):
        items = raw.get(field, [])
        if not isinstance(items, list):
            items = []
        out[field] = [item for item in items[:limit] if matched and isinstance(item, dict) and quote_ok(item)]
    if out["change_status"] in {"CHANGED", "NEW_EVIDENCE"} and not out["changes"]:
        out["change_status"] = "INSUFFICIENT_EVIDENCE"
    for field in ("changes", "packages"):
        for item in out[field]:
            for date_field in ("event_date", "publication_date", "deadline"):
                value = item.get(date_field)
                if value is not None and (not isinstance(value, str) or not any(
                        value in indexed[i] for i in item["evidence_ids"])):
                    item[date_field] = None
    for item in out["packages"]:
        if item.get("status") not in {"UNKNOWN", "POTENTIAL", "TENDER_PUBLISHED", "AWARDED", "CLOSED"}:
            item["status"] = "UNKNOWN"
        if item.get("basis") != "DOCUMENTED":
            item["status"] = "POTENTIAL"
        if item["status"] == "TENDER_PUBLISHED" and not (item.get("solicitation_id") and item.get("deadline")):
            item["status"] = "UNKNOWN"
        item["open_contract_verified"] = False
    for item in out["participants"]:
        contact = item.get("public_business_contact")
        if not isinstance(contact, str) or not any(contact in indexed[i] for i in item["evidence_ids"]):
            item["public_business_contact"] = ""
        item["purchasing_authority_verified"] = False
    out["missing_evidence"] = raw.get("missing_evidence", []) if isinstance(raw.get("missing_evidence"), list) else []
    out["next_queries"] = raw.get("next_queries", [])[:4] if isinstance(raw.get("next_queries"), list) else []
    out["conflicts"] = raw.get("conflicts", []) if isinstance(raw.get("conflicts"), list) else []
    out["qualification"] = "AI_REVIEW_ONLY_NOT_INDEPENDENTLY_VERIFIED"
    return out


def search_pages(project, db, day, legacy, key, transport):
    pages, errors, seen = [], [], set()
    for index, query in enumerate(queries(project, day)):
        charge = f"LC50:{project['project_id']}:search:{index}"
        if not native.ledger_claim(db, day, charge, native.SEARCH_COST, legacy):
            errors.append("SEARCH_BUDGET_OR_ALREADY_ATTEMPTED")
            continue
        try:
            data = native.request("/v1/tools/search", {"query": query, "count": 8, "need_content": True}, key, transport)
            entries = data.get("results", [])
            if not isinstance(entries, list):
                raise ValueError("Unexpected search results")
            native.ledger_finish(db, day, charge, "DONE" if entries else "NONBILLABLE",
                                 native.SEARCH_COST if entries else 0)
        except native.DeepSeekAccountBalanceError:
            native.ledger_finish(db, day, charge, "NONBILLABLE")
            raise
        except Exception as exc:
            native.ledger_finish(db, day, charge, "UNKNOWN")
            errors.append(type(exc).__name__)
            continue
        for item in entries:
            if not isinstance(item, dict):
                continue
            url, content = item.get("url"), item.get("content")
            if not isinstance(url, str) or not native.safe_url(url) or url in seen:
                continue
            if not isinstance(content, str) or not content.strip():
                continue
            # Discovery evidence only. Never reproduce source pages in customer outputs.
            seen.add(url)
            pages.append({"id": len(pages)+1, "url": url, "text": content[:1500],
                          "retrieved_on": day, "source_type": "PROVIDER_SEARCH_CONTENT",
                          "reuse_permission": "UNCONFIRMED"})
            if len(pages) >= 5:
                return pages, errors
    return pages, errors


def review_one(project, prior, db, day, legacy, key, transport, prompt):
    pid = project["project_id"]
    if native.effective_spend(db, day)[0] + legacy + MODEL_RESERVE + 2 * native.SEARCH_COST > DEEPSEEK_DAILY_LIMIT_USD:
        return {"status": "DEFERRED_SHARED_BUDGET"}
    pages, errors = search_pages(project, db, day, legacy, key, transport)
    if not pages:
        return {"status": "NO_RETRIEVED_EVIDENCE", "errors": errors}
    name = f"LC50:{pid}:model"
    payload = {"model": native.MODEL, "thinking": {"type": "disabled"},
               "response_format": {"type": "json_object"}, "max_tokens": 2000,
               "stream": False, "messages": [
                   {"role": "system", "content": prompt},
                   {"role": "user", "content": json.dumps({
                       "project": project, "review_date": day,
                       "previous_review": json.dumps(prior or {}, ensure_ascii=True)[:1800],
                       "documents": pages}, ensure_ascii=True)}]}
    if len(json.dumps(payload, ensure_ascii=True).encode("ascii")) > 35000:
        return {"status": "INPUT_LIMIT", "sources": pages, "errors": errors}
    if not native.ledger_claim(db, day, name, MODEL_RESERVE, legacy):
        return {"status": "DEFERRED_SHARED_BUDGET_OR_PRIOR_ATTEMPT", "sources": pages, "errors": errors}
    try:
        response = native.request("/chat/completions", payload, key, transport)
        cost = native.model_usage_cost(response.get("usage", {}))
        native.ledger_finish(db, day, name, "DONE" if cost is not None else "UNKNOWN", cost)
    except native.DeepSeekAccountBalanceError:
        native.ledger_finish(db, day, name, "NONBILLABLE")
        raise
    except Exception as exc:
        native.ledger_finish(db, day, name, "UNKNOWN")
        return {"status": "MODEL_REQUEST_FAILED", "errors": errors+[type(exc).__name__], "sources": pages}
    try:
        choice = response["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ValueError("Truncated model response")
        raw = native.parse_model_json(choice["message"]["content"])
        review = verified_review(raw, pages)
    except Exception as exc:
        return {"status": "MODEL_OUTPUT_INVALID", "errors": errors+[type(exc).__name__], "sources": pages}
    return {"status": "AI_REVIEW_SAVED", "review": review, "sources": pages,
            "evidence_hash": evidence_hash(pages), "errors": errors, "model_cost_estimate_usd": cost}


def last_review(folder, before):
    for path in sorted(folder.glob("????-??-??.json"), reverse=True):
        if path.stem >= before:
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("status") == "AI_REVIEW_SAVED":
            return path.stem, value.get("review", {})
    return "", {}


def safe_cell(x):
    value = str(x or "")
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def run(results, *, paid=False, key=None, transport=None, today=None):
    root = Path(results)
    root.mkdir(parents=True, exist_ok=True)
    dest = root / FOLDER
    dest.mkdir(exist_ok=True)
    day = (today or dt.date.today()).isoformat()
    projects = load_seeds()
    prompt = (ROOT / "config/lifecycle_investigator_prompt.txt").read_text(encoding="utf-8")
    prior = {p["project_id"]: last_review(dest / p["project_id"], day) for p in projects}
    # Rotate oldest successful review first so budget holds do not permanently starve later projects.
    projects.sort(key=lambda p: (prior[p["project_id"]][0], p["project_id"]))
    key = (v5.key_from_windows() if key is None else key) if paid else None
    db = v5._ledger(root / "v5_ai_budget.sqlite") if paid and key else None
    legacy = v5._legacy_reserved(root / "deepseek_budget.sqlite", day) if db is not None else 0
    rows, stopped = [], False
    try:
        for project in projects:
            pid = project["project_id"]
            folder = dest / pid
            folder.mkdir(exist_ok=True)
            path = folder / (day + ".json")
            if path.exists():
                record = json.loads(path.read_text(encoding="utf-8"))
            elif not paid:
                record = {"status": "PREVIEW_NO_PAID_CALL"}
            elif not key:
                record = {"status": "MISSING_API_KEY"}
            elif stopped:
                record = {"status": "DEFERRED_PROVIDER_BALANCE"}
            else:
                try:
                    record = review_one(project, prior[pid][1], db, day, legacy, key, transport, prompt)
                except native.DeepSeekAccountBalanceError:
                    record, stopped = {"status": "PROVIDER_HTTP_402"}, True
                record.update({"project_id": pid, "review_date": day, "outreach_authorized": False})
                # Preserve daily attempts except budget deferrals, which may be retried if funds are available.
                if not record["status"].startswith("DEFERRED"):
                    atomic_json(path, record)
            result = record.get("review", {})
            last_day, last = prior[pid]
            rows.append({"project_id": pid, "project": project["name"], "location": project["location"],
                         "run_status": record["status"], "review_date": day,
                         "last_successful_ai_review": day if record["status"] == "AI_REVIEW_SAVED" else last_day,
                         "current_stage_ai_hint": result.get("stage", "UNKNOWN"),
                         "previous_stage_ai_hint": last.get("stage", "UNKNOWN"),
                         "change_status": result.get("change_status", "NOT_ASSESSED"),
                         "packages_review_only": len(result.get("packages", [])),
                         "participants_review_only": len(result.get("participants", [])),
                         "evidence_urls": " | ".join(p["url"] for p in record.get("sources", [])),
                         "verified_open_contract": False, "sale_ready": False})
        budget = native.effective_spend(db, day)[0] + legacy if db is not None else None
    finally:
        if db is not None:
            db.close()
    rows.sort(key=lambda r: r["project_id"])
    csv_path = root / CSV
    temp = csv_path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: safe_cell(v) for k,v in row.items()} for row in rows)
    os.replace(temp, csv_path)
    count = sum(row["run_status"] == "AI_REVIEW_SAVED" for row in rows)
    report = {"status": "REVIEW_ONLY_COMPLETE" if count == 50 else "REVIEW_ONLY_PARTIAL",
              "review_date": day, "watchlist_count": 50, "ai_reviewed_today": count,
              "not_reviewed_today": 50-count, "shared_budget_used_or_held_usd": budget,
              "shared_budget_cap_usd": DEEPSEEK_DAILY_LIMIT_USD,
              "verified_open_contracts": 0, "outreach_authorized": False,
              "report_csv": CSV, "history_folder": FOLDER,
              "counts": {s: sum(row["run_status"] == s for row in rows)
                         for s in sorted({row["run_status"] for row in rows})}}
    atomic_json(root / STATUS, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    parser.add_argument("--paid", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.results, paid=args.paid), indent=2))
