"""Read-only Brampton GIS versus saved Radar evidence, exact City file ID only.

No network, paid AI, production SQLite mutations, guessed buyer, or artificial
publisher-first dates. Twenty review cases, not 20 sale-ready leads.
"""
from __future__ import annotations
import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from gta_brampton_official_gis_planning import ALL as GIS_CSV, STATUS as GIS_STATUS, BASE, LAYERS
from gta_brampton_featured_pdc import CSV as PDC_CSV, STATUS as PDC_STATUS
from gta_opportunity_lanes import _city

OUT = "BRAMPTON_GIS_20_FILE_CROSS_SOURCE_AUDIT.csv"
STATUS = "BRAMPTON_GIS_RECONCILIATION_STATUS.json"
LIMIT = 20
SOURCES = {
    "EARLY_APPLICATIONS_SAVED": "GTA_RADAR_EARLY_APPLICATION_CANDIDATES.csv",
    "CORE_MASTER_SAVED": "GTA_RADAR_COLLECTION_MASTER.csv",
    "PRIVATE_INVESTIGATION_SAVED": "GTA_RADAR_PRIVATE_DEVELOPMENT_REVIEW.csv",
    "PRIVATE_TOP_TEN_SAVED": "GTA_RADAR_PRIVATE_TOP_10.csv",
}
CASE = re.compile(r"\b(?:OZS|SP|PDC|SPA|ZBA|OPA)[\s/_-]*20\d{2}[\s/_-]*\d{3,6}\b", re.I)
FIELDS = (
    "research_rank", "application_id", "layer", "location",
    "project_scope_excerpt", "source_status", "date_received_utc",
    "date_received_basis", "first_observed_utc", "gis_source_observation",
    "source_layer_url", "applicant_company_source_text", "agent_company_source_text",
    "exact_id_saved_radar_sources", "matching_saved_output_rows",
    "previously_in_private_investigation", "previously_in_private_top_ten",
    "featured_pdc_exact_file_match", "match_evidence_level",
    "municipal_file_receipt_is_not_publication", "project_verified",
    "buyer_verified", "open_procurement_verified", "follow_up"
)


def _read(path, maximum=75000):
    file = Path(path)
    if not file.is_file():
        return []
    if file.stat().st_size > 30_000_000:
        raise ValueError("SAVED_SOURCE_CSV_OVER_LIMIT:" + file.name)
    with file.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("SAVED_SOURCE_HEADERS_MISSING")
        rows = []
        for i, row in enumerate(reader):
            if i >= maximum:
                raise ValueError("SAVED_SOURCE_ROW_LIMIT")
            rows.append(row)
        return rows


def _json(path):
    file = Path(path)
    if not file.is_file():
        return {}
    data = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("STATUS_MUST_BE_JSON_OBJECT")
    return data


def _key(raw):
    if not isinstance(raw, str):
        return ""
    raw = " ".join(raw.split()).upper()
    return re.sub(r"[\s/_-]", "", raw) if CASE.fullmatch(raw) else ""


def _ids(record):
    keys = set()
    for name in ("application_id", "application_ids"):
        raw = record.get(name)
        if not isinstance(raw, str):
            continue
        for value in re.split(r"[;|,]", raw):
            key = _key(value.strip())
            if key:
                keys.add(key)
    return keys


def _source_index(results):
    index = defaultdict(lambda: defaultdict(set))
    health = {}
    for source, filename in SOURCES.items():
        file = Path(results) / filename
        if not file.is_file():
            health[source] = "SAVED_OUTPUT_MISSING"
            continue
        try:
            for row_number, row in enumerate(_read(file), 2):
                if _city(row.get("city"), row.get("address")) != "Brampton":
                    continue
                for key in _ids(row):
                    index[key][source].add(row_number)
            health[source] = "SAVED_ONLY_NOT_CONFIRMED_CURRENT"
        except (ValueError, OSError, UnicodeError, csv.Error) as exc:
            health[source] = "SAVED_OUTPUT_HELD_" + type(exc).__name__
    return index, health


