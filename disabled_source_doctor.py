"""Run the existing configured-source doctor on all disabled feeds in GitHub CI.

Only metadata/count requests. Does not enable feeds, create data DBs, collect
records, change existing snapshots, or call DeepSeek.
"""
import argparse
import csv
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

FIELDS=("source_id","family","mode","doctor","decision","full_count",
        "recent_count","reason")
KNOWN_EMPTY_DATES={"durham_planit_consents","durham_planit_opa",
                   "durham_business_sites"}

def evaluate(source, run=None, timeout=90):
    runner=run or subprocess.run
    sid=source["id"]
    row=dict(source_id=sid,family=source.get("family",""),mode=source.get("mode",""),
             doctor="NOT_CHECKED",decision="UNVERIFIED",full_count="",recent_count="",
             reason="")
    command=[sys.executable,"main.py","doctor","--source",sid]
    try:
        outcome=runner(command,capture_output=True,text=True,timeout=timeout)
        output=(str(outcome.stdout or "")+" "+str(outcome.stderr or "")).strip()
        detail=output.splitlines()[-1][:450] if output else "No output"
        row["reason"]=detail
        counts=re.search(r"full filtered count=([0-9,]+)",output)
        recent=re.search(r"recent-window count=([0-9,]+)",output)
        row["full_count"]=counts.group(1) if counts else ""
        row["recent_count"]=recent.group(1) if recent else ""
        row["doctor"]="PASS" if outcome.returncode==0 and "OK (" in output else "FAIL"
        if row["doctor"]!="PASS":
            row["decision"]="BLOCKED_DOCTOR"
        elif "incremental filter FAILED" in output:
            row["decision"]="BLOCKED_INCREMENTAL_QUERY"
        elif source.get("family")=="permit_history" or source.get("mode")=="backfill":
            row["decision"]="HISTORICAL_ONLY"
        elif source.get("family")=="business_directory":
            row["decision"]="ENRICHMENT_ONLY"
        elif not source.get("date_fields"):
            row["decision"]="REVIEW_DATE_SEMANTICS"
        elif sid in KNOWN_EMPTY_DATES:
            row["decision"]="REVIEW_EMPTY_DATES"
        else:
            row["decision"]="READY_FOR_ISOLATED_BASELINE_TEST"
    except subprocess.TimeoutExpired:
        row.update(doctor="TIMEOUT",decision="UNVERIFIED_TIMEOUT",
                   reason="Source doctor exceeded time limit; not proven broken")
    except OSError as exc:
        row.update(doctor="ERROR",decision="UNVERIFIED_TEST_ERROR",
                   reason=(type(exc).__name__+": "+str(exc))[:200])
    return row

def audit(config="config/sources.json",
          output="source-audit/DISABLED_SOURCE_DOCTOR.csv",workers=3,run=None):
    sources=json.loads(Path(config).read_text(encoding="utf-8"))
    disabled=[s for s in sources if s.get("enabled") is False]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        rows=list(executor.map(lambda s:evaluate(s,run=run),disabled))
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open("w",encoding="utf-8-sig",newline="") as file:
        writer=csv.DictWriter(file,fieldnames=FIELDS)
        writer.writeheader();writer.writerows(rows)
    print("Disabled source health check:",len(rows),"sources. No sources enabled.")
    for row in rows:
        print(row["source_id"],"::",row["doctor"],"::",row["decision"],
              ":: full",row["full_count"],":: recent",row["recent_count"],
              "::",row["reason"],flush=True)
    return rows

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",default="config/sources.json")
    parser.add_argument("--output",default="source-audit/DISABLED_SOURCE_DOCTOR.csv")
    args=parser.parse_args()
    audit(config=args.config,output=args.output)
