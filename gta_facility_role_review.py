"""Exact-project company-role research hints from existing Radar research exports.

This joins ONLY the same stable project_id, never address/name similarity. The
existing research CSV is not proof of the organization identity, buyer, award,
contact or purchasing authority. All role claims stay UNVERIFIED.

No network, AI, outreach, project promotion or source DB modification.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import gta_facility_intelligence as graph

OUT_CSV="GTA_RADAR_EXACT_PROJECT_ROLE_HINTS_TO_VERIFY.csv"
OUT_STATUS="GTA_RADAR_EXACT_PROJECT_ROLE_HINTS_STATUS.json"
FIELDS=(
    "dossier_id","event_id","project_id","source_id","source_record_id",
    "role_type_claimed","organization_name_claimed","source_field",
    "claim_origin","record_identity_match","project_identity_confidence",
    "official_record_url_reference","official_verification_level",
    "role_document_quote_present","company_role_verified",
    "buyer_verified","public_contact_verified","procurement_verified",
    "review_status","verification_required",
)
FIELDS_TO_ROLES=(
    ("company_applicant","APPLICANT_CLAIM"),
    ("company_builder","BUILDER_CLAIM"),
    ("company_owner","OWNER_CLAIM"),
    ("company_tenant","TENANT_CLAIM"),
    ("company_operator_claim","OPERATOR_CLAIM"),
    ("company_developer_claim","DEVELOPER_CLAIM"),
    ("company_contractor_claim","CONTRACTOR_CLAIM"),
    ("operator","OPERATOR_RESEARCH_HINT"),
    ("developer","DEVELOPER_RESEARCH_HINT"),
)
IDENTITY_EXCLUSIONS={
    "ADDRESS_CONTEXT_ONLY", "ADDRESS_MATCH_ONLY", "UNVERIFIED_ADDRESS_MATCH",
    "UNVERIFIED_IDENTITY", "NOT_A_PROJECT_MATCH",
}
PLACEHOLDERS={"","unknown","n/a","none","not available","not identified",
              "not verified","to be determined","tbd"}


def clean_name(value):
    value=graph.clean(value)
    if value.lower() in PLACEHOLDERS or len(value)>200:
        return ""
    if not any(c.isalpha() for c in value):
        return ""
    return value


def dossier_id(event_id):
    return hashlib.sha256(("GTA_DOSSIER_V1|"+event_id).encode()).hexdigest()[:20]


def exact_role_hints(events, opportunity_rows):
    """Output project-ID-matched hypotheses; never legal/buyer verification."""
    projects=defaultdict(list)
    for ev in events:
        if ev.get("source_family")=="radar" and ev.get("project_id"):
            projects[ev["project_id"]].append(ev)
    matched_ids=set()
    excluded=Counter()
    found={}
    for row in opportunity_rows:
        project=graph.clean(row.get("project_id"))
        if not project or project not in projects:
            excluded["NO_EXACT_PROJECT_ID_JOIN"]+=1
            continue
        identity=graph.clean(row.get("project_identity_confidence"))
        if identity.upper() in IDENTITY_EXCLUSIONS:
            excluded["WEAK_PROJECT_IDENTITY_RESEARCH_ENTRY"]+=1
            continue
        matched_ids.add(project)
        official_url=graph.https(row.get("official_record_url"))
        official_level=graph.clean(row.get("official_verification_level"))
        for ev in projects[project]:
            for field,role in FIELDS_TO_ROLES:
                name=clean_name(row.get(field))
                if not name:
                    continue
                # The field's name (even "company_owner") is a source-claim
                # category, not proof. Require a separately checked quotation
                # and actual role review before anyone can act on it.
                key=(ev["event_id"],role,name.casefold())
                if key in found:
                    continue
                found[key]={
                    "dossier_id":dossier_id(ev["event_id"]),
                    "event_id":ev["event_id"],"project_id":project,
                    "source_id":ev.get("source_id",""),
                    "source_record_id":ev.get("source_record_id",""),
                    "role_type_claimed":role,
                    "organization_name_claimed":name,
                    "source_field":field,
                    "claim_origin":"EXISTING_RADAR_RESEARCH_EXPORT_NOT_INDEPENDENT_EVIDENCE",
                    "record_identity_match":"EXACT_LOCAL_PROJECT_ID_ONLY",
                    "project_identity_confidence":identity,
                    "official_record_url_reference":official_url,
                    "official_verification_level":official_level,
                    "role_document_quote_present":"NO",
                    "company_role_verified":"NO",
                    "buyer_verified":"NO",
                    "public_contact_verified":"NO",
                    "procurement_verified":"NO",
                    "review_status":"SOURCE_ROLE_EVIDENCE_REQUIRED",
                    "verification_required":"Retrieve and check primary document identifying this "
                                            "organization's actual role in this specific project; "
                                            "then separately verify purchasing authority, "
                                            "public business contact and procurement status",
                }
    return list(sorted(found.values(),key=lambda r:(r["project_id"],r["role_type_claimed"],
                                                     r["organization_name_claimed"]))), {
        "exact_project_ids_in_graph":len(projects),
        "exact_project_ids_with_research_row":len(matched_ids),
        "project_ids_with_role_claims":len({x["project_id"] for x in found.values()}),
        "research_rows_without_exact_project_match":excluded["NO_EXACT_PROJECT_ID_JOIN"],
        "research_rows_with_weak_identity_excluded":excluded["WEAK_PROJECT_IDENTITY_RESEARCH_ENTRY"],
    }


def run(graph_dir, opportunities_file, out=None):
    graph_dir=Path(graph_dir);opportunities_file=Path(opportunities_file)
    out=Path(out) if out is not None else graph_dir.parent/"FACILITY_DOSSIER_PILOT"
    if out.resolve()==graph_dir.resolve():
        raise ValueError("Role review must not overwrite the graph source directory")
    events_file=graph_dir/graph.OUTPUT_EVENTS
    if not events_file.is_file():
        raise FileNotFoundError("Facility event graph missing: "+str(events_file))
    with events_file.open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        keys=set(reader.fieldnames or [])
        if not {"event_id","project_id","source_family","source_id","source_record_id"} <= keys:
            raise ValueError("Unexpected facility events schema; cannot join roles safely")
        events=list(reader)
    if opportunities_file.is_file():
        with opportunities_file.open(encoding="utf-8-sig",newline="") as f:
            r=csv.DictReader(f)
            if not {"project_id","project_identity_confidence"} <= set(r.fieldnames or []):
                raise ValueError("Unexpected project-opportunities schema; refusing role claims")
            sources=list(r)
        source_status="EXISTING_RESEARCH_EXPORT_REVIEWED_FOR_EXACT_PROJECT_IDS"
    else:
        sources=[]
        source_status="RESEARCH_EXPORT_MISSING_NO_ROLE_CLAIMS"
    rows,counts=exact_role_hints(events,sources)
    out.mkdir(parents=True,exist_ok=True)
    graph.write_csv(out/OUT_CSV,rows,FIELDS)
    status={
        "mode":"OFFLINE_EXACT_PROJECT_ID_ROLE_RESEARCH_NOT_VERIFIED_CONTACTS",
        "research_export_status":source_status,
        "research_rows_read":len(sources),
        "graph_source_events":len(events),
        "role_hints":len(rows),
        **counts,
        "verified_company_roles":0,
        "verified_purchasing_authorities":0,
        "verified_contact_records":0,
        "verified_open_supplier_contracts":0,
        "never_use_as_automatic_buyer":"All organization names are research claims; "
            "a matching project_id is not proof of owner/operator/contractor role, "
            "public contact, purchasing authority or open procurement.",
        "output_csv":str(out/OUT_CSV),
    }
    (out/OUT_STATUS).write_text(json.dumps(status,indent=2),encoding="utf-8")
    return status


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-dir",type=Path,required=True)
    parser.add_argument("--opportunities",type=Path,required=True)
    parser.add_argument("--out",type=Path)
    args=parser.parse_args()
    print(json.dumps(run(args.graph_dir,args.opportunities,args.out),indent=2))


if __name__=="__main__":
    main()
