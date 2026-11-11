"""Standalone manual industrial equipment pilot launcher for the existing Windows workspace.

Never schedules itself, runs main discovery, writes to the collector SQLite
database or invokes any AI APIs. Launch explicitly to opt into limited ERO reads.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from v6_daily_pipeline import choose_database, find_workspace
from gta_industrial_equipment_pilot import run as pilot_run
from gta_pilot_acceptance_pack import build as build_acceptance_pack

def execute(workspace=None, *, limit=10, pilot=pilot_run):
    ws = find_workspace(workspace)
    db = choose_database(ws)
    results = ws / "GTA_RADAR_RESULTS"
    out = results / "INDUSTRIAL_PILOT"
    summary = pilot(out, db=db, results=results,
                    fetch_official=True, fetch_limit=limit)
    acceptance = (build_acceptance_pack(results, pilot="industrial")
                  if (out / "GTA_RADAR_INDUSTRIAL_EQUIPMENT_REVIEW.csv").is_file()
                  else None)
    print(json.dumps({
        "review_queue": acceptance.get("industrial", {}).get("queue") if acceptance else "",
        "mode": "MANUAL_INDUSTRIAL_EQUIPMENT_PILOT",
        "db_read_only": str(db),
        "output": str(out),
        "notices_loaded": summary.get("official_notice_excerpts_loaded", 0),
        "equipment_candidates": summary.get("equipment_change_candidates", 0),
        "fetch_audit": summary.get("official_fetch_audit", []),
        "commercially_qualified_leads": 0,
        "notice": "Review only: no verified purchasing authority or open contracts.",
    }, indent=2))
    return summary

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", help="Optional existing Radar 'new data' folder")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    try:
        execute(args.workspace, limit=args.limit)
    except (FileNotFoundError, OSError) as exc:
        print("Cannot locate existing Radar workspace/database: " + str(exc))
        raise SystemExit(2) from exc

if __name__ == "__main__":
    main()
