"""Integrate independent industrial investment and public B2B contact research.

Runs AFTER the existing municipal/council/AI pipeline, and ONLY with explicit
--paid from an operator-initiated full run. No duplicate collector, no fixed
company or project keyword, no automatic outreach. Uses the SAME daily paid
ledger, lock and source-evidence gates as standalone investigators.

A project found by generic Brampton search may advance to announcement
qualification and contact research; absent a source-backed named project, the
stage honestly reports NO_NEW_SOURCE_BACKED_PROJECT, not fake success.
Up to three cited projects may be researched; the shared budget still hard-stops spending.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path

from gta_ai_ten_capabilities import _write_json
from gta_investment_announcement_discovery import run as discover
from gta_announcement_commercial_qualification import qualify
from gta_contact_intelligence import investigate

FOLDER = "GTA_RADAR_INVESTMENT_CONTACT_BRIDGE"
REPORT = "INVESTMENT_CONTACT_INTEGRATION_STATUS.json"
OPPORTUNITIES = "GTA_RADAR_EQUIPMENT_INVESTMENT_OPPORTUNITIES.csv"
MAX_PAID_PROJECTS = 3
COLUMNS = ("project_name", "city", "company_source_claim", "project_address_source_claim",
           "equipment_or_investment_scope_quote", "source_urls", "published_date_verified",
           "public_professional_name", "public_professional_title",
           "public_professional_email", "public_professional_source_url",
           "professional_project_relationship", "public_company_channel",
           "public_company_channel_source_url", "named_purchasing_person",
           "purchasing_email", "buyer_verified", "open_package_verified",
           "research_status")
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
        "equipment_opportunities_csv": str(output.parent / OPPORTUNITIES),
        "candidates": [],
        "research_completed_count": 0,
    }
    def save():
        _write_json(output, state)
    if not paid:
        save()
        return state
    # A fresh paid discovery attempt must not silently reuse yesterday's
    # equipment CSV as today's results when source research is blocked.
    # Historical snapshots remain preserved by the existing ZIP archive.
    with (output.parent / OPPORTUNITIES).open(
            "w", encoding="utf-8-sig", newline="") as stream:
        csv.DictWriter(stream, fieldnames=COLUMNS).writeheader()
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
    # Export the entire source-backed discovery set independently of optional
    # qualification spend. No unquoted scope, invented physical address,
    # publication date, buyer name or procurement status is allowed.
    exported = []
    for candidate in cited[:10]:
        companies = candidate.get("companies") or []
        quotes = [str(claim.get("quote") or "").strip() for claim in
                  candidate.get("claims") or [] if isinstance(claim, dict)
                  and claim.get("kind") in ("scope", "project", "construction")]
        exported.append({
            "project_name": str(candidate["project_name"])[:150],
            "city": city,
            "company_source_claim": " | ".join(str(x.get("subject") or "")
                    for x in companies if isinstance(x, dict))[:350],
            "project_address_source_claim": str(candidate.get("location_text") or "")[:200],
            "equipment_or_investment_scope_quote": " | ".join(quotes)[:800],
            "source_urls": " | ".join(str(u) for u in candidate["sources_used"])[:1200],
            "published_date_verified": "False",
            "named_purchasing_person": "", "purchasing_email": "",
            "buyer_verified": "False", "open_package_verified": "False",
            "research_status": "SOURCE_BACKED_RESEARCH_ONLY_NOT_OPEN_RFQ",
        })
    with (output.parent / OPPORTUNITIES).open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=COLUMNS)
        writer.writeheader()
        for entry in exported:
            writer.writerow({k: ("'" + str(v) if str(v).lstrip().startswith(
                ("=", "+", "-", "@", "\\t", "\\r")) else v)
                for k,v in entry.items()})
    state["discovery"]["exported_source_backed_opportunities"] = len(exported)
    # Preserve backwards-compatible first project/status fields. Research
    # additional projects only through existing shared, idempotent ledger.
    state["project"] = str(cited[0]["project_name"]).strip()
    state["source_backed_company_count"] = len(cited[0]["companies"])
    had_error = False
    for idx, selected in enumerate(cited[:MAX_PAID_PROJECTS]):
        name = str(selected["project_name"]).strip()
        record = {"project": name, "qualification": {"status": "NOT_RUN"},
                  "contacts": {"status": "NOT_RUN"},
                  "buyer_verified": False, "open_supplier_contract_verified": False}
        try:
            q = assess(root, project_name=name, city=city, paid=True, day=stamp)
            record["qualification"] = _digest(q)
            record["qualification"]["accepted_claims"] = len(q.get("accepted_claims") or [])
            record["qualification"]["assessment"] = str(
                (q.get("assessment") or {}).get("classification") or "UNKNOWN")
        except (ValueError, OSError, RuntimeError, KeyError, TypeError) as exc:
            record["qualification"] = {"status": "QUALIFICATION_ERROR_REVIEW",
                                       "error_type": type(exc).__name__}
        try:
            response = contacts(root, project_name=name, city=city, paid=True, day=stamp)
            record["contacts"] = _digest(response)
            record["contacts"]["named_people"] = len(response.get("people") or [])
            record["contacts"]["public_company_channels"] = len(
                response.get("public_channels") or [])
            # These are source-quoted professional contacts. An engineer,
            # executive or general inbox is NOT the project's purchaser.
            people = [p for p in response.get("people") or []
                      if isinstance(p, dict) and p.get("person")
                      and p["person"] != "NOT_NAMED"]
            if people:
                p = people[0]
                exported[idx]["public_professional_name"] = p.get("person", "")
                exported[idx]["public_professional_title"] = p.get("job_title", "")
                exported[idx]["public_professional_email"] = (
                    "" if p.get("email") == "NOT_PUBLICLY_VERIFIED" else
                    p.get("email", ""))
                exported[idx]["public_professional_source_url"] = p.get("source_url", "")
                exported[idx]["professional_project_relationship"] = p.get(
                    "project_relationship", "")
            channels = [p for p in response.get("public_channels") or []
                        if isinstance(p, dict) and p.get("source_url")]
            if channels:
                exported[idx]["public_company_channel"] = channels[0].get("value", "")
                exported[idx]["public_company_channel_source_url"] = channels[0][
                    "source_url"]
        except (ValueError, OSError, RuntimeError, KeyError, TypeError) as exc:
            record["contacts"] = {"status": "CONTACTS_ERROR_REVIEW",
                                  "error_type": type(exc).__name__}
        if idx == 0:
            state["qualification"] = record["qualification"]
            state["contacts"] = record["contacts"]
        state["candidates"].append(record)
        state["research_completed_count"] += 1
        if record["qualification"]["status"].startswith((
                "QUALIFICATION_ERROR", "MODEL_", "SEARCH_", "FETCH_",
                "LEDGER_")) or record["contacts"]["status"].startswith((
                "CONTACTS_ERROR", "MODEL_", "BLOCKED_", "SEARCH_",
                "FETCH_", "LEDGER_")):
            had_error = True
        save()
    # Refresh research CSV with cited PUBLIC contacts after model review.
    # Purchasing fields and buyer flags deliberately remain unverified.
    with (output.parent / OPPORTUNITIES).open(
            "w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=COLUMNS)
        writer.writeheader()
        for entry in exported:
            writer.writerow({k: ("'" + str(v) if str(v).lstrip().startswith(
                ("=", "+", "-", "@", "\\t", "\\r")) else str(v))
                for k,v in entry.items()})
    state["status"] = ("PARTIAL_SOURCE_OR_BUDGET_REVIEW_REQUIRED" if had_error
                       else "SOURCE_BACKED_PROJECT_RESEARCH_COMPLETE_REVIEW_ONLY")
    # Public companies, names and channels never by themselves prove buyer
    # purchasing authority, an unawarded contract or permission to outreach.
    save()
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    parser.add_argument("--city", choices=("Brampton", "Mississauga", "Toronto"),
                        default=None)
    parser.add_argument("--paid", action="store_true")
    args = parser.parse_args()
    # Rotate generic discovery geography without hardcoding a company.
    # Prior project checkpoints and the shared daily ledger remain intact.
    today = dt.date.today()
    city = args.city or ("Brampton", "Toronto", "Mississauga")[today.toordinal() % 3]
    result = run(args.results, paid=args.paid, city=city, today=today)
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
