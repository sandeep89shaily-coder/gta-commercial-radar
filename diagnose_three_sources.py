"""Print real source failures from the three-collector desktop retest.

No network calls; no changes to any SQLite database, V8, scheduler or AI.
Shows what failed instead of hiding actionable error behind a 0/1 exit code.
"""
from __future__ import annotations
import argparse
import csv
from pathlib import Path

TARGETS=[
 ("IESO","EARLY_CUES_SOURCE_STATUS.csv","ieso_connections"),
 ("Brampton PDC","EARLY_DISCOVERY_SOURCE_STATUS.csv","brampton_planning_agendas"),
 ("Ajax","EARLY_AJAX_SOURCE_STATUS.csv","ajax_planning_properties"),
]
PASS={"SUCCESS","SUCCESS_INDEX_ONLY"}

def parse_source_status(directory):
    items=[]
    for label,filename,identifier in TARGETS:
        file=Path(directory)/filename
        if not file.is_file():
            items.append((label,"NOT_RUN",0,
                 "Status CSV missing. Source command may have crashed before writing it."))
            continue
        try:
            with file.open(encoding="utf-8-sig",newline="") as handle:
                rows=list(csv.DictReader(handle))
            row=next((r for r in rows if r.get("source_id")==identifier),None)
            if row is None:
                items.append((label,"NO_MATCHING_SOURCE_STATUS",0,
                     "Status file does not describe this source. Run the versioned three-source retry."))
                continue
            state=row.get("status") or row.get("state") or "UNKNOWN"
            count=row.get("fetched") or row.get("parsed") or "0"
            explanation=" | ".join(part for part in (
                row.get("error","").strip(),row.get("warning","").strip(),
                row.get("coverage","").strip()) if part).strip()
            items.append((label,state,count,explanation or "No additional publisher notes"))
        except (OSError,UnicodeError,csv.Error) as error:
            items.append((label,"UNREADABLE_STATUS",0,str(error)[:200]))
    return items

def run(directory):
    print("\n=== GTA Radar three official sources: exact diagnostics ===")
    problems=0
    for label,status,n,explanation in parse_source_status(directory):
        print(f"\n{label}: {status} | fetched/parsed: {n}")
        print("Reason:",explanation[:450])
        if status not in PASS:
            problems+=1
    print("\nSUCCESS means publisher source retrieved, not a verified sales lead.")
    print("PARTIAL_CALENDAR_ONLY means Brampton meeting IDs only, not agenda items.")
    print("Existing database snapshots preserved on source failures.")
    print("Problems to investigate:",problems)
    return 0 if problems==0 else 1

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir",default="GTA_RADAR_RESULTS")
    args=p.parse_args()
    raise SystemExit(run(args.output_dir))
