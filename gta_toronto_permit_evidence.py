"""Toronto permit/revision evidence audit for existing GTA Radar daily exports.

Runs OFFLINE by default. When an existing Radar SQLite database is supplied it
reconciles exact permit+revision keys against the original official CKAN snapshot
stored by Radar, read-only. Optional --live-ckan performs a bounded, explicitly
requested check of *individual permit/revision records* against Toronto's public
CKAN DataStore. No schedule, AI, outreach or production collector modifications.

An exact matching CKAN row proves only what the published dataset reported on
the retrieval date. It does NOT prove permit approval, current inspection outcome,
tenant identity, purchasing authority, live contract availability or opening.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

import gta_facility_intelligence as graph

SOURCE="toronto_active_building_permits"
DAILY_CSV="GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv"
AUDIT_CSV="GTA_RADAR_TORONTO_PERMIT_EXACT_RECORD_AUDIT.csv"
PROJECT_CSV="GTA_RADAR_TORONTO_PROJECT_PERMIT_RECONCILIATION.csv"
AUDIT_JSON="GTA_RADAR_TORONTO_PERMIT_EVIDENCE_STATUS.json"
LIVE_BATCH_DIR="LIVE_VERIFICATION_BATCHES"
PACKAGE="building-permits-active-permits"
RESOURCE_HINT="6d0229af-bc54-46de-9c2b-26759b01dd05"
API="https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/"
OFFICIAL_DATASET="https://open.toronto.ca/dataset/building-permits-active-permits/"
OFFICIAL_STATUS=graph.TORONTO_PERMIT_STATUS_SEARCH

# Example original keys: "26 265617 HVA|00 | 26 265617 BLD|00".
KEY=re.compile(r"^(?P<folder>\d{2} \d{6}) (?P<type>[A-Z]{3})\|(?P<rev>\d{2})$")
FOLDER=re.compile(r"^\d{2} \d{6}$")
MAX_KEYS_PER_PROJECT=12
MAX_LIVE=10
MAX_RESPONSE_BYTES=1_500_000
REQUIRED={"project_id","source_id","source_keys","address",
          "current_source_status","observation"}
AUDIT_FIELDS=(
    "project_id","source_key","permit_num","revision_num","permit_type",
    "raw_city_dataset_url","official_lookup_url",
    "local_snapshot_status","local_source_first_seen_at","local_source_date",
    "local_payload_sha256","local_record_status","local_record_address",
    "local_address_comparison","local_status_comparison",
    "remote_status","remote_record_status","remote_record_address",
    "remote_address_comparison","remote_stage_comparison",
    "remote_payload_sha256","remote_query_url","remote_retrieved_at",
    "final_evidence_level","individual_record_retrieved_live",
    "record_is_a_verified_open_supplier_contract","buyer_verified",
    "review_blockers",
)
PROJECT_FIELDS=(
    "project_id","permit_folder","source_key_count","local_records_matched",
    "local_records_missing","local_record_stage_count",
    "local_statuses","live_records_matched","live_records_checked",
    "project_review_status","source_permit_evidence_summary",
    "source_provenance","verified_open_contract","buyer_verified",
)
# Verification selection is *stratified*, not a leaderboard and not proof of
# buyer availability. Recheck a mix of municipal stages, including blocked ones.
REVIEW_STAGE={
    "BLOCKED": ("on hold","application on hold","permit on hold",
                "refusal notice","revocation pending","cancellation pending",
                "suspended","violation"),
    "ISSUED": ("permit issued","revision issued","issuance pending","ready for issuance",
               "forwarded for issuance"),
    "INSPECTION": ("inspection","work not started"),
    "PREPARATION": ("under review","not started","application acceptable",
                    "application received","pending parent folder review",
                    "examiner's notice sent","response received"),
}
STAGE_SEQUENCE=("ISSUED","PREPARATION","INSPECTION","BLOCKED","OTHER")

def clean(value):
    return graph.clean(value)

def split_source_keys(project):
    """Fail closed on malformed, mixed-folder or excessive constituent IDs."""
    expected=clean(project.get("project_id",""))
    root=expected.removeprefix(SOURCE+":")
    if not expected.startswith(SOURCE+":") or not FOLDER.fullmatch(root):
        return [],"INVALID_PROJECT_FOLDER_ID"
    string=clean(project.get("source_keys"))
    if not string:
        return [],"NO_CONSTITUENT_PERMIT_KEYS"
    tokens=re.split(r"\s+\|\s+",string)
    if len(tokens)>MAX_KEYS_PER_PROJECT:
        return [],"TOO_MANY_KEYS_REQUIRE_MANUAL_REVIEW"
    records=[];seen=set()
    for token in tokens:
        match=KEY.fullmatch(token)
        if not match or match["folder"] != root:
            return [],"MALFORMED_OR_DIFFERENT_FOLDER_KEY"
        permit_num=match["folder"]+" "+match["type"]
        revision=match["rev"]
        ident=permit_num+"|"+revision
        if ident in seen:
            return [],"DUPLICATE_CONSTITUENT_KEYS"
        seen.add(ident)
        records.append((ident,permit_num,revision))
    if not records:
        return [],"NO_CONSTITUENT_PERMIT_KEYS"
    return records,""

def _official_status_address(raw):
    addr=clean(" ".join(clean(raw.get(field)) for field in
        ("STREET_NUM","STREET_NAME","STREET_TYPE","STREET_DIRECTION")))
    return graph.normalize_address(addr)[0]

def _local_read(db, record_keys):
    """Reads latest records, including inactive history, without mutating SQLite."""
    path=Path(db)
    if not path.is_file():
        raise FileNotFoundError("Existing Radar SQLite missing: "+str(path))
    answers={}
    with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro",
                                 uri=True,timeout=8)) as con:
        con.execute("PRAGMA query_only=ON")
        for ident in sorted(set(record_keys)):
            row=con.execute(
                """SELECT c.record_key,c.first_seen_at,c.source_date,c.active,
                          v.payload_json
                   FROM records_current c JOIN record_versions v
                   ON v.source_id=c.source_id AND v.record_key=c.record_key
                   AND v.version_id=(
                      SELECT MAX(v2.version_id) FROM record_versions v2
                      WHERE v2.source_id=c.source_id AND v2.record_key=c.record_key
                   )
                   WHERE c.source_id=? AND c.record_key=?
                   LIMIT 2""",(SOURCE,ident)).fetchall()
            if len(row)>1:
                answers[ident]={"error":"DUPLICATE_DATABASE_RECORD_KEY"}
                continue
            if not row:continue
            key,seen,date,active,payload=row[0]
            try:
                parsed=json.loads(payload)
            except (TypeError,ValueError):
                answers[ident]={"error":"INVALID_STORED_JSON"}
                continue
            if not isinstance(parsed,dict):
                answers[ident]={"error":"STORED_PAYLOAD_NOT_OBJECT"}
                continue
            answers[ident]={
                "raw":parsed,"active":bool(active),"first_seen":clean(seen),
                "source_date":clean(date),
                "sha256":hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            }
    return answers

def _local_verdict(record, evidence, expected_address, expected_status):
    if evidence is None:
        return "LOCAL_SOURCE_KEY_NOT_FOUND","", "", "", "", "", ""
    if "error" in evidence:
        return evidence["error"], "", "", "", "", "", ""
    raw=evidence["raw"]
    permit_num,rev=record
    if clean(raw.get("PERMIT_NUM"))!=permit_num or clean(raw.get("REVISION_NUM"))!=rev:
        return "LOCAL_KEY_PAYLOAD_MISMATCH","","","","","",""
    addr=_official_status_address(raw)
    status=clean(raw.get("STATUS"))
    if not addr:
        addr_check="SOURCE_ADDRESS_MISSING"
    elif expected_address and expected_address!=addr:
        addr_check="SOURCE_ADDRESS_CONFLICT"
    else:
        addr_check="STREET_MATCHES_EXISTING_RADAR_EXPORT" if expected_address else "NO_EXPORT_ADDRESS_TO_COMPARE"
    status_check=("STAGE_MATCHES_EXPORT" if status==expected_status else
                  "STAGE_DIFFERS_FROM_EXPORT_REVIEW_REQUIRED" if status and expected_status else
                  "NO_UNAMBIGUOUS_STAGE_COMPARISON")
    state = ("LOCAL_RECORD_INACTIVE_HISTORY" if not evidence["active"] else
             "LOCAL_RECORD_ADDRESS_CONFLICT" if addr_check=="SOURCE_ADDRESS_CONFLICT" else
             "LOCAL_RECORD_ADDRESS_MISSING_REVIEW" if addr_check=="SOURCE_ADDRESS_MISSING" else
             "LOCAL_EXACT_PERMIT_REVISION_PAYLOAD_MATCH_NOT_LIVE_RECHECKED")
    return state, evidence["first_seen"],evidence["source_date"],evidence["sha256"],status,addr,addr_check+";"+status_check

def _get_payload(url):
    """Fixed official CKAN host, no redirect, bounded JSON, network opt-in only."""
    parsed=urlsplit(url)
    if parsed.scheme!="https" or parsed.netloc!="ckan0.cf.opendata.inter.prod-toronto.ca":
        raise ValueError("Public Toronto CKAN API host only")
    if not parsed.path.startswith("/api/3/action/"):
        raise ValueError("Public Toronto CKAN action endpoint only")
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            return None
    opener=build_opener(NoRedirect)
    req=Request(url,headers={"Accept":"application/json",
        "User-Agent":"GTARadarManualRecordEvidenceAudit/1.0"})
    with opener.open(req,timeout=18) as response:
        if response.status!=200:raise ValueError("CKAN returned non-200 HTTP status")
        raw=response.read(MAX_RESPONSE_BYTES+1)
    if len(raw)>MAX_RESPONSE_BYTES:
        raise ValueError("CKAN response exceeded fixed byte limit")
    return json.loads(raw)

def _official_action(operation,values,fetch=_get_payload):
    if operation not in ("package_show","datastore_search"):
        raise ValueError("CKAN operation not permitted")
    url=API+operation+"?"+urlencode(values)
    data=fetch(url)
    if not isinstance(data,dict) or data.get("success") is not True:
        raise ValueError("Official CKAN API did not return a successful result")
    result=data.get("result")
    if not isinstance(result,dict):
        raise ValueError("Unexpected CKAN result schema")
    return result,url

def _resource(fetch):
    metadata,_=_official_action("package_show",{"id":PACKAGE},fetch)
    if metadata.get("name")!=PACKAGE:
        raise ValueError("Unexpected Toronto dataset package identity")
    for res in metadata.get("resources",[]):
        if (res.get("id")==RESOURCE_HINT and res.get("datastore_active") is True):
            return RESOURCE_HINT,clean(res.get("last_modified"))
    raise ValueError("Expected active Toronto permit DataStore resource unavailable; no fallback to wrong dataset")

def _remote_record(permit_num,revision,resource_id,fetch):
    params={"resource_id":resource_id,"filters":json.dumps({
        "PERMIT_NUM":permit_num,"REVISION_NUM":revision},separators=(",",":")),"limit":3}
    result,url=_official_action("datastore_search",params,fetch)
    records=result.get("records")
    if not isinstance(records,list):
        raise ValueError("Toronto CKAN returned no records array")
    matched=[r for r in records if isinstance(r,dict)
             and clean(r.get("PERMIT_NUM"))==permit_num
             and clean(r.get("REVISION_NUM"))==revision]
    if len(matched)!=1 or len(records)!=1:
        if not records:
            return "NOT_PRESENT_IN_ACTIVE_DATASTORE_NOT_PROOF_OF_CLOSURE",{},url
        return "AMBIGUOUS_OR_NONEXACT_CKAN_PERMIT_MATCH",{},url
    return "LIVE_EXACT_KEY_MATCH_OFFICIAL_DATASET",matched[0],url

def _stage_bucket(value):
    status=clean(value).lower()
    for name, patterns in REVIEW_STAGE.items():
        if status in patterns:
            return name
    return "OTHER"


def _recent_date(value):
    # ISO source-record date is evidence of event date, not first publication.
    value=clean(value)
    try:
        return dt.date.fromisoformat(value[:10]).toordinal()
    except ValueError:
        return 0


def choose_live_recheck_sample(audit, projects, limit=MAX_LIVE, offset=0):
    """Fair bounded rotating sample: stages, distinct projects, recent first.

    Never claim a project is checked if only one of its revision keys was
    queried. This samples *records*, not source-complete facilities.
    """
    limit=max(0,min(int(limit),MAX_LIVE))
    offset=int(offset)
    if offset<0 or offset>10000:
        raise ValueError("Live source-record offset must be 0..10000")
    if not limit:
        return []
    metadata={p["project_id"]:p for p in projects}
    by_stage=defaultdict(list)
    for row in audit:
        source=metadata.get(row["project_id"],{})
        stage=_stage_bucket(source.get("current_source_status",""))
        by_stage[stage].append((
            row, _recent_date(source.get("source_record_date",""))
        ))
    for rows in by_stage.values():
        rows.sort(key=lambda item:(
            -item[1], item[0]["permit_type"]!="BLD",
            item[0]["project_id"],item[0]["source_key"]
        ))
    selected=[]
    used_ids=set()
    used_projects=set()
    # Stage coverage first: one source record per status tier. Offset applies
    # to the resulting deterministic full order, not before stage sampling.
    for stage in STAGE_SEQUENCE:
        if by_stage[stage]:
            row,_=by_stage[stage].pop(0)
            selected.append(row)
            used_ids.add(row["source_key"])
            used_projects.add(row["project_id"])
    # Then maximize distinct projects; after that remaining records from
    # multi-permit folders may be checked, explicitly labelled partial.
    remaining=[
        (STAGE_SEQUENCE.index(stage),r,when)
        for stage,items in by_stage.items()
        for r,when in items if r["source_key"] not in used_ids
    ]
    remaining.sort(key=lambda item:(
        -item[2],item[0],item[1]["permit_type"]!="BLD",
        item[1]["project_id"],item[1]["source_key"]
    ))
    for _,row,_ in remaining:
        if row["project_id"] in used_projects:
            continue
        selected.append(row)
        used_ids.add(row["source_key"])
        used_projects.add(row["project_id"])
    for _,row,_ in remaining:
        if row["source_key"] in used_ids:
            continue
        selected.append(row)
        used_ids.add(row["source_key"])
    return selected[offset:offset+limit]


def _audit_row(project,ident,permit_num,rev,local,export_status,export_address):
    state,seen,date,digest,raw_status,raw_address,checks=_local_verdict(
        (permit_num,rev),local,export_address,export_status)
    comp=checks.split(";") if checks else []
    blockers=["NOT_LIVE_RECHECKED","BUYER_NOT_VERIFIED","PROCUREMENT_NOT_VERIFIED"]
    if state!="LOCAL_EXACT_PERMIT_REVISION_PAYLOAD_MATCH_NOT_LIVE_RECHECKED":
        blockers.append(state)
    if "STAGE_DIFFERS_FROM_EXPORT_REVIEW_REQUIRED" in comp:
        blockers.append("LOCAL_STAGE_DIFFERS_FROM_ARCHIVED_EXPORT")
    return {
        "project_id":project["project_id"],"source_key":ident,
        "permit_num":permit_num,"revision_num":rev,
        "permit_type":permit_num.split()[-1],
        "raw_city_dataset_url":OFFICIAL_DATASET,
        "official_lookup_url":OFFICIAL_STATUS,
        "local_snapshot_status":state,"local_source_first_seen_at":seen,
        "local_source_date":date,"local_payload_sha256":digest,
        "local_record_status":raw_status,"local_record_address":raw_address,
        "local_address_comparison":comp[0] if comp else "",
        "local_status_comparison":comp[1] if len(comp)>1 else "",
        "remote_status":"NOT_REQUESTED_MANUAL_LIVE_ONLY",
        "remote_record_status":"","remote_record_address":"",
        "remote_address_comparison":"","remote_stage_comparison":"",
        "remote_payload_sha256":"",
        "remote_query_url":"","remote_retrieved_at":"",
        "final_evidence_level":"SOURCE_SNAPSHOT_EXACT_KEY_NOT_LIVE_CHECKED" if
             state=="LOCAL_EXACT_PERMIT_REVISION_PAYLOAD_MATCH_NOT_LIVE_RECHECKED" else
             "UNVERIFIED_SOURCE_RECORD_ID",
        "individual_record_retrieved_live":"NO",
        "record_is_a_verified_open_supplier_contract":"NO",
        "buyer_verified":"NO","review_blockers":";".join(blockers)
    }

def run(results, out=None, *, db=None, live=False, live_limit=10,
        live_offset=0, fetch=_get_payload, as_of=None):
    results=Path(results)
    source=results/DAILY_CSV
    rows=graph.read_csv(source,REQUIRED) if source.is_file() else None
    if rows is None:
        raise FileNotFoundError("Existing daily Radar CSV required: "+str(source))
    out=Path(out) if out is not None else results/"TORONTO_PERMIT_EVIDENCE_PILOT"
    if out.resolve()==results.resolve():
        raise ValueError("Output must not overwrite Radar source folder")
    if not 0<=int(live_limit)<=MAX_LIVE:
        raise ValueError("Bounded live query limit must be 0.."+str(MAX_LIVE))
    if not 0<=int(live_offset)<=10000:
        raise ValueError("Live source-record offset must be 0..10000")
    all_projects=[r for r in rows if clean(r.get("source_id"))==SOURCE]
    audit=[];projects=[];failures=Counter();parsed_projects=[]
    keyset=set()
    for p in all_projects:
        keys,why=split_source_keys(p)
        if why:
            failures[why]+=1
            projects.append({"project_id":p.get("project_id",""),
                "permit_folder":p.get("project_id","").removeprefix(SOURCE+":"),
                "source_key_count":0,"local_records_matched":0,
                "local_records_missing":0,"local_record_stage_count":0,
                "local_statuses":"","live_records_matched":0,
                "live_records_checked":0,
                "project_review_status":"INVALID_SOURCE_KEY_REVIEW_REQUIRED",
                "source_permit_evidence_summary":why,
                "source_provenance":"EXISTING_RADAR_CSV_NOT_LIVE_RECHECKED",
                "verified_open_contract":"NO","buyer_verified":"NO"})
            continue
        parsed_projects.append((p,keys))
        keyset.update(key for key,_,_ in keys)
    local={}
    db_state="NO_LOCAL_SQLITE_PROVIDED"
    if db is not None:
        try:
            local=_local_read(db,keyset)
            db_state="LOCAL_SQLITE_READ_ONLY"
        except (FileNotFoundError,sqlite3.Error) as exc:
            db_state="LOCAL_SQLITE_UNAVAILABLE_"+type(exc).__name__
    evidence={}
    for p,keys in parsed_projects:
        export_address=graph.normalize_address(p.get("address",""))[0]
        export_status=clean(p.get("current_source_status"))
        keyed=[]
        for ident,permit,revision in keys:
            row=_audit_row(p,ident,permit,revision,local.get(ident),
                           export_status,export_address)
            keyed.append(row)
            audit.append(row)
        evidence[p["project_id"]]=keyed
    live_requested=bool(live)
    live_checked=0
    live_status="NOT_REQUESTED"
    resource_id=""
    metadata_modified=""
    remote_public_rows={}
    if live_requested and audit and live_limit>0:
        try:
            resource_id,metadata_modified=_resource(fetch)
            live_status="OFFICIAL_CKAN_RESOURCE_RESOLVED"
            # Stratify stage classes and prefer the most recently source-dated
            # records, with distinct projects before secondary constituent keys.
            selected=choose_live_recheck_sample(
                audit,all_projects,live_limit,live_offset)
            stamp=(as_of.isoformat() if isinstance(as_of,(dt.date,dt.datetime))
                   else str(as_of) if as_of else
                   dt.datetime.now(dt.timezone.utc).isoformat())
            for row in selected:
                live_checked += 1
                try:
                    state,record,url=_remote_record(row["permit_num"],
                        row["revision_num"],resource_id,fetch)
                    row["remote_query_url"]=url
                    row["remote_retrieved_at"]=stamp
                    row["remote_status"]=state
                    if record:
                        # Preserve the original public CKAN row in its batch.
                        # A hash of unpreserved text is not auditable evidence.
                        canonical=json.dumps(
                            record,sort_keys=True,ensure_ascii=False,separators=(",",":"))
                        row["remote_payload_sha256"]=hashlib.sha256(
                            canonical.encode("utf-8")).hexdigest()
                        remote_public_rows[row["source_key"]]=record
                        row["remote_record_status"]=clean(record.get("STATUS"))
                        row["remote_record_address"]=_official_status_address(record)
                        original_stage=clean(next((
                            source.get("current_source_status","") for source,_ in parsed_projects
                            if source.get("project_id")==row["project_id"]), ""))
                        remote_stage=row["remote_record_status"]
                        row["remote_stage_comparison"]=(
                            "REMOTE_STATUS_MISSING_RECHECK" if not remote_stage else
                            "STATUS_CHANGED_SINCE_EXPORTED_GROUP" if original_stage and
                                remote_stage!=original_stage else
                            "MATCHES_EXPORTED_GROUP_STATUS" if original_stage else
                            "NO_EXPORTED_GROUP_STATUS_FOR_COMPARISON"
                        )
                        exported = graph.normalize_address(
                            next((p.get("address","") for p,ks in parsed_projects
                                  if p.get("project_id")==row["project_id"]), ""))[0]
                        previous = graph.normalize_address(row["local_record_address"])[0]
                        current = row["remote_record_address"]
                        if not remote_stage:
                            row["final_evidence_level"]="LIVE_ROW_STAGE_UNVERIFIED"
                            row["review_blockers"]+=";REMOTE_STATUS_MISSING"
                        if not current:
                            row["remote_address_comparison"]="LIVE_CITY_RECORD_ADDRESS_MISSING"
                            row["final_evidence_level"]="LIVE_ROW_ADDRESS_UNVERIFIED"
                        elif (exported and exported!=current) or (
                                previous and previous!=current):
                            row["remote_address_comparison"]="LIVE_ADDRESS_CONTRADICTS_ARCHIVED_SOURCE"
                            row["final_evidence_level"]="REVIEW_SOURCE_ADDRESS_CONFLICT"
                        else:
                            row["remote_address_comparison"]="ADDRESS_COMPATIBLE_WITH_AVAILABLE_SNAPSHOTS"
                            row["final_evidence_level"]=(
                                "OFFICIAL_CKAN_EXACT_KEY_LIVE_RECHECKED" if remote_stage else
                                "LIVE_ROW_STAGE_UNVERIFIED")
                        row["individual_record_retrieved_live"]="YES"
                        row["review_blockers"]+=";OFFICIAL_CKAN_ROW_DOES_NOT_PROVE_BUYER_OR_OPEN_CONTRACT"
                        if row["remote_stage_comparison"]=="STATUS_CHANGED_SINCE_EXPORTED_GROUP":
                            row["review_blockers"]+=";ARCHIVED_PROJECT_STATUS_DIFFERS_FROM_LIVE_CONSTITUENT"
                    else:
                        row["final_evidence_level"]="LIVE_RECORD_MISSING_OR_AMBIGUOUS_MANUAL_REVIEW"
                except (ValueError,OSError,TimeoutError,sqlite3.Error) as exc:
                    row["remote_status"]="LIVE_CKAN_QUERY_ERROR_"+type(exc).__name__
                    row["final_evidence_level"]="LIVE_RECHECK_FAILED_MANUAL_REVIEW"
            live_status="QUERIED_BOUNDED_OFFICIAL_CKAN"
        except (ValueError,OSError,TimeoutError) as exc:
            live_status="RESOURCE_LOOKUP_UNAVAILABLE_"+type(exc).__name__
    elif live_requested:
        live_status="NO_KEYS_OR_ZERO_LIMIT"
    for p,keys in parsed_projects:
        rows_for=evidence[p["project_id"]]
        localmatched=[r for r in rows_for if r["local_snapshot_status"]==
                      "LOCAL_EXACT_PERMIT_REVISION_PAYLOAD_MATCH_NOT_LIVE_RECHECKED"]
        statuses={r["local_record_status"] for r in rows_for if r["local_record_status"]}
        livehits=[r for r in rows_for if r["final_evidence_level"]==
                  "OFFICIAL_CKAN_EXACT_KEY_LIVE_RECHECKED"]
        problems=any(r["local_snapshot_status"] not in {
            "LOCAL_EXACT_PERMIT_REVISION_PAYLOAD_MATCH_NOT_LIVE_RECHECKED"
        } for r in rows_for)
        result=("SOURCE_DATA_CONFLICT_OR_INCOMPLETE_REVIEW" if db is not None and problems else
            "LOCAL_SNAPSHOT_MULTIPLE_DISTINCT_PERMIT_STAGES" if len(statuses)>1 else
            "LOCAL_SNAPSHOT_EXACT_KEY_MATCH_UNRECHECKED" if localmatched and
                len(localmatched)==len(rows_for) else
            "NO_LOCAL_SNAPSHOT_OR_INDIVIDUAL_RECHECK")
        if livehits and len(livehits)==len(rows_for):
            result="ALL_CONSTITUENTS_EXACT_LIVE_DATASET_MATCH_NOT_BUYER_PROOF"
        projects.append({
            "project_id":p["project_id"],
            "permit_folder":p["project_id"].removeprefix(SOURCE+":"),
            "source_key_count":len(keys),
            "local_records_matched":len(localmatched),
            "local_records_missing":len(rows_for)-len(localmatched),
            "local_record_stage_count":len(statuses),
            "local_statuses":";".join(sorted(statuses)),
            "live_records_matched":len(livehits),
            "live_records_checked":sum(r["individual_record_retrieved_live"]=="YES" for r in rows_for),
            "project_review_status":result,
            "source_permit_evidence_summary":"BUNDLE_OF_DISTINCT_PERMIT_REVISIONS_NOT_A_SINGLE_PERMIT",
            "source_provenance":"OFFICIAL_RADAR_SNAPSHOT_OR_EXPLICIT_PUBLIC_CKAN_QUERY",
            "verified_open_contract":"NO","buyer_verified":"NO",
        })
    projects.sort(key=lambda r:r["project_id"])
    audit.sort(key=lambda r:(r["project_id"],r["source_key"]))
    out.mkdir(parents=True,exist_ok=True)
    batch_file=""
    if live_requested and live_checked:
        # Preserve evidence from each explicitly opted-in bounded verification.
        # The normal CSV is a latest-run view and may be overwritten, whereas
        # these batches cannot overwrite one another or be silently reclassified.
        stamped=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        batch_folder=out/LIVE_BATCH_DIR
        batch_folder.mkdir(parents=True,exist_ok=True)
        path=batch_folder/("TORONTO_CKAN_EXACT_CHECK_"+stamped+
                           "_OFFSET_"+str(int(live_offset))+".json")
        selected_rows=[
            {field:row.get(field,"") for field in AUDIT_FIELDS}
            for row in audit if row["remote_status"]!="NOT_REQUESTED_MANUAL_LIVE_ONLY"
        ]
        batch={
            "mode":"BOUNDED_EXPLICIT_PUBLIC_TORONTO_CKAN_QUERIES",
            "retrieved_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "resource_id":resource_id,
            "source_dataset":OFFICIAL_DATASET,
            "offset":int(live_offset),
            "requested_limit":int(live_limit),
            "attempted_records":live_checked,
            "records_with_exact_live_key":sum(
                row["individual_record_retrieved_live"]=="YES" for row in selected_rows),
            "commercial_buyer_verified":False,
            "open_supplier_contracts_verified":0,
            "audit_records":selected_rows,
            "original_public_ckan_rows_by_source_key":remote_public_rows,
        }
        with path.open("x",encoding="utf-8") as outstream:
            json.dump(batch,outstream,indent=2)
        batch_file=str(path)
    graph.write_csv(out/AUDIT_CSV,audit,AUDIT_FIELDS)
    graph.write_csv(out/PROJECT_CSV,projects,PROJECT_FIELDS)
    status={
        "mode":"LOCAL_SNAPSHOT_ONLY" if not live_requested else "BOUNDED_OPTIONAL_LIVE_CKAN_RECHECK",
        "as_of":clean(as_of or dt.datetime.now(dt.timezone.utc).isoformat()),
        "total_daily_rows":len(rows),
        "toronto_project_groups":len(all_projects),
        "valid_toronto_permit_groups":len(parsed_projects),
        "distinct_original_constituent_keys":len(keyset),
        "invalid_project_group_reasons":dict(sorted(failures.items())),
        "local_snapshot_state":db_state,
        "local_record_payloads_matched":sum(r["local_snapshot_status"]==
            "LOCAL_EXACT_PERMIT_REVISION_PAYLOAD_MATCH_NOT_LIVE_RECHECKED" for r in audit),
        "live_requested":live_requested,
        "live_requested_limit":int(live_limit),
        "live_offset":int(live_offset),
        "live_selection_eligible_records":len(audit),
        "live_selected_record_keys":(
            [row["source_key"] for row in choose_live_recheck_sample(
                audit,all_projects,live_limit,live_offset)]
            if live_requested else []),
        "live_next_offset":(
            min(int(live_offset)+len(choose_live_recheck_sample(
                audit,all_projects,live_limit,live_offset)),len(audit))
            if live_requested else None),
        "immutable_live_batch_file":batch_file,
        "live_selection_policy":"STAGE_DIVERSITY_THEN_RECENT_SOURCE_DATE_THEN_DISTINCT_PROJECTS;ONE_RECORD_DOES_NOT_VERIFY_WHOLE_PROJECT",
        "live_status":live_status,
        "live_record_queries_attempted":live_checked,
        "live_queries_failed":sum(
            row["remote_status"].startswith("LIVE_CKAN_QUERY_ERROR_") for row in audit),
        "live_exact_record_payloads_received":sum(r["individual_record_retrieved_live"]=="YES"
                                                  for r in audit),
        "metadata_resource_id":resource_id,
        "metadata_resource_last_modified_not_proof_of_row_publication":metadata_modified,
        "verified_buyers":0,"verified_open_contracts":0,
        "unverified_portal_not_individual_record":OFFICIAL_STATUS,
        "limitations":[
            "Local collector SQLite is a historical source snapshot, not live permit verification.",
            "City CKAN exact-row response is source publication evidence, not live construction or purchase intent.",
            "Toronto status portal is updated as of the previous business day and can differ from CKAN.",
            "Not present in active CKAN does not prove closed; check the separately cleared archive and official status portal.",
            "Multiple BLD/HVA/PLB permit records in a project group may have different statuses; never collapse into one verified stage.",
            "Live mode is opt-in and capped; missing/unqueried records stay unverified.",
            "No buyers, organizations, contact details, procurement or business opening is verified here.",
        ],
        "outputs":{"permit_records_csv":str(out/AUDIT_CSV),
                   "projects_csv":str(out/PROJECT_CSV)},
    }
    (out/AUDIT_JSON).write_text(json.dumps(status,indent=2),encoding="utf-8")
    return status

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results",type=Path,required=True)
    p.add_argument("--out",type=Path)
    p.add_argument("--db",type=Path,help="Existing collector radar.sqlite, opened strictly read-only")
    p.add_argument("--live-ckan",action="store_true",
                   help="Opt-in: at most 10 official CKAN exact permit/revision queries")
    p.add_argument("--live-limit",type=int,default=10)
    p.add_argument("--live-offset",type=int,default=0,
                   help="Next bounded manual batch; offset 10 checks new records")
    args=p.parse_args()
    print(json.dumps(run(args.results,args.out,db=args.db,
                         live=args.live_ckan,live_limit=args.live_limit,
                         live_offset=args.live_offset),indent=2))

if __name__=="__main__":
    main()
