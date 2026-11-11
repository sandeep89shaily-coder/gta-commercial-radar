"""Separate Windows-friendly commercial activation pilot; no scheduled changes."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from v6_daily_pipeline import find_workspace,choose_database
from gta_commercial_activation_pilot import run
from gta_pilot_acceptance_pack import build as build_acceptance_pack

def execute(workspace=None, *, as_of=None, window_days=120, max_per_source=40000):
    ws=find_workspace(workspace)
    db=choose_database(ws)
    out=Path(ws)/"GTA_RADAR_RESULTS"/"COMMERCIAL_ACTIVATION_PILOT"
    summary=run(db,out,as_of=as_of,window_days=window_days,max_per_source=max_per_source)
    acceptance = (build_acceptance_pack(Path(ws)/"GTA_RADAR_RESULTS", pilot="activation")
                  if (out / "GTA_RADAR_COMMERCIAL_ACTIVATION_REVIEW.csv").is_file()
                  else None)
    print(json.dumps({
      "acceptance_sample": (acceptance.get("activation", {}).get("queue")
                            if acceptance else ""),
      "status":"OFFLINE_COMMERCIAL_ACTIVATION_REVIEW",
      "existing_database_read_only":str(db),"results":str(out),
      "records_scanned":summary["source_rows_total_read"],
      "candidates_for_manual_review":summary["activation_review_candidates"],
      "verified_business_openings":0,"verified_open_supplier_contracts":0,
      "note":"Source activity is not proof of opening or buying intent. No AI or outbound communication.",
    },indent=2))
    return summary

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace",help="Existing Radar 'new data' folder; auto-detects if omitted")
    p.add_argument("--as-of",default=None)
    p.add_argument("--window-days",type=int,default=120)
    p.add_argument("--max-per-source",type=int,default=40000)
    a=p.parse_args()
    try:
        execute(a.workspace,as_of=a.as_of,window_days=a.window_days,
                max_per_source=a.max_per_source)
    except (FileNotFoundError,OSError,ValueError) as exc:
        print("Pilot stopped; existing workspace/data not available: "+str(exc))
        raise SystemExit(2) from exc

if __name__=="__main__":main()
