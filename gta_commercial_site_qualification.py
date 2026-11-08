"""Commercial qualification research overlay for already validated Toronto dossiers.

This file does NOT infer purchasing authority from property-manager websites.
It accepts manually researched site associations only if BOTH the exact source
project_id and normalized civic address match an existing source-evidence dossier.
Research contacts are explicitly channel/role hints, never approved contacts
for a specific permit or evidence that supplier bids are available.

Offline, no paid AI, no collection, no outreach, no live access.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path

import gta_facility_intelligence as graph
import gta_facility_dossiers as dossiers

DEFAULT_RESEARCH=Path(__file__).parent/"research"/"toronto_20_site_qualification_20261108.json"
OUTPUT_CSV="GTA_RADAR_TORONTO_20_COMMERCIAL_QUALIFICATION.csv"
OUTPUT_STATUS="GTA_RADAR_TORONTO_20_COMMERCIAL_QUALIFICATION_STATUS.json"
FIELDS=(
 "project_id","dossier_id","site_address","source_record_id","source_stage",
 "source_event_date","source_lookup_key","company_or_property_org",
 "org_role_classification","public_business_contact_name",
 "public_business_contact_role","public_business_contact_phone",
 "public_business_contact_email","source_website","research_date",
 "association_evidence_limit","commercial_research_summary",
 "primary_city_record_url","source_record_evidence_level",
 "permit_status_held","contact_is_verified_permit_buyer",
 "procurement_open_verified","vendor_work_package_verified",
 "outreach_authorized","research_priority","recommended_follow_up",
)
CONTACT_FIELDS=("contact_name","contact_role","contact_phone","contact_email")
NONBUYER_FLAGS={"LEASING_CONTACT_NOT_PERMIT_BUYER",
 "PROPERTY_MANAGER_NOT_PERMIT_BUYER","BUILDING_MANAGEMENT_NOT_PERMIT_BUYER",
 "PROCUREMENT_CONTACT_GENERAL_NOT_THIS_CONTRACT",
 "MULTI_TENANT_RISK_SUPPRESS_COMPANY_JOIN",
 "REFUSAL_NOTICE_HOLD_NOT_MARKETABLE"}
REQUIRED={"project_id","site_address","organization","organization_role",
          "source_url","association_limit","research_as_of",
          "verified_buyer_for_permit","verified_open_work"}

def load_research(path):
    content=json.loads(Path(path).read_text(encoding="utf-8"))
    if content.get("schema_version")!="1.0" or not isinstance(content.get("rows"),list):
        raise ValueError("Unexpected source-backed commercial research schema")
    result={}
    for row in content["rows"]:
        if not isinstance(row,dict) or not REQUIRED.issubset(row):
            raise ValueError("Missing required source-backed research fields")
        project=graph.clean(row["project_id"])
        if project in result or not project.startswith("toronto_active_building_permits:"):
            raise ValueError("Duplicate or non-Toronto project identity in research")
        if row.get("verified_buyer_for_permit") is not False or row.get("verified_open_work") is not False:
            raise ValueError("Site-context research cannot claim verified permit buyer or open contract")
        if row.get("verified_for_project_procurement") is not False:
            raise ValueError("Property contact cannot be automatically verified purchasing authority")
        source=graph.clean(row["source_url"])
        if source and not graph.https(source):
            raise ValueError("Only valid HTTPS official/research source URLs are accepted")
        try:
            dt.date.fromisoformat(row["research_as_of"])
        except (ValueError,TypeError) as exc:
            raise ValueError("Research verification date must be explicit YYYY-MM-DD") from exc
        for field in CONTACT_FIELDS:
            value=graph.clean(row.get(field,""))
            if value.startswith("=") or value.startswith("@"):
                raise ValueError("Untrusted contact data must not be a spreadsheet formula")
        result[project]=row
    return result

def classify(dossier,research):
    status=graph.clean(dossier.get("source_stage",""))
    tier=graph.clean(dossier.get("commercial_readiness",""))
    if tier.startswith("HOLD") or graph.TERMINAL.search(status) or graph.ON_HOLD.search(status):
        return "HOLD_PERMIT_NOT_MARKETABLE","Recheck current City status before any business opportunity analysis"
    if not research:
        return "NO_SOURCE_BACKED_COMPANY_RELATION","Identify legal project applicant, operator and purchasing authority using original filing"
    if research["association_limit"] in NONBUYER_FLAGS:
        if research["association_limit"]=="MULTI_TENANT_RISK_SUPPRESS_COMPANY_JOIN":
            return "MULTI_TENANT_SITE_UNIT_UNKNOWN","Identify exact unit/tenant from the individual permit; do not use unrelated licences"
        if research["association_limit"]=="PROCUREMENT_CONTACT_GENERAL_NOT_THIS_CONTRACT":
            return "GENERAL_PROCUREMENT_ROUTE_NOT_ACTIVE_CONTRACT","Check CBC official supplier registration and exact permit-related tender, if any"
    return "PROPERTY_ROLE_EVIDENCE_ONLY","Verify permit-specific tenant, actual work package, awarding contractor and procurement window"

def run(dossier_csv, research_file=DEFAULT_RESEARCH, out=None):
    dossier_csv=Path(dossier_csv)
    if not dossier_csv.is_file():
        raise FileNotFoundError("Original evidence dossier CSV missing")
    out=Path(out) if out is not None else dossier_csv.parent/"COMMERCIAL_QUALIFICATION_PILOT"
    if out.resolve()==dossier_csv.parent.resolve():
        raise ValueError("Never overwrite original dossier evidence output folder")
    research=load_research(research_file)
    with dossier_csv.open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        cols=set(reader.fieldnames or [])
        needed={"source_record_id","source_id","site_address","dossier_id",
                "source_stage","commercial_readiness","source_url",
                "source_event_date","source_lookup_key"}
        if not needed.issubset(cols):
            raise ValueError("Incompatible source-dossier schema")
        dossiers_in=list(reader)
    outrows=[];matches=set();refusals=Counter()
    for d in dossiers_in:
        project=graph.clean(d.get("source_record_id",""))
        if d.get("source_id")!="toronto_active_building_permits":
            continue
        found=research.get(project)
        if found:
            expected=graph.normalize_address(found["site_address"])[0]
            actual=graph.normalize_address(d.get("site_address",""))[0]
            if not actual or actual!=expected:
                refusals["EXACT_PROJECT_ID_WITH_DIFFERENT_CIVIC_SITE"]+=1
                found=None
            else:
                matches.add(project)
        priority,action=classify(d,found)
        row={
            "project_id":project,"dossier_id":d["dossier_id"],
            "site_address":d.get("site_address",""),
            "source_record_id":project,"source_stage":d.get("source_stage",""),
            "source_event_date":d.get("source_event_date",""),
            "source_lookup_key":d.get("source_lookup_key",""),
            "company_or_property_org":found["organization"] if found else "",
            "org_role_classification":found["organization_role"] if found else "NOT_VERIFIED",
            "public_business_contact_name":found.get("contact_name","") if found else "",
            "public_business_contact_role":found.get("contact_role","") if found else "",
            "public_business_contact_phone":found.get("contact_phone","") if found else "",
            "public_business_contact_email":found.get("contact_email","") if found else "",
            "source_website":found["source_url"] if found else "",
            "research_date":found["research_as_of"] if found else "",
            "association_evidence_limit":found["association_limit"] if found else "NO_EXACT_SITE_AND_PROJECT_ASSOCIATION",
            "commercial_research_summary":found["context_note"] if found else "",
            "primary_city_record_url":d.get("source_url",""),
            "source_record_evidence_level":d.get("source_url_quality",""),
            "permit_status_held":"YES" if priority=="HOLD_PERMIT_NOT_MARKETABLE" else "NO",
            "contact_is_verified_permit_buyer":"NO",
            "procurement_open_verified":"NO",
            "vendor_work_package_verified":"NO",
            "outreach_authorized":"NO",
            "research_priority":priority,
            "recommended_follow_up":action,
        }
        outrows.append(row)
    outrows.sort(key=lambda x:(
        x["research_priority"]=="HOLD_PERMIT_NOT_MARKETABLE",
        x["research_priority"]=="NO_SOURCE_BACKED_COMPANY_RELATION",
        x["project_id"]))
    out.mkdir(parents=True,exist_ok=True)
    graph.write_csv(out/OUTPUT_CSV,outrows,FIELDS)
    counts=Counter(x["research_priority"] for x in outrows)
    status={
        "mode":"OFFLINE_SOURCE_BACKED_COMMERCIAL_SITE_RESEARCH_NOT_CONFIRMED_BUYERS",
        "dossiers_examined":len(dossiers_in),
        "toronto_permit_dossiers":len(outrows),
        "research_entries":len(research),
        "exact_project_and_civic_site_matches":len(matches),
        "source_backed_org_mentions":sum(bool(x["company_or_property_org"]) and
             x["org_role_classification"] not in {
                 "NO_INDEPENDENT_OPERATOR_IDENTIFIED","MULTI_TENANT_SITE_ROLE_UNKNOWN"}
             for x in outrows),
        "public_business_contact_channels_identified":sum(
             bool(x["public_business_contact_email"] or x["public_business_contact_phone"])
             for x in outrows),
        "rows_without_exact_site_match":dict(refusals),
        "research_records_not_matched_to_dossiers":sorted(set(research)-matches),
        "research_review_tiers":dict(sorted(counts.items())),
        "verified_permit_buyers":0,"verified_open_supplier_contracts":0,
        "outreach_authorized":False,
        "limitations":[
            "Organization and business contact identified for property address ONLY, not project-specific buyer",
            "A leasing agent or property manager is not necessarily a construction procurement decision-maker",
            "A tenant/owner cannot be inferred for a multi-tenant address without suite-level source proof",
            "Permit status and City source date are not live vendor bid availability",
            "No human-confirmed scope, open tender, procurement timing or supplier authority",
            "Contact information is business-facing public information from linked organizational sources",
        ],
        "output_csv":str(out/OUTPUT_CSV),
    }
    (out/OUTPUT_STATUS).write_text(json.dumps(status,indent=2),encoding="utf-8")
    return status

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dossiers",type=Path,required=True)
    p.add_argument("--research",type=Path,default=DEFAULT_RESEARCH)
    p.add_argument("--out",type=Path)
    args=p.parse_args()
    print(json.dumps(run(args.dossiers,args.research,args.out),indent=2))

if __name__=="__main__":
    main()
