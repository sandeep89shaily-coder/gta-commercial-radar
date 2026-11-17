"""Reconcile actual failed municipal sources across separate Radar subsystems.

The consolidated collection-health report previously marked Mississauga as
zero failed sources because its working HTML collector concealed two blocked
official GIS layers run by a separate council stage. Count exact failed feeds,
not city configuration or "stage PASSED" booleans. No source retrieval/AI.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

STATUS = "GTA_RADAR_CROSS_COLLECTOR_HEALTH.json"
CSV = "GTA_RADAR_CROSS_COLLECTOR_SOURCE_FAILURES.csv"

COUNCIL = (
    ("Mississauga",
     "COUNCIL_INTELLIGENCE_REVIEW/MISSISSAUGA_OFFICIAL_GIS_SOURCE_AUDIT/MISSISSAUGA_OFFICIAL_GIS_SOURCE_AUDIT.json",
     "MISSISSAUGA_OFFICIAL_GIS_AUDIT", "layers", "layer"),
    ("Brampton",
     "COUNCIL_INTELLIGENCE_REVIEW/BRAMPTON_OFFICIAL_GIS_PLANNING/BRAMPTON_OFFICIAL_GIS_SOURCE_STATUS.json",
     "BRAMPTON_OFFICIAL_GIS", "layer_results", "name"),
)


def _json(path):
    try:
        result = json.loads(Path(path).read_text(encoding="utf-8"))
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _is_failed(status):
    token = str(status or "").upper()
    return any(x in token for x in ("FAIL", "BLOCK", "DENIED", "HELD",
                                     "INCOMPLETE", "RESTRICTED", "SOURCE_FAILED"))


def extra_source_failures(root):
    """Failures omitted from the original collection-truth source registry.

    Not a count of independent projects or a substitute for permissions.
    Other existing GIS/HTML collectors are already counted in collection_truth.
    """
    root = Path(root)
    errors = {}
    for city, rel, source, field, id_field in COUNCIL:
        obj = _json(root / rel)
        layer_rows = obj.get(field, [])
        if not isinstance(layer_rows, list):
            continue
        seen = set()
        for layer in layer_rows:
            if not isinstance(layer, dict) or not _is_failed(layer.get("status")):
                continue
            name = str(layer.get("layer") or layer.get(id_field) or "UNKNOWN_LAYER")
            if name in seen:
                continue
            seen.add(name)
            reason = str(layer.get("reason") or layer.get("error") or "")[:250]
            errors.setdefault(city, []).append({
                "city": city, "source_id": source + ":" + name,
                "status": str(layer.get("status", ""))[:90],
                "reason": reason,
                "access_failure": any(x in reason.upper() for x in
                    ("ROBOTS", "HTTP_403", "ACCESS_DENIED", "PERMISSION")),
            })
    return errors


def build(results):
    root = Path(results)
    if not root.is_dir():
        raise FileNotFoundError("EXISTING_RESULTS_REQUIRED")
    supplement = extra_source_failures(root)
    rows = [item for items in supplement.values() for item in items]
    previous = _json(root / "GTA_RADAR_COLLECTION_ACCEPTANCE.json")
    reconciled = _json(root / "GTA_RADAR_MUNICIPAL_RECOVERY_STATUS.json")
    try:
        with (root / "GTA_RADAR_COLLECTION_HEALTH.csv").open(
                encoding="utf-8-sig", newline="") as fp:
            original = list(csv.DictReader(fp))
    except OSError:
        original = []
    original_by_city = {item.get("city"): item for item in original}
    cities = []
    for city in sorted(set(original_by_city) | set(supplement)):
        src = original_by_city.get(city, {})
        extra = supplement.get(city, [])
        base = int(src.get("source_failures") or 0)
        access = int(src.get("access_failures") or 0)
        applications = int(src.get("application_files") or 0)
        cities.append({
            "city": city,
            "canonical_application_files_not_new_projects": applications,
            "original_reported_failed_sources": base,
            "extra_council_gis_failures": len(extra),
            "reconciled_source_failures": base + len(extra),
            "reconciled_access_failures": access + sum(
                1 for item in extra if item["access_failure"]),
            "source_coverage": (
                "PARTIAL_APPLICATION_RECORDS_WITH_FAILED_PARALLEL_FEEDS"
                if applications and base + len(extra) else
                "SOURCE_FAILURE_NO_CONFIRMED_APPLICATION_RECORDS"
                if base + len(extra) else
                "SOME_APPLICATION_RECORDS_NOT_CITYWIDE_COMPLETE"
                if applications else "NO_APPLICATION_RECORDS_COVERAGE_UNKNOWN"),
            "live_feed_completeness_verified": False,
            "original_documented_errors": src.get("source_notes", ""),
            "extra_documented_errors": " | ".join(
                x["source_id"] + ":" + x["reason"] for x in extra)[:900],
        })
    output = {
        "status": "CROSS_STAGE_SOURCE_ACCESS_RECONCILED_NOT_CITYWIDE_VERIFIED",
        "cities_checked": len(cities),
        "cities_with_any_failed_source": sum(
            x["reconciled_source_failures"] > 0 for x in cities),
        "new_application_records_proven_by_this_audit": 0,
        "buyer_contacts_proven_by_this_audit": 0,
        "missing_citywide_coverage_still_unresolved": True,
        "per_city": cities,
        "extra_explicit_failed_sources": rows,
        "source_warning": ("A successful municipality index and a successful "
                           "overall run do not establish coverage if another "
                           "official collector is blocked. Failures here refer "
                           "to source attempts, not absent real-world projects."),
        "paid_calls": 0, "network_calls": 0,
    }
    (root / STATUS).write_text(json.dumps(output, indent=2), encoding="utf-8")
    with (root / CSV).open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=(
            "city", "source_id", "status", "reason", "access_failure"))
        writer.writeheader()
        writer.writerows(rows)
    return output
