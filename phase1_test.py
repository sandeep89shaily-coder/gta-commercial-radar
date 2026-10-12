"""One-click Phase 1 integration test: Brampton, Toronto, Mississauga only.

Preserves existing databases and checkpoints. Does not run the lead engine,
AI enrichment or municipal sources outside Phase 1. Runs unit tests first, then
a bounded live collector sequence. Creates a privacy-conscious diagnostic ZIP
with aggregate counts, error statuses and stage outcomes only; NO SQLite files,
individual businesses, raw records or full logs are included.

Windows launcher: TEST_PHASE1.bat
"""
from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
ZIP_PATH = DATA / "PHASE1_TEST_RESULTS.zip"
LOCAL_LOGS = DATA / "phase1_test_logs"

MUNICIPAL_SOURCES = (
    "brampton_building_permits",
    "mississauga_issued_building_permits",
    "toronto_active_building_permits",
    "toronto_business_licences",
    "toronto_dinesafe",
    "toronto_development_applications",
)

# Steps are scoped to Phase 1. No full government backfill or AI processing.
STEPS = (
    ("regression_tests", ("-m", "unittest", "discover", "-s", "tests"), 180),
    ("phase1_main_collectors",
     ("main.py", "poll") + tuple(item for sid in MUNICIPAL_SOURCES for item in ("--source", sid)),
     1800),
    ("brampton_source_check", ("brampton_network.py", "--activity-limit", "1000"), 1800),
    ("toronto_live_catalogue", ("toronto_catalog_audit.py", "--force"), 600),
    ("toronto_department_coverage", ("toronto_coverage.py",), 120),
    ("toronto_schema_checks", ("toronto_source_validator.py", "--force"), 600),
    ("toronto_public_records", ("toronto_public_records.py",), 1800),
    ("toronto_signal_export", ("toronto_signals.py",), 180),
    ("mississauga_live_catalogue", ("mississauga_catalog_audit.py", "--force"), 900),
    ("mississauga_planning_records", ("mississauga_planning_records.py",), 1200),
    ("mississauga_procurement_portals", ("mississauga_procurement.py",), 450),
    ("mississauga_signal_export", ("mississauga_signals.py",), 180),
)

CITY_ARCHIVES = (
    ("brampton", "brampton_sources.sqlite"),
    ("toronto", "toronto_priority_sources.sqlite"),
    ("mississauga_planning", "mississauga_planning_sources.sqlite"),
    ("mississauga_procurement", "mississauga_procurement_sources.sqlite"),
)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def redact(message):
    """Report source failure shape, not home directory names or credentials."""
    text = str(message or "")[:700]
    text = re.sub(r"(?i)C:[/\\]Users[/\\][^/\\\s]+", r"C:\\Users\\[redacted]", text)
    text = re.sub(r"(?i)(api[_-]?key|token|password|authorization)\s*[:=]\s*[^\s&;,]+",
                  r"\1=[redacted]", text)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted-email]", text)
    return text[:340]


def db_readonly(path):
    if not path.is_file():
        return None
    # Read-only SQLite mode; no WAL checkpoint and no schema migrations.
    return sqlite3.connect("file:" + path.resolve().as_posix() + "?mode=ro", uri=True)


def select_safe(db, query, params=()):
    try:
        return db.execute(query, params).fetchall()
    except sqlite3.DatabaseError:
        return []


