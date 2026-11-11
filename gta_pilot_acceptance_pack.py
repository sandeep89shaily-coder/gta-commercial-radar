"""Read-only acceptance queues for the existing industrial and activation pilots.

This module never validates a buyer, opening, source posting date or contract.
It consumes *already created* manual pilot CSV/status files; no SQLite writes,
web requests, AI calls, emails or changes to the daily collection runner.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

FOLDER = "PRIORITY_3_4_ACCEPTANCE_PACK"
INDUSTRIAL = "INDUSTRIAL_NOTICE_RECHECK.csv"
ACTIVATION = "ACTIVATION_SOURCE_SAMPLE_20.csv"
FACILITIES = "ACTIVATION_FACILITY_DOSSIERS_10.csv"
STATUS = "ACCEPTANCE_PACK_STATUS.json"

INDUSTRIAL_COLS = (
    "ero_number", "official_notice_url", "notice_stage", "proponent",
    "city", "site_address", "equipment_changes", "fetch_status",
    "source_hashes", "source_evidence_status", "buyer_verified",
    "supplier_package_available", "original_notice_rechecked",
    "site_and_stage_rechecked", "review_notes",
)
ACTIVATION_COLS = (
    "source_id", "source_record_key", "source_record_sha256",
    "source_dataset_url", "municipality", "site_address", "site_unit",
    "source_event_date", "radar_first_seen_at", "activation_stage",
    "business_name_unverified", "same_site_link_status", "source_excerpt",
    "original_record_rechecked", "tenant_verified", "opening_verified",
    "review_notes",
)
DOSSIER_COLS = (
    "municipality", "site_address", "site_unit", "source_record_keys",
    "source_dataset_urls", "source_event_dates", "activation_stages",
    "source_records_count", "same_site_tenant_verified", "business_opening_verified",
    "buyer_or_supplier_package_verified", "original_source_records_reviewed",
    "human_review_notes",
)


def _read_csv(path):
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path):
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _safe(v):
    value = str(v if v is not None else "")
    return "'" + value if value.startswith(("=", "+", "-", "@")) else value


def _write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({f: _safe(row.get(f, "")) for f in fields})


def _site(row):
    """Site-and-unit key, not proof of tenant or project identity."""
    city = str(row.get("municipality", "")).strip().casefold()
    address = re.sub(r"[^a-z0-9]+", " ", str(row.get("site_address", "")).casefold()).strip()
    unit = re.sub(r"[^a-z0-9]+", "", str(row.get("site_unit", "")).casefold())
    return city, address, unit


def _activation_sample(rows, limit=20):
    """Deterministically balance approved sources rather than choose only Toronto."""
    sources = defaultdict(list)
    for row in rows:
        sources[row.get("source_id", "")].append(row)
    for source in sources:
        sources[source].sort(key=lambda r: (
            r.get("source_event_date", ""), r.get("source_record_key", "")), reverse=True)
    keys = sorted(sources)
    result = []
    while len(result) < limit and any(sources.values()):
        for source in keys:
            if len(result) >= limit:
                break
            if sources[source]:
                result.append(sources[source].pop(0))
    return result


def _facility_queue(rows, limit=10):
    # Group by exact civic site/unit without inferring a common tenant.
    sites = defaultdict(list)
    for row in rows:
        key = _site(row)
        if all(key[:2]):
            sites[key].append(row)
    by_city = defaultdict(list)
    for key, members in sites.items():
        members.sort(key=lambda r: (
            r.get("source_event_date", ""), r.get("source_record_key", "")), reverse=True)
        by_city[key[0]].append((key, members))
    for groups in by_city.values():
        groups.sort(key=lambda p: (
            p[1][0].get("source_event_date", ""), len(p[1]), p[0]), reverse=True)
    selection = []
    cities = sorted(by_city)
    while len(selection) < limit and any(by_city.values()):
        for city in cities:
            if len(selection) >= limit:
                break
            if by_city[city]:
                selection.append(by_city[city].pop(0))
    result = []
    for (city, address, unit), members in selection:
        first = members[0]
        result.append({
            "municipality": first.get("municipality", ""),
            "site_address": first.get("site_address", ""),
            "site_unit": first.get("site_unit", ""),
            "source_record_keys": " | ".join(
                sorted({r.get("source_id", "")+":"+r.get("source_record_key", "")
                        for r in members})[:16]),
            "source_dataset_urls": " | ".join(sorted({
                r.get("source_dataset_url", "") for r in members if r.get("source_dataset_url")
            })),
            "source_event_dates": " | ".join(sorted({
                r.get("source_event_date", "") for r in members if r.get("source_event_date")
            })),
            "activation_stages": " | ".join(sorted({
                r.get("activation_stage", "") for r in members if r.get("activation_stage")
            })),
            "source_records_count": len(members),
            "same_site_tenant_verified": "NO",
            "business_opening_verified": "NO",
            "buyer_or_supplier_package_verified": "NO",
            "original_source_records_reviewed": "NOT_YET_RECHECKED",
            "human_review_notes": "",
        })
    return result


def build(results, *, pilot="all"):
    root = Path(results)
    out = root / FOLDER
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "status": "REVIEW_QUEUE_GENERATED_NOT_SOURCE_ACCEPTANCE",
        "source_folder": str(root), "pilot_selection": pilot,
        "human_verified_openings": 0, "human_verified_buyers": 0,
        "open_supplier_packages_verified": 0,
        "note": "Queues are derived from prior source snapshots; NOT 20 rechecked "
                "original records, 10 human-approved dossiers or live market acceptance.",
    }
    if pilot in ("all", "industrial"):
        folder = root / "INDUSTRIAL_PILOT"
        signals = _read_csv(folder / "GTA_RADAR_INDUSTRIAL_EQUIPMENT_REVIEW.csv")
        status = _read_json(folder / "GTA_RADAR_INDUSTRIAL_EQUIPMENT_STATUS.json")
        groups = defaultdict(list)
        for row in signals:
            if row.get("ero_number"):
                groups[row["ero_number"]].append(row)
        audit = {a.get("ero_number"): a.get("status", "")
                 for a in status.get("official_fetch_audit", [])
                 if isinstance(a, dict) and a.get("ero_number")}
        numbers = sorted(set(groups) | set(audit), reverse=True)
        source_rows = []
        for number in numbers:
            first = groups.get(number, [{}])[0]
            source_rows.append({
                "ero_number": number,
                "official_notice_url": first.get("official_notice_url") or (
                    "https://ero.ontario.ca/notice/" + number),
                "notice_stage": first.get("notice_stage", ""),
                "proponent": first.get("proponent", ""),
                "city": first.get("city", ""),
                "site_address": first.get("site_address", ""),
                "equipment_changes": " | ".join(sorted({
                    r.get("equipment", "")+":"+r.get("action", "") for r in groups.get(number, [])
                })),
                "fetch_status": audit.get(number, "PRIOR_SAVED_EVIDENCE"),
                "source_hashes": " | ".join(sorted({
                    r.get("source_text_sha256", "") for r in groups.get(number, [])
                    if r.get("source_text_sha256")
                })),
                "source_evidence_status": "SOURCE_TEXT_REVIEW_ONLY"
                                          if groups.get(number) else "NO_EQUIPMENT_EXTRACTED",
                "buyer_verified": "NO",
                "supplier_package_available": "UNKNOWN",
                "original_notice_rechecked": "NOT_YET_RECHECKED",
                "site_and_stage_rechecked": "NOT_YET_RECHECKED",
                "review_notes": "",
            })
        _write_csv(out / INDUSTRIAL, INDUSTRIAL_COLS, source_rows)
        report["industrial"] = {
            "equipment_findings": len(signals),
            "distinct_notices_with_equipment_findings": len(groups),
            "last_run_source_notices_audited": len(audit),
            "notice_recheck_queue_rows": len(source_rows),
            "queue": str(out / INDUSTRIAL),
            "source_status_present": bool(status),
        }
    if pilot in ("all", "activation"):
        folder = root / "COMMERCIAL_ACTIVATION_PILOT"
        rows = _read_csv(folder / "GTA_RADAR_COMMERCIAL_ACTIVATION_REVIEW.csv")
        status = _read_json(folder / "GTA_RADAR_COMMERCIAL_ACTIVATION_STATUS.json")
        sample = [{
            "source_id": r.get("source_id", ""),
            "source_record_key": r.get("source_record_key", ""),
            "source_record_sha256": r.get("source_record_sha256", ""),
            "source_dataset_url": r.get("source_dataset_url", ""),
            "municipality": r.get("municipality", ""),
            "site_address": r.get("site_address", ""),
            "site_unit": r.get("site_unit", ""),
            "source_event_date": r.get("source_event_date", ""),
            "radar_first_seen_at": r.get("radar_first_seen_at", ""),
            "activation_stage": r.get("activation_stage", ""),
            "business_name_unverified": r.get("business_name", ""),
            "same_site_link_status": r.get("same_site_link_status", ""),
            "source_excerpt": r.get("source_excerpt", ""),
            "original_record_rechecked": "NOT_YET_RECHECKED",
            "tenant_verified": "NO", "opening_verified": "NO", "review_notes": "",
        } for r in _activation_sample(rows)]
        dossiers = _facility_queue(rows)
        _write_csv(out / ACTIVATION, ACTIVATION_COLS, sample)
        _write_csv(out / FACILITIES, DOSSIER_COLS, dossiers)
        report["activation"] = {
            "existing_pilot_source_candidates": len(rows),
            "accepted_pilot_count_from_status": status.get("activation_review_candidates"),
            "source_sample_rows": len(sample),
            "distinct_facility_dossiers_queued": len(dossiers),
            "same_site_cross_source_rows": status.get("same_site_cross_source_rows", 0),
            "rejection_counts_from_pilot": status.get("excluded_counts", {}),
            "original_rejected_record_samples": 0,
            "original_source_records_rechecked": 0,
            "queue": str(out / ACTIVATION), "dossiers": str(out / FACILITIES),
            "source_status_present": bool(status),
        }
    (out / STATUS).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--pilot", choices=("all", "industrial", "activation"), default="all")
    options = parser.parse_args()
    print(json.dumps(build(options.results, pilot=options.pilot), indent=2))
