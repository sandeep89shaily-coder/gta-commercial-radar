"""Commercial evidence dossier builder for the shared GTA Radar facility graph.

Produces researched *candidate dossiers*, NEVER verified tender/buyer/contract
claims. Consumes only the read-only facility graph's existing CSV snapshots.
No network, AI, contact scraping, external dependencies or production changes.

One dossier = one source event / possible work package. Same civic address can
supply contextual evidence, but never merges different tenants/projects.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

import gta_facility_intelligence as graph

DOSSIERS_CSV = "GTA_RADAR_EVIDENCE_DOSSIERS.csv"
DOSSIERS_JSONL = "GTA_RADAR_EVIDENCE_DOSSIERS.jsonl"
TASKS_CSV = "GTA_RADAR_DOSSIER_VERIFICATION_TASKS.csv"
REPORT_HTML = "GTA_RADAR_EVIDENCE_DOSSIERS.html"
REPORT_STATUS = "GTA_RADAR_EVIDENCE_DOSSIER_STATUS.json"

DOSSIER_FIELDS = (
    "dossier_id", "event_id", "source_family", "source_id",
    "source_record_id", "site_id", "city", "site_address", "site_unit",
    "organization_mention", "organization_role_unverified",
    "source_event_date", "radar_first_seen_at", "source_age_days",
    "source_url", "source_url_quality", "source_record_hash",
    "signal_type", "source_stage", "source_scope", "source_description",
    "possible_customer_segments", "cross_source_context_events",
    "cross_source_context_status", "source_families_at_civic_site",
    "research_priority", "commercial_readiness", "readiness_blockers",
    "procurement_verified", "buyer_verified", "verified_business_contact",
    "opening_verified", "verified_open_contract", "outreach_authorized",
    "recommended_research_action",
)
TASK_FIELDS = (
    "dossier_id", "event_id", "task_code", "priority",
    "evidence_needed", "current_status", "source_record_id",
    "source_url", "reviewer", "evidence_confirmed_at",
)
HOLD = {
    "HISTORICAL_OR_TERMINAL_REVIEW_ONLY",
    "HISTORICAL_PLANNING_BASELINE_SITE_CONTEXT_ONLY",
    "HISTORICAL_SOURCE_DATE_REVIEW_ONLY",
    "SOURCE_DATE_UNVERIFIED_REVIEW_ONLY",
    "IDENTITY_REPAIR_REQUIRED",
}
UNSAFE_RELATIONSHIP = {"DIFFERENT_UNITS_NOT_SAME_TENANT"}
CONTEXT_ONLY = {
    "DESCRIPTION_ADDRESS_SAME_SITE_CANDIDATE_ONLY",
    "SAME_BUILDING_UNIT_UNKNOWN",
    "SAME_CIVIC_SITE_PROJECT_UNVERIFIED",
    "SAME_ADDRESS_AND_UNIT_TENANT_UNVERIFIED",
}
PRIORITY_ORDER = {
    "P1_EQUIPMENT_SOURCE_RESEARCH": 0,
    "P2_ACTIVATION_SOURCE_RESEARCH": 1,
    "P3_PLANNING_OR_PERMIT_RESEARCH": 2,
    "HOLD_HISTORY_OR_INCOMPLETE_IDENTITY": 3,
}
ACTION_DESCRIPTIONS = {
    "RECHECK_HISTORICAL_OR_TERMINAL_STATUS":
        "Review original authority record for current lifecycle; do not present as new procurement.",
    "REPAIR_SITE_IDENTITY":
        "Confirm exact physical site city, number, road and suite from an individual primary record.",
    "VERIFY_INDIVIDUAL_OFFICIAL_RECORD":
        "Open exact official filing/permit/licence by source ID and record a stable evidence link and current stage.",
    "VERIFY_CURRENT_PROCUREMENT_STATUS":
        "Confirm whether purchasing or supplier selection is open, awarded, cancelled or unknown.",
    "VERIFY_OPERATOR_AND_BUYER_ROLE":
        "Confirm who operates/owns the facility and who actually selects suppliers for this work package.",
    "VERIFY_PUBLIC_BUSINESS_CONTACT":
        "Find source-backed public business contact for verified purchasing organization; no personal scraping.",
    "VERIFY_SOURCE_SCOPE_AND_TIMELINE":
        "Check whether source description identifies current work and when the work will occur.",
    "VERIFY_ACTUAL_OPENING":
        "Seek independent opening/occupancy evidence; licence or inspection is not an opening.",
    "INVESTIGATE_SAME_SITE_RELATIONSHIP":
        "Verify whether distinct filings refer to the same project or work package, not merely an address.",
}
TASK_ORDER = {name: i for i, name in enumerate(ACTION_DESCRIPTIONS)}


def read_rows(path, required):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError("Required facility graph export missing: " + str(path))
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        fields = set(reader.fieldnames or [])
        missing = set(required) - fields
        if missing:
            raise ValueError("Unexpected graph schema in "+path.name+"; missing: "+", ".join(sorted(missing)))
        return list(reader)


def source_record_quality(event):
    # These fields are inherited from source snapshots, never live-revalidated.
    level = event.get("url_evidence_level", "")
    url = graph.https(event.get("source_url", ""))
    if not url:
        return "NO_STABLE_SOURCE_URL"
    if level == "RECORD_URL_NOT_LIVE_CHECKED":
        return "INDIVIDUAL_SOURCE_REFERENCE_NOT_RECHECKED"
    return "DATASET_OR_PORTAL_REFERENCE_NOT_INDIVIDUAL_VERIFICATION"


def research_priority(event):
    state = event.get("review_tier", "")
    if state in HOLD or state.startswith("HISTORICAL_"):
        return "HOLD_HISTORY_OR_INCOMPLETE_IDENTITY"
    if event.get("source_family") == "industrial" and event.get("scope_specificity") == "EXPLICIT_EQUIPMENT_CHANGE":
        return "P1_EQUIPMENT_SOURCE_RESEARCH"
    if event.get("source_family") == "activation":
        return "P2_ACTIVATION_SOURCE_RESEARCH"
    return "P3_PLANNING_OR_PERMIT_RESEARCH"


def blocker_codes(event, quality, related_count):
    blockers = set(filter(None, (event.get("verification_required") or "").split(";")))
    # No graph signal can independently confirm sourcing or buying authority.
    blockers.update(("PROCUREMENT_STATUS_NOT_INDEPENDENTLY_VERIFIED",
                     "PURCHASING_AUTHORITY_NOT_VERIFIED",
                     "PUBLIC_BUSINESS_CONTACT_NOT_VERIFIED"))
    if quality != "INDIVIDUAL_SOURCE_REFERENCE_NOT_RECHECKED":
        blockers.add("EXACT_INDIVIDUAL_OFFICIAL_RECORD_NOT_RECHECKED")
    else:
        blockers.add("INDIVIDUAL_OFFICIAL_RECORD_NOT_LIVE_RECHECKED")
    if not event.get("site_id"):
        blockers.add("SITE_IDENTITY_UNRESOLVED")
    if not event.get("organization"):
        blockers.add("COMPANY_OR_OPERATOR_UNKNOWN")
    if event.get("source_family") == "activation":
        blockers.add("ACTUAL_OPENING_NOT_VERIFIED")
    if related_count:
        blockers.add("CROSS_SOURCE_SAME_PROJECT_NOT_VERIFIED")
    return sorted(blockers)


def task_codes(event, quality, related_count):
    tier = event.get("review_tier", "")
    if tier in HOLD or tier.startswith("HISTORICAL_"):
        if tier == "IDENTITY_REPAIR_REQUIRED":
            return ["REPAIR_SITE_IDENTITY", "VERIFY_INDIVIDUAL_OFFICIAL_RECORD"]
        return ["RECHECK_HISTORICAL_OR_TERMINAL_STATUS"]
    codes = []
    if not event.get("site_id"):
        codes.append("REPAIR_SITE_IDENTITY")
    if quality != "INDIVIDUAL_SOURCE_REFERENCE_NOT_RECHECKED":
        codes.append("VERIFY_INDIVIDUAL_OFFICIAL_RECORD")
    else:
        # The link still has to be opened and validated; never treat it as done.
        codes.append("VERIFY_INDIVIDUAL_OFFICIAL_RECORD")
    codes.append("VERIFY_SOURCE_SCOPE_AND_TIMELINE")
    codes.append("VERIFY_CURRENT_PROCUREMENT_STATUS")
    codes.append("VERIFY_OPERATOR_AND_BUYER_ROLE")
    codes.append("VERIFY_PUBLIC_BUSINESS_CONTACT")
    if event.get("source_family") == "activation":
        codes.append("VERIFY_ACTUAL_OPENING")
    if related_count:
        codes.append("INVESTIGATE_SAME_SITE_RELATIONSHIP")
    return list(dict.fromkeys(codes))


def related_context(primary, event_map, site_links):
    """Context is never treated as independent proof of scope or a buyer."""
    found = {}
    unsafe_count = 0
    for link in site_links.get(primary["site_id"], ()):
        left, right = link.get("left_event_id"), link.get("right_event_id")
        if primary["event_id"] not in (left, right):
            continue
        other_id = right if primary["event_id"] == left else left
        other = event_map.get(other_id)
        if other is None or other.get("site_id") != primary["site_id"]:
            continue
        relation = link.get("relationship", "")
        if relation in UNSAFE_RELATIONSHIP:
            unsafe_count += 1
            continue
        if relation not in CONTEXT_ONLY:
            continue
        # The same original record through different paths isn't corroboration.
        if (primary.get("source_id"), primary.get("source_record_id")) == (
                other.get("source_id"), other.get("source_record_id")):
            continue
        found[other_id] = {
            "event_id": other_id, "source_family": other.get("source_family",""),
            "source_record_id": other.get("source_record_id",""),
            "source_date": other.get("source_date",""),
            "source_url": graph.https(other.get("source_url","")),
            "source_record_description": (other.get("description","") or "")[:400],
            "relationship_label": relation,
            "same_project_verified": "NO",
            "same_company_verified": "NO",
            "scope_corroborated": "NO",
        }
    return list(sorted(found.values(), key=lambda x:x["event_id"]))[:20], unsafe_count


def build_dossier(event, events_by_id, site_links):
    context, conflicts = related_context(event, events_by_id, site_links)
    quality = source_record_quality(event)
    priority = research_priority(event)
    blockers = blocker_codes(event, quality, len(context))
    codes = task_codes(event, quality, len(context))
    dossier_id = hashlib.sha256(("GTA_DOSSIER_V1|"+event["event_id"]).encode("utf-8")).hexdigest()[:20]
    if priority.startswith("HOLD"):
        readiness = "HOLD_NOT_COMMERCIALLY_ACTIVE"
    else:
        readiness = "RESEARCH_SIGNAL_ONLY_NOT_VERIFIED_LEAD"
    site_families = sorted({event.get("source_family","")} |
                           {x["source_family"] for x in context})
    row = {
        "dossier_id": dossier_id,
        "event_id": event["event_id"],
        "source_family": event.get("source_family",""),
        "source_id": event.get("source_id",""),
        "source_record_id": event.get("source_record_id",""),
        "site_id": event.get("site_id",""),
        "city": event.get("city",""),
        "site_address": event.get("site_address",""),
        "site_unit": event.get("site_unit",""),
        "organization_mention": event.get("organization",""),
        "organization_role_unverified": event.get("organization_role",""),
        "source_event_date": event.get("source_date",""),
        "radar_first_seen_at": event.get("radar_first_seen_at",""),
        "source_age_days": event.get("source_age_days",""),
        "source_url": graph.https(event.get("source_url","")),
        "source_url_quality": quality,
        "source_record_hash": event.get("record_hash",""),
        "signal_type": event.get("signal_type",""),
        "source_stage": event.get("stage_label",""),
        "source_scope": event.get("scope_specificity",""),
        "source_description": (event.get("description","") or "")[:750],
        "possible_customer_segments": event.get("supplier_segments_possible",""),
        "cross_source_context_events": len(context),
        "cross_source_context_status": (
            "UNVERIFIED_CIVIC_SITE_LINK_ONLY" if context else
            "UNIT_CONFLICTS_EXCLUDED" if conflicts else
            "NONE"),
        "source_families_at_civic_site": ";".join(site_families),
        "research_priority": priority,
        "commercial_readiness": readiness,
        "readiness_blockers": ";".join(blockers),
        "procurement_verified": "NO",
        "buyer_verified": "NO",
        "verified_business_contact": "",
        "opening_verified": "NO" if event.get("source_family") == "activation" else "NOT_APPLICABLE",
        "verified_open_contract": "NO",
        "outreach_authorized": "NO",
        "recommended_research_action": ACTION_DESCRIPTIONS[codes[0]],
    }
    details = {
        "dossier_id": dossier_id,
        "commercial_readiness": readiness,
        "research_priority": priority,
        "primary_source_event": {
            "event_id": event["event_id"],
            "source_id": event.get("source_id",""),
            "source_record_id": event.get("source_record_id",""),
            "source_record_hash": event.get("record_hash",""),
            "url": row["source_url"], "url_quality": quality,
            "source_event_date": row["source_event_date"],
            "radar_first_seen_at": row["radar_first_seen_at"],
            "source_stage": row["source_stage"],
            "organization_mention": row["organization_mention"],
            "role_claim_limit": row["organization_role_unverified"],
            "source_record_description": row["source_description"],
        },
        "physical_site_only": {
            "site_id": row["site_id"], "municipality": row["city"],
            "civic_address": row["site_address"], "unit": row["site_unit"],
            "identity_status": event.get("site_identity_status",""),
        },
        "site_context_not_project_corroboration": context,
        "unit_conflicts_excluded": conflicts,
        "possible_customer_segments_not_confirmed_purchases": row["possible_customer_segments"],
        "outreach_authorized": False,
        "verified_buying_authority": False,
        "verified_open_procurement": False,
        "research_questions": [{"code":code,"required_evidence":ACTION_DESCRIPTIONS[code]}
                               for code in codes],
        "readiness_blockers": blockers,
    }
    tasks = [{
        "dossier_id": dossier_id, "event_id": event["event_id"],
        "task_code": code, "priority": TASK_ORDER[code]+1,
        "evidence_needed": ACTION_DESCRIPTIONS[code],
        "current_status": "NOT_VERIFIED",
        "source_record_id": event.get("source_record_id",""),
        "source_url": row["source_url"],
        "reviewer": "", "evidence_confirmed_at": "",
    } for code in codes]
    return row, details, tasks


def run(graph_dir, out=None, *, html_limit=200):
    graph_dir = Path(graph_dir)
    out = Path(out) if out is not None else graph_dir.parent/"FACILITY_DOSSIER_PILOT"
    if out.resolve() == graph_dir.resolve():
        raise ValueError("Dossier output folder must be separate from the graph input folder")
    # Read all inputs and validate before creating output files.
    event_rows = read_rows(graph_dir/graph.OUTPUT_EVENTS,
        ("event_id","source_family","source_id","source_record_id","review_tier",
         "site_id","source_url","source_date","scope_specificity"))
    link_rows = read_rows(graph_dir/graph.OUTPUT_LINKS,
        ("site_id","left_event_id","right_event_id","relationship"))
    events_by_id = {}
    for e in event_rows:
        if not e.get("event_id"):
            raise ValueError("Graph contains a source event with no stable event_id")
        if e["event_id"] in events_by_id:
            raise ValueError("Duplicate stable event_id in graph export: "+e["event_id"])
        events_by_id[e["event_id"]] = e
    site_links = defaultdict(list)
    for link in link_rows:
        if link.get("site_id"):
            site_links[link["site_id"]].append(link)
    all_dossiers = []
    details = []
    tasks = []
    for event in events_by_id.values():
        dossier, rich, todo = build_dossier(event, events_by_id, site_links)
        all_dossiers.append(dossier)
        details.append(rich)
        tasks.extend(todo)
    all_dossiers.sort(key=lambda r:(
        PRIORITY_ORDER[r["research_priority"]],
        (int(r["source_age_days"]) if (r["source_age_days"] or "").isdigit()
         else 1000000),
        r["dossier_id"]))
    rich_by_id = {r["dossier_id"]:r for r in details}
    tasks_by_id = defaultdict(list)
    for task in tasks:
        tasks_by_id[task["dossier_id"]].append(task)
    details = [rich_by_id[r["dossier_id"]] for r in all_dossiers]
    tasks = [t for d in all_dossiers for t in tasks_by_id[d["dossier_id"]]]
    out.mkdir(parents=True, exist_ok=True)
    graph.write_csv(out/DOSSIERS_CSV, all_dossiers, DOSSIER_FIELDS)
    graph.write_csv(out/TASKS_CSV, tasks, TASK_FIELDS)
    with (out/DOSSIERS_JSONL).open("w", encoding="utf-8") as handle:
        for detail in details:
            handle.write(json.dumps(detail,ensure_ascii=False)+"\n")
    columns = ("city", "site_address", "organization_mention","signal_type",
               "source_event_date", "research_priority","commercial_readiness",
               "cross_source_context_events", "recommended_research_action")
    table_rows = []
    for d in all_dossiers[:max(0,min(int(html_limit),1000))]:
        safe_url = graph.https(d["source_url"])
        tds = "".join("<td>"+html.escape(graph.clean(d[k]))+"</td>" for k in columns)
        link = ("<td><a target='_blank' rel='noopener noreferrer' href='"+
                html.escape(safe_url,quote=True)+"'>Source</a></td>" if safe_url
                else "<td>Not available</td>")
        table_rows.append("<tr>"+tds+link+"</tr>")
    (out/REPORT_HTML).write_text(
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>GTA Radar evidence dossiers</title>"
        "<style>body{font:14px Arial,sans-serif;margin:24px}"
        "table{border-collapse:collapse}th,td{border:1px solid #ddd;"
        "padding:7px;vertical-align:top}th{background:#eee}</style>"
        "</head><body><h1>GTA Radar — candidate evidence dossiers</h1>"
        "<p>RESEARCH-ONLY. Source hints are not confirmed suppliers, contacts,"
        " openings or available contracts. Source and relationship review are required. "
        "Only the first selected dossiers appear here; CSV/JSONL hold all.</p>"
        "<table><tr>"+"".join("<th>"+html.escape(c)+"</th>" for c in columns)+
        "<th>Original source reference</th></tr>"+"".join(table_rows)+
        "</table></body></html>",encoding="utf-8")
    priorities = Counter(r["research_priority"] for r in all_dossiers)
    status = {
        "mode":"OFFLINE_EVIDENCE_DOSSIERS_RESEARCH_ONLY_NO_AI_NO_LIVE_FETCH",
        "graph_directory":str(graph_dir), "source_event_rows":len(event_rows),
        "source_link_rows":len(link_rows),
        "candidate_dossiers":len(all_dossiers),
        "research_priority_counts":dict(sorted(priorities.items())),
        "dossiers_with_unverified_cross_source_context":sum(
            int(r["cross_source_context_events"])>0 for r in all_dossiers),
        "site_identities_missing":sum(not r["site_id"] for r in all_dossiers),
        "exact_individual_source_rechecks_required":sum(
            r["source_url_quality"] != "INDIVIDUAL_SOURCE_REFERENCE_NOT_RECHECKED"
            for r in all_dossiers),
        "manual_verification_tasks":len(tasks),
        "verified_open_supplier_contracts":0,"verified_buyers":0,
        "verified_business_openings":0,"outreach_authorized":0,
        "limitations":[
            "All dossiers remain investigative candidates, not confirmed sales leads",
            "Shared civic location, including matching unit, does not verify same tenant or project",
            "Source descriptions and portal URLs have not been rechecked live",
            "No manually reviewed procurement evidence or buyer authority accepted in this module",
            "No schedule, paid AI, outbound communication or production results changed",
        ],
        "outputs":{
            "csv":str(out/DOSSIERS_CSV), "jsonl":str(out/DOSSIERS_JSONL),
            "verification_tasks":str(out/TASKS_CSV),
            "html":str(out/REPORT_HTML),
        },
    }
    (out/REPORT_STATUS).write_text(json.dumps(status,indent=2),encoding="utf-8")
    return status


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--graph-dir",type=Path,required=True,
                   help="Existing FACILITY_INTELLIGENCE_PILOT output")
    p.add_argument("--out",type=Path)
    p.add_argument("--html-limit",type=int,default=200)
    args=p.parse_args()
    print(json.dumps(run(args.graph_dir,args.out,html_limit=args.html_limit),indent=2))


if __name__=="__main__":
    main()