def city_source_summary(city, filename):
    db = db_readonly(DATA / filename)
    if db is None:
        return {"city": city, "database": "NOT_PRESENT", "sources": []}
    try:
        if city == "brampton":
            rows = select_safe(db, """SELECT id,department,access_status
                FROM sources ORDER BY department,id""")
            history = select_safe(db, """SELECT source_id,status,seen,created,changed,detail
                FROM runs WHERE id IN (SELECT MAX(id) FROM runs GROUP BY source_id)
                ORDER BY source_id""")
            recent = {r[0]: r for r in history}
            sources = []
            for sid, dept, state in rows:
                record = recent.get(sid)
                sources.append({"id": sid, "department": dept or "",
                    "status": (record[1] if record else state) or "UNKNOWN",
                    "checked": record[2] if record else None,
                    "created": record[3] if record else None,
                    "modified": record[4] if record else None,
                    "error": redact(record[5]) if record and record[1] == "ERROR" else ""})
            return {"city": city, "database": "PRESENT", "sources": sources}
        if city == "mississauga_procurement":
            rows = select_safe(db, """SELECT source_id,status,parsed_bid_count
                FROM public_pages ORDER BY source_id""")
            results = [{"id": sid, "status": state, "parsed_bid_count": count}
                       for sid, state, count in rows]
            failures = select_safe(db, """SELECT source_id,detail FROM runs
                WHERE status='ERROR' AND id IN
                  (SELECT MAX(id) FROM runs GROUP BY source_id)""")
            for sid, detail in failures:
                results.append({"id":sid,"status":"ERROR","error":redact(detail)})
            return {"city": city, "database": "PRESENT", "sources": results}
        rows = select_safe(db, """SELECT source_id,status,fetched,created,updated,detail
            FROM runs WHERE id IN (SELECT MAX(id) FROM runs GROUP BY source_id)
            ORDER BY source_id""")
        return {"city": city, "database": "PRESENT",
                "sources": [{"id":sid,"status":status,"fetched":count,
                             "created":created,"updated":updated,
                             "error":redact(detail) if status=="ERROR" else ""}
                            for sid,status,count,created,updated,detail in rows]}
    finally:
        db.close()


def main_source_summary():
    db = db_readonly(DATA / "radar.sqlite")
    if db is None:
        return {"database":"NOT_PRESENT","sources":[]}
    try:
        placeholders = ",".join("?" for _ in MUNICIPAL_SOURCES)
        query = ("""SELECT source_id,success,record_count,new_count,updated_count,error
                    FROM runs WHERE run_id IN
                    (SELECT MAX(run_id) FROM runs WHERE source_id IN (""" +
                 placeholders + """) GROUP BY source_id) ORDER BY source_id""")
        records = select_safe(db, query, MUNICIPAL_SOURCES)
        return {"database":"PRESENT","sources":[
            {"id":sid, "success":bool(ok),"fetched":count,"new":new,
             "updated":updated,"error":redact(err) if not ok else ""}
            for sid,ok,count,new,updated,err in records]}
    finally:
        db.close()


def safe_error_tail(log_path):
    """Return the final exception message, not just 'Traceback'; never export raw logs."""
    if not log_path.is_file():
        return ""
    # Bound memory and avoid exposing stack frames, data rows or entire logs.
    from collections import deque
    with log_path.open(encoding="utf-8", errors="replace") as source:
        tail = [line.strip() for line in deque(source, maxlen=100) if line.strip()]
    if not tail:
        return ""
    # Python exceptions are usually named ValueError, requests.exceptions.HTTPError,
    # etc. The original filter missed those and reported only 'Traceback'.
    exception_line = re.compile(
        r"(?:^|\s)(?:[\w.]+(?:Error|Exception|Exit)|ERROR|FAILED)\s*:", re.I)
    matches = [line for line in tail if exception_line.search(line)]
    if matches:
        return redact(" | ".join(matches[-2:]))
    # Non-Python failures can also return nonzero without a traceback.
    fallback = [line for line in tail
                if not line.startswith(("Traceback (most recent call last):",
                                        'File "', "^"))]
    return redact(fallback[-1] if fallback else "No error details in local log")


def execute_step(name, command, timeout, logger=print):
    LOCAL_LOGS.mkdir(parents=True, exist_ok=True)
    logfile = LOCAL_LOGS / (name + ".log")
    started = now()
    began = time.monotonic()
    logger("RUN:", name, flush=True)
    try:
        with logfile.open("w",encoding="utf-8",errors="replace") as output:
            proc = subprocess.run([sys.executable, *command], cwd=ROOT,
                                  stdout=output,stderr=subprocess.STDOUT,
                                  timeout=timeout,check=False)
        code=proc.returncode
        status="PASS" if code==0 else "FAIL"
    except subprocess.TimeoutExpired:
        code=None
        status="TIMEOUT"
    except OSError as exc:
        code=None
        status="ERROR"
        logfile.write_text(redact(str(exc)),encoding="utf-8")
    elapsed=round(time.monotonic()-began,1)
    logger(" ", status, "-", name, "-", elapsed, "sec",flush=True)
    return {"step":name,"started_at":started,"finished_at":now(),
            "status":status,"return_code":code,"elapsed_seconds":elapsed,
            "error_excerpt":safe_error_tail(logfile) if status!="PASS" else ""}


