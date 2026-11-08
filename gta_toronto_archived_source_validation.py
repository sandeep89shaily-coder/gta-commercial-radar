"""One-time PR-only validation of twenty *archived* Toronto permit/revision IDs.

The fixture is a minimized, address-and-status-only selection from the user's
2026-11-07 GTA_RADAR_RESULTS (13).zip, original daily CSV SHA-256
a4d0f1ee098e30dd504dcb7aa00e8ee13471ba396e874e8748473f7ca118b13d.

This intentionally creates TWO bounded independent ten-key source lookups
into a temporary scratch results directory, never against the production
Radar workspace or SQLite. Its only network access is the official public
Toronto CKAN API, using existing fixed-host and response-size restrictions.

No owner names, user contact information, public outreach, paid AI,
scheduled collector, database mutations or procurement decisions.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path

import gta_facility_intelligence as graph
import gta_toronto_permit_evidence as permit
import gta_toronto_permit_acceptance as acceptance

FIXTURE=Path(__file__).resolve().parent/"tests"/"fixtures"/"toronto_archived_20_permits_20261107.csv"
ORIGINAL_DAILY_CSV_SHA256="a4d0f1ee098e30dd504dcb7aa00e8ee13471ba396e874e8748473f7ca118b13d"
REPORT_NAME="GTA_RADAR_TORONTO_20_ARCHIVED_PERMIT_LIVE_FINDINGS.json"
MIN_ROWS=20


def validate_fixture(path):
    path=Path(path)
    with path.open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        required=permit.REQUIRED|{"source_record_date"}
        if not required<=set(reader.fieldnames or ()):
            raise ValueError("Archived City permit fixture schema is incomplete")
        rows=list(reader)
    if len(rows)!=MIN_ROWS:
        raise ValueError("Expected exactly 20 independently sampled permit records")
    unique_keys=set()
    unique_projects=set()
    unique_sites=set()
    for row in rows:
        if row["source_id"]!=permit.SOURCE:
            raise ValueError("Unrecognized archived City source")
        keys,why=permit.split_source_keys(row)
        if why or len(keys)!=1:
            raise ValueError("Expected one exact archived permit/revision per project: "+why)
        key=keys[0][0]
        if key in unique_keys:
            raise ValueError("Duplicate source key in independently sampled evidence")
        unique_keys.add(key)
        unique_projects.add(row["project_id"])
        site=graph.normalize_address(row["address"])[0]
        if not site:
            raise ValueError("Missing physical-site identity in archived sample")
        unique_sites.add(site)
    if len(unique_projects)!=MIN_ROWS or len(unique_sites)!=MIN_ROWS:
        raise ValueError("Archive sample must contain 20 distinct projects and civic sites")
    return rows


def run(out,*,fixture=FIXTURE,fetch=permit._get_payload,check_cleared=True):
    rows=validate_fixture(fixture)
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    result={
        "mode":"ISOLATED_REAL_TORONTO_CKAN_ARCHIVED_TWENTY_PERMIT_VALIDATION",
        "archived_original_daily_source_sha256":ORIGINAL_DAILY_CSV_SHA256,
        "selected_fixture_sha256":hashlib.sha256(Path(fixture).read_bytes()).hexdigest(),
        "record_selection":"20 source IDs at 20 distinct public permit sites; one constituent key each",
        "archived_source_dates_are_not_first_publication_dates":True,
        "current_source_rows_exactly_checked":False,
        "has_not_run_radar_collector":True,
        "has_not_modified_radar_sqlite":True,
        "personal_contact_research_performed":False,
        "source_attribution":permit.TORONTO_LICENSE,
        "source_licence_url":permit.TORONTO_LICENSE_URL,
        "actual_current_buyer_verified":False,
        "active_open_supplier_contracts_verified":0,
        "commercial_production_accepted":False,
        "batch_results":[],
        "source_acceptance":None,
        "errors":[]
    }
    report_path=out/REPORT_NAME
    try:
        with tempfile.TemporaryDirectory(prefix="toronto_archived_ckan_") as tmp:
            scratch=Path(tmp)
            # Replicate only the sanitized archived source CSV shape in scratch.
            with (scratch/permit.DAILY_CSV).open("w",encoding="utf-8-sig",newline="") as stream:
                fields=list(rows[0])
                writer=csv.DictWriter(stream,fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            city_dir=out/"TORONTO_PERMIT_EVIDENCE_PILOT"
            for offset in (0,10):
                status=permit.run(scratch,city_dir,live=True,live_limit=10,
                                  live_offset=offset,check_cleared=check_cleared,
                                  fetch=fetch)
                result["batch_results"].append({
                    "offset":offset,
                    "active_exact_query_attempts":status["live_record_queries_attempted"],
                    "active_exact_payloads_received":status["live_exact_record_payloads_received"],
                    "cleared_exact_queries_attempted":status["cleared_exact_queries_attempted"],
                    "cleared_exact_matches":status["cleared_exact_source_records_received"],
                    "live_api_status":status["live_status"],
                    "missing_or_unavailable_cleared_source":status["cleared_source_error"],
                    "immutable_batch_file":status["immutable_live_batch_file"],
                })
            accept=acceptance.run(city_dir/permit.LIVE_BATCH_DIR,city_dir)
            result["source_acceptance"]={
                "recent_unique_exact_active_source_records":
                    accept["recent_unique_exact_ckan_source_records"],
                "distinct_project_folders":accept["distinct_project_folders_rechecked"],
                "distinct_physical_sites":accept["distinct_physical_sites_rechecked"],
                "source_stage_categories":accept["source_stage_buckets_covered"],
                "exact_cleared_historical_records":
                    accept["recent_distinct_exact_cleared_history_records"],
                "rejection_reasons":accept["rejected_or_unproven_counts"],
                "source_sample_gate_passed":accept["official_source_sample_gate_passed"],
                "commercial_production_accepted":False,
            }
            result["current_source_rows_exactly_checked"]=(
                accept["recent_unique_exact_ckan_source_records"]+
                accept["recent_distinct_exact_cleared_history_records"]>0
            )
    except Exception as exc:
        result["errors"].append(type(exc).__name__+": "+str(exc)[:250])
    result["api_evidence_sample_passed"]=bool(
        result["source_acceptance"] and
        result["source_acceptance"]["source_sample_gate_passed"] and
        not result["errors"])
    result["timestamp_utc"]=dt.datetime.now(dt.timezone.utc).isoformat()
    report_path.write_text(json.dumps(result,indent=2,ensure_ascii=False),
                           encoding="utf-8")
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,default=Path("toronto_archived_source_verification"))
    p.add_argument("--fixture",type=Path,default=FIXTURE)
    p.add_argument("--no-cleared",action="store_true",
                   help="Skip historical cleared lookup if no active match")
    args=p.parse_args()
    result=run(args.out,fixture=args.fixture,check_cleared=not args.no_cleared)
    print(json.dumps(result,indent=2,ensure_ascii=False))
    if not result["api_evidence_sample_passed"]:
        raise SystemExit(2)


if __name__=="__main__":
    main()
