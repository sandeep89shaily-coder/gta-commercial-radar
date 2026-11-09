"""One manual Monday run: existing Radar + all four isolated intelligence pilots.

Runs the existing collector once, then read-only pilot stages on that workspace.
Industrial ERO fetch is robots-gated, limited to <=10 notices; AI harness stays
free/preflight because the core collector already owns the shared paid budget.
Each stage gets a log and status; failed stages never become verified leads.
"""
from __future__ import annotations
import argparse
import datetime as dt
import html
import json
import subprocess
import sys
from pathlib import Path

from v6_daily_pipeline import find_workspace

ROOT = Path(__file__).resolve().parent
REPORT = "MONDAY_FULL_RADAR_STATUS.json"
INDEX = "MONDAY_FULL_RADAR_REPORT.html"


def stages(workspace, results, *, industrial_limit=10, skip_collection=False):
    ws, out = str(workspace), str(results)
    base = [
        ("daily_radar", ["gta_total_intelligence_run.py", "--workspace", ws], True),
        ("industrial_equipment", ["gta_industrial_equipment_run.py",
                                  "--workspace", ws, "--limit", str(industrial_limit)], False),
        ("commercial_activation", ["gta_commercial_activation_run.py",
                                   "--workspace", ws], False),
        ("facility_evidence", ["gta_facility_review_run.py",
                               "--workspace", ws, "--results", out], False),
        ("toronto_20_source_research", ["gta_toronto_20_commercial_review.py",
                                       "--out", str(results / "TORONTO_20_COMMERCIAL_REVIEW")], False),
        ("ai_harness_free", ["gta_agent_harness.py",
                             "--results", out], False),
    ]
    if skip_collection:
        base = base[1:]
    return base


def execute(workspace=None, *, industrial_limit=10, skip_collection=False,
            runner=None):
    if not 0 <= int(industrial_limit) <= 10:
        raise ValueError("industrial_limit must be between 0 and 10")
    ws = Path(find_workspace(workspace))
    results = ws / "GTA_RADAR_RESULTS"
    results.mkdir(parents=True, exist_ok=True)
    out = results / "MONDAY_FULL_RADAR"
    logs = out / "LOGS"
    logs.mkdir(parents=True, exist_ok=True)
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    report = {
        "mode": "MANUAL_COMPLETE_RADAR_REVIEW",
        "started_utc": started,
        "workspace": str(ws),
        "collection_performed": not skip_collection,
        "fresh_collection_verified": False,
        "industrial_official_fetch_maximum": industrial_limit,
        "ai_harness_mode": "FREE_PREFLIGHT_NO_ADDITIONAL_PAID_REQUESTS",
        "buyer_verified_by_integration": False,
        "open_supplier_contract_verified_by_integration": False,
        "outreach_performed": False,
        "status": "RUNNING",
        "stages": [],
    }
    manifest = out / REPORT
    index = out / INDEX

    def save():
        manifest.write_text(json.dumps(report, indent=2), encoding="utf-8")

    def render():
        tr = "".join(
            "<tr><td>" + html.escape(row["name"]) +
            "</td><td>" + html.escape(row["status"]) +
            "</td><td>" + html.escape(str(row.get("exit_code", ""))) +
            "</td><td>" + html.escape(row["log"]) + "</td></tr>"
            for row in report["stages"]
        )
        index.write_text(
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>GTA Radar manual full run</title>"
            "<style>body{font:15px Arial;margin:2rem;max-width:1100px}"
            "table{border-collapse:collapse;width:100%}"
            "th,td{padding:9px;border:1px solid #bbb;text-align:left}</style>"
            "</head><body><h1>GTA Radar — all-pilot manual run</h1>"
            "<p>Status: <b>" + html.escape(report["status"]) + "</b></p>"
            "<p>Collector: " + ("fresh output required" if not skip_collection else
                                 "SKIPPED; saved evidence may be older") + "</p>"
            "<p>Source events are not verified buyers, openings or available contracts.</p>"
            "<table><tr><th>Stage</th><th>Status</th><th>Exit</th><th>Log</th></tr>"
            + tr + "</table>"
            "<p>Review the individual pilot CSV/HTML reports under GTA_RADAR_RESULTS."
            " No automated outreach, scheduling or extra paid AI was authorized.</p>"
            "</body></html>", encoding="utf-8"
        )

    save()
    run = runner or subprocess.run
    for name, args, critical in stages(
            ws, results, industrial_limit=industrial_limit,
            skip_collection=skip_collection):
        log = logs / (name + ".log")
        cmd = [sys.executable, str(ROOT / args[0]), *args[1:]]
        try:
            with log.open("w", encoding="utf-8") as stream:
                result = run(cmd, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
            exit_code = result.returncode
            failure = ""
        except (OSError, ValueError) as exc:
            exit_code = 125
            failure = type(exc).__name__ + ": " + str(exc)[:200]
            log.write_text(failure, encoding="utf-8")
        row = {
            "name": name, "status": "PASSED" if exit_code == 0 else "FAILED",
            "exit_code": exit_code, "critical": critical,
            "log": str(log),
        }
        if failure:
            row["error"] = failure
        report["stages"].append(row)
        if name == "daily_radar":
            # Discovery itself refuses missing/stale daily output. Its success
            # does not mean evidence/commercial gates have been satisfied.
            report["fresh_collection_verified"] = exit_code == 0
        save()
        print(name + ": " + row["status"] + " | " + str(log), flush=True)

    passed = sum(x["status"] == "PASSED" for x in report["stages"])
    failed = [x["name"] for x in report["stages"] if x["status"] != "PASSED"]
    report["stage_successes"] = passed
    report["failed_stages"] = failed
    report["status"] = (
        "ALL_STAGES_RAN_REVIEW_ONLY" if not failed and not skip_collection
        else "REVIEW_COMPLETED_WITH_FAILURES" if failed
        else "SAVED_DATA_REVIEW_ONLY_NO_NEW_COLLECTION"
    )
    report["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    report["report_html"] = str(index)
    save()
    render()
    print("FULL RUN REPORT: " + str(index), flush=True)
    print("FULL RUN MANIFEST: " + str(manifest), flush=True)
    return 0 if not failed else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", help="Existing Desktop/new data workspace")
    parser.add_argument("--industrial-limit", type=int, default=10)
    parser.add_argument("--skip-collection", action="store_true",
                        help="Explicit historical-only review; cannot claim fresh run")
    args = parser.parse_args()
    try:
        return execute(args.workspace, industrial_limit=args.industrial_limit,
                       skip_collection=args.skip_collection)
    except (OSError, ValueError, FileNotFoundError) as exc:
        print("Cannot start Radar: " + type(exc).__name__ + ": " + str(exc))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
