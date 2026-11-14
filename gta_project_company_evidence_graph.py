"""Project/company evidence graph composed from existing *review-only* Radar exports.

This is a read-only typed mention graph, NOT a verified company registry or CRM.
Never equate the same name, civic address or shared application keyword with an
identical legal company, project, buyer or open contract. No new source fetch,
AI, outreach, DB writes, or historical timestamp revision.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from gta_local_caption_evidence import CITIES
from gta_facility_intelligence import https

OUTPUT = "GTA_RADAR_PROJECT_COMPANY_EVIDENCE_GRAPH.json"
CROSS = "GTA_RADAR_CROSS_SOURCE_RECONCILIATION.json"
EVENTS = "FACILITY_INTELLIGENCE_PILOT/GTA_RADAR_FACILITY_EVIDENCE_EVENTS.csv"
HINTS = "FACILITY_DOSSIER_PILOT/GTA_RADAR_EXACT_PROJECT_ROLE_HINTS_TO_VERIFY.csv"
OFFICIAL = "FACILITY_DOSSIER_PILOT/GTA_RADAR_OFFICIAL_APPLICATION_EXACT_SITE_ROLE_REVIEW.csv"
MAX_SOURCE_BYTES = 35_000_000
MAX_EVENT_ROWS = 100_000
MAX_ROLE_ROWS = 12_000
MAX_EXPORTED_ROLE_MENTIONS = 800
MAX_EXPORTED_SITE_MENTIONS = 300
MAX_CROSS_CANDIDATES = 100
MAX_HOLDS = 100

ROLE_MAP = {
    "APPLICANT_CLAIM": "APPLICANT",
    "BUILDER_CLAIM": "BUILDER",
    "OWNER_CLAIM": "PROPERTY_OWNER",
    "TENANT_CLAIM": "TENANT",
    "OPERATOR_CLAIM": "OPERATOR",
    "DEVELOPER_CLAIM": "DEVELOPER",
    "CONTRACTOR_CLAIM": "CONTRACTOR",
    "OPERATOR_RESEARCH_HINT": "OPERATOR",
    "DEVELOPER_RESEARCH_HINT": "DEVELOPER",
}
OFFICIAL_ROLE_FIELDS = {
    "applicant_unverified": "APPLICANT",
    "property_owner_unverified": "PROPERTY_OWNER",
    "planning_reviewer_unverified": "MUNICIPAL_PLANNING_REVIEWER",
}
SITE_ROLE_MAP = {
    "REGULATORY_PROPONENT_NOT_VERIFIED_BUYER": "REGULATORY_PROPONENT",
    "LICENCE_OPERATING_NAME_NOT_VERIFIED_TENANT": "BUSINESS_LICENSE_NAME",
}
PLACEHOLDERS = {"", "unknown", "n/a", "na", "none", "null", "tbd",
                "not verified", "not available", "not identified"}


def _hash(*parts):
    return hashlib.sha256(
        json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:24]


def _name(value):
    s = " ".join(str(value or "").split())
    if (s.casefold() in PLACEHOLDERS or len(s) < 2 or len(s) > 200
            or not any(ch.isalpha() for ch in s)):
        return ""
    return s


def _city(value):
    raw = " ".join(str(value or "").split())
    return next((c for c in CITIES if c.casefold() == raw.casefold()), "")


def _read_csv(root, relative, required, limit):
    path = root / relative
    if not path.is_file():
        return None
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("UNSAFE_INPUT_PATH:" + path.name)
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("SOURCE_CSV_TOO_LARGE:" + path.name)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not set(required).issubset(reader.fieldnames):
            raise ValueError("SOURCE_CSV_SCHEMA_MISMATCH:" + path.name)
        rows = []
        for row in reader:
            if len(rows) >= limit:
                raise ValueError("SOURCE_CSV_ROW_LIMIT:" + path.name)
            rows.append(row)
        return rows


def _read_cross(root):
    path = root / CROSS
    if not path.is_file():
        return None
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("UNSAFE_RECONCILIATION_INPUT")
    if path.stat().st_size > 3_000_000:
        raise ValueError("RECONCILIATION_INPUT_TOO_LARGE")
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    if (not isinstance(obj, dict) or obj.get("status") != "READ_ONLY_CROSS_SOURCE_REVIEW"
            or not isinstance(obj.get("review_candidates"), list)):
        raise ValueError("UNRECOGNIZED_RECONCILIATION_INPUT")
    return obj["review_candidates"][:MAX_CROSS_CANDIDATES]


def build(results, *, now=None):
    """Compose existing evidence; all entity IDs are scoped mentions, not legal IDs."""
    root = Path(results)
    events = _read_csv(root, EVENTS,
                       {"event_id", "project_id", "city", "site_id",
                        "source_family", "source_id", "organization",
                        "organization_role", "source_url"}, MAX_EVENT_ROWS)
    hints = _read_csv(root, HINTS,
                      {"event_id", "project_id", "role_type_claimed",
                       "organization_name_claimed"}, MAX_ROLE_ROWS)
    officials = _read_csv(root, OFFICIAL,
                          {"city", "import_project_id", "application_id",
                           "import_source_url", *OFFICIAL_ROLE_FIELDS.keys()},
                          MAX_ROLE_ROWS)
    recon = _read_cross(root)
    statuses = {
        "facility_events": "PRESENT" if events is not None else "MISSING",
        "research_role_hints": "PRESENT" if hints is not None else "MISSING",
        "official_role_review": "PRESENT" if officials is not None else "MISSING",
        "council_application_reconciliation": "PRESENT" if recon is not None else "MISSING",
    }
    indexed_events = {}
    for event in events or []:
        identifier = event["event_id"]
        if not identifier:
            continue
        if identifier in indexed_events:
            raise ValueError("DUPLICATED_FACILITY_EVENT_ID")
        indexed_events[identifier] = event

    projects, organizations, sites = {}, {}, {}
    edges, holds = [], []
    role_names = defaultdict(set)
    truncated = {"role_mentions": 0, "site_mentions": 0}
    emitted = set()
    site_mentions_emitted = 0

    def hold(reason, origin):
        if len(holds) < MAX_HOLDS:
            holds.append({"reason": reason, "origin": str(origin)[:160]})

    def project(city, raw_id):
        city = _city(city)
        key = " ".join(str(raw_id or "").split())[:180]
        if not city or not key:
            return None
        pid = "project:" + _hash(city, key)
        projects[pid] = {"node_id": pid, "kind": "PROJECT_CANDIDATE",
                         "city": city, "project_id": key,
                         "identity_verified": False,
                         "buyer_verified": False}
        return pid

    def role_edge(city, project_id, org_name, role, origin, source_url,
                  *, source_record_id="", source_event_id="", evidence_id="",
                  quote_present=False):
        if len(organizations) >= MAX_EXPORTED_ROLE_MENTIONS:
            truncated["role_mentions"] += 1
            return
        pid = project(city, project_id)
        name = _name(org_name)
        if not pid or not name or not role:
            hold("INVALID_PROJECT_ROLE_CONTEXT", origin)
            return
        # Explicitly do not coalesce equal names across projects or roles:
        # the same string is not legal company identity.
        org_id = "org_mention:" + _hash(pid, role, name.casefold(), origin)
        edge_id = "edge:" + _hash(pid, org_id, origin, source_record_id)
        if edge_id in emitted:
            return
        emitted.add(edge_id)
        organizations[org_id] = {
            "node_id": org_id, "kind": "ORGANIZATION_MENTION",
            "organization_name_as_stated": name, "identity_verified": False,
            "canonical_company_id": None,
        }
        role_names[(pid, role)].add(name.casefold())
        edges.append({
            "edge_id": edge_id, "from_node": pid, "to_node": org_id,
            "relationship": "PROJECT_ROLE_SOURCE_CLAIM",
            "role_claimed": role, "evidence_origin": origin,
            "source_url": https(source_url), "source_event_id": source_event_id,
            "source_record_id": str(source_record_id or "")[:200],
            "source_evidence_id": evidence_id,
            "role_quote_present": bool(quote_present),
            "project_role_verified": False, "company_identity_verified": False,
            "buyer_verified": False, "procurement_verified": False,
            "review_action": "Check the original project-specific source and role; "
                             "verify legal entity and purchasing authority separately",
        })

    # Research roles are accepted only when the matching original facility
    # event exists and has the identical exact project ID. A role hint alone
    # cannot create a cross-project/company identity.
    for record in hints or []:
        event = indexed_events.get(record["event_id"])
        if not event or not event.get("project_id") or (
                event["project_id"] != record["project_id"]):
            hold("ROLE_HINT_EVENT_OR_PROJECT_ID_MISMATCH", record.get("project_id", ""))
            continue
        if event.get("source_family") != "radar":
            hold("ROLE_HINT_NOT_FROM_PROJECT_RECORD", record["event_id"])
            continue
        role = ROLE_MAP.get(record["role_type_claimed"])
        if not role:
            hold("UNSUPPORTED_RESEARCH_ROLE", record["role_type_claimed"])
            continue
        role_edge(event["city"], record["project_id"],
                  record["organization_name_claimed"], role,
                  "RADAR_PROJECT_RESEARCH_HINT_NOT_INDEPENDENTLY_VERIFIED",
                  record.get("official_record_url_reference") or event.get("source_url"),
                  source_record_id=event.get("source_record_id"),
                  source_event_id=event["event_id"],
                  quote_present=record.get("role_document_quote_present") == "YES")

    # Official CSV import's project ID is its own scoped candidate, never
    # automatically merged with similarly named/site-matched Radar projects.
    for record in officials or []:
        city, pid = record["city"], record["import_project_id"]
        if not _city(city) or not pid or not record["application_id"]:
            hold("INVALID_OFFICIAL_IMPORT_IDENTITY", pid)
            continue
        for field, role in OFFICIAL_ROLE_FIELDS.items():
            name = _name(record.get(field))
            if name:
                role_edge(city, pid, name, role,
                          "AUTHORIZED_EXPORT_ROLE_FIELD_REVIEW_ONLY",
                          record.get("import_source_url"),
                          source_record_id=record["application_id"],
                          quote_present=False)

    # Site-local mentions are not project associations. They never link to a
    # project node, even when another record shares site_id or organization.
    for record in events or []:
        if not record.get("site_id") or not _city(record.get("city")):
            continue
        role = SITE_ROLE_MAP.get(record.get("organization_role"))
        name = _name(record.get("organization"))
        if not role or not name:
            continue
        if site_mentions_emitted >= MAX_EXPORTED_SITE_MENTIONS:
            truncated["site_mentions"] += 1
            continue
        city = _city(record["city"])
        site_key = "site:" + _hash(city, record["site_id"])
        sites[site_key] = {
            "node_id": site_key, "kind": "SOURCE_SITE_CONTEXT",
            "city": city, "source_site_id": record["site_id"],
            "site_identity_verified": False,
        }
        org_id = "org_mention:" + _hash(site_key, role, name.casefold(),
                                        record["event_id"])
        edge_id = "edge:" + _hash(site_key, org_id, record["event_id"])
        if edge_id in emitted:
            continue
        emitted.add(edge_id)
        organizations[org_id] = {
            "node_id": org_id, "kind": "ORGANIZATION_MENTION",
            "organization_name_as_stated": name,
            "identity_verified": False, "canonical_company_id": None,
        }
        site_mentions_emitted += 1
        edges.append({
            "edge_id": edge_id, "from_node": site_key, "to_node": org_id,
            "relationship": "SOURCE_SITE_ORGANIZATION_MENTION_NOT_PROJECT_ROLE",
            "role_claimed": role,
            "evidence_origin": record["source_family"],
            "source_url": https(record.get("source_url")),
            "source_event_id": record["event_id"],
            "project_role_verified": False, "company_identity_verified": False,
            "buyer_verified": False, "procurement_verified": False,
        })

    # Council text can link to an exact application-ID research candidate, not
    # to any company. Preserve exact reference without introducing a role.
    council_links = []
    for match in recon or []:
        if not isinstance(match, dict) or match.get("status") != (
                "EXACT_ID_CANDIDATE_HUMAN_REVIEW_REQUIRED"):
            continue
        pid = project(match.get("city"), match.get("project_id"))
        if pid is None:
            hold("INVALID_COUNCIL_MATCH_IDENTITY", match.get("evidence_id"))
            continue
        council_links.append({
            "project_node_id": pid,
            "source_evidence_id": str(match.get("evidence_id") or "")[:60],
            "source_url": https(match.get("source_url")),
            "source_sha256": str(match.get("source_sha256") or "")[:64],
            "pdf_page": match.get("page"),
            "recording_timestamp_ms": match.get("start_ms"),
            "application_id": match.get("application_id"),
            "relationship": "SOURCE_MENTIONS_EXACT_APPLICATION_ID_REVIEW_ONLY",
            "project_link_verified": False,
        })
    conflicts = [
        {"project_node_id": pid, "role_claimed": role,
         "distinct_names": len(names),
         "status": "CONFLICTING_SOURCE_ROLE_NAMES_HUMAN_REVIEW_REQUIRED"}
        for (pid, role), names in sorted(role_names.items())
        if len(names) > 1
    ]
    return {
        "status": "PROJECT_COMPANY_MENTION_GRAPH_REVIEW_ONLY",
        "generated_utc": now or dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_statuses": statuses,
        "project_candidates": len(projects),
        "organization_mentions": len(organizations),
        "source_site_contexts": len(sites),
        "claimed_relationships": len(edges),
        "council_id_context_links": len(council_links),
        "role_conflicts": len(conflicts),
        "held_issues": len(holds),
        "truncated": truncated,
        "verified_company_entities": 0,
        "verified_project_company_roles": 0,
        "verified_buyers": 0,
        "verified_open_supplier_packages": 0,
        "paid_ai_usd": 0,
        "warning": ("Every organization is a source-specific mention, not a "
                    "deduplicated legal entity. Research roles, official import "
                    "fields and same-site references are unverified. "
                    "A matching project ID does not prove a buyer."),
        "project_nodes": sorted(projects.values(), key=lambda n: n["node_id"]),
        "organization_nodes": sorted(organizations.values(), key=lambda n: n["node_id"]),
        "site_nodes": sorted(sites.values(), key=lambda n: n["node_id"]),
        "edges": sorted(edges, key=lambda e: e["edge_id"]),
        "council_evidence": council_links,
        "conflicts": conflicts,
        "holds": holds,
    }


def run(results):
    root = Path(results)
    report = build(root)
    path = root / OUTPUT
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    tmp.replace(path)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    result = run(args.results)
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ("project_nodes", "organization_nodes",
                                   "site_nodes", "edges", "council_evidence",
                                   "conflicts", "holds")}, indent=2))
