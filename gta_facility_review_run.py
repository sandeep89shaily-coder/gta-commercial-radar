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
from v6_daily_pipeline import find_workspace


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
        "verified_open_supplier_contracts":0,
        "buyers_verified":0,
        "outreach_authorized":False,
        "new_records_published_claimed":False,
        "graph_status_file":str(graph_dir/graph.OUTPUT_STATUS),
        "dossier_status_file":str(dossier_dir/dossiers.REPORT_STATUS),
        "dossier_csv":str(dossier_dir/dossiers.DOSSIERS_CSV),
        "dossier_html":str(dossier_dir/dossiers.REPORT_HTML),
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
