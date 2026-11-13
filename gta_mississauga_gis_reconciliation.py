"""Read-only exact file-number overlap between current Mississauga GIS and saved Radar.

Historical CSV matches are labelled historical; neither posting dates nor buyers
are inferred. No SQLite, network, paid AI, or source-record mutation.
"""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from gta_mississauga_official_gis_records import CSV, STATUS
from gta_opportunity_lanes import _city

OUT = "MISSISSAUGA_GIS_20_FILE_CROSS_SOURCE_AUDIT.csv"
REPORT = "MISSISSAUGA_GIS_CROSS_SOURCE_STATUS.json"
SOURCES = {
    "EARLY_APPLICATIONS_SAVED": "GTA_RADAR_EARLY_APPLICATION_CANDIDATES.csv",
    "CORE_MASTER_SAVED": "GTA_RADAR_COLLECTION_MASTER.csv",
    "PRIVATE_INVESTIGATION_SAVED": "GTA_RADAR_PRIVATE_DEVELOPMENT_REVIEW.csv",
    "PRIVATE_TOP_TEN_SAVED": "GTA_RADAR_PRIVATE_TOP_10.csv",
}
HEADERS = ("research_rank", "application_id", "layer", "site_address",
           "description", "applicant_source_text", "source_status",
           "application_date_not_publication", "first_observed_utc",
           "exact_id_saved_radar_sources", "previously_in_private_investigation",
           "previously_in_private_top_ten", "match_evidence_level",
           "buyer_verified", "open_procurement_verified", "follow_up")


def _key(raw):
    if not isinstance(raw, str):
        return ""
    value = raw.strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9 /_.-]{2,79}", value) or not any(x.isdigit() for x in value):
        return ""
    return re.sub(r"[ /_.-]", "", value)


def _read(file):
    file = Path(file)
    if not file.is_file():
        return []
    if file.stat().st_size > 30_000_000:
        raise ValueError("SOURCE_CSV_TOO_LARGE")
    with file.open("r", newline="", encoding="utf-8-sig") as handle:
        data = csv.DictReader(handle)
        if not data.fieldnames:
            raise ValueError("CSV_HEADER_REQUIRED")
        rows = []
        for index, row in enumerate(data):
            if index >= 75000:
                raise ValueError("CSV_ROW_LIMIT")
            rows.append(row)
        return rows


def _index(results):
    matches = defaultdict(set)
    health = {}
    for source, name in SOURCES.items():
        path = Path(results) / name
        if not path.is_file():
            health[source] = "SAVED_OUTPUT_MISSING"
            continue
        try:
            for row in _read(path):
                if _city(row.get("city"), row.get("address")) != "Mississauga":
                    continue
                for name in ("application_id", "application_ids"):
                    for raw in re.split(r"[;|,]", row.get(name) or ""):
                        key = _key(raw)
                        if key:
                            matches[key].add(source)
            health[source] = "SAVED_OUTPUT_NOT_CURRENT_PROOF"
        except (OSError, ValueError, csv.Error, UnicodeError):
            health[source] = "HISTORICAL_OUTPUT_HELD"
    return matches, health


def run(source_folder, results, output):
    folder = Path(output)
    folder.mkdir(parents=True, exist_ok=True)
    status = {"status": "HOLD", "cases_for_manual_audit": 0,
              "exact_ids_in_saved_radar": 0, "paid_ai_calls": 0,
              "buyers_verified": 0, "publisher_first_publications_verified": 0,
              "warning": "Only exact ID overlap with historical CSVs; receipt is not first publication."}
    try:
        current = json.loads((Path(source_folder) / STATUS).read_text(encoding="utf-8"))
        if current.get("status") not in ("BOTH_LAYERS_REVIEW_ONLY", "PARTIAL_OFFICIAL_GIS_REVIEW_ONLY"):
            status["status"] = "NO_CURRENT_SUCCESSFUL_GIS_SOURCE"
            return status
        checked = current.get("checked_utc")
        complete_layers = {item.get("layer") for item in current.get("layer_results", [])
                           if item.get("status") == "COMPLETE_REVIEW_ONLY"}
        if not checked or len(complete_layers) != current.get("layers_complete"):
            status["status"] = "CONFLICTING_SOURCE_STATUS_HELD"
            return status
        records = _read(Path(source_folder) / CSV)
        if (not records or any(
                row.get("city") != "Mississauga"
                or row.get("layer") not in complete_layers
                or row.get("last_observed_utc") != checked
                or not _key(row.get("application_id"))
                for row in records)):
            status["status"] = "STALE_OR_INVALID_SOURCE_RECORDS_HELD"
            return status
        keys = [(row["layer"], _key(row["application_id"])) for row in records]
        if len(keys) != len(set(keys)):
            status["status"] = "DUPLICATE_SOURCE_FILE_IDS_HELD"
            return status
        index, health = _index(results)
        status["saved_source_health"] = health
        status["exact_ids_in_saved_radar"] = len({key for _, key in keys if key in index})
        candidates = [row for row in records
                      if row.get("commercial_screen") == "COMMERCIAL_RESEARCH_ONLY"]
        candidates.sort(key=lambda row: (
            row.get("application_date", ""), row.get("layer", ""),
            row.get("application_id", "")), reverse=True)
        with (folder / OUT).open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADERS)
            writer.writeheader()
            for rank, row in enumerate(candidates[:20], 1):
                known = index.get(_key(row["application_id"]), set())
                item = {
                    "research_rank": rank,
                    "application_id": row["application_id"],
                    "layer": row["layer"], "site_address": row.get("site_address", ""),
                    "description": row.get("description", ""),
                    "applicant_source_text": row.get("applicant_source_text", ""),
                    "source_status": row.get("source_status", ""),
                    "application_date_not_publication": row.get("application_date", ""),
                    "first_observed_utc": row.get("first_observed_utc", ""),
                    "exact_id_saved_radar_sources": "; ".join(sorted(known)),
                    "previously_in_private_investigation": "PRIVATE_INVESTIGATION_SAVED" in known,
                    "previously_in_private_top_ten": "PRIVATE_TOP_TEN_SAVED" in known,
                    "match_evidence_level": ("EXACT_ID_IN_HISTORICAL_RADAR_OUTPUT" if known
                                             else "GIS_ONLY_NO_SAVED_ID_MATCH"),
                    "buyer_verified": False, "open_procurement_verified": False,
                    "follow_up": "Verify City original, posting date, stage, developer and open supplier work",
                }
                writer.writerow({k: ("'" + str(v) if str(v).lstrip().startswith(
                    ("=", "+", "-", "@")) else v) for k, v in item.items()})
        status["cases_for_manual_audit"] = min(len(candidates), 20)
        status["status"] = "EXACT_FILE_ID_REVIEW_READY"
    except (OSError, ValueError, KeyError, TypeError, csv.Error, UnicodeError) as exc:
        status["status"] = "RECONCILIATION_FAILED_HELD"
        status["failure"] = type(exc).__name__ + ":" + str(exc)[:120]
    finally:
        (folder / REPORT).write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status