def _featured(folder):
    status = _json(Path(folder) / PDC_STATUS)
    if status.get("status") != "FEATURED_APPLICATIONS_REVIEW_ONLY":
        return set(), "CURRENT_FEATURED_PDC_UNAVAILABLE"
    checked = status.get("checked_utc")
    ids = {
        _key(row.get("application_id"))
        for row in _read(Path(folder) / PDC_CSV, maximum=100)
        if row.get("city") == "Brampton"
        and row.get("last_observed_utc") == checked
    }
    return ids - {""}, "CURRENT_FEATURED_PDC_MATCH_ELIGIBLE"


def run(gis_folder, featured_folder, results, output, *, limit=LIMIT):
    if not 1 <= limit <= LIMIT:
        raise ValueError("MAX_20_RESEARCH_CASES")
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "status": "HOLD", "mode": "BRAMPTON_READ_ONLY_FILE_NUMBER_REVIEW",
        "gis_layers_complete": 0, "gis_current_rows": 0,
        "gis_unique_file_numbers": 0, "commercial_keyword_rows": 0,
        "exact_ids_in_saved_radar": 0, "exact_ids_in_private_investigation": 0,
        "exact_ids_in_private_top_ten": 0, "exact_ids_in_featured_pdc": 0,
        "cases_for_manual_audit": 0, "saved_radar_source_health": {},
        "publisher_first_publications_verified": 0, "buyers_verified": 0,
        "open_supplier_packages_verified": 0, "paid_ai_calls": 0,
        "warning": "Exact municipal file number overlap only. Saved Radar outputs "
                   "may be historical. Application DATE_RECEIVED is not first "
                   "online publication. Applicants/agents are not verified buyers."
    }
    try:
        source = _json(Path(gis_folder) / GIS_STATUS)
        report["gis_status"] = source.get("status", "MISSING")
        if report["gis_status"] not in (
                "ALL_THREE_LAYERS_REVIEW_ONLY",
                "PARTIAL_OFFICIAL_GIS_LAYERS_REVIEW_ONLY"):
            report["status"] = "NO_CURRENT_GIS_SOURCE_DATA_HOLD"
            return report
        checked = source.get("checked_utc")
        complete = {
            item.get("layer") for item in source.get("layer_results", [])
            if isinstance(item, dict)
            and item.get("status") == "COMPLETE_REVIEW_ONLY"
            and item.get("layer") in LAYERS
        }
        report["gis_layers_complete"] = len(complete)
        if (not checked or len(complete) != source.get("layers_complete")
                or not complete):
            report["status"] = "CONFLICTING_GIS_SOURCE_HEALTH_HOLD"
            return report
        rows = _read(Path(gis_folder) / GIS_CSV)
        if not rows:
            report["status"] = "NO_GIS_APPLICATION_ROWS_HOLD"
            return report
        seen = set()
        for row in rows:
            number = next((n for n, name in LAYERS.items()
                           if name == row.get("layer")), None)
            key = _key(row.get("application_id"))
            identity = (number, key)
            if (number not in complete or not key
                    or row.get("city") != "Brampton"
                    or row.get("last_observed_utc") != checked
                    or row.get("source_layer_url") != BASE + "/" + str(number)
                    or identity in seen):
                report["status"] = "STALE_INVALID_OR_DUPLICATE_GIS_ROWS_HOLD"
                return report
            seen.add(identity)
        report["gis_current_rows"] = len(rows)
        keys = {_key(row["application_id"]) for row in rows}
        report["gis_unique_file_numbers"] = len(keys)
        report["commercial_keyword_rows"] = sum(
            row.get("commercial_screen") == "COMMERCIAL_KEYWORD_REVIEW_ONLY"
            for row in rows)
        matched, health = _source_index(results)
        report["saved_radar_source_health"] = health
        try:
            pdc, pdc_health = _featured(featured_folder)
        except (ValueError, OSError, csv.Error, UnicodeError) as exc:
            pdc, pdc_health = set(), "FEATURED_PDC_HELD_" + type(exc).__name__
        report["featured_pdc_health"] = pdc_health
        report["exact_ids_in_saved_radar"] = len(keys & set(matched))
        report["exact_ids_in_private_investigation"] = sum(
            bool(matched.get(key, {}).get("PRIVATE_INVESTIGATION_SAVED"))
            for key in keys)
        report["exact_ids_in_private_top_ten"] = sum(
            bool(matched.get(key, {}).get("PRIVATE_TOP_TEN_SAVED"))
            for key in keys)
        report["exact_ids_in_featured_pdc"] = len(keys & pdc)
        candidates = [
            row for row in rows
            if row.get("commercial_screen") == "COMMERCIAL_KEYWORD_REVIEW_ONLY"
        ]
        # Most recent City receipt date first. Never call it first-publication.
        stage = {"PRE_CONSULTATION": 0, "OPA_ZBA_SUBDIVISION": 1,
                 "SITE_PLAN_APPROVAL": 2}
        candidates.sort(key=lambda row: (
            row.get("date_received_utc") or "",
            -stage.get(row["layer"], 3),
            row.get("application_id") or ""), reverse=True)
        with (out / OUT).open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            writer.writeheader()
            for rank, item in enumerate(candidates[:limit], 1):
                key = _key(item["application_id"])
                matches = matched.get(key, {})
                names = sorted(matches)
                report_row = {
                    "research_rank": rank,
                    "application_id": item["application_id"],
                    "layer": item["layer"],
                    "location": item.get("location", ""),
                    "project_scope_excerpt": (
                        item.get("proposal_description") or
                        item.get("description") or
                        item.get("application_title") or "")[:500],
                    "source_status": item.get("status", ""),
                    "date_received_utc": item.get("date_received_utc", ""),
                    "date_received_basis": item.get("date_received_basis", ""),
                    "first_observed_utc": item.get("first_observed_utc", ""),
                    "gis_source_observation": item.get("observation", ""),
                    "source_layer_url": item.get("source_layer_url", ""),
                    "applicant_company_source_text":
                        item.get("applicant_company_source_text", ""),
                    "agent_company_source_text":
                        item.get("agent_company_source_text", ""),
                    "exact_id_saved_radar_sources": "; ".join(names),
                    "matching_saved_output_rows": sum(
                        len(v) for v in matches.values()),
                    "previously_in_private_investigation":
                        bool(matches.get("PRIVATE_INVESTIGATION_SAVED")),
                    "previously_in_private_top_ten":
                        bool(matches.get("PRIVATE_TOP_TEN_SAVED")),
                    "featured_pdc_exact_file_match": key in pdc,
                    "match_evidence_level": (
                        "EXACT_ID_MATCH_SAVED_OUTPUT_NOT_CURRENT_SOURCE_PROOF"
                        if names else "OFFICIAL_GIS_ONLY_NO_SAVED_FILE_MATCH"),
                    "municipal_file_receipt_is_not_publication": True,
                    "project_verified": False, "buyer_verified": False,
                    "open_procurement_verified": False,
                    "follow_up": (
                        "Confirm original City file, publication timestamp, current "
                        "stage, developer/GC and whether supplier work is unawarded")
                }
                writer.writerow({
                    k: ("'" + v if isinstance(v, str)
                        and v.lstrip().startswith(("=", "+", "-", "@")) else v)
                    for k, v in report_row.items()
                })
        report["cases_for_manual_audit"] = min(len(candidates), limit)
        report["status"] = (
            "AUDIT_READY_COMPLETE_GIS_LAYERS" if len(complete) == 3
            else "AUDIT_READY_PARTIAL_GIS_LAYERS")
    except (OSError, ValueError, TypeError, KeyError, csv.Error, UnicodeError) as exc:
        report["status"] = "RECONCILIATION_FAILED_HELD"
        report["error_type"] = type(exc).__name__
        report["error_reason"] = str(exc)[:180]
    finally:
        (out / STATUS).write_text(json.dumps(report, indent=2),
                                  encoding="utf-8")
    return report


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--gis", required=True)
    cli.add_argument("--featured", required=True)
    cli.add_argument("--results", required=True)
    cli.add_argument("--out", required=True)
    a = cli.parse_args()
    print(json.dumps(run(a.gis, a.featured, a.results, a.out), indent=2))
