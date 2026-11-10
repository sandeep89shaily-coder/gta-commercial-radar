"""Offline, proof-gated Toronto source evidence overlay for facility dossiers.

Reads existing facility dossier CSV and saved City exact-permit source acceptance
exports. Never modifies either input. Verifies the SHA-256 of the accepted source
CSV and requires the source-only gate to pass; exact original project ID, permit
key, municipality and civic site must all match before linking evidence.

One exact permit/revision is NEVER proof of all permits in its project folder,
a commercial tenant, purchasing authority, a supplier opportunity or permission
to contact anyone. The source stage and the original *project summary* stage are
shown separately, without claiming they were ever the same constituent stage.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import gta_facility_intelligence as graph
import gta_facility_dossiers as dossiers
import gta_toronto_permit_evidence as permits
import gta_toronto_permit_acceptance as acceptance

OUTPUT_CSV="GTA_RADAR_TORONTO_DOSSIER_SOURCE_EVIDENCE.csv"
OUTPUT_JSON="GTA_RADAR_TORONTO_DOSSIER_SOURCE_STATUS.json"
FIELDS=(
    "dossier_id","event_id","project_id","city","site_address",
    "verified_permit_revision_key","original_project_permit_key_count",
    "original_project_stage","exact_permit_source_stage",
    "source_stage_comparison","source_stage_bucket",
    "exact_permit_source_evidence_level","source_checked_at_utc",
    "source_record_age_days","official_city_filtered_query_url",
    "source_licence_attribution","original_project_full_status_verified",
    "buyer_verified","procurement_verified","open_supplier_contract_verified",
    "outreach_authorized","commercial_research_status","next_review_action",
)
REQUIRED_DOSSIERS={
    "dossier_id","event_id","source_family","source_id","source_record_id",
    "source_lookup_key","city","site_address","source_stage",
}
REQUIRED_ACCEPTANCE={
    "source_key","project_id","permit_num","revision_num",
    "source_address","source_status","source_query_url",
    "record_validation","live_checked_at_utc","buyer_verified",
    "open_supplier_contract_verified",
}
SOURCE_EVIDENCE="EXACT_OFFICIAL_SOURCE_ROW_WITH_ARCHIVED_ADDRESS_COMPATIBLE"


def _utc(as_of):
    if as_of is None:
        return dt.datetime.now(dt.timezone.utc)
    stamp=dt.datetime.fromisoformat(as_of) if isinstance(as_of,str) else as_of
    if stamp.tzinfo is None:
        raise ValueError("Reference time must include timezone")
    return stamp.astimezone(dt.timezone.utc)


def _read_csv(path,needed):
    with Path(path).open(encoding="utf-8-sig",newline="") as stream:
        reader=csv.DictReader(stream)
        missing=set(needed)-set(reader.fieldnames or [])
        if missing:
            raise ValueError("Incompatible evidence schema "+str(path)+": "+
                             ",".join(sorted(missing)))
        return list(reader)


def _source_gate(permit_dir):
    manifest=permit_dir/acceptance.OUTPUT_JSON
    csvpath=permit_dir/acceptance.OUTPUT_CSV
    if not manifest.is_file() or not csvpath.is_file():
        return False,"NO_ACCEPTED_CITY_SOURCE_EVIDENCE",[]
    with manifest.open(encoding="utf-8") as file:
        status=json.load(file)
    if (not isinstance(status,dict) or
        status.get("official_source_sample_gate_passed") is not True or
        status.get("commercial_production_accepted") is not False or
        status.get("buyer_and_open_procurement_verified") is not False or
        status.get("integrity_or_source_mismatch_rejection_count")!=0):
        return False,"OFFICIAL_SOURCE_SAMPLE_GATE_NOT_PASSED",[]
    expected=status.get("accepted_active_csv_sha256","")
    if len(expected)!=64 or hashlib.sha256(csvpath.read_bytes()).hexdigest()!=expected:
        raise ValueError("Accepted City CSV differs from source gate manifest")
    return True,"SOURCE_SAMPLE_ACCEPTED_FOR_RESEARCH_ONLY",_read_csv(
        csvpath,REQUIRED_ACCEPTANCE)


def _row(dossier, key="", cityrecord=None, *, reason="NOT_IN_APPROVED_SAMPLE",
         age_days=None, key_count=0):
    cityrecord=cityrecord or {}
    stage=cityrecord.get("source_status","")
    original_stage=dossier.get("source_stage","")
    changed=bool(stage and original_stage and stage!=original_stage)
    if not stage:
        comparison="NO_VERIFIED_EXACT_PERMIT_STAGE"
    elif key_count>1 and changed:
        comparison="PROJECT_AGGREGATE_DIFFERS_NOT_PROOF_OF_INDIVIDUAL_STAGE_CHANGE"
    elif changed:
        comparison="SINGLE_CONSTITUENT_STAGE_DIFFERS_FROM_ARCHIVED_SNAPSHOT"
    else:
        comparison="STAGE_MATCHES_ARCHIVED_PROJECT_SUMMARY"
    bucket=permits._stage_bucket(stage) if stage else ""
    if stage and bucket=="BLOCKED":
        review="BLOCKED_PERMIT_REVIEW_ONLY"
        next_action="Recheck original City refusal/hold/revocation record; not an active buyer lead."
    elif stage:
        review="SOURCE_PERMIT_CONFIRMED_COMMERCIAL_PROSPECT_UNVERIFIED"
        next_action="Verify project operator, exact work scope and whether supplier procurement remains available."
    else:
        review="INDIVIDUAL_CITY_SOURCE_EVIDENCE_NOT_AVAILABLE"
        next_action="Check the exact original permit/revision with the City before evaluating purchase intent."
    if reason!="ACCEPTED_EXACT_CITY_RECORD":
        review="SOURCE_ID_OR_SITE_EVIDENCE_NOT_ACCEPTED"
        next_action="Resolve exact permit ID, source evidence, expiry and physical site."
    return {
        "dossier_id":dossier["dossier_id"],
        "event_id":dossier["event_id"],
        "project_id":dossier["source_record_id"],
        "city":dossier["city"],
        "site_address":dossier["site_address"],
        "verified_permit_revision_key":key if reason=="ACCEPTED_EXACT_CITY_RECORD" else "",
        "original_project_permit_key_count":key_count,
        "original_project_stage":original_stage,
        "exact_permit_source_stage":stage if reason=="ACCEPTED_EXACT_CITY_RECORD" else "",
        "source_stage_comparison":comparison if reason=="ACCEPTED_EXACT_CITY_RECORD" else reason,
        "source_stage_bucket":bucket if reason=="ACCEPTED_EXACT_CITY_RECORD" else "",
        "exact_permit_source_evidence_level":reason,
        "source_checked_at_utc":cityrecord.get("live_checked_at_utc","")
                                 if reason=="ACCEPTED_EXACT_CITY_RECORD" else "",
        "source_record_age_days":age_days if age_days is not None else "",
        "official_city_filtered_query_url":cityrecord.get("source_query_url","")
                                 if reason=="ACCEPTED_EXACT_CITY_RECORD" else "",
        "source_licence_attribution":permits.TORONTO_LICENSE,
        "original_project_full_status_verified":"NO",
        "buyer_verified":"NO","procurement_verified":"NO",
        "open_supplier_contract_verified":"NO","outreach_authorized":"NO",
        "commercial_research_status":review,
        "next_review_action":next_action,
    }


def run(dossier_dir,permit_dir,out=None,*,as_of=None,age_days=7):
    dossier_dir=Path(dossier_dir)
    permit_dir=Path(permit_dir)
    out=Path(out) if out is not None else dossier_dir
    if out.resolve()==permit_dir.resolve():
        raise ValueError("Cannot overwrite original City evidence folder")
    timestamp=_utc(as_of)
    age_days=max(1,min(int(age_days),30))
    source=_read_csv(dossier_dir/dossiers.DOSSIERS_CSV,REQUIRED_DOSSIERS)
    applicable=[r for r in source if r.get("source_family")=="radar" and
                r.get("source_id")==permits.SOURCE]
    enabled,reason,accepted=_source_gate(permit_dir)
    by_project=defaultdict(list)
    # Even a previously accepted export can contain contradictory duplicated
    # constituent keys; never pick one source record arbitrarily.
    accepted_key_counts=Counter((r.get("project_id",""),r.get("source_key",""))
                                for r in accepted)
    for accepted_row in accepted:
        by_project[accepted_row.get("project_id","")].append(accepted_row)
    out_rows=[]
    problems=Counter()
    verified_dossiers=set()
    stage_differences=0
    partial_project_stages=0
    blocked=0
    for d in applicable:
        original={"project_id":d["source_record_id"],
                  "source_keys":d["source_lookup_key"]}
        keys,why=permits.split_source_keys(original)
        valid_keys={k for k,_,_ in keys}
        if why:
            problems["ARCHIVED_PROJECT_KEY_INVALID"]+=1
            out_rows.append(_row(d,reason="ARCHIVED_PROJECT_KEY_INVALID"))
            continue
        if not enabled:
            problems[reason]+=1
            out_rows.append(_row(d,reason=reason,key_count=len(keys)))
            continue
        found=False
        for record in by_project.get(d["source_record_id"],[]):
            key=record.get("source_key","")
            if key not in valid_keys:
                problems["CITY_SOURCE_KEY_NOT_IN_ORIGINAL_PROJECT"]+=1
                continue
            if accepted_key_counts[(d["source_record_id"],key)]!=1:
                problems["DUPLICATE_ACCEPTED_CITY_CONSTITUENT_KEY"]+=1
                continue
            # The source key must describe the SAME permit and revision as
            # the fields in the publisher-filtered query, not a sibling key.
            if key != (str(record.get("permit_num") or "")+"|"+
                       str(record.get("revision_num") or "")):
                problems["ACCEPTED_CITY_RECORD_KEY_COMPONENT_CONFLICT"]+=1
                continue
            if (record.get("record_validation")!=SOURCE_EVIDENCE or
                record.get("buyer_verified")!="NO" or
                record.get("open_supplier_contract_verified")!="NO" or
                not acceptance._validate_remote_url(
                    record.get("source_query_url",""),record.get("permit_num",""),
                    record.get("revision_num",""))):
                problems["ACCEPTED_CITY_RECORD_PROVENANCE_FAILED"]+=1
                continue
            city=graph.normalized_city(d.get("city",""))
            source_site,source_unit=graph.normalize_address(
                record.get("source_address",""))
            archived_site,archived_unit=graph.normalize_address(
                d.get("site_address",""))
            if city!="Toronto" or not source_site or source_site!=archived_site:
                problems["EXACT_PERMIT_SITE_OR_CITY_CONFLICT"]+=1
                continue
            # Same building is insufficient evidence of the same suite or
            # tenant. An explicit unit on just one side is also ambiguous.
            if source_unit!=archived_unit:
                problems["EXACT_PERMIT_UNIT_CONFLICT"]+=1
                continue
            try:
                checked=dt.datetime.fromisoformat(
                    record.get("live_checked_at_utc","").replace("Z","+00:00"))
                if checked.tzinfo is None:
                    raise ValueError("No timezone")
                delta=(timestamp-checked.astimezone(dt.timezone.utc)).total_seconds()
                if delta< -3600 or delta>age_days*86400:
                    problems["ACCEPTED_CITY_SOURCE_PROOF_EXPIRED"]+=1
                    continue
            except (TypeError,ValueError):
                problems["ACCEPTED_CITY_SOURCE_TIMESTAMP_INVALID"]+=1
                continue
            row=_row(d,key,record,reason="ACCEPTED_EXACT_CITY_RECORD",
                     age_days=max(0,int(delta//86400)),key_count=len(keys))
            out_rows.append(row)
            verified_dossiers.add(d["dossier_id"])
            found=True
            stage_differences+=int("DIFFERS" in row["source_stage_comparison"])
            partial_project_stages+=int(len(keys)>1)
            blocked+=int(row["commercial_research_status"]=="BLOCKED_PERMIT_REVIEW_ONLY")
        if not found:
            problems["NO_MATCHING_VERIFIED_CONSTITUENT_SOURCE_RECORD"]+=1
            out_rows.append(_row(d,reason="NO_MATCHING_VERIFIED_CONSTITUENT_SOURCE_RECORD",
                                 key_count=len(keys)))
    # Every original dossier is read-only; the overlay is a separate source
    # audit, never a rewriting of its buyer, project status or sales priority.
    out_rows.sort(key=lambda r:(r["project_id"],r["verified_permit_revision_key"]))
    out.mkdir(parents=True,exist_ok=True)
    graph.write_csv(out/OUTPUT_CSV,out_rows,FIELDS)
    summary={
        "mode":"OFFLINE_PROOF_GATED_INDIVIDUAL_TORONTO_PERMIT_DOSSIER_LINK",
        "sample_source_gate_enabled":enabled,
        "source_gate_reason":reason,
        "toronto_dossiers_in_research":len(applicable),
        "toronto_dossiers_with_exact_checked_permit_source":len(verified_dossiers),
        "exact_permit_records_linked":sum(
            r["exact_permit_source_evidence_level"]=="ACCEPTED_EXACT_CITY_RECORD"
            for r in out_rows),
        "source_stage_difference_to_archived_project_summary":stage_differences,
        "verified_constituents_in_multi_permit_project_folders":partial_project_stages,
        "blocked_source_status_records_not_sales_ready":blocked,
        "unresolved_matching_reasons":dict(sorted(problems.items())),
        "verified_buyers":0,"verified_open_supplier_contracts":0,
        "outreach_authorized":False,"production_promotion_allowed":False,
        "accepted_source_csv_sha256":(
            hashlib.sha256((permit_dir/acceptance.OUTPUT_CSV).read_bytes()).hexdigest()
            if enabled else None),
        "output_csv":str(out/OUTPUT_CSV),
        "caveats":[
            "A verified constituent permit/revision does not validate every permit in the original project folder.",
            "A difference from the archived PROJECT summary does not necessarily prove that individual permit's stage advanced.",
            "City active-permit stage is not verified contractor selection, start/completion of work or a sales opportunity.",
            "No company, buyer, contact, procurement, opening or outreach claim can be created by this overlay.",
        ]
    }
    (out/OUTPUT_JSON).write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dossiers",type=Path,required=True)
    parser.add_argument("--permit-evidence",type=Path,required=True)
    parser.add_argument("--out",type=Path)
    parser.add_argument("--as-of",help="Timezone-aware ISO timestamp")
    args=parser.parse_args()
    print(json.dumps(run(args.dossiers,args.permit_evidence,args.out,
                         as_of=args.as_of),indent=2))


if __name__=="__main__":
    main()
