"""Integrate independent industrial investment and public B2B contact research.

Runs AFTER the existing municipal/council/AI pipeline, and ONLY with explicit
--paid from an operator-initiated full run. No duplicate collector, no fixed
company or project keyword, no automatic outreach. Uses the SAME daily paid
ledger, lock and source-evidence gates as standalone investigators.

A project found by generic Brampton search may advance to announcement
qualification and contact research; absent a source-backed named project, the
stage honestly reports NO_NEW_SOURCE_BACKED_PROJECT, not fake success.
Only one cited project per execution is researched to bound API use.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from gta_ai_ten_capabilities import _write_json
from gta_investment_announcement_discovery import run as discover
from gta_announcement_commercial_qualification import qualify
from gta_contact_intelligence import investigate

FOLDER = "GTA_RADAR_INVESTMENT_CONTACT_BRIDGE"
REPORT = "INVESTMENT_CONTACT_INTEGRATION_STATUS.json"
HOLD_PREFIXES = ("SEARCH_", "FETCH_", "MODEL_", "BLOCKED_")
FATAL_PREFIXES = ("MISSING_API_KEY", "HTTP_402")


def _digest(result):
    return {
        "status": str(result.get("status") or "UNKNOWN"),
        "search_calls": int(result.get("search_calls") or 0),
        "fetch_calls": int(result.get("fetch_calls") or 0),
        "model_calls": int(result.get("model_calls") or 0),
        "checkpoint_reused": bool(result.get("checkpoint_reused")),
        "report_path": str(result.get("report_path") or result.get("report") or ""),
    }


def run(results, *, paid=False, city="Brampton", today=None,
        discoverer=None, qualifier=None, investigator=None):
    root = Path(results)
    if not root.is_dir():
        raise FileNotFoundError("ESTABLISHED_RESULTS_DIRECTORY_REQUIRED")
    stamp = today or dt.date.today()
    output = root / FOLDER / REPORT
    output.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "mode": "INTEGRATED_INDEPENDENT_EARLY_INVESTMENT_RESEARCH",
        "date": stamp.isoformat(), "city": city,
        "status": "NO_SPEND_PREFLIGHT",
        "project": "NOT_SELECTED", "discovery": {},
        "qualification": {"status": "NOT_RUN"},
        "contacts": {"status": "NOT_RUN"},
        "paid_allowed": bool(paid),
        "buyer_verified": False,
        "open_supplier_contract_verified": False,
        "outreach_authorized": False,
        "source_is_first_publication_proven": False,
        "report_path": str(output),
    }
    def save():
        _write_json(output, state)
    if not paid:
        save()
        return state
    search = discoverer or discover
    assess = qualifier or qualify
    contacts = investigator or investigate
    # Discovery uses the existing V5+legacy ledger and dated idempotent
    # checkpoints. We never start a separate quota or a second collection.
    try:
        found = search(root, city=city, paid=True, today=stamp)
    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as exc:
        state["status"] = "DISCOVERY_ERROR_REVIEW"
        state["error_type"] = type(exc).__name__
        save()
        return state
    state["discovery"] = _digest(found)
    state["discovery"]["source_pages"] = len(found.get("source_pages") or [])
    candidates = found.get("discovered_projects") or []
    cited = [
        x for x in candidates if isinstance(x, dict)
        and x.get("project_name") and x.get("companies")
        and x.get("sources_used")
        and str(x.get("project_name")).strip().upper() != "UNNAMED_PROJECT"
    ]
    state["discovery"]["source_backed_candidates"] = len(cited)
    if not cited:
        state["status"] = (
            "DISCOVERY_HELD_" + str(found.get("status"))
            if str(found.get("status", "")).startswith(HOLD_PREFIXES)
            or str(found.get("status", "")).startswith(FATAL_PREFIXES)
            else "NO_NEW_SOURCE_BACKED_PROJECT_FOR_QUALIFICATION")
        save()
        return state
    # Only one project per run. No hardcoded Ace name, guessed municipal
    # match, or arbitrary lead promotion; more candidates remain visible.
    selected = cited[0]
    name = str(selected["project_name"]).strip()
    state["project"] = name
    state["source_backed_company_count"] = len(selected["companies"])
    save()
    try:
        q = assess(root, project_name=name, city=city, paid=True, day=stamp)
        state["qualification"] = _digest(q)
        state["qualification"]["accepted_claims"] = len(q.get("accepted_claims") or [])
        state["qualification"]["assessment"] = str(
            (q.get("assessment") or {}).get("classification") or "UNKNOWN")
        save()
    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as exc:
        state["qualification"] = {
            "status": "QUALIFICATION_ERROR_REVIEW",
            "error_type": type(exc).__name__}
        save()
    try:
        c = contacts(root, project_name=name, city=city, paid=True, day=stamp)
        state["contacts"] = _digest(c)
        state["contacts"]["named_people"] = len(c.get("people") or [])
        state["contacts"]["public_company_channels"] = len(
            c.get("public_channels") or [])
        save()
    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as exc:
        state["contacts"] = {
            "status": "CONTACTS_ERROR_REVIEW",
            "error_type": type(exc).__name__}
        save()
    state["status"] = "SOURCE_BACKED_PROJECT_RESEARCH_COMPLETE_REVIEW_ONLY"
    if (state["qualification"]["status"].startswith(
            ("QUALIFICATION_ERROR", "MODEL_", "SEARCH_", "FETCH_")) or
            state["contacts"]["status"].startswith(
                ("CONTACTS_ERROR", "MODEL_", "BLOCKED_", "SEARCH_", "FETCH_"))):
        state["status"] = "PARTIAL_SOURCE_OR_BUDGET_REVIEW_REQUIRED"
    # Public companies, names and channels never by themselves prove buyer
    # purchasing authority, an unawarded contract or permission to outreach.
    save()
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    parser.add_argument("--city", choices=("Brampton", "Mississauga", "Toronto"),
                        default="Brampton")
    parser.add_argument("--paid", action="store_true")
    args = parser.parse_args()
    result = run(args.results, paid=args.paid, city=args.city)
    print(json.dumps({
        "status": result["status"],
        "project": result["project"],
        "discovery": result["discovery"],
        "qualification": result["qualification"],
        "contacts": result["contacts"],
        "no_automatic_outreach": True,
        "report": result["report_path"],
    }, indent=2))
    return 0 if result["status"] != "DISCOVERY_ERROR_REVIEW" else 2


if __name__ == "__main__":
    raise SystemExit(main())
