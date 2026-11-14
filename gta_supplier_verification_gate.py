"""Auditable human-review gate for company roles and public supplier tenders.

Reads PR #209's project/role graph plus an OPTIONAL operator-authored review
manifest in the workspace. Never fetches sources, contacts buyers, changes
SQLite/history, calls AI or claims independent live verification. Reviewer
attestations are NOT independently authenticated source evidence.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

GRAPH = "GTA_RADAR_PROJECT_COMPANY_EVIDENCE_GRAPH.json"
INPUT = "GTA_RADAR_REVIEW_DECISIONS_V1.json"
REPORT = "GTA_RADAR_COMPANY_PROCUREMENT_REVIEW_STATUS.json"
ROLE_QUEUE = "GTA_RADAR_COMPANY_ROLE_REVIEW_QUEUE.csv"
TENDER_QUEUE = "GTA_RADAR_SUPPLIER_PACKAGE_REVIEW.csv"
MAX_INPUT_BYTES = 2_000_000
MAX_GRAPH_BYTES = 12_000_000
MAX_REVIEWS = 150
MAX_QUEUE = 75
ALLOWED_SECTORS = {
    "HVAC", "INDUSTRIAL_EQUIPMENT", "ELECTRICAL", "SECURITY",
    "INSURANCE", "FACILITY_SERVICES", "OTHER",
}
ROLE_FIELDS = (
    "edge_id", "project_node_id", "role", "organization_name",
    "decision", "reviewer_id", "reviewed_at_utc", "evidence_url",
    "evidence_quote", "evidence_locator", "source_document_sha256",
)
TENDER_FIELDS = (
    "project_node_id", "tender_id", "decision", "sector", "work_scope",
    "reviewer_id", "reviewed_at_utc", "tender_url", "evidence_quote",
    "source_document_sha256",
)
ROLE_QUEUE_FIELDS = (
    "edge_id", "project_node_id", "project_id", "city",
    "organization_name", "role_claimed", "source_url", "review_status",
    "verification_action",
)
TENDER_QUEUE_FIELDS = (
    "project_node_id", "project_id", "city", "supplier_sector",
    "tender_id", "work_scope", "tender_url", "closing_date",
    "buyer_role_edge_id", "review_status", "verification_action",
)
REVIEWED_ROLES = {"APPLICANT", "BUILDER", "PROPERTY_OWNER", "TENANT",
                  "OPERATOR", "DEVELOPER", "CONTRACTOR",
                  "MUNICIPAL_PLANNING_REVIEWER"}
POTENTIAL_BUYER_ROLES = {"BUILDER", "PROPERTY_OWNER", "OPERATOR",
                         "DEVELOPER", "CONTRACTOR", "TENANT"}


def _text(value, max_length=500):
    return " ".join(str(value or "").split())[:max_length]


def _https(url):
    value = _text(url, 1200)
    try:
        p = urlsplit(value)
        if (p.scheme != "https" or not p.hostname or p.username or p.password
                or p.fragment or p.port not in (None, 443)
                or p.hostname.lower() in ("localhost", "127.0.0.1", "::1")):
            return ""
        return value
    except ValueError:
        return ""


def _sha(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[a-fA-F0-9]{64}", value))


def _review_time(value, now):
    if not isinstance(value, str):
        raise ValueError("MISSING_REVIEW_TIMESTAMP")
    instant = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if instant.tzinfo is None:
        raise ValueError("REVIEW_TIMESTAMP_MUST_INCLUDE_UTC_OFFSET")
    stamp = instant.astimezone(dt.timezone.utc)
    if stamp > now + dt.timedelta(minutes=5):
        raise ValueError("REVIEW_TIMESTAMP_IN_FUTURE")
    if stamp < now - dt.timedelta(days=30):
        raise ValueError("REVIEW_TOO_OLD_RECHECK_SOURCE")
    return stamp


def _load(path, limit):
    if not path.is_file():
        return None
    if path.is_symlink() or path.stat().st_size > limit:
        raise ValueError("UNSAFE_OR_OVERSIZED_INPUT:" + path.name)
    content = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(content, dict):
        raise ValueError("INPUT_ROOT_MUST_BE_JSON_OBJECT")
    return content


def _safe_csv(path, rows, fields):
    """Sanitize all untrusted cells against spreadsheet formula injection."""
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            sanitized = {}
            for field in fields:
                value = str(row.get(field, "") or "")
                if value.lstrip().startswith(("=", "+", "-", "@")):
                    value = "'" + value
                sanitized[field] = value
            writer.writerow(sanitized)


def _role_review(row, edge, now):
    """Validate human attestation bound to one specific existing graph edge."""
    if not isinstance(row, dict):
        raise ValueError("INVALID_ROLE_REVIEW_ROW")
    if row.get("decision") not in ("CONFIRM_ROLE", "REJECT_ROLE"):
        raise ValueError("INVALID_ROLE_DECISION")
    if (row.get("edge_id") != edge.get("edge_id") or
            row.get("project_node_id") != edge.get("from_node") or
            row.get("role") != edge.get("role_claimed") or
            row.get("organization_name") != edge.get("_organization_name")):
        raise ValueError("ROLE_ASSERTION_DOES_NOT_MATCH_CURRENT_GRAPH")
    if edge.get("relationship") != "PROJECT_ROLE_SOURCE_CLAIM":
        raise ValueError("ROLE_NOT_PROJECT_BOUND")
    if edge.get("role_claimed") not in REVIEWED_ROLES:
        raise ValueError("ROLE_NOT_SUPPORTED")
    if not 2 <= len(_text(row.get("reviewer_id"), 80)) <= 80:
        raise ValueError("REVIEWER_ID_REQUIRED")
    _review_time(row.get("reviewed_at_utc"), now)
    if (not _https(row.get("evidence_url")) or
            len(_text(row.get("evidence_quote"))) < 30 or
            not _text(row.get("evidence_locator"), 100) or
            not _sha(row.get("source_document_sha256"))):
        raise ValueError("MISSING_EXACT_ROLE_SOURCE_EVIDENCE")
    if (row["organization_name"].casefold() not in
            _text(row["evidence_quote"]).casefold()):
        raise ValueError("ROLE_NAME_NOT_IN_SOURCE_QUOTE")
    # The reviewer declares a checked document + locator; neither the source
    # URL nor quote is independently fetched and authenticated by Radar.
    return {
        "edge_id": edge["edge_id"],
        "project_node_id": edge["from_node"],
        "organization_name": row["organization_name"],
        "role": row["role"],
        "decision": row["decision"],
        "evidence_url": _https(row["evidence_url"]),
        "evidence_locator": _text(row["evidence_locator"], 100),
        "source_document_sha256": row["source_document_sha256"].lower(),
        "reviewed_at_utc": row["reviewed_at_utc"],
        "evidence_level": "REVIEWER_ATTESTED_SOURCE_NOT_INDEPENDENTLY_RECHECKED",
        "legal_identity_verified": False,
        "buyer_verified": False,
    }


def _tender_review(row, project_ids, confirmed_roles, now, today):
    if not isinstance(row, dict):
        raise ValueError("INVALID_TENDER_REVIEW_ROW")
    if not all(k in row for k in TENDER_FIELDS):
        raise ValueError("TENDER_REVIEW_SCHEMA_MISMATCH")
    if row["project_node_id"] not in project_ids:
        raise ValueError("TENDER_PROJECT_NOT_IN_GRAPH")
    if row["decision"] not in ("OPEN_PUBLIC_TENDER", "AWARDED", "CLOSED"):
        raise ValueError("INVALID_TENDER_STATUS")
    if row["sector"] not in ALLOWED_SECTORS:
        raise ValueError("UNRECOGNIZED_SUPPLIER_SECTOR")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _./-]{2,100}", str(row["tender_id"])):
        raise ValueError("INVALID_EXACT_TENDER_ID")
    if not 2 <= len(_text(row["reviewer_id"], 80)) <= 80:
        raise ValueError("TENDER_REVIEWER_REQUIRED")
    _review_time(row["reviewed_at_utc"], now)
    if (not _https(row["tender_url"]) or not _sha(row["source_document_sha256"])
            or len(_text(row["evidence_quote"])) < 30
            or len(_text(row["work_scope"], 200)) < 12):
        raise ValueError("INCOMPLETE_PROJECT_SPECIFIC_TENDER_EVIDENCE")
    scope = _text(row["work_scope"], 200)
    close = row.get("closing_date")
    status = "REVIEWED_TENDER_CLOSED_OR_AWARDED"
    buyer_edge = str(row.get("buyer_role_edge_id") or "")
    if row["decision"] == "OPEN_PUBLIC_TENDER":
        try:
            date = dt.date.fromisoformat(close)
        except (ValueError, TypeError):
            raise ValueError("OPEN_TENDER_CLOSING_DATE_REQUIRED") from None
        if date < today:
            status = "CLOSING_DATE_PASSED_HOLD"
        elif date > today + dt.timedelta(days=365):
            status = "IMPLAUSIBLE_CLOSING_DATE_HOLD"
        elif buyer_edge not in confirmed_roles or (
                confirmed_roles[buyer_edge]["project_node_id"] != row["project_node_id"]
                or confirmed_roles[buyer_edge]["role"] not in POTENTIAL_BUYER_ROLES):
            status = "PURCHASING_AUTHORITY_NOT_REVIEWED_HOLD"
        elif not _text(row.get("authority_evidence_quote"), 600) or not _https(
                row.get("authority_evidence_url")):
            status = "PURCHASING_AUTHORITY_SOURCE_MISSING_HOLD"
        else:
            # A human's attestation of an open tender is not a live availability
            # confirmation. Recheck before any outreach or client publication.
            status = "REVIEWER_ATTESTED_OPEN_TENDER_LIVE_RECHECK_REQUIRED"
    return {
        "project_node_id": row["project_node_id"],
        "tender_id": row["tender_id"], "sector": row["sector"],
        "work_scope": scope, "tender_url": _https(row["tender_url"]),
        "closing_date": close or "", "buyer_role_edge_id": buyer_edge,
        "decision": row["decision"], "review_status": status,
        "source_document_sha256": row["source_document_sha256"].lower(),
        "reviewed_at_utc": row["reviewed_at_utc"],
        "buyer_verified": False, "procurement_live_verified": False,
        "outreach_authorized": False,
    }


def build(results, workspace=None, *, now=None):
    root = Path(results)
    folder = Path(workspace) if workspace is not None else root.parent
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError("AWARE_CLOCK_REQUIRED")
    now = now.astimezone(dt.timezone.utc)
    today = now.date()
    graph = _load(root / GRAPH, MAX_GRAPH_BYTES)
    if graph is None:
        return {"status": "SOURCE_GRAPH_MISSING_HOLD",
                "role_queue": [], "tender_queue": [],
                "accepted_roles": [], "tender_reviews": [],
                "verified_buyers": 0, "verified_open_supplier_contracts": 0}
    if graph.get("status") != "PROJECT_COMPANY_MENTION_GRAPH_REVIEW_ONLY":
        raise ValueError("UNKNOWN_SOURCE_GRAPH_STATUS")
    for key in ("project_nodes", "organization_nodes", "edges"):
        if not isinstance(graph.get(key), list):
            raise ValueError("SOURCE_GRAPH_SCHEMA_MISMATCH")
    projects = {p["node_id"]: p for p in graph["project_nodes"]}
    orgs = {o["node_id"]: o for o in graph["organization_nodes"]}
    edges = {}
    role_queue = []
    for edge in graph["edges"]:
        if edge.get("relationship") != "PROJECT_ROLE_SOURCE_CLAIM":
            continue
        if edge.get("from_node") not in projects or edge.get("to_node") not in orgs:
            raise ValueError("GRAPH_EDGE_REFERENTIAL_INTEGRITY")
        name = orgs[edge["to_node"]].get("organization_name_as_stated", "")
        enriched = {**edge, "_organization_name": name}
        if edge["edge_id"] in edges:
            raise ValueError("GRAPH_DUPLICATE_EDGE_ID")
        edges[edge["edge_id"]] = enriched
        if len(role_queue) < MAX_QUEUE:
            p = projects[edge["from_node"]]
            role_queue.append({
                "edge_id": edge["edge_id"], "project_node_id": p["node_id"],
                "project_id": p["project_id"], "city": p["city"],
                "organization_name": name, "role_claimed": edge.get("role_claimed", ""),
                "source_url": edge.get("source_url", ""),
                "review_status": "ORIGINAL_PROJECT_ROLE_EVIDENCE_REQUIRED",
                "verification_action": "Inspect exact primary source; save quote, page or record ID, reviewer, date and document hash",
            })
    reviews = _load(folder / INPUT, MAX_INPUT_BYTES)
    status = "NO_OPERATOR_VERIFICATION_MANIFEST_REVIEW_QUEUE_ONLY"
    if reviews is None:
        reviews = {"version": 1, "role_reviews": [], "procurement_reviews": []}
    else:
        status = "OPERATOR_REVIEW_MANIFEST_PROCESSED_NOT_INDEPENDENTLY_AUTHENTICATED"
    if (reviews.get("version") != 1 or
            not isinstance(reviews.get("role_reviews"), list) or
            not isinstance(reviews.get("procurement_reviews"), list) or
            len(reviews["role_reviews"]) + len(reviews["procurement_reviews"]) > MAX_REVIEWS):
        raise ValueError("REVIEW_MANIFEST_SCHEMA_OR_SIZE")
    holds, accepted, seen_edge = [], {}, set()
    for row in reviews["role_reviews"]:
        edge_id = row.get("edge_id") if isinstance(row, dict) else None
        if not edge_id or edge_id in seen_edge:
            holds.append({"kind": "ROLE", "edge_id": edge_id,
                          "reason": "DUPLICATE_OR_MISSING_ROLE_EDGE_ID"})
            continue
        seen_edge.add(edge_id)
        if edge_id not in edges:
            holds.append({"kind": "ROLE", "edge_id": edge_id,
                          "reason": "ROLE_EDGE_NOT_IN_CURRENT_GRAPH"})
            continue
        try:
            record = _role_review(row, edges[edge_id], now)
            if record["decision"] == "CONFIRM_ROLE":
                accepted[edge_id] = record
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            holds.append({"kind": "ROLE", "edge_id": edge_id,
                          "reason": str(exc)[:120]})
    tender_rows, seen_tender = [], set()
    for row in reviews["procurement_reviews"]:
        key = ((row.get("project_node_id"), row.get("tender_id"))
               if isinstance(row, dict) else (None, None))
        if key in seen_tender:
            # Two contradictory decisions about a tender block its promotion.
            tender_rows = [t for t in tender_rows if
                           (t["project_node_id"], t["tender_id"]) != key]
            holds.append({"kind": "TENDER", "tender_id": str(key[1])[:100],
                          "reason": "CONFLICTING_OR_DUPLICATE_TENDER_DECISIONS"})
            continue
        seen_tender.add(key)
        try:
            tender_rows.append(_tender_review(row, projects, accepted, now, today))
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            holds.append({"kind": "TENDER", "tender_id": str(key[1])[:100],
                          "reason": str(exc)[:120]})
    tender_queue = []
    for tender in tender_rows[:MAX_QUEUE]:
        p = projects[tender["project_node_id"]]
        tender_queue.append({
            "project_node_id": p["node_id"], "project_id": p["project_id"],
            "city": p["city"], "supplier_sector": tender["sector"],
            "tender_id": tender["tender_id"], "work_scope": tender["work_scope"],
            "tender_url": tender["tender_url"], "closing_date": tender["closing_date"],
            "buyer_role_edge_id": tender["buyer_role_edge_id"],
            "review_status": tender["review_status"],
            "verification_action": "Reopen exact public tender and independently reconfirm buyer, availability, award status and closing date",
        })
    return {
        "status": status,
        "generated_utc": now.isoformat(),
        "source_graph_project_candidates": len(projects),
        "source_graph_role_claims": len(edges),
        "operator_role_decisions": len(reviews["role_reviews"]),
        "operator_tender_decisions": len(reviews["procurement_reviews"]),
        "reviewer_attested_role_claims": len(accepted),
        "reviewer_attested_open_tender_needing_live_recheck": sum(
            t["review_status"] == "REVIEWER_ATTESTED_OPEN_TENDER_LIVE_RECHECK_REQUIRED"
            for t in tender_rows),
        "held_or_conflicting_decisions": len(holds),
        "role_queue": role_queue,
        "tender_queue": tender_queue,
        "accepted_roles": list(accepted.values()),
        "tender_reviews": tender_rows,
        "holds": holds,
        "verified_legal_company_identities": 0,
        "verified_buyers": 0,
        "verified_open_supplier_contracts": 0,
        "outreach_authorized": False,
        "paid_ai_usd": 0,
        "warning": ("Reviewer-supplied URLs, quotes and hashes are attestations; "
                    "Radar has not independently fetched and authenticated them. "
                    "OPEN is not live verified. No outreach is authorized."),
    }


def run(results, workspace=None):
    root = Path(results)
    result = build(root, workspace)
    for name, rows, fields in (
            (ROLE_QUEUE, result["role_queue"], ROLE_QUEUE_FIELDS),
            (TENDER_QUEUE, result["tender_queue"], TENDER_QUEUE_FIELDS)):
        path = root / name
        temporary = path.with_suffix(".csv.tmp")
        _safe_csv(temporary, rows, fields)
        temporary.replace(path)
    report_path = root / REPORT
    temporary = report_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({
        key: value for key, value in result.items()
        if key not in ("role_queue", "tender_queue")
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(report_path)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    parser.add_argument("--workspace",
                        help="Root Radar workspace holding operator review manifest")
    args = parser.parse_args()
    out = run(args.results, args.workspace)
    print(json.dumps({
        k: v for k,v in out.items()
        if k not in ("role_queue", "tender_queue", "accepted_roles",
                     "tender_reviews", "holds")
    }, indent=2))
