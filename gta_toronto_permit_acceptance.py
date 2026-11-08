"""Offline acceptance check for bounded Toronto permit verification batches.

Reads evidence produced by explicit opt-in official CKAN queries. Does not fetch
anything, alter source records, declare a business opening, or authorize outreach.
A matched CKAN row supports SOURCE-RECORD review only; never a supplier contract.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import gta_facility_intelligence as graph
import gta_toronto_permit_evidence as permits

OUTPUT_JSON="GTA_RADAR_TORONTO_SOURCE_ACCEPTANCE.json"
OUTPUT_CSV="GTA_RADAR_TORONTO_ACCEPTANCE_RECORDS.csv"
BATCH_MAX=1000
BATCH_MAX_BYTES=2_000_000
SOURCE_DAYS_MAX=7
MIN_SOURCE_RECORDS=20
MIN_DISTINCT_PROJECTS=15
MIN_DISTINCT_PHYSICAL_SITES=10
FIELDNAMES=(
    "source_key","project_id","permit_num","revision_num",
    "live_checked_at_utc","source_status","source_address","source_query_url",
    "record_validation","stage_evidence_scope","buyer_verified",
    "open_supplier_contract_verified","research_action",
)


def _read_batch(path):
    if path.stat().st_size>BATCH_MAX_BYTES:
        raise ValueError("Saved CKAN acceptance batch exceeds size bound: "+path.name)
    with path.open(encoding="utf-8") as stream:
        data=json.load(stream)
    if not isinstance(data,dict):
        raise ValueError("Saved CKAN evidence batch must be an object")
    if data.get("mode")!="BOUNDED_EXPLICIT_PUBLIC_TORONTO_CKAN_QUERIES":
        raise ValueError("Evidence batch mode is not approved")
    if data.get("resource_id")!=permits.RESOURCE_HINT:
        raise ValueError("Unrecognized Toronto permit source resource")
    if data.get("source_dataset")!=permits.OFFICIAL_DATASET:
        raise ValueError("Unrecognized official source dataset")
    rows=data.get("audit_records")
    original_rows=data.get("original_public_ckan_rows_by_source_key")
    if not isinstance(rows,list) or len(rows)>permits.MAX_LIVE:
        raise ValueError("Evidence batch is not bounded to ten records")
    if not isinstance(original_rows,dict) or len(original_rows)>permits.MAX_LIVE:
        raise ValueError("Evidence batch missing bounded original public source rows")
    if data.get("attempted_records")!=len(rows):
        raise ValueError("Evidence batch attempt count contradicts saved rows")
    timestamp=data.get("retrieved_at_utc","")
    try:
        checked=dt.datetime.fromisoformat(timestamp.replace("Z","+00:00"))
    except (TypeError,ValueError) as exc:
        raise ValueError("Evidence retrieval time missing or malformed") from exc
    if checked.tzinfo is None:
        raise ValueError("Evidence retrieval timestamp must be timezone aware")
    return checked.astimezone(dt.timezone.utc),rows,original_rows


def _validate_remote_url(url,permit_num,revision):
    """Check the exact query metadata, never trust an arbitrary 'official URL'."""
    try:
        parsed=urlsplit(url)
        if (parsed.scheme!="https" or
            parsed.netloc!="ckan0.cf.opendata.inter.prod-toronto.ca" or
            parsed.path!="/api/3/action/datastore_search"):
            return False
        qs=parse_qs(parsed.query)
        if qs.get("resource_id")!=[permits.RESOURCE_HINT]:
            return False
        if len(qs.get("filters",[]))!=1:
            return False
        filters=json.loads(qs["filters"][0])
        return (isinstance(filters,dict) and
                set(filters)=={"PERMIT_NUM","REVISION_NUM"} and
                filters["PERMIT_NUM"]==permit_num and
                filters["REVISION_NUM"]==revision and
                qs.get("limit")==["3"])
    except (TypeError,ValueError,KeyError):
        return False


def _classify(row, original=None):
    key=graph.clean(row.get("source_key",""))
    match=permits.KEY.fullmatch(key)
    if not match:
        return "INVALID_PERMIT_KEY"
    permit=match["folder"]+" "+match["type"]
    revision=match["rev"]
    if row.get("permit_num")!=permit or row.get("revision_num")!=revision:
        return "SOURCE_KEY_FIELD_CONFLICT"
    expected_project=permits.SOURCE+":"+match["folder"]
    if row.get("project_id")!=expected_project:
        return "SOURCE_PROJECT_FOLDER_CONFLICT"
    if row.get("individual_record_retrieved_live")!="YES":
        return "NOT_ACTUALLY_RETRIEVED"
    if row.get("remote_status")!="LIVE_EXACT_KEY_MATCH_OFFICIAL_DATASET":
        return "NOT_EXACT_REMOTE_RECORD"
    if not _validate_remote_url(row.get("remote_query_url",""),
                                permit,revision):
        return "REMOTE_QUERY_PROVENANCE_INVALID"
    if row.get("final_evidence_level")!="OFFICIAL_CKAN_EXACT_KEY_LIVE_RECHECKED":
        return "LIVE_RECORD_STAGE_OR_ADDRESS_NOT_VERIFIED"
    if not row.get("remote_record_status") or not row.get("remote_record_address"):
        return "REMOTE_STATUS_OR_ADDRESS_MISSING"
    if row.get("remote_address_comparison")!="ADDRESS_COMPATIBLE_WITH_AVAILABLE_SNAPSHOTS":
        return "ADDRESS_NOT_COMPATIBLE_WITH_ARCHIVE"
    if not isinstance(original,dict):
        return "ORIGINAL_PUBLIC_SOURCE_PAYLOAD_NOT_SAVED"
    canonical=json.dumps(original,sort_keys=True,ensure_ascii=False,separators=(",",":"))
    digest=hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if row.get("remote_payload_sha256")!=digest:
        return "ORIGINAL_PUBLIC_SOURCE_ROW_HASH_MISMATCH"
    original_permit=graph.clean(original.get("PERMIT_NUM"))
    original_revision=graph.clean(original.get("REVISION_NUM"))
    if original_permit!=permit or original_revision!=revision:
        return "ORIGINAL_PUBLIC_SOURCE_RECORD_KEY_CONFLICT"
    original_status=graph.clean(original.get("STATUS"))
    original_address=permits._official_status_address(original)
    if original_status!=row.get("remote_record_status") or (
            original_address!=row.get("remote_record_address")):
        return "ORIGINAL_SOURCE_ROW_STATUS_OR_SITE_CONTRADICTION"
    if row.get("buyer_verified")!="NO":
        return "UNEXPECTED_BUYER_VERIFICATION_CLAIM"
    if row.get("record_is_a_verified_open_supplier_contract")!="NO":
        return "UNEXPECTED_OPEN_CONTRACT_CLAIM"
    return "EXACT_OFFICIAL_SOURCE_ROW_WITH_ARCHIVED_ADDRESS_COMPATIBLE"


def run(batches_dir, out=None, *, as_of=None, days=SOURCE_DAYS_MAX):
    batches_dir=Path(batches_dir)
    out=Path(out) if out is not None else batches_dir.parent
    as_of=(dt.datetime.fromisoformat(as_of) if isinstance(as_of,str) else
           as_of or dt.datetime.now(dt.timezone.utc))
    if isinstance(as_of,dt.date) and not isinstance(as_of,dt.datetime):
        as_of=dt.datetime.combine(as_of,dt.time.min,tzinfo=dt.timezone.utc)
    if as_of.tzinfo is None:
        raise ValueError("Acceptance as_of must specify a timezone")
    as_of=as_of.astimezone(dt.timezone.utc)
    days=max(1,min(int(days),30))
    if out.resolve()==batches_dir.resolve():
        raise ValueError("Acceptance reports must not overwrite evidence batch folder")
    files=sorted(batches_dir.glob("TORONTO_CKAN_EXACT_CHECK_*_OFFSET_*.json")) if batches_dir.is_dir() else []
    if len(files)>BATCH_MAX:
        raise ValueError("Too many saved CKAN batches to review safely")
    recent={}
    rejected=Counter()
    total_records=0
    for path in files:
        try:
            checked,rows,original_rows=_read_batch(path)
        except (ValueError,OSError,UnicodeError,json.JSONDecodeError) as exc:
            rejected["MALFORMED_OR_UNTRUSTED_BATCH"]+=1
            continue
        if (as_of-checked).total_seconds() < -3600 or (as_of-checked).days>days:
            rejected["OUTSIDE_RECENT_VERIFICATION_WINDOW"]+=1
            continue
        for row in rows:
            total_records+=1
            state=_classify(row,original_rows.get(row.get("source_key","")))
            if state!="EXACT_OFFICIAL_SOURCE_ROW_WITH_ARCHIVED_ADDRESS_COMPATIBLE":
                rejected[state]+=1
                continue
            key=row["source_key"]
            prev=recent.get(key)
            if prev is None or checked>prev[0]:
                recent[key]=(checked,row)
    records=[]
    for key,(checked,row) in sorted(recent.items(),key=lambda i:i[0]):
        records.append({
            "source_key":key,"project_id":row["project_id"],
            "permit_num":row["permit_num"],"revision_num":row["revision_num"],
            "live_checked_at_utc":checked.isoformat(),
            "source_status":row["remote_record_status"],
            "source_address":row["remote_record_address"],
            "source_query_url":row["remote_query_url"],
            "record_validation":"EXACT_OFFICIAL_SOURCE_ROW_WITH_ARCHIVED_ADDRESS_COMPATIBLE",
            "stage_evidence_scope":"PUBLIC_CKAN_DATASET_STATUS_AS_RETRIEVED_NOT_CURRENT_INSPECTION_OR_APPROVAL",
            "buyer_verified":"NO","open_supplier_contract_verified":"NO",
            "research_action":"Manually verify City permit status and independently establish project buyer/procurement",
        })
    projects={r["project_id"] for r in records}
    physical_sites={r["source_address"] for r in records}
    stage_buckets={permits._stage_bucket(r["source_status"]) for r in records}
    sample_gate=(len(records)>=MIN_SOURCE_RECORDS and
                 len(projects)>=MIN_DISTINCT_PROJECTS and
                 len(physical_sites)>=MIN_DISTINCT_PHYSICAL_SITES and
                 len(stage_buckets)>=2 and
                 not any(k in rejected for k in ("UNEXPECTED_BUYER_VERIFICATION_CLAIM",
                                                 "UNEXPECTED_OPEN_CONTRACT_CLAIM")))
    # Source-record acceptance is NOT a release or customer-readiness gate.
    result={
        "mode":"OFFLINE_SAVED_PUBLIC_CKAN_SOURCE_RECORD_ACCEPTANCE",
        "as_of_utc":as_of.isoformat(),
        "age_window_days":days,
        "batch_files_seen":len(files),
        "batch_files_rejected_or_unreadable":rejected["MALFORMED_OR_UNTRUSTED_BATCH"],
        "recheck_row_attempts_in_eligible_batches":total_records,
        "recent_unique_exact_ckan_source_records":len(records),
        "distinct_project_folders_rechecked":len(projects),
        "distinct_physical_sites_rechecked":len(physical_sites),
        "source_stage_buckets_covered":sorted(stage_buckets),
        "rejected_or_unproven_counts":dict(sorted(rejected.items())),
        "source_sample_threshold":MIN_SOURCE_RECORDS,
        "distinct_project_threshold":MIN_DISTINCT_PROJECTS,
        "distinct_physical_site_threshold":MIN_DISTINCT_PHYSICAL_SITES,
        "official_source_sample_gate_passed":sample_gate,
        "field_human_reviewer_approved":False,
        "buyer_and_open_procurement_verified":False,
        "commercial_production_accepted":False,
        "user_outreach_authorized":False,
        "caveats":[
            "This is a sampled original public record ledger, not complete Toronto coverage.",
            "The City dataset may be updated on a different schedule from the building-permit status application.",
            "An exact original record and matching address do not identify tenant, supplier, buyer or available project work.",
            "No human original-record review, procurement, licensing or buyer attestation is accepted here.",
            "Only bounded exact-record batches with preserved original public CKAN rows and matching hashes count.",
            "Saved local source rows and hashes can still be falsified; acceptance is not independent City attestation.",
            "Malformed and stale verification batches cannot inflate the accepted source count.",
        ],
        "records_csv":str(out/OUTPUT_CSV),
    }
    out.mkdir(parents=True,exist_ok=True)
    graph.write_csv(out/OUTPUT_CSV,records,FIELDNAMES)
    (out/OUTPUT_JSON).write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--batches",type=Path,required=True,
                   help="TORONTO_PERMIT_EVIDENCE_PILOT/LIVE_VERIFICATION_BATCHES")
    p.add_argument("--out",type=Path)
    p.add_argument("--as-of",help="Timezone-aware ISO timestamp")
    p.add_argument("--days",type=int,default=SOURCE_DAYS_MAX)
    args=p.parse_args()
    print(json.dumps(run(args.batches,args.out,as_of=args.as_of,days=args.days),
                     indent=2))


if __name__=="__main__":
    main()
