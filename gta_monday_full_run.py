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
    # A source fetch is allowed only within a true operator-initiated
    # collection run, never a --skip-collection historical review.
    council_args = ["gta_council_integrated_manual.py",
                    "--workspace", ws, "--results", out]
    if not skip_collection:
        council_args.append("--fetch-brampton-featured")
        council_args.append("--fetch-brampton-official-gis")
        council_args.append("--fetch-mississauga-pdc")
        council_args.append("--fetch-mississauga-official-gis")
        council_args.append("--fetch-toronto-official-agendas")
        council_args.append("--fetch-toronto-schedule")
        council_args.append("--fetch-toronto-planning-notices")
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
        ("council_agenda_intelligence", council_args, False),
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

    def inspect_daily_stage():
        # Include sanitized primary diagnostics in the archived manifest. A
        # previous run's saved JSON must never be presented as today's stage.
        names=(("discovery", "GTA_RADAR_DISCOVERY_RUN_STATUS.json"),
               ("integrated", "GTA_RADAR_INTEGRATED_INTELLIGENCE_STATUS.json"),
               ("collector", "GTA_RADAR_V6_RUN.json"))
        details={}
        threshold=dt.datetime.fromisoformat(started).timestamp()-3
        for key, filename in names:
            path=results / filename
            try:
                if path.stat().st_mtime < threshold:
                    details[key]={"status":"OLDER_SAVED_EVIDENCE_NOT_TODAYS_RUN"}
                    continue
                data=json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data,dict):
                    raise ValueError("EXPECTED_JSON_OBJECT")
                if key=="discovery":
                    details[key]={k:data.get(k) for k in (
                        "status","completed","collection_exit_code",
                        "collector_status","code_check_status",
                        "meeting_document_pipeline_complete","optional_stage_failures",
                        "required_stage_failures")}
                elif key=="integrated":
                    details[key]={k:data.get(k) for k in (
                        "status","failed_stages","required_failed_stages",
                        "optional_failed_stages","blocked_sources",
                        "combined_records","cities_with_application_candidates_measured")}
                    details[key]["stage_errors"]=[{
                        "stage":str(s.get("stage",""))[:110],
                        "required":bool(s.get("required")),
                        "status":str(s.get("status",""))[:30],
                        "error":str(s.get("error",""))[:250]}
                        for s in data.get("stages",[]) if isinstance(s,dict)
                        and s.get("status") in ("FAILED","BLOCKED")][:35]
                else:
                    details[key]={k:data.get(k) for k in (
                        "status","projects","investigated","queue_stop_reason")}
            except (OSError, ValueError, TypeError) as exc:
                details[key]={"status":"NO_CURRENT_STAGE_DIAGNOSTIC",
                              "error_type":type(exc).__name__}
        return details

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
        if name == "council_agenda_intelligence":
            council_file = results / "COUNCIL_INTELLIGENCE_REVIEW" / "COUNCIL_INTEGRATED_REVIEW_STATUS.json"
            try:
                if council_file.stat().st_mtime < dt.datetime.fromisoformat(started).timestamp() - 3:
                    raise ValueError("OLDER_COUNCIL_EVIDENCE_NOT_TODAY")
                council_data = json.loads(council_file.read_text(encoding="utf-8"))
                report["council_review_diagnostics"] = {
                    key: council_data.get(key) for key in (
                        "status", "documents_considered", "documents_parsed",
                        "source_documents_missing", "source_documents_failed",
                        "source_documents_held", "source_manifest_status",
                        "agenda_to_application_permit_chains_verified",
                        "publisher_first_publications_verified", "paid_ai_usd")
                }
                report["council_review_diagnostics"]["index"] = council_data.get("official_index_audit", {})
                report["council_review_diagnostics"]["brampton_featured"] = council_data.get(
                    "brampton_featured_public_applications", {})
                report["council_review_diagnostics"]["brampton_official_gis_planning"] = council_data.get(
                    "brampton_official_gis_planning", {})
                report["council_review_diagnostics"]["brampton_gis_existing_radar_reconciliation"] = council_data.get(
                    "brampton_gis_existing_radar_reconciliation", {})
                report["council_review_diagnostics"]["mississauga_discovered_pdc"] = council_data.get(
                    "mississauga_discovered_pdc", {})
                report["council_review_diagnostics"]["toronto_exact_agenda_retrieval"] = council_data.get(
                    "toronto_exact_agenda_retrieval", {})
                report["council_review_diagnostics"]["toronto_official_meeting_schedule"] = council_data.get(
                    "toronto_official_meeting_schedule", {})
                report["council_review_diagnostics"]["toronto_schedule_to_agenda_item_link"] = council_data.get(
                    "toronto_schedule_to_agenda_item_link", {})
                report["council_review_diagnostics"]["toronto_official_planning_notices"] = council_data.get(
                    "toronto_official_planning_notices", {})
                report["council_review_diagnostics"]["mississauga_match"] = {
                    key: council_data.get("mississauga_20_case_comparison", {}).get(key)
                    for key in ("cases_reviewed", "missing_case_count",
                                "three_source_identity_review_candidates",
                                "early_detection_advantage_proven")
                }
            except (OSError, ValueError, TypeError, KeyError) as exc:
                report["council_review_diagnostics"] = {
                    "status": "NO_CURRENT_COUNCIL_STAGE_DIAGNOSTIC",
                    "error_type": type(exc).__name__
                }
        if name == "daily_radar":
            # Discovery itself refuses missing/stale daily output. Its success
            # does not mean evidence/commercial gates have been satisfied.
            report["fresh_collection_verified"] = exit_code == 0
            report["daily_radar_diagnostics"] = inspect_daily_stage()
        save()
        print(name + ": " + row["status"] + " | " + str(log), flush=True)

    # Read-only quality report is part of post-run evidence accounting, not a
    # new collector/stage. Preserve the established seven-stage contract.
    if not skip_collection:
        try:
            from gta_source_quality_v1 import run as run_source_quality
            quality = run_source_quality(results)
            report["source_quality"] = {
                "status": quality["status"],
                "municipalities_with_records": quality.get("municipalities_with_records", 0),
                "citywide_verified": 0,
                "buyer_leads_verified": 0,
                "report": str(results / "GTA_RADAR_SOURCE_QUALITY_V1.json"),
            }
        except (OSError, ValueError, ImportError) as exc:
            report["source_quality"] = {
                "status": "SOURCE_QUALITY_REPORT_FAILED",
                "error_type": type(exc).__name__,
            }
    else:
        report["source_quality"] = {"status": "NOT_RUN_HISTORICAL_MODE"}

    passed = sum(x["status"] == "PASSED" for x in report["stages"])
    failed = [x["name"] for x in report["stages"] if x["status"] != "PASSED"]
    report["stage_successes"] = passed
    report["failed_stages"] = failed
    integrated_diag=report.get("daily_radar_diagnostics",{}).get("integrated",{})
    report["optional_source_warnings"]={
        "optional_failed_stages":integrated_diag.get("optional_failed_stages") or [],
        "blocked_sources":integrated_diag.get("blocked_sources") or [],
        "details":integrated_diag.get("stage_errors") or []}
    has_warnings=bool(report["optional_source_warnings"]["optional_failed_stages"]
                      or report["optional_source_warnings"]["blocked_sources"])
    report["status"] = (
        "ALL_STAGES_RAN_WITH_SOURCE_WARNINGS_REVIEW_ONLY"
        if not failed and not skip_collection and has_warnings
        else "ALL_STAGES_RAN_REVIEW_ONLY" if not failed and not skip_collection
        else "REVIEW_COMPLETED_WITH_FAILURES" if failed
        else "SAVED_DATA_REVIEW_ONLY_NO_NEW_COLLECTION"
    )
    report["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    report["report_html"] = str(index)
    save()
    render()
    # Create one dated, bounded export *after* the final integration manifest
    # is written. Never include SQLite, API keys or live collector credentials.
    # Failure to package is reported, not disguised as a complete run.
    try:
        from gta_daily_result_archive import create as create_archive
        package = create_archive(results)
        report["archive_status"] = "CREATED_REVIEW_ONLY"
        report["run_archive"] = package["archive"]
        report["run_archive_freshness_gate"] = package["freshness_gate"]
        print("DATED REVIEW ZIP: " + package["archive"], flush=True)
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        report["archive_status"] = "FAILED_NOT_PACKAGED"
        report["archive_error"] = type(exc).__name__ + ": " + str(exc)[:250]
        print("ARCHIVE FAILED: " + report["archive_error"], flush=True)
    save()
    render()
    print("FULL RUN REPORT: " + str(index), flush=True)
    print("FULL RUN MANIFEST: " + str(manifest), flush=True)
    return 0 if not failed and report["archive_status"] == "CREATED_REVIEW_ONLY" else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", help="Existing Desktop/new data workspace")
    parser.add_argument("--industrial-limit", type=int, default=10)
    parser.add_argument("--skip-collection", action="store_true",
                        help="Explicit historical-only review; cannot claim fresh run")
    parser.add_argument("--unattended", action="store_true",
                        help="Accepted for the batch shortcut; controls console pause only")
    args = parser.parse_args()
    try:
        return execute(args.workspace, industrial_limit=args.industrial_limit,
                       skip_collection=args.skip_collection)
    except (OSError, ValueError, FileNotFoundError) as exc:
        print("Cannot start Radar: " + type(exc).__name__ + ": " + str(exc))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
