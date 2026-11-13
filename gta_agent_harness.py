"""Evidence-first, bounded AI harness for GTA Commercial Radar.

Orchestrates the EXISTING candidate selector, AI task planner, source-backed
DeepSeek executor, shared budget ledger and review gates. The default is free
preflight only; --paid is explicit. Nothing is merged into production leads.

The harness owns workflow state, per-input checkpoint reconciliation and
quality metrics. The existing executor owns ALL paid network/model requests,
tool permissions, idempotency and DeepSeek spending.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

from gta_ai_work_allocator import plan as allocate_work
from gta_execute_ai_project_research import (
    execute as execute_project_research,
    locate_candidates,
    select_projects,
)
from radar_config import DEEPSEEK_DAILY_LIMIT_USD
from radar_run_lock import once_lock

EXACT_IDENTITY = "EXACT_CURRENT_PERMIT_ID_IN_PAGE"
CONTEXT_ONLY = "PROJECT_CONTEXT_NOT_APPLICATION_VERIFIED"
VERSION = "1.0"


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def input_hash(row):
    """Use the executor's exact existing input-version algorithm."""
    return hashlib.sha256(json.dumps(
        {key: row.get(key) for key in sorted(row)}, sort_keys=True
    ).encode()).hexdigest()


def review_paths(folder, row):
    """Return both immutable filenames used by the existing paid executor."""
    stem = "AI_PROJECT_" + hashlib.sha256(row["project_id"].encode()).hexdigest()[:16]
    digest = input_hash(row)
    base = Path(folder) / (stem + ".json")
    versioned = Path(folder) / (stem + "_" + digest[:12] + ".json")
    return base, versioned


def load_checkpoint(folder, row):
    """Never accept a result for an earlier version of the same project."""
    for path in review_paths(folder, row):
        try:
            if not path.is_file():
                continue
            record = json.loads(path.read_text(encoding="utf-8"))
            if (isinstance(record, dict)
                    and record.get("project_id") == row["project_id"]
                    and record.get("input_hash") == input_hash(row)
                    and record.get("research_status") == "AI_REVIEW_ONLY"):
                return path, record
        except (OSError, ValueError, TypeError):
            continue
    return None, None


def evidence_gate(record):
    """Assess evidence coverage, NOT buyer authority or sale readiness.

    Search snippets and the model's output are never verified facts. A source
    URL must come from actual fetched pages and have a permitted identity label.
    Even an exact-ID page only creates a human-review candidate.
    """
    sources = record.get("sources")
    if not isinstance(sources, list):
        sources = []
    accepted = {}
    for item in sources:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        identity = item.get("page_identity")
        if (isinstance(url, str) and url.startswith("https://")
                and identity in (EXACT_IDENTITY, CONTEXT_ONLY)):
            if url not in accepted or identity == EXACT_IDENTITY:
                accepted[url] = identity
    exact = sum(label == EXACT_IDENTITY for label in accepted.values())
    status = ("EXACT_ID_SOURCE_REVIEW_ONLY" if exact else
              "PROJECT_CONTEXT_REVIEW_ONLY" if accepted else
              "NO_ACCEPTED_FETCHED_EVIDENCE")
    return {
        "status": status,
        "accepted_source_pages": len(accepted),
        "exact_project_id_source_pages": exact,
        "buyer_authority_verified": False,
        "supplier_availability_verified": False,
        "verified_lead": False,
        "human_review_required": True,
    }


def task_plan(row):
    """Unverified CSV fields do not become verified claims."""
    url = row.get("record_source_url", "")
    candidate = {
        "project_id": row["project_id"],
        "sources": [{"type": "official_record", "url": url, "analyzed": True}],
        "project_identity_confirmed": False,
        "buying_authority_verified": False,
        "supplier_selection_verified": False,
    }
    return allocate_work(candidate)["tasks"]


