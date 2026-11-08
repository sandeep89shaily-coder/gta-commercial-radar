"""Toronto permit commercial qualification: primary scope + public work routes.

Offline research join of exact City source-checked permits and separately
documented public business contact routes. This never represents landlord,
property manager, leasing broker, or a proposed tenant as a verified buyer.
Never discovers/scrapes personal contacts, contacts anyone, calls APIs, or
modifies the main Radar, its source database, or the schedule.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import gta_facility_intelligence as graph

ROOT=Path(__file__).resolve().parent
SCOPES=ROOT/"research"/"toronto_20_city_exact_scope_20261108.json"
CONTACTS=ROOT/"research"/"toronto_20_public_business_contact_routes_20261108.json"
OUTPUT="GTA_RADAR_TORONTO_20_COMMERCIAL_QUALIFICATION.csv"
CONTACT_OUTPUT="GTA_RADAR_TORONTO_PUBLIC_CONTACT_ROUTES_AUDIT.csv"
STATUS_OUTPUT="GTA_RADAR_TORONTO_20_COMMERCIAL_STATUS.json"
FIELDS=(
    "rank","project_id","source_key","site_address","municipal_status",
    "qualification_category","research_priority","city_scope_description",
    "estimated_construction_cost_cad","potential_supplier_work_packages",
    "organization_association","public_contact_type","public_company_contact",
    "public_business_phone","public_business_email","contact_source_url",
    "exact_city_permit_source_url","permit_identity_and_site_verified",
    "project_buyer_verified","available_supplier_contract_verified",
    "general_contractor_verified","procurement_stage_verified",
    "outreach_authorized","qualification_blockers","next_verification_action",
)
CONTACT_FIELDS=(
    "project_id","site_address","organization","public_contact_name",
    "job_title_or_channel","public_business_phone","public_business_email",
    "contact_role_type","primary_evidence_url",
    "site_organization_association_verified",
    "project_specific_purchasing_authority_verified",
    "open_supplier_package_verified","outreach_authorized",
    "qualification_limit",
)
BLOCKED=("Refusal Notice","Application On Hold","Revocation Pending",
         "Cancellation Pending","Revoked","Cancelled","Withdrawn","Denied")
ISSUED=("Permit Issued","Revision Issued")
POSSIBLE_PACKAGES=(
    (("skylight","glazing"),"Skylight / commercial glazing / waterproofing / structural / drainage"),
    (("basket ball","basketball"),"Sports studio interior improvements / HVAC / finishes"),
    (("pharmacy",),"Pharmacy tenant fit-out / lighting / plumbing / security / HVAC"),
    (("coffee shop","restaurant"),"Hospitality fit-out / ventilation / plumbing / fire systems"),
    (("domestic cold water","domestic/fire"),"Building plumbing / domestic water and fire-feed coordination"),
    (("elevator lobbies","corridors"),"Commercial interior finishes / plumbing / partitions"),
    (("broadcasting","studios"),"Broadcasting studio fit-out / electrical / HVAC / acoustics"),
    (("dental office","wellness centre"),"Health-clinic interior fit-out / plumbing / ventilation"),
    (("office","tenant"),"Office tenant interior improvements / partitions / mechanical / electrical"),
    (("fire rated walls",),"Fire-rated walls / code compliance / interior partitions"),
)


def load(path, collection):
    obj=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj,dict) or not isinstance(obj.get(collection),list):
        raise ValueError("Expected source-research JSON records: "+str(path))
    return obj[collection]


def normalized_cost(cost):
    if isinstance(cost,bool):return None
    if isinstance(cost,(int,float)) and 0<cost<100_000_000_000:
        return cost
    return None


def qualification(status):
    state=graph.clean(status)
    if state in BLOCKED:
        return "HOLD_SOURCE_STATUS",4,"Verify whether blocked/refused permit was resubmitted and approved; no outreach."
    if state in ISSUED:
        return "ISSUED_AWARD_RISK",2,"Identify existing general contractor and whether any subcontractor packages remain unawarded."
    if state=="Not Started":
        return "PRE_START_RESEARCH",1,"Identify developer/tenant project manager; check whether suppliers were already selected."
    if state=="Application Acceptable":
        return "PRE_APPROVAL_RESEARCH",1,"Recheck permit milestone; identify project owner/GC and sourcing process."
    return "STATUS_UNKNOWN_RECHECK",3,"Confirm specific municipal status and tender timing before qualification."


def possible_packages(description):
    text=graph.clean(description).lower()
    for needles,packages in POSSIBLE_PACKAGES:
        if any(n in text for n in needles):
            return packages
    return "Project-specific trade scope not sufficiently identified; inspect primary drawings"


def build(scope_rows,contact_rows):
    if len(scope_rows)!=20:
        raise ValueError("Twenty exact City source records are required")
    project_ids=set()
    for r in scope_rows:
        pid=r.get("project_id","")
        if pid in project_ids or r.get("exact_ckan_identity_verified") not in (True,"YES"):
            raise ValueError("Duplicate or unverified exact City permit ID")
        if r.get("archived_civic_address_compatible") not in (True,"YES"):
            raise ValueError("Unverified City physical-site association")
        project_ids.add(pid)
    by_project=defaultdict(list)
    exclusions=Counter()
    safe_contacts=[]
    for r in contact_rows:
        pid=r.get("project_id","")
        expected=next((x for x in scope_rows if x["project_id"]==pid),None)
        if expected is None:
            exclusions["NO_EXACT_PROJECT_ID"]+=1
            continue
        actual_city=graph.normalize_address(expected["civic_site"])[0]
        contact_city=graph.normalize_address(r.get("site_address",""))[0]
        if not actual_city or contact_city!=actual_city:
            exclusions["ADDRESS_MISMATCH"]+=1
            continue
        url=graph.https(r.get("primary_evidence_url",""))
        if not url:
            exclusions["INVALID_OR_UNTRUSTED_CONTACT_URL"]+=1
            continue
        # Contact leads are public reference routes, NOT authenticated
        # decisions of buying authority or open procurement.
        r=dict(r,
               primary_evidence_url=url,
               project_specific_purchasing_authority_verified=False,
               open_supplier_package_verified=False,
               outreach_authorized=False)
        by_project[pid].append(r)
        safe_contacts.append(r)
    outputs=[]
    for source in scope_rows:
        stage=graph.clean(source["source_status"])
        category,order,action=qualification(stage)
        contacts=by_project[source["project_id"]]
        reference=contacts[0] if contacts else {}
        block=["BUYER_ROLE_UNVERIFIED","PROCUREMENT_STATUS_NOT_VERIFIED",
               "GENERAL_CONTRACTOR_NOT_VERIFIED","OPEN_SUPPLIER_PACKAGE_NOT_VERIFIED",
               "CITY_ESTIMATED_COST_NOT_SUPPLIER_CONTRACT"]
        if not contacts:block.append("PUBLIC_COMPANY_CHANNEL_NOT_YET_RESEARCHED")
        if category=="HOLD_SOURCE_STATUS":block.append("BLOCKED_MUNICIPAL_PERMIT_STAGE")
        if category=="ISSUED_AWARD_RISK":block.append("POSSIBLE_ALREADY_AWARDED")
        if normalized_cost(source.get("city_estimated_cost_cad")) is None:
            block.append("NO_VALID_NUMERIC_CITY_COST")
        outputs.append({
            "rank":0,"project_id":source["project_id"],
            "source_key":source["permit_key"],
            "site_address":source["civic_site"],"municipal_status":stage,
            "qualification_category":category,"research_priority":order,
            "city_scope_description":source["city_scope"],
            "estimated_construction_cost_cad":normalized_cost(
                source.get("city_estimated_cost_cad")),
            "potential_supplier_work_packages":possible_packages(source["city_scope"]),
            "organization_association":"; ".join(
                sorted({r.get("organization","") for r in contacts if r.get("organization")})),
            "public_contact_type":"; ".join(
                sorted({r.get("contact_role_type","") for r in contacts if r.get("contact_role_type")})),
            "public_company_contact":reference.get("public_contact_name",""),
            "public_business_phone":reference.get("public_business_phone",""),
            "public_business_email":reference.get("public_business_email",""),
            "contact_source_url":reference.get("primary_evidence_url",""),
            "exact_city_permit_source_url":source["source_url"],
            "permit_identity_and_site_verified":"YES",
            "project_buyer_verified":"NO",
            "available_supplier_contract_verified":"NO",
            "general_contractor_verified":"NO",
            "procurement_stage_verified":"NO",
            "outreach_authorized":"NO",
            "qualification_blockers":";".join(block),
            "next_verification_action":action,
        })
    outputs.sort(key=lambda r:(
        r["research_priority"],-int(bool(r["organization_association"])),
        -(r["estimated_construction_cost_cad"] or 0),r["site_address"]))
    for index,row in enumerate(outputs,1):row["rank"]=index
    return outputs,safe_contacts,dict(exclusions)



def validated_city_scope(row):
    """Fail closed on a mismatched source lookup; never synthesize City verification."""
    import re
    project=graph.clean(row.get("project_id",""))
    key=graph.clean(row.get("permit_key",""))
    match=re.fullmatch(r"(\d{2} \d{6}) ([A-Z]{3})\|(\d{2})",key)
    if not match or project!="toronto_active_building_permits:"+match.group(1):
        raise ValueError("City permit project ID and exact revision key mismatch")
    if row.get("source_lookup_validation")!="EXACT_PERMIT_AND_REVISION_AND_CIVIC_ADDRESS_MATCH_CITY_DATASET":
        raise ValueError("City exact permit source lookup validation missing")
    if graph.clean(row.get("city","")).lower()!="toronto" or not graph.normalize_address(row.get("site_address",""))[0]:
        raise ValueError("City exact permit site missing or incompatible")
    url=graph.clean(row.get("source_url",""))
    parsed=urlsplit(url)
    if parsed.scheme!="https" or parsed.hostname!="ckan0.cf.opendata.inter.prod-toronto.ca" or parsed.path!="/api/3/action/datastore_search":
        raise ValueError("City permit lookup URL is not the official exact-record endpoint")
    params=parse_qs(parsed.query,keep_blank_values=True)
    if set(params)!={"resource_id","filters","limit"} or any(len(v)!=1 for v in params.values()):
        raise ValueError("City exact-record lookup parameters invalid")
    if params["resource_id"][0]!="6d0229af-bc54-46de-9c2b-26759b01dd05" or params["limit"][0]!="3":
        raise ValueError("City permit source resource or row limit unexpected")
    try:
        filters=json.loads(params["filters"][0])
    except (TypeError,ValueError) as exc:
        raise ValueError("City exact-record lookup filters malformed") from exc
    if filters!={"PERMIT_NUM":match.group(1)+" "+match.group(2),"REVISION_NUM":match.group(3)}:
        raise ValueError("City permit source URL does not match imported ID/revision")
    return True

def run(scope=SCOPES,contacts=CONTACTS,out=None):
    scope_rows=load(scope,"records")
    contact_rows=load(contacts,"rows")
    # Source JSON contract uses different but explicit field names. No fuzzy.
    clean_scope=[]
    for x in scope_rows:
        validated_city_scope(x)
        clean_scope.append({
            "project_id":x["project_id"],
            "permit_key":x["permit_key"],
            "civic_site":x["site_address"],
            "source_status":x["city_status"],
            "city_scope":x["city_scope"],
            "city_estimated_cost_cad":x.get("city_estimated_cost_cad"),
            "source_url":x["source_url"],
            "exact_ckan_identity_verified":True,
            "archived_civic_address_compatible":True,
        })
    records,verified_routes,exclusions=build(clean_scope,contact_rows)
    out=Path(out) if out else Path("TORONTO_COMMERCIAL_QUALIFICATION_PILOT")
    out.mkdir(parents=True,exist_ok=True)
    graph.write_csv(out/OUTPUT,records,FIELDS)
    graph.write_csv(out/CONTACT_OUTPUT,verified_routes,CONTACT_FIELDS)
    counts=Counter(x["qualification_category"] for x in records)
    summary={
        "mode":"OFFLINE_TORONTO_EXACT_SCOPE_COMMERCIAL_RESEARCH_ONLY",
        "original_city_source_checked_permit_count":len(records),
        "numeric_city_construction_estimates":sum(
            x["estimated_construction_cost_cad"] is not None for x in records),
        "total_city_construction_estimates_not_contract_value_cad":sum(
            x["estimated_construction_cost_cad"] or 0 for x in records),
        "public_business_routes_with_site_match":len(verified_routes),
        "projects_with_public_business_routes":len({
            x["project_id"] for x in verified_routes}),
        "rejected_public_contact_hints":exclusions,
        "qualification_groups":dict(counts),
        "project_buyers_verified":0,"general_contractors_verified":0,
        "open_supplier_packages_verified":0,"outreach_authorized":False,
        "source_licence_attribution":"Contains information licensed under the Open Government Licence – Toronto.",
        "source_licence_url":"https://open.toronto.ca/open-data-licence/",
        "limitations":[
            "City project values are estimates for permits, not supplier tender or project awards",
            "Proposed tenant use, property manager or leasing broker is not proven buying authority",
            "Even issued permits may have awarded supply packages",
            "This is a manual research shortlist, NOT a buyer-ready pipeline",
            "Contact association is site-verified and requires role verification before using it for sales",
        ],
        "output_csv":str(out/OUTPUT),"contact_audit_csv":str(out/CONTACT_OUTPUT),
    }
    (out/STATUS_OUTPUT).write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scopes",type=Path,default=SCOPES)
    p.add_argument("--contacts",type=Path,default=CONTACTS)
    p.add_argument("--out",type=Path)
    args=p.parse_args()
    print(json.dumps(run(args.scopes,args.contacts,args.out),indent=2))

if __name__=="__main__":
    main()
