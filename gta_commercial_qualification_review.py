"""Evidence-led commercial research worklist across existing Radar outputs.

This is a bounded, zero-cost internal research queue, NOT a client-ready verified
lead list. Source dates are kept distinct from observed dates and from publication
dates. AI source claims are joined only on exact project IDs, never addresses.
No network, model, DB changes, contacts harvesting, or automatic outreach.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

CLIENT = "GTA_RADAR_CLIENT_FRESH_NONREPEAT_TOP_10.csv"
PRIVATE = "GTA_RADAR_PRIVATE_DEVELOPMENT_REVIEW.csv"
PENDING = "GTA_RADAR_V8_PENDING_QUEUE.csv"
GRAPH = "GTA_RADAR_PROJECT_COMPANY_EVIDENCE_GRAPH.json"
BRIDGE = "GTA_RADAR_AI_PROJECT_EVIDENCE_BRIDGE.json"
PREVIOUS = "GTA_RADAR_CLIENT_PREVIOUSLY_REPORTED.csv"
ALL_OUT = "GTA_RADAR_COMMERCIAL_QUALIFICATION_RESEARCH.csv"
TOP_OUT = "GTA_RADAR_COMMERCIAL_TOP10_ANALYST_REVIEW.csv"
REPORT = "GTA_RADAR_COMMERCIAL_QUALIFICATION_STATUS.json"

MAX_BYTES = 24_000_000
MAX_RECORDS = 5000
INDUSTRIAL = re.compile(
    r"\b(industrial|manufactur\w*|warehouse|logistics|distribution|"
    r"factory|plant expansion|processing plant|cleanroom|laborator\w*|"
    r"data cent(?:er|re)|cold storage|refrigerat\w*|production line|"
    r"self[- ]storage|equipment)\b", re.I)
COMMERCIAL = re.compile(
    r"\b(commercial|retail|hotel|restaurant|office|shopping|grocery|"
    r"medical clinic|business park|fitness cent(?:er|re)|banquet)\b", re.I)
RESIDENTIAL = re.compile(
    r"\b(residential|condominium|apartment|dwelling|housing|rental units)\b", re.I)
TRADE = re.compile(
    r"\b(hvac|mechanical|electrical|chiller|cooling|fire alarm|"
    r"sprinkler|security|generator|loading dock|cleanroom|refrigeration)\b", re.I)
EXACT_URL = re.compile(r"(?:\bwhere=|/posts/current-development-projects/|/active-development-applications/[^/]+/)", re.I)
PLACEHOLDER = {"", "unknown", "n/a", "none", "not verified", "tbd"}


def _read_csv(root, filename):
    path = root / filename
    if not path.is_file():
        return []
    if path.is_symlink() or path.stat().st_size > MAX_BYTES:
        raise ValueError("UNSAFE_OR_OVERSIZED_SOURCE:" + filename)
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            return []
        rows = []
        for row in reader:
            if len(rows) >= MAX_RECORDS:
                raise ValueError("INPUT_TOO_MANY_ROWS:" + filename)
            rows.append(row)
    return rows


def _read_json(root, filename):
    path = root / filename
    if not path.is_file():
        return {}
    if path.is_symlink() or path.stat().st_size > MAX_BYTES:
        raise ValueError("UNSAFE_OR_OVERSIZED_SOURCE:" + filename)
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("BAD_SOURCE_FORMAT:" + filename)
    return data


def _clean(value, limit=200):
    return " ".join(str(value or "").split())[:limit]


def _url(value):
    for raw in str(value or "").split("|"):
        url = raw.strip()
        try:
            p = urlsplit(url)
            if (p.scheme == "https" and p.hostname and
                    not p.username and not p.password and len(url) < 1600):
                return url
        except ValueError:
            pass
    return ""


def _date(value, now):
    try:
        d = dt.date.fromisoformat(str(value or "")[:10])
        return d if d <= now else None
    except ValueError:
        return None


def _sector(description):
    text = description or ""
    if INDUSTRIAL.search(text):
        return "INDUSTRIAL_EQUIPMENT_WAREHOUSE"
    if COMMERCIAL.search(text):
        return "COMMERCIAL_BUILDING_SERVICES"
    if RESIDENTIAL.search(text):
        return "RESIDENTIAL_DOMINANT"
    return "SCOPE_UNKNOWN"


def _stage(status):
    s = str(status or "").casefold()
    if any(x in s for x in ("completed", "final approval", "noac issued", "issued",
                             "occupancy", "closed", "withdrawn")):
        return "POST_APPROVAL_OR_COMPLETED_RECHECK"
    if any(x in s for x in ("under review", "planning", "applied", "pending",
                             "received", "pre-consultation", "pre-application")):
        return "PLANNING_OR_PRE_AWARD_REVIEW_ONLY"
    return "STAGE_UNKNOWN"


def _normalize(source, row, today):
    if source == "CLIENT":
        project_id = _clean(row.get("opportunity_id"), 180)
        description = _clean(row.get("nature_of_work"), 2500)
        application_id = _clean(row.get("application_ids"), 180)
        source_date = _date(row.get("source_event_date"), today)
        date_basis = _clean(row.get("source_event_date_basis"))
        status = row.get("stage_gate")
        url = _url(row.get("source_url"))
        name = _clean(row.get("named_company_role_unverified"))
        previous = False
        first_seen = ""
    elif source == "PRIVATE":
        project_id = _clean(row.get("opportunity_id"), 180)
        description = _clean(row.get("nature_of_work"), 2500)
        application_id = _clean(row.get("application_ids"), 180)
        source_date = _date(row.get("source_date"), today)
        date_basis = _clean(row.get("date_basis"))
        status = row.get("project_stage")
        url = _url(row.get("source_urls"))
        name = _clean(row.get("company_name"))
        previous = row.get("observation") == "PREVIOUSLY_REPORTED"
        first_seen = _clean(row.get("first_seen_local"))
    else:
        project_id = _clean(row.get("project_id"), 180)
        description = _clean(row.get("description"), 2500)
        application_id = _clean(row.get("source_keys"), 180)
        source_date = _date(row.get("source_record_date"), today)
        date_basis = _clean(row.get("source_record_date_basis"))
        status = row.get("current_source_status")
        url = _url(row.get("record_source_url"))
        name = _clean(row.get("company_name"))
        previous = False
        first_seen = _clean(row.get("_queued_on"))

    if not project_id or not url or not _clean(row.get("city")) or not _clean(row.get("address")):
        return None
    if source_date and (today-source_date).days <= 7:
        freshness = "SOURCE_EVENT_0_7_DAYS_NOT_PUBLICATION"
        freshness_score = 35
    elif source_date and (today-source_date).days <= 30:
        freshness = "SOURCE_EVENT_8_30_DAYS_NOT_PUBLICATION"
        freshness_score = 23
    elif source_date and (today-source_date).days <= 90:
        freshness = "SOURCE_EVENT_31_90_DAYS_NOT_PUBLICATION"
        freshness_score = 9
    elif source_date:
        freshness = "OLDER_SOURCE_RECORD_NOT_NEW_EVENT"
        freshness_score = 0
    else:
        freshness = "SOURCE_DATE_UNKNOWN_NOT_FIRST_SEEN"
        freshness_score = 2
    # A first-seen/changed timestamp is NEVER promoted into a first
    # publication date or used to place an older project in a fresh bucket.
    sector = _sector(description)
    stage = _stage(status)
    specific = bool(EXACT_URL.search(url) or (
        source == "PRIVATE" and urlsplit(url).path.strip("/").count("/") >= 2))
    return {
        "record_id": project_id,
        "origin": source,
        "city": _clean(row.get("city"), 100),
        "address": _clean(row.get("address"), 220),
        "application_id": application_id,
        "project_description": description,
        "source_url": url,
        "source_specificity": "PROJECT_SPECIFIC_URL_REVIEW" if specific else "GENERIC_SOURCE_PORTAL",
        "source_date": source_date.isoformat() if source_date else "",
        "date_basis": date_basis or "NO_CONFIRMED_SOURCE_EVENT_DATE",
        "radar_first_seen_local": first_seen,
        "freshness_band": freshness,
        "freshness_points": freshness_score,
        "sector": sector,
        "source_stage": _clean(status),
        "lifecycle_review": stage,
        "named_company_unverified": (name if name.casefold() not in PLACEHOLDER else ""),
        "was_previously_reported": previous,
        "exact_project_roles": [],
        "ai_conflicts": [],
        "role_evidence_level": "NO_EXACT_SOURCE_SUPPORTED_COMPANY_ROLE",
        "buyer_verified": False,
        "public_contact_verified": False,
        "open_supplier_package_verified": False,
        "procurement_status": "UNKNOWN_NOT_EVIDENCED",
        "contact_email": "",
        "contact_phone": "",
        "outreach_authorized": False,
    }


def _graph_roles(graph):
    if graph.get("status") != "PROJECT_COMPANY_MENTION_GRAPH_REVIEW_ONLY":
        return {}
    projects = {p.get("node_id"): p for p in graph.get("project_nodes", [])
                if isinstance(p, dict)}
    orgs = {o.get("node_id"): o for o in graph.get("organization_nodes", [])
            if isinstance(o, dict)}
    found = {}
    for edge in graph.get("edges", []):
        if (not isinstance(edge, dict) or
                edge.get("relationship") != "PROJECT_ROLE_SOURCE_CLAIM" or
                edge.get("evidence_origin") != "AI_RESEARCH_EXACT_ID_SOURCE_LITERAL_REVIEW_ONLY"):
            continue
        p = projects.get(edge.get("from_node"))
        org = orgs.get(edge.get("to_node"))
        if not p or not org:
            continue
        pid = p.get("project_id")
        found.setdefault((p.get("city", "").casefold(), pid), []).append({
            "organization": _clean(org.get("organization_name_as_stated")),
            "role": _clean(edge.get("role_claimed")),
            "source_url": _url(edge.get("source_url")),
            "verification": "SOURCE_LITERALLY_SUPPORTS_ROLE_HUMAN_RECHECK_REQUIRED",
            "buyer_verified": False,
        })
    return found


def _add_review_context(row, roles, bridge):
    key = (row["city"].casefold(), row["record_id"])
    row["exact_project_roles"] = roles.get(key, [])
    if row["exact_project_roles"]:
        row["role_evidence_level"] = "SOURCE_LINKED_PROJECT_ROLE_NOT_BUYER"
    item = bridge.get(row["record_id"])
    if item and str(item.get("city") or "").casefold() == row["city"].casefold():
        row["ai_conflicts"] = [str(x.get("reason") or "") for x in item.get("holds", [])
                               if isinstance(x, dict)]
        row["official_lifecycle_from_ai_review"] = _clean(item.get("official_status"))
    return row


def _score(row):
    sector = {
        "INDUSTRIAL_EQUIPMENT_WAREHOUSE": 28,
        "COMMERCIAL_BUILDING_SERVICES": 15,
        "RESIDENTIAL_DOMINANT": -20,
        "SCOPE_UNKNOWN": 0,
    }[row["sector"]]
    stage = {
        "PLANNING_OR_PRE_AWARD_REVIEW_ONLY": 12,
        "STAGE_UNKNOWN": 0,
        "POST_APPROVAL_OR_COMPLETED_RECHECK": -12,
    }[row["lifecycle_review"]]
    specific = 11 if row["source_specificity"] == "PROJECT_SPECIFIC_URL_REVIEW" else -8
    role = 9 if row["exact_project_roles"] else 0
    trade = 8 if TRADE.search(row["project_description"]) else 0
    conflict = -7 if row["ai_conflicts"] else 0
    repeat = -24 if row["was_previously_reported"] else 0
    score = row["freshness_points"] + sector + stage + specific + role + trade + conflict + repeat
    row["internal_research_priority_score_not_sale_probability"] = score
    row["next_verification_action"] = (
        "Resolve exact official application identity, address and stage contradictions"
        if row["ai_conflicts"] else
        "Confirm owner/operator and actual purchasing authority; verify trade package and award status"
        if row["sector"] in ("INDUSTRIAL_EQUIPMENT_WAREHOUSE", "COMMERCIAL_BUILDING_SERVICES") else
        "Confirm meaningful supplier scope before allocating paid AI")
    row["commercial_qualification"] = "RESEARCH_ONLY_NOT_CLIENT_READY"
    row["missing_required_proof"] = (
        "LEGAL_ENTITY_IDENTITY|PURCHASING_AUTHORITY|UNAWARDED_SUPPLIER_SCOPE|"
        "CURRENT_PROCUREMENT_STATUS|PUBLIC_CONTACT_PATH")
    return row


def build(results, *, today=None):
    root = Path(results)
    if not root.is_dir():
        raise FileNotFoundError("EXISTING_RADAR_RESULTS_REQUIRED")
    today = today or dt.date.today()
    counts = {}
    rows = []
    for origin, file in (("CLIENT", CLIENT), ("PRIVATE", PRIVATE), ("V8", PENDING)):
        data = _read_csv(root, file)
        counts[file] = len(data)
        for item in data:
            record = _normalize(origin, item, today)
            if record:
                rows.append(record)
    prior = {str(r.get("opportunity_id") or "") for r in _read_csv(root, PREVIOUS)}
    graph = _read_json(root, GRAPH)
    bridge_data = _read_json(root, BRIDGE)
    roles = _graph_roles(graph)
    bridge = {str(p.get("project_id")): p for p in bridge_data.get("projects", [])
              if isinstance(p, dict)}
    for row in rows:
        if row["record_id"] in prior:
            row["was_previously_reported"] = True
        _score(_add_review_context(row, roles, bridge))

    # Do not collapse two unrelated records merely because of a shared street
    # address or company name. Suppress only identical per-record URLs or exact
    # same city+single official application ID in the *presented worklist*.
    rows.sort(key=lambda r: (-r["internal_research_priority_score_not_sale_probability"],
                             r["city"], r["record_id"]))
    seen = set()
    deduped = []
    suppressed = 0
    for row in rows:
        application = row["application_id"].strip().casefold()
        if application and "|" not in application and ";" not in application:
            token = (row["city"].casefold(), "APP", application)
        elif row["source_specificity"] == "PROJECT_SPECIFIC_URL_REVIEW":
            token = (row["city"].casefold(), "URL", row["source_url"].casefold())
        else:
            token = (row["city"].casefold(), "REC", row["origin"], row["record_id"])
        if token in seen:
            suppressed += 1
            continue
        seen.add(token)
        deduped.append(row)

    # Small geographically balanced analyst worklist; do not fabricate a
    # fixed city minimum when no viable source-backed candidates exist.
    top = []
    city_counts = {}
    for row in deduped:
        if len(top) >= 10:
            break
        if city_counts.get(row["city"].casefold(), 0) >= 4:
            continue
        if row["sector"] not in ("INDUSTRIAL_EQUIPMENT_WAREHOUSE",
                                 "COMMERCIAL_BUILDING_SERVICES"):
            continue
        top.append(row)
        city = row["city"].casefold()
        city_counts[city] = city_counts.get(city, 0) + 1
    for i, row in enumerate(top, 1):
        row["analyst_queue_rank"] = i
    return {
        "status": "COMMERCIAL_RESEARCH_QUEUE_NOT_SALES_QUALIFIED",
        "source_rows": counts,
        "deduplicated_review_candidates": len(deduped),
        "presentation_duplicates_suppressed": suppressed,
        "internal_top_10_count": len(top),
        "source_supported_ai_company_roles": sum(len(r["exact_project_roles"]) for r in deduped),
        "projects_with_ai_conflicts": sum(bool(r["ai_conflicts"]) for r in deduped),
        "verified_buyers": 0, "verified_open_supplier_contracts": 0,
        "paid_ai_calls": 0, "live_source_fetches": 0,
        "outreach_authorized": False,
        "freshness_policy": (
            "Only source event dates qualify for source-date freshness; filing "
            "dates are NOT public announcement dates; Radar first-seen does not "
            "prove first publication. Unknown dates remain unknown."
        ),
        "all_candidates": deduped, "top10": top,
    }


FIELDS = ("analyst_queue_rank", "record_id", "origin", "city", "address",
          "application_id", "project_description", "sector",
          "internal_research_priority_score_not_sale_probability",
          "source_stage", "lifecycle_review",
          "source_date", "date_basis", "freshness_band", "radar_first_seen_local",
          "source_specificity", "source_url", "named_company_unverified",
          "role_evidence_level", "exact_project_roles", "ai_conflicts",
          "commercial_qualification", "procurement_status",
          "contact_email", "contact_phone", "missing_required_proof",
          "next_verification_action")


def _csv_safe(value):
    text = str(value if value is not None else "")
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + text
    return text


def _write_csv(path, records):
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            row = {key: (json.dumps(record[key], ensure_ascii=False)
                         if key in ("exact_project_roles", "ai_conflicts") else record.get(key, ""))
                   for key in FIELDS}
            writer.writerow({k: _csv_safe(v) for k,v in row.items()})
    tmp.replace(path)


def run(results):
    root = Path(results)
    summary = build(root)
    _write_csv(root / ALL_OUT, summary["all_candidates"])
    _write_csv(root / TOP_OUT, summary["top10"])
    report = {key: value for key, value in summary.items()
              if key not in ("all_candidates", "top10")}
    path = root / REPORT
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", required=True)
    a = p.parse_args()
    print(json.dumps(run(a.results), indent=2))