def _atomic_json(path, record):
    """Keep a durable status snapshot even across interrupted runs."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + str(os.getpid()) + ".tmp")
    try:
        temp.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _event(path, entry):
    """Append a machine-readable event; do not rewrite earlier observations."""
    with Path(path).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run(results, out=None, *, candidates=None, paid=False, max_projects=3,
        executor=None, acquire_lock=None):
    """Run one bounded cycle. All paid work goes through the legacy ledger.

    The paid run takes the shared collector OS lock to prevent concurrency
    with the normal daily pipeline. It never retries a paid failure blindly:
    existing per-day claims and output checkpoints are respected by the
    source-backed executor.
    """
    if not 1 <= int(max_projects) <= 10:
        raise ValueError("max_projects must be between 1 and 10")
    results = Path(results)
    if not results.is_dir():
        raise ValueError("Existing GTA_RADAR_RESULTS directory required")
    out = Path(out) if out else results / "AGENT_HARNESS_REVIEW"
    out.mkdir(parents=True, exist_ok=True)
    status_path = out / "AI_HARNESS_STATUS.json"
    events_path = out / "AI_HARNESS_EVENTS.jsonl"
    review = out / "PROJECT_RESEARCH"
    state = {
        "harness_version": VERSION,
        "started_utc": utc_now(),
        "mode": "PAID_EXPLICIT" if paid else "FREE_PREFLIGHT",
        "status": "STARTED",
        "production_promotion": False,
        "verified_leads_created": 0,
        "automatic_outreach": False,
        "daily_deepseek_cap_usd": DEEPSEEK_DAILY_LIMIT_USD,
        "max_paid_projects": int(max_projects),
        "steps": [],
        "projects": [],
    }
    _atomic_json(status_path, state)
    _event(events_path, {"at": state["started_utc"], "event": "RUN_STARTED",
                         "mode": state["mode"]})
    try:
        source, projects = locate_candidates(results, candidates)
        eligible, selection = select_projects(projects)
        selected = [row for row, _ in eligible[:10]]
        state["candidate_source"] = str(source)
        state["selection"] = selection
        state["steps"].append({"name": "candidate_preflight", "status": "COMPLETE",
                               "candidates": len(projects),
                               "eligible": len(eligible)})
        state["projects"] = [
            {"project_id": row["project_id"],
             "input_hash": input_hash(row),
             "planned_tasks": task_plan(row),
             "selection": "ELIGIBLE_FOR_RESEARCH_NOT_VERIFIED"}
            for row in selected
        ]
        state["steps"].append({"name": "task_planning", "status": "COMPLETE",
                               "planned_projects": len(selected),
                               "paid_model_calls": 0})
        _atomic_json(status_path, state)

        if paid and eligible:
            # Hold the SAME OS lock as the daily pipeline until research ends.
            # The executor retains all DeepSeek accounting, safe tools and
            # immutable per-input result files. Never implement a second ledger.
            lock_factory = acquire_lock or once_lock
            with lock_factory(results):
                state["executor"] = (executor or execute_project_research)(
                    source, results, review, paid=True,
                    max_projects=max_projects
                )
            state["steps"].append({
                "name": "existing_deepseek_research",
                "status": state["executor"].get("status", "UNKNOWN"),
                "attempted": state["executor"].get("attempted", 0),
                "completed": state["executor"].get("completed", 0),
                "budget_used_or_held_usd": state["executor"].get(
                    "budget_used_or_held_usd"
                ),
            })
        else:
            state["steps"].append({
                "name": "existing_deepseek_research",
                "status": "NO_PAID_CALLS_PREFLIGHT" if not paid else "NO_ELIGIBLE_CANDIDATES",
                "attempted": 0,
            })

        sourced = 0
        context = 0
        no_source = 0
        for project, row in zip(state["projects"], selected):
            checkpoint, record = load_checkpoint(review, row)
            if record is None:
                project["checkpoint"] = "PENDING_OR_BUDGET_DEFERRED"
                project["evidence_gate"] = {
                    "status": "NO_CURRENT_RESEARCH_CHECKPOINT",
                    "verified_lead": False,
                    "human_review_required": True,
                }
                continue
            gate = evidence_gate(record)
            project["checkpoint"] = "REVIEW_ONLY_SAVED"
            project["checkpoint_file"] = str(checkpoint)
            project["evidence_gate"] = gate
            if gate["exact_project_id_source_pages"]:
                sourced += 1
            elif gate["accepted_source_pages"]:
                context += 1
            else:
                no_source += 1
        state["metrics"] = {
            "planned_projects": len(selected),
            "saved_current_input_reviews": sourced + context + no_source,
            "exact_id_source_review_candidates": sourced,
            "context_only_review_candidates": context,
            "saved_reviews_without_accepted_pages": no_source,
            "verified_commercial_leads": 0,
        }
        state["steps"].append({"name": "source_evidence_gate", "status": "COMPLETE",
                               "checks": state["metrics"]})
        state["status"] = ("PREFLIGHT_READY_NO_SPEND" if not paid else
                           "REVIEW_ONLY_REQUIRES_HUMAN_VALIDATION" if sourced or context or no_source else
                           "PAID_MODE_NO_COMPLETED_REVIEWS")
    except Exception as exc:
        # Preserve the partial plan and failure reason for safe resumption.
        state["status"] = "FAILED_SAFE"
        state["failure"] = {"type": type(exc).__name__, "message": str(exc)[:250]}
        raise
    finally:
        state["finished_utc"] = utc_now()
        _atomic_json(status_path, state)
        _event(events_path, {"at": state["finished_utc"], "event": "RUN_FINISHED",
                             "status": state["status"],
                             "verified_leads_created": 0})
    return state


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", help="Existing GTA_RADAR_RESULTS directory")
    p.add_argument("--workspace", help="Existing Desktop/new data workspace (auto-detected by default)")
    p.add_argument("--out", help="Separate harness review output folder")
    p.add_argument("--candidates", help="Optional explicit existing canonical CSV")
    p.add_argument("--paid", action="store_true",
                   help="Explicitly authorize DeepSeek within configured shared daily cap")
    p.add_argument("--max-projects", type=int, default=3)
    args = p.parse_args()
    try:
        from v6_daily_pipeline import find_workspace
        results = (Path(args.results) if args.results else
                   find_workspace(args.workspace) / "GTA_RADAR_RESULTS")
        result = run(results, args.out, candidates=args.candidates,
                     paid=args.paid, max_projects=args.max_projects)
    except Exception as exc:
        print(json.dumps({"status": "FAILED_SAFE", "error": type(exc).__name__,
                          "reason": str(exc)[:250]}, indent=2))
        return 2
    print(json.dumps({
        "status": result["status"],
        "review_folder": str(Path(args.out) if args.out else
                             results / "AGENT_HARNESS_REVIEW"),
        "metrics": result.get("metrics", {}),
        "paid_attempts": result.get("executor", {}).get("attempted", 0),
        "production_promotion": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
