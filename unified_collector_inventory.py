"""Per-source inventory for the one V8 pipeline; no collection or AI calls."""
import csv
import json
from datetime import datetime
from pathlib import Path

# One runner can monitor several independently identified public feeds.
# The four aliases below are *already configured in V8*, not four new feeds.
PILOT_GROUPS = {
    "early_planning_pilot": (
        "EARLY_SIGNALS_SOURCES_STATUS.csv", "status",
        ("brampton_preconsultation", "brampton_rezoning_opa", "brampton_site_plans",
         "mississauga_site_plans", "mississauga_rezonings",
         "york_region_development", "toronto_development")),
    "early_industrial_cues": (
        "EARLY_CUES_SOURCE_STATUS.csv", "state",
        ("ieso_connections", "burlington_project_pages")),
    "early_agendas": (
        "EARLY_DISCOVERY_SOURCE_STATUS.csv", "status",
        ("burlington_ward_discovery", "brampton_planning_agendas")),
    "early_hamilton": (
        "EARLY_HAMILTON_SOURCE_STATUS.csv", "status",
        ("hamilton_applications_gis", "hamilton_planning_notices")),
    "early_notices": (
        "EARLY_PUBLIC_NOTICES_SOURCE_STATUS.csv", "status",
        ("milton_notices", "pickering_proposals", "ero_proposal_watch")),
    "early_ajax": (
        "EARLY_AJAX_SOURCE_STATUS.csv", "status",
        ("ajax_planning_properties",)),
    "early_oakville": (
        "EARLY_OAKVILLE_SOURCE_STATUS.csv", "status",
        ("oakville_development",)),
    "early_markham": (
        "EARLY_MARKHAM_REPORT_SOURCE_STATUS.csv", "status",
        ("markham_circulated_application_reports",)),
    "early_investment_tenders": (
        "EARLY_INVESTMENT_TENDERS_STATUS.csv", "status",
        ("ontario_investment_news", "federal_open_tenders")),
}
OVERLAP_V8 = {
    "mississauga_site_plans": "mississauga_site_plan_applications",
    "mississauga_rezonings": "mississauga_rezoning_applications",
    "york_region_development": "york_region_active_development_applications",
    "toronto_development": "toronto_development_applications",
}
REVIEW_ONLY = {"early_markham", "early_investment_tenders"}
FIELDS = ("source_id", "group", "execution_status", "integration_status",
          "validation_state", "opportunity_role", "reactivation_decision", "reason")


def _status_rows(path):
    if not path.is_file():
        return {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        return {row.get("source_id"): row for row in csv.DictReader(f)
                if row.get("source_id")}


def _fresh(path, run_started):
    if run_started is None:
        return True
    try:
        timestamp = datetime.fromisoformat(str(run_started).replace("Z", "+00:00")).timestamp()
        return path.stat().st_mtime >= timestamp - 2
    except (OSError, ValueError, TypeError):
        return False


def build(results, config, steps, *, run_started=None):
    out = Path(results)
    output = out / "GTA_RADAR_ALL_SOURCE_STATUS.csv"
    source_defs = json.loads(Path(config).read_text(encoding="utf-8"))
    core_ids = {source["id"] for source in source_defs}
    review_path = Path(config).with_name("disabled_source_review.json")
    review = {}
    if review_path.is_file():
        checked = json.loads(review_path.read_text(encoding="utf-8"))
        review = {s["source_id"]: s for s in checked.get("sources", [])}

    rows = []
    for source in source_defs:
        active = bool(source.get("enabled", False))
        item = review.get(source["id"], {}) if not active else {}
        rows.append(dict(
            source_id=source["id"], group="CORE_CONFIG",
            execution_status="CONFIGURED_ENABLED" if active else "CONFIGURED_DISABLED",
            integration_status="CORE_ENGINE" if active else "NOT_ENABLED",
            validation_state="ACTIVE" if active else item.get("validation_state", "UNVERIFIED"),
            opportunity_role="CORE_SOURCE" if active else item.get("opportunity_role", "UNREVIEWED"),
            reactivation_decision="ENABLED" if active else item.get("reactivation_decision", "NOT_YET_DECIDED"),
            reason="" if active else item.get("integration_reason") or item.get("reason", "Awaiting safe activation")))

    executed = {step.get("step"): step.get("status") for step in steps}
    total_pilot_sources = 0
    unique_pilot_sources = 0
    for runner, (filename, status_column, source_ids) in PILOT_GROUPS.items():
        run_status = executed.get(runner)
        report = out / filename
        current = run_status == "SUCCESS" and report.is_file() and _fresh(report, run_started)
        statuses = _status_rows(report) if current else {}
        for source_id in source_ids:
            total_pilot_sources += 1
            mapped = OVERLAP_V8.get(source_id)
            if not mapped:
                unique_pilot_sources += 1
            elif mapped not in core_ids:
                raise ValueError("Missing V8 overlap mapping: " + mapped)
            source_state = statuses.get(source_id, {}).get(status_column, "").strip()
            execution = (source_state or "SOURCE_NOT_REPORTED") if current else (
                "STALE_STATUS_FILE" if run_status == "SUCCESS" and report.is_file()
                    else (run_status or "NOT_RUN_THIS_RUN"))
            integration = ("OVERLAPS_V8" if mapped else
                           "REVIEW_ONLY" if runner in REVIEW_ONLY else "EARLY_CHANGE_BRIDGE")
            reason = ("Same official source as V8 " + mapped if mapped else
                      "Document/tender signal only; not promoted to project leads"
                      if runner in REVIEW_ONLY else
                      "Post-baseline changes only; further qualification required")
            rows.append(dict(source_id=source_id, group=runner,
                             execution_status=execution, integration_status=integration,
                             validation_state="REPORTED_THIS_RUN" if source_state else "UNVERIFIED_THIS_RUN",
                             opportunity_role="EARLY_PILOT_SOURCE",
                             reactivation_decision="INTEGRATED_RUNNER",
                             reason=reason))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return output, {
        "inventory_count": len(rows),
        "disabled_count": sum(r["integration_status"] == "NOT_ENABLED" for r in rows),
        "review_only_pilots": sum(r["integration_status"] == "REVIEW_ONLY" for r in rows),
        "pilot_runner_count": len(PILOT_GROUPS),
        "pilot_source_definitions": total_pilot_sources,
        "pilot_source_overlaps_v8": len(OVERLAP_V8),
        "pilot_unique_outside_v8": unique_pilot_sources,
    }
