"""Bounded City of Toronto CKAN connectivity and exact-key schema smoke test.

Runs only when explicitly invoked as a standalone command or a dedicated PR
workflow. It does NOT run Radar, fetch all records, write its SQLite database,
schedule a job, or validate any buyer or purchase. Produces only non-personal
permit identifiers/status metadata. No raw source records are persisted.

This module intentionally exits nonzero when public source connectivity or
schema validation fails. An unreachable official API is a failed smoke test,
not successful live evidence.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import gta_toronto_permit_evidence as permits

FIELDS_REQUIRED={
    "PERMIT_NUM", "REVISION_NUM", "STREET_NUM",
    "STREET_NAME", "STATUS"
}


def probe_one(kind, package, expected_resource, fetch):
    result={"kind":kind,"package":package,"expected_resource":expected_resource,
            "package_metadata_verified":False,
            "datastore_resource_active":False,
            "field_schema_verified":False,
            "exact_key_datastore_query_verified":False,
            "source_data_last_modified":None,
            "sample_permit_number":None,
            "sample_revision":None,
            "sample_status":None,
            "error":None}
    try:
        meta,_=permits._official_action("package_show",{"id":package},fetch)
        if meta.get("name")!=package:
            raise ValueError("Unexpected CKAN package identity")
        result["package_metadata_verified"]=True
        resources=meta.get("resources") or []
        matching=[r for r in resources if r.get("id")==expected_resource and
                  r.get("datastore_active") is True]
        if len(matching)!=1:
            raise ValueError("Expected permit DataStore resource ID not active")
        result["datastore_resource_active"]=True
        result["source_data_last_modified"]=matching[0].get("last_modified")
        sample,_=permits._official_action("datastore_search",
            {"resource_id":expected_resource,"limit":1},fetch)
        rows=sample.get("records")
        if not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict):
            raise ValueError("Unexpected CKAN sample record schema")
        raw=rows[0]
        missing=FIELDS_REQUIRED-set(raw)
        if missing:
            raise ValueError("Official CKAN record missing fields: "+",".join(sorted(missing)))
        result["field_schema_verified"]=True
        permit=permits.clean(raw.get("PERMIT_NUM"))
        revision=permits.clean(raw.get("REVISION_NUM"))
        if not permit or not revision or not permits.KEY.fullmatch(permit+"|"+revision):
            raise ValueError("Unexpected CKAN original permit/revision key format")
        result["sample_permit_number"]=permit
        result["sample_revision"]=revision
        result["sample_status"]=permits.clean(raw.get("STATUS"))
        state,matched,_=permits._remote_record(permit,revision,expected_resource,fetch)
        if state!="LIVE_EXACT_KEY_MATCH_OFFICIAL_DATASET":
            raise ValueError("Exact permit+revision filter returned "+state)
        if (permits.clean(matched.get("PERMIT_NUM"))!=permit or
                permits.clean(matched.get("REVISION_NUM"))!=revision):
            raise ValueError("Exact-filter returned contradictory record identity")
        result["exact_key_datastore_query_verified"]=True
    except Exception as exc:
        # No personal data or response body is written to logs/artifacts.
        result["error"]=type(exc).__name__+": "+str(exc)[:220]
    return result


def run(out,fetch=permits._get_payload):
    result={
        "mode":"ISOLATED_TORONTO_CKAN_API_SCHEMA_SMOKE_NO_RADAR_COLLECTION",
        "timestamp_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "official_active_dataset":permits.OFFICIAL_DATASET,
        "official_cleared_dataset":permits.OFFICIAL_CLEARED_DATASET,
        "source_licence_attribution":permits.TORONTO_LICENSE,
        "source_licence_url":permits.TORONTO_LICENSE_URL,
        "live_exact_project_export_verified":False,
        "buyer_verified":False,
        "open_procurement_verified":False,
        "sample_records_are_unrelated_to_user_export":True,
        "results":[
            probe_one("active",permits.PACKAGE,permits.RESOURCE_HINT,fetch),
            probe_one("cleared",permits.CLEARED_PACKAGE,
                      permits.CLEARED_RESOURCE_HINT,fetch)
        ]
    }
    result["api_schema_acceptance_passed"]=all(
        x["package_metadata_verified"] and x["datastore_resource_active"]
        and x["field_schema_verified"] and x["exact_key_datastore_query_verified"]
        for x in result["results"])
    out=Path(out)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,
        default=Path("toronto_ckan_connectivity_report.json"))
    args=parser.parse_args()
    result=run(args.out)
    print(json.dumps(result,indent=2,ensure_ascii=False))
    if not result["api_schema_acceptance_passed"]:
        raise SystemExit(2)


if __name__=="__main__":
    main()
