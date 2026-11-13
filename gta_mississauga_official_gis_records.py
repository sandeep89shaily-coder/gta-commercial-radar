"""Complete, bounded Mississauga official planning GIS review-only collector.

A fresh full OBJECTID inventory and exact batch retrieval are mandatory before
publishing a layer snapshot. Never change local Radar SQLite or infer posting
dates, verified buyers, or procurement from municipal application dates.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

from gta_mississauga_official_gis_source_audit import (
    LAYERS, NAMES, REQUIRED, _fetch,
)

CSV = "MISSISSAUGA_OFFICIAL_GIS_APPLICATIONS_REVIEW.csv"
CHANGES = "MISSISSAUGA_OFFICIAL_GIS_CHANGED_APPLICATIONS.csv"
LEDGER = "MISSISSAUGA_OFFICIAL_GIS_FIRST_OBSERVED.json"
STATUS = "MISSISSAUGA_OFFICIAL_GIS_COLLECTOR_STATUS.json"
TWENTY = "MISSISSAUGA_GIS_20_FILE_COMMERCIAL_AUDIT.csv"
FIELDS = ("city", "layer", "application_id", "site_address",
          "description", "applicant_source_text", "source_status",
          "application_date", "date_basis", "approval_date",
          "total_non_res_gfa_source", "ici_industrial_source",
          "ici_office_source", "ici_retail_source",
          "commercial_screen", "source_layer_url", "first_observed_utc",
          "last_observed_utc", "observation", "first_publication_verified",
          "buyer_verified", "open_procurement_verified")
MAX_IDS = 20000
BATCH = 200
WORDS = re.compile(r"\b(?:industrial|warehouse|manufactur\w*|office|retail|commercial|logistics|distribution|hotel|restaurant|data.cent(?:er|re)|employment)\b", re.I)
CLOSED = re.compile(r"\b(?:withdrawn|cancelled|refused)\b", re.I)


def _string(value, limit=500):
    return " ".join(str(value or "").split())[:limit]


def _date(value):
    if value is None or isinstance(value, bool):
        return ""
    try:
        ms = int(value)
        if not 0 < ms < 4_000_000_000_000:
            return ""
        return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date().isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def _number(value):
    if value is None or isinstance(value, bool):
        return ""
    try:
        n = float(value)
        return str(n) if 0 <= n <= 1_000_000_000 and n == n else ""
    except (TypeError, ValueError, OverflowError):
        return ""


def _clean_file(raw):
    value = _string(raw, 60).upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9 /_.-]{2,59}", value) or not any(x.isdigit() for x in value):
        return ""
    return value


def _write(path, rows):
    with Path(path).open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: ("'" + str(row.get(key, "")) if
                          str(row.get(key, "")).lstrip().startswith(("=", "+", "-", "@"))
                          else row.get(key, "")) for key in FIELDS})


def _layer(layer, fetch):
    url = LAYERS[layer]
    meta = fetch(url, {"f": "json"})
    names = {field.get("name") for field in meta.get("fields", [])
             if isinstance(field, dict)}
    if (meta.get("name") != NAMES[layer]
            or meta.get("objectIdField") != "OBJECTID"
            or not REQUIRED.issubset(names)):
        raise ValueError("OFFICIAL_LAYER_SCHEMA_MISMATCH")
    inventory = fetch(url + "/query", {
        "f": "json", "where": "1=1", "returnIdsOnly": "true"})
    ids = inventory.get("objectIds")
    if (not isinstance(ids, list) or not 0 < len(ids) <= MAX_IDS
            or any(type(i) is not int or i < 1 for i in ids)
            or len(ids) != len(set(ids))):
        raise ValueError("OBJECTID_INVENTORY_INVALID_OR_UNBOUNDED")
    attrs = []
    for start in range(0, len(ids), BATCH):
        chunk = sorted(ids)[start:start + BATCH]
        result = fetch(url + "/query", {
            "f": "json", "objectIds": ",".join(map(str, chunk)),
            "outFields": ",".join(sorted(REQUIRED)),
            "returnGeometry": "false"})
        features = result.get("features")
        if not isinstance(features, list):
            raise ValueError("FEATURE_BATCH_MISSING")
        seen = {}
        for feat in features:
            item = feat.get("attributes") if isinstance(feat, dict) else None
            if not isinstance(item, dict) or type(item.get("OBJECTID")) is not int:
                raise ValueError("FEATURE_ATTRIBUTES_MISSING")
            ident = item["OBJECTID"]
            if ident not in chunk or ident in seen:
                raise ValueError("FEATURE_OBJECTID_UNEXPECTED_OR_DUPLICATE")
            seen[ident] = item
        if set(seen) != set(chunk):
            raise ValueError("INCOMPLETE_FEATURE_BATCH")
        attrs.extend(seen[i] for i in chunk)
    return attrs, (meta.get("editingInfo") or {}).get("dataLastEditDate")


def _rows(layer, attrs):
    results = {}
    conflict = set()
    invalid = 0
    for attr in attrs:
        file_id = _clean_file(attr.get("APP_FILE_NO"))
        description = _string(attr.get("DESCRIPTION"), 700)
        address = _string(attr.get("SITE_ADDRESS"), 250)
        if not file_id or not (description or address):
            invalid += 1
            continue
        row = {
            "city": "Mississauga", "layer": layer,
            "application_id": file_id, "site_address": address,
            "description": description,
            "applicant_source_text": _string(attr.get("APPLICANT"), 250),
            "source_status": _string(attr.get("SIMPLE_STATUS"), 100),
            "application_date": _date(attr.get("APPLICATION_DATE")),
            "date_basis": "GIS_APPLICATION_DATE_NOT_FIRST_PUBLICATION",
            "approval_date": _date(attr.get("APPROVAL_DATE")),
            "total_non_res_gfa_source": _number(attr.get("TOTAL_NON_RES_GFA")),
            "ici_industrial_source": _number(attr.get("ICI_INDUST")),
            "ici_office_source": _number(attr.get("ICI_OFFICE")),
            "ici_retail_source": _number(attr.get("ICI_RETAIL")),
            "commercial_screen": "COMMERCIAL_RESEARCH_ONLY" if (
                not CLOSED.search(_string(attr.get("SIMPLE_STATUS"))) and (
                    WORDS.search(description) or
                    any(float(_number(attr.get(x)) or 0) > 0 for x in (
                        "ICI_INDUST", "ICI_OFFICE", "ICI_RETAIL", "TOTAL_NON_RES_GFA"))
                )) else "HISTORICAL_OR_NONCOMMERCIAL_REVIEW",
            "source_layer_url": LAYERS[layer],
            "first_publication_verified": False,
            "buyer_verified": False, "open_procurement_verified": False,
        }
        if file_id in conflict:
            continue
        if file_id in results:
            # Multiple polygons can represent one application; conflicting
            # attributes must not silently select one polygon's record.
            stable = ("site_address", "description", "applicant_source_text",
                      "source_status", "application_date")
            if any(results[file_id][name] != row[name] for name in stable):
                del results[file_id]
                conflict.add(file_id)
                invalid += 1
        else:
            results[file_id] = row
    if not results:
        raise ValueError("NO_USABLE_APPLICATION_IDS")
    return list(results.values()), invalid


def run(out, *, fetch=False, fetcher=None, now=None):
    folder = Path(out)
    folder.mkdir(parents=True, exist_ok=True)
    clock = now or dt.datetime.now(dt.timezone.utc)
    if clock.tzinfo is None:
        raise ValueError("TIMEZONE_AWARE_TIMESTAMP_REQUIRED")
    at = clock.astimezone(dt.timezone.utc).isoformat()
    report = {
        "status": "HOLD", "checked_utc": at, "layers_complete": 0,
        "layer_results": [], "current_application_files": 0,
        "commercial_review_files": 0, "changed_records_review_only": 0,
        "cases_for_manual_audit": 0, "publisher_first_publications_verified": 0,
        "buyers_verified": 0, "open_procurement_verified": 0,
        "paid_ai_calls": 0,
        "warning": "APP_FILE_NO and application date are official records, not proof of new public posting, a buyer, or an open supplier contract."
    }
    if not fetch:
        report["status"] = "FETCH_NOT_REQUESTED"
        (folder / STATUS).write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    ledger_path = folder / LEDGER
    try:
        old = (json.loads(ledger_path.read_text(encoding="utf-8"))
               if ledger_path.exists() else {"version": 1, "items": {}})
        if old.get("version") != 1 or not isinstance(old.get("items"), dict):
            raise ValueError("HISTORY_FORMAT_NOT_RECOGNIZED")
        next_items = dict(old["items"])
        output, changes = [], []
        for layer in LAYERS:
            status = {"layer": layer, "status": "HOLD"}
            try:
                attrs, source_edit = _layer(layer, fetcher or _fetch)
                records, held = _rows(layer, attrs)
                for item in records:
                    key = layer + ":" + item["application_id"]
                    digest = hashlib.sha256(json.dumps(
                        {k: item[k] for k in FIELDS if k in item},
                        sort_keys=True).encode("utf-8")).hexdigest()
                    prev = old["items"].get(key)
                    event = ("BASELINE_EXISTING_NOT_NEW_PUBLICATION" if prev is None
                             else "SOURCE_RECORD_CHANGED_NOT_NEW_PUBLICATION"
                             if digest != prev.get("source_sha256") else "UNCHANGED")
                    item.update(first_observed_utc=prev.get("first_observed_utc", at)
                                if prev else at, last_observed_utc=at,
                                observation=event)
                    next_items[key] = {
                        "first_observed_utc": item["first_observed_utc"],
                        "last_observed_utc": at, "source_sha256": digest}
                    output.append(item)
                    if event == "SOURCE_RECORD_CHANGED_NOT_NEW_PUBLICATION":
                        changes.append(item)
                report["layers_complete"] += 1
                status.update(status="COMPLETE_REVIEW_ONLY",
                              feature_count=len(attrs), application_files=len(records),
                              held_rows=held, publisher_layer_last_edit_ms=source_edit)
            except Exception as exc:
                status.update(status="SOURCE_FAILED_HISTORY_PRESERVED",
                              reason=type(exc).__name__ + ":" + str(exc)[:120])
            report["layer_results"].append(status)
        if output:
            _write(folder / CSV, output)
            _write(folder / CHANGES, changes)
            candidates = [item for item in output
                          if item["commercial_screen"] == "COMMERCIAL_RESEARCH_ONLY"]
            candidates.sort(key=lambda row: (
                row["application_date"], row["layer"], row["application_id"]),
                reverse=True)
            _write(folder / TWENTY, candidates[:20])
            report["current_application_files"] = len(output)
            report["commercial_review_files"] = len(candidates)
            report["changed_records_review_only"] = len(changes)
            report["cases_for_manual_audit"] = min(len(candidates), 20)
            tmp = folder / (LEDGER + ".tmp")
            tmp.write_text(json.dumps({
                "version": 1, "updated_utc": at, "items": next_items
            }, indent=2), encoding="utf-8")
            tmp.replace(ledger_path)
            report["status"] = ("BOTH_LAYERS_REVIEW_ONLY" if
                                report["layers_complete"] == 2 else
                                "PARTIAL_OFFICIAL_GIS_REVIEW_ONLY")
        else:
            report["status"] = "NO_CURRENT_SOURCE_ROWS_HISTORY_PRESERVED"
    except Exception as exc:
        report["status"] = "COLLECTOR_FAILED_HISTORY_PRESERVED"
        report["reason"] = type(exc).__name__ + ":" + str(exc)[:150]
    finally:
        (folder / STATUS).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.out, fetch=args.fetch), indent=2))
