"""PR-only, twenty-record official Toronto permit scope/value evidence check.

Uses the existing archived 20-record sample from Radar; reads each *exact*
PERMIT_NUM + REVISION_NUM from Toronto's official CKAN active-permit DataStore.
Does not fetch personal names, vendor emails, business contact fields, or
complete public row. Source descriptions are truncated and sanitized for
potential phone/email details. They are NOT company-identity proof.

No collector run, user database, schedule, DeepSeek, or outreach.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

import gta_toronto_permit_evidence as permit
import gta_facility_intelligence as graph
import gta_toronto_archived_source_validation as fixture_validation

FIELDS=(
    "project_id","source_key","civic_site","source_status",
    "source_date","source_work_type","scope_summary_unverified",
    "city_estimated_construction_cost_cad","value_field_name",
    "scope_field_name","exact_ckan_identity_verified",
    "archived_civic_address_compatible","source_scope_requires_human_review",
    "buyer_verified","procurement_open_verified","tenant_verified",
    "official_query_url","retrieved_at_utc","record_projection_sha256",
)
WORK_FIELDS=("WORK","WORK_TYPE")
DESCRIPTION_FIELDS=("DESCRIPTION","PROPOSAL_DESCRIPTION","WORK_DESCRIPTION")
COST_FIELDS=("EST_CONST_COST","ESTIMATED_CONSTRUCTION_COST","CONST_VALUE",
             "CONSTRUCTION_VALUE","EST_CONSTRUCTION_COST","EST_PROJECT_COST")
EMAIL=re.compile(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}",re.I)
PHONE=re.compile(r"(?<!\w)(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}(?!\w)")
MAX=20

def source_text(row,fields):
    for name in fields:
        value=graph.clean(row.get(name,""))
        if value:return name,value
    return "",""

def clean_scope(value):
    value=graph.clean(value)
    value=EMAIL.sub("[email redacted]",value)
    value=PHONE.sub("[phone redacted]",value)
    return value[:600]

def run(out,fetch=permit._get_payload):
    sample=fixture_validation.validate_fixture(fixture_validation.FIXTURE)
    # Fixture validation returns original rows; only exact source-key requests.
    if len(sample)!=MAX: raise ValueError("Expected exactly twenty original source keys")
    resource,_=permit._resource(fetch)
    checked_at=dt.datetime.now(dt.timezone.utc).isoformat()
    records=[]
    for entry in sample:
        keys,reason=permit.split_source_keys(entry)
        if reason or len(keys)!=1:raise ValueError("Invalid source fixture permit revision")
        source_key,permit_num,revision=keys[0]
        status,raw,query_url=permit._remote_record(permit_num,revision,resource,fetch)
        exact=status=="LIVE_EXACT_KEY_MATCH_OFFICIAL_DATASET"
        city_address=permit._official_status_address(raw) if exact else ""
        export_address=graph.normalize_address(entry.get("address",""))[0]
        address_match=bool(exact and city_address and export_address==city_address)
        work_field,work=source_text(raw,WORK_FIELDS)
        scope_field,scope=source_text(raw,DESCRIPTION_FIELDS)
        value_field,value=source_text(raw,COST_FIELDS)
        # Exact original address/ID is necessary to report associated scope.
        # A source record with mismatching site may not be attached to Radar.
        if not (exact and address_match):
            scope="";value=""
        projection={
            "permit_num":permit_num,"revision":revision,
            "site":city_address,"status":graph.clean(raw.get("STATUS")),
            "work":work,"scope":clean_scope(scope),
            "estimated_cost":value
        }
        digest=hashlib.sha256(json.dumps(projection,sort_keys=True,
             ensure_ascii=False,separators=(",",":")).encode("utf-8")).hexdigest()
        records.append({
            "project_id":entry["project_id"],"source_key":source_key,
            "civic_site":city_address,"source_status":projection["status"],
            "source_date":graph.clean(raw.get("APPLICATION_DATE")),
            "source_work_type":work,
            "scope_summary_unverified":clean_scope(scope),
            "city_estimated_construction_cost_cad":value,
            "value_field_name":value_field,"scope_field_name":scope_field,
            "exact_ckan_identity_verified":"YES" if exact else "NO",
            "archived_civic_address_compatible":"YES" if address_match else "NO",
            "source_scope_requires_human_review":"YES",
            "buyer_verified":"NO","procurement_open_verified":"NO",
            "tenant_verified":"NO","official_query_url":query_url,
            "retrieved_at_utc":checked_at,"record_projection_sha256":digest
        })
    result={
        "mode":"OFFICIAL_TORONTO_20_PERMIT_SCOPE_FIELDS_RESEARCH_ONLY",
        "retrieved_at_utc":checked_at,
        "source_licence_attribution":permit.TORONTO_LICENSE,
        "source_licence_url":permit.TORONTO_LICENSE_URL,
        "rows_requested":len(sample),
        "exact_identity_and_address_matches":sum(
            x["exact_ckan_identity_verified"]=="YES" and
            x["archived_civic_address_compatible"]=="YES" for x in records),
        "rows_with_scope_text":sum(bool(x["scope_summary_unverified"]) for x in records),
        "rows_with_city_estimated_cost":sum(bool(x["city_estimated_construction_cost_cad"])
                                           for x in records),
        "vendor_or_tenant_buyer_verified":0,
        "supplier_contracts_open_verified":0,
        "no_personal_builder_fields_exported":True,
        "caveat":"A City permit description and estimated construction cost are not a "
                 "quote, tender, available purchase, or proven tenant/contractor.",
        "records":records,
    }
    out=Path(out)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    # Print only fields needed for research; do not log raw source rows.
    for x in records:
        print(json.dumps({
            "project_id":x["project_id"],
            "source_key":x["source_key"],
            "site":x["civic_site"],"status":x["source_status"],
            "work":x["source_work_type"],
            "scope":x["scope_summary_unverified"],
            "cost":x["city_estimated_construction_cost_cad"],
            "cost_field":x["value_field_name"],
            "scope_field":x["scope_field_name"],
            "exact":x["exact_ckan_identity_verified"],
            "address_compatible":x["archived_civic_address_compatible"]
        },ensure_ascii=False))
    print(json.dumps({"rows_requested":result["rows_requested"],
                      "exact_and_address_matched":result["exact_identity_and_address_matches"],
                      "with_scope":result["rows_with_scope_text"],
                      "with_cost":result["rows_with_city_estimated_cost"]}))
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    r=run(args.out)
    if r["exact_identity_and_address_matches"]!=MAX:
        raise SystemExit(2)

if __name__=="__main__":
    main()
