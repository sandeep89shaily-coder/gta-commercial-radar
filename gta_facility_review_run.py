"""Manual-only offline shared evidence run (facility graph + dossier research queue).

Designed for one future acceptance run, not scheduled use. Never touches Radar
source SQLite, collector settings, daily runner, AI ledger, or pilot databases.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import gta_facility_intelligence as graph
import gta_facility_dossiers as dossiers
import gta_facility_role_review as role_review
import gta_toronto_permit_evidence as permit_evidence
import gta_toronto_permit_acceptance as permit_acceptance
import gta_toronto_dossier_source_overlay as verified_overlay
from v6_daily_pipeline import find_workspace,choose_database


def execute(workspace=None, *, results=None, as_of=None, max_age_days=180):
    if results is not None:
        folder = Path(results).expanduser().resolve()
    else:
        folder = Path(find_workspace(workspace)).resolve()/"GTA_RADAR_RESULTS"
    if not folder.is_dir():
        raise FileNotFoundError("Existing Radar results folder missing: "+str(folder))
    available = [(family,str(folder/filename)) for family,filename in graph.INPUTS
                 if (folder/filename).is_file()]
    if not available:
        raise FileNotFoundError("No existing Radar or pilot source exports; refusing empty output")
    date = (dt.date.fromisoformat(as_of) if isinstance(as_of,str) else
            as_of or dt.datetime.now(dt.timezone.utc).date())
    if not isinstance(date,dt.date):
        raise ValueError("as_of must be a YYYY-MM-DD date")
    graph_dir = folder/"FACILITY_INTELLIGENCE_PILOT"
    dossier_dir = folder/"FACILITY_DOSSIER_PILOT"
    graph_status = graph.run(folder,graph_dir,as_of=date,max_age_days=max_age_days)
    dossier_status = dossiers.run(graph_dir,dossier_dir)
    role_status = role_review.run(
        graph_dir,folder/"GTA_RADAR_PROJECT_OPPORTUNITIES.csv",dossier_dir)
    # A separate exact-record layer: never fetch live data in the combined
    # manual runner, and never block the graph if the local source DB is absent.
    permit_status = None
    permit_acceptance_status = None
    permit_overlay_status = None
    permit_db = None
    if (folder/permit_evidence.DAILY_CSV).is_file():
        try:
            workspace_root = Path(find_workspace(workspace)) if workspace is not None else folder.parent
            permit_db = choose_database(workspace_root)
        except (FileNotFoundError,OSError,ValueError):
            permit_db = None
        permit_dir=folder/"TORONTO_PERMIT_EVIDENCE_PILOT"
        permit_status = permit_evidence.run(
            folder,permit_dir,db=permit_db,live=False)
        # Offline evidence inventory, even when no explicit City rechecks
        # have ever been requested. Cannot promote commercial readiness.
        permit_acceptance_status=permit_acceptance.run(
            permit_dir/permit_evidence.LIVE_BATCH_DIR,permit_dir)
        # Source proof can only be attached to a research dossier after the
        # accepted CSV hash, source gate, exact permit ID and civic site agree.
        permit_overlay_status=verified_overlay.run(
            dossier_dir,permit_dir,dossier_dir)
    result = {
        "mode":"MANUAL_OFFLINE_EVIDENCE_REVIEW_ONLY",
        "as_of":date.isoformat(),
        "available_input_families":[family for family,_ in available],
        "available_input_paths":[path for _,path in available],
        "source_rows_read":graph_status["source_rows_seen"],
        "graph_site_identities":graph_status["sites_with_civic_identity"],
        "cross_source_civic_candidate_links":graph_status["cross_source_candidate_links"],
        "research_dossiers":dossier_status["candidate_dossiers"],
        "manual_evidence_tasks":dossier_status["manual_verification_tasks"],
        "unverified_company_role_hints":role_status["role_hints"],
        "role_hints_verified":0,
        "toronto_permit_audit_status":(
            "NOT_RUN_MISSING_DAILY_EXPORT" if permit_status is None else
            "NO_TORONTO_PERMITS_IN_EXISTING_EXPORT" if not
                permit_status["toronto_project_groups"] else
            "LOCAL_COLLECTOR_DATABASE_UNAVAILABLE_NOT_VERIFIED" if
                permit_status["local_snapshot_state"] != "LOCAL_SQLITE_READ_ONLY" else
            "NO_LOCAL_EXACT_PERMIT_PAYLOADS_MATCHED" if not
                permit_status["local_record_payloads_matched"] else
            "SOME_LOCAL_EXACT_PERMIT_PAYLOADS_MATCHED_NOT_LIVE_RECHECKED"),
        "toronto_constituent_permit_keys_found":(
            0 if permit_status is None else
            permit_status["distinct_original_constituent_keys"]),
        "toronto_exact_local_permit_payloads_matched":(
            0 if permit_status is None else
            permit_status["local_record_payloads_matched"]),
        "toronto_permit_evidence_status_file":(
            "" if permit_status is None else
            str(folder/"TORONTO_PERMIT_EVIDENCE_PILOT"/permit_evidence.AUDIT_JSON)),
        "toronto_saved_live_source_records":(
            0 if permit_acceptance_status is None else
            permit_acceptance_status["recent_unique_exact_ckan_source_records"]),
        "toronto_source_sample_gate_passed":(
            False if permit_acceptance_status is None else
            permit_acceptance_status["official_source_sample_gate_passed"]),
        "toronto_commercial_production_accepted":False,
        "toronto_dossiers_with_exact_city_permit_evidence":(
            0 if permit_overlay_status is None else
            permit_overlay_status["toronto_dossiers_with_exact_checked_permit_source"]),
        "toronto_permit_stage_disagreements_requiring_review":(
            0 if permit_overlay_status is None else
            permit_overlay_status["source_stage_difference_to_archived_project_summary"]),
        "toronto_permit_dossier_source_overlay_csv":(
            "" if permit_overlay_status is None else
            str(dossier_dir/verified_overlay.OUTPUT_CSV)),
        "verified_open_supplier_contracts":0,
        "buyers_verified":0,
        "outreach_authorized":False,
        "new_records_published_claimed":False,
        "graph_status_file":str(graph_dir/graph.OUTPUT_STATUS),
        "dossier_status_file":str(dossier_dir/dossiers.REPORT_STATUS),
        "dossier_csv":str(dossier_dir/dossiers.DOSSIERS_CSV),
        "dossier_html":str(dossier_dir/dossiers.REPORT_HTML),
        "role_review_csv":str(dossier_dir/role_review.OUT_CSV),
        "caveat":"This processes previously exported source snapshots, not a live run; "
                 "no newly published records or procurement opportunities are confirmed.",
    }
    (dossier_dir/"GTA_RADAR_MANUAL_EVIDENCE_RUN_STATUS.json").write_text(
        json.dumps(result,indent=2),encoding="utf-8")
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace",type=Path,help="Existing Radar new data folder")
    parser.add_argument("--results",type=Path,help="Existing GTA_RADAR_RESULTS directly")
    parser.add_argument("--as-of",help="Reference date YYYY-MM-DD, default local UTC today")
    parser.add_argument("--max-age-days",type=int,default=180)
    args=parser.parse_args()
    try:
        result=execute(args.workspace,results=args.results,
                       as_of=args.as_of,max_age_days=args.max_age_days)
    except (FileNotFoundError,ValueError,OSError) as exc:
        print("Facility review refused: "+str(exc))
        raise SystemExit(2) from exc
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
