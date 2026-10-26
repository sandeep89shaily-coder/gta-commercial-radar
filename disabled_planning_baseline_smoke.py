"""Temporary full-baseline smoke test for four disabled early-planning feeds.

No user data, production config edits, scheduled tasks, DeepSeek, or output
project records. Reports count/status metrics only.
"""
import csv
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

SOURCES=(
    "york_region_active_development_applications",
    "mississauga_site_plan_applications",
    "mississauga_rezoning_applications",
    "richmond_hill_active_development_applications",
)
FIELDS=("source_id","full_baseline","records","first_pass_changes",
        "repeat_changes","status","detail")

def run(output="source-audit/DISABLED_PLANNING_BASELINE.csv"):
    target=Path(output)
    target.parent.mkdir(parents=True,exist_ok=True)
    reports=[]
    with tempfile.TemporaryDirectory(prefix="radar_disabled_planning_") as directory:
        data=Path(directory)/"data"
        cmd=[sys.executable,"main.py","poll","--data-dir",str(data)]
        for source in SOURCES:
            cmd.extend(["--source",source])
        try:
            first=subprocess.run(cmd,capture_output=True,text=True,timeout=480)
            print("Initial isolated poll exit:",first.returncode,flush=True)
            print((first.stdout or "")[-2500:],flush=True)
            print((first.stderr or "")[-1200:],flush=True)
            database=data/"radar.sqlite"
            if not database.exists():
                raise RuntimeError("No isolated database was created")
            with sqlite3.connect(database) as con:
                for source in SOURCES:
                    record=con.execute(
                        "SELECT success,baseline,record_count FROM runs "
                        "WHERE source_id=? ORDER BY run_id DESC LIMIT 1",(source,)).fetchone()
                    changes=con.execute(
                        "SELECT count(*) FROM changes WHERE source_id=?",(source,)).fetchone()[0]
                    ok=record is not None and record[0]==1 and record[1]==1 and record[2]>0 and changes==0
                    reports.append(dict(source_id=source,full_baseline=str(bool(record and record[1])),
                        records=record[2] if record else 0,first_pass_changes=changes,
                        repeat_changes="",status="BASELINE_PASS" if ok else "BASELINE_FAILED",
                        detail="First import must be a successful historical baseline with zero changes"))
            if all(x["status"]=="BASELINE_PASS" for x in reports):
                repeat=subprocess.run(cmd,capture_output=True,text=True,timeout=240)
                print("Repeat isolated poll exit:",repeat.returncode,flush=True)
                print((repeat.stdout or "")[-1000:],flush=True)
                with sqlite3.connect(database) as con:
                    for row in reports:
                        delta=con.execute("SELECT count(*) FROM changes WHERE source_id=?",
                                          (row["source_id"],)).fetchone()[0]
                        row["repeat_changes"]=delta
                        # Exit 2 means all snapshot sources correctly skipped
                        # because their scheduled refresh is not due yet.
                        if repeat.returncode not in (0,2) or delta!=0:
                            row["status"]="REPEAT_FAILED"
        except (subprocess.TimeoutExpired,OSError,sqlite3.DatabaseError,RuntimeError) as exc:
            print("Isolated baseline test could not finish:",type(exc).__name__,str(exc)[:260])
            if not reports:
                reports=[dict(source_id=source,full_baseline="",records=0,
                    first_pass_changes="",repeat_changes="",status="UNVERIFIED",
                    detail=(type(exc).__name__+": "+str(exc))[:220]) for source in SOURCES]
    with target.open("w",newline="",encoding="utf-8-sig") as out:
        w=csv.DictWriter(out,fieldnames=FIELDS);w.writeheader();w.writerows(reports)
    for row in reports:print("RESULT",row["source_id"],row["status"],
                           "records",row["records"],"changes",row["first_pass_changes"],
                           "repeat",row["repeat_changes"],flush=True)
    return 0 if len(reports)==len(SOURCES) and all(
        x["status"]=="BASELINE_PASS" for x in reports) else 1

if __name__=="__main__":
    raise SystemExit(run())