def summarize(results, started):
    return {
        "generated_at": now(),
        "started_at": started,
        "scope": ["Brampton", "Toronto", "Mississauga"],
        "steps": results,
        "phase1_radar": main_source_summary(),
        "archives": [city_source_summary(city,filename) for city,filename in CITY_ARCHIVES],
        "catalogues": [{
            "city": city, "status": (
                {"dataset_count": count, "commercial_candidates": prioritized}
                if count is not None else "NOT_AVAILABLE")
        } for city,count,prioritized in (
            catalogue_status("toronto_catalog_inventory.json","package_count","priority_candidates","Toronto"),
            catalogue_status("mississauga_catalog_inventory.json","item_count","commercial_candidates","Mississauga")
        )],
        "note": "Local integration results, not proof of record completeness, licence rights, newly published leads or uninterrupted daily scheduling. ZIP contains only diagnostic aggregates; full source logs remain local."
    }


def catalogue_status(filename,count_key,candidate_key,city):
    try:
        data=json.loads((DATA/filename).read_text(encoding="utf-8"))
        return city,int(data[count_key]),int(data[candidate_key])
    except (OSError,ValueError,KeyError,TypeError):
        return city,None,None


def package(report):
    DATA.mkdir(exist_ok=True)
    summary_file=DATA/"phase1_test_summary.json"
    readable_file=DATA/"phase1_test_summary.txt"
    summary_file.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    lines=["GTA Radar — Phase 1 Combined Test", "Brampton • Toronto • Mississauga",
           "Generated: "+report["generated_at"], "",
           "Collector steps:"]
    for result in report["steps"]:
        lines.append("  %-34s %-9s %7.1fs" %
                     (result["step"],result["status"],result["elapsed_seconds"]))
        if result["error_excerpt"]:
            lines.append("    "+result["error_excerpt"])
    lines.extend(["", "Source health (latest available):"])
    for group in report["archives"]:
        lines.append("  "+group["city"]+": "+str(group["database"]) +
                     " / "+str(len(group["sources"]))+" sources reported")
        for source in group["sources"]:
            lines.append("    "+str(source["id"]) +": "+str(source["status"]) +
                         (" "+source["error"] if source.get("error") else ""))
    for entry in report["catalogues"]:
        lines.append("  "+entry["city"]+" open-data catalogue: "+str(entry["status"]))
    lines += ["", "Upload PHASE1_TEST_RESULTS.zip, not any SQLite database.",
              "No private record contents or full run logs included."]
    readable_file.write_text("\n".join(lines)+"\n",encoding="utf-8")
    tmp=ZIP_PATH.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp,"w",compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(summary_file,arcname=summary_file.name)
        archive.write(readable_file,arcname=readable_file.name)
    tmp.replace(ZIP_PATH)
    return ZIP_PATH


def run():
    DATA.mkdir(exist_ok=True)
    started=now()
    print("\nGTA RADAR — PHASE 1 COMBINED TEST",flush=True)
    if not (DATA/"radar.sqlite").is_file():
        print("Missing original data/radar.sqlite; no live collectors launched.",flush=True)
        results=[{"step":"preflight","status":"FAIL","started_at":started,
                  "finished_at":now(),"return_code":1,"elapsed_seconds":0.0,
                  "error_excerpt":"Missing existing Radar DB; run SETUP_DESKTOP_ONCE.bat if needed."}]
        destination=package(summarize(results,started))
        print("Diagnostic ZIP:",destination,flush=True)
        return 1
    results=[]
    for name,command,timeout in STEPS:
        result=execute_step(name,command,timeout)
        results.append(result)
        if name=="regression_tests" and result["status"]!="PASS":
            print("Safety checks failed: not running live collectors.",flush=True)
            break
    destination=package(summarize(results,started))
    print("\nTEST COMPLETE:",sum(x["status"]=="PASS" for x in results),
          "passed;",sum(x["status"]!="PASS" for x in results),"not passed",flush=True)
    print("Please upload ONLY this ZIP:",destination,flush=True)
    return 0 if all(x["status"]=="PASS" for x in results) else 1


if __name__=="__main__":
    raise SystemExit(run())
