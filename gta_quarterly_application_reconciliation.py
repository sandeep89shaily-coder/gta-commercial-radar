"""Offline 31-city application coverage reconciliation.

Reads approved operator-provided quarterly reference CSVs. Never fetches sites.
Only compares exact municipal application IDs within the SAME city. Raw data
is quarantined from AI/sales; missing rows are investigation tasks, not leads.
"""
from __future__ import annotations
import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

MASTER = "GTA_RADAR_COMBINED_31_CITY_PROJECT_MASTER.csv"
COVERAGE = "GTA_RADAR_COMBINED_31_CITY_COVERAGE.csv"
IMPORTS = "authorized_quarterly_reference_exports"
DETAIL = "GTA_RADAR_31_CITY_QUARTERLY_GAPS.csv"
SCORE = "GTA_RADAR_31_CITY_QUARTERLY_COVERAGE.csv"
STATUS = "GTA_RADAR_31_CITY_QUARTERLY_COVERAGE_STATUS.json"
RIGHTS = {"WRITTEN_PUBLISHER_AUTHORIZATION", "PUBLISHED_OPEN_DATA_LICENSED_FOR_COMMERCIAL_REUSE"}
FIELDS = ("city","application_id","reference_period","reference_source","comparison",
          "radar_address","reference_address","radar_scope","reference_scope","notes")
SUMMARY = ("city","reference_state","reference_unique_ids","matched_exact_ids",
           "reference_only_ids","radar_unique_ids","radar_only_ids",
           "matched_pct_of_reference","scope_mismatches","address_mismatches",
           "reference_periods","limitations")


def canonical(value):
    """Conservative normalization: punctuation only; never map GIS object IDs."""
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def manifest_check(manifest, city):
    if not isinstance(manifest, dict) or manifest.get("city") != city:
        return False, "CITY_MISMATCH"
    if manifest.get("rights_scope") not in RIGHTS:
        return False, "NO_COMMERCIAL_REUSE_AUTHORIZATION"
    if not str(manifest.get("source_url", "")).startswith("https://"):
        return False, "MISSING_SOURCE_URL"
    if not str(manifest.get("licence_evidence_url", "")).startswith("https://"):
        return False, "MISSING_LICENCE_EVIDENCE"
    if manifest.get("rights_scope") == "WRITTEN_PUBLISHER_AUTHORIZATION" and not manifest.get("authorization_reference"):
        return False, "MISSING_AUTHORIZATION_REFERENCE"
    if not re.fullmatch(r"20\d\d-Q[1-4]", str(manifest.get("reference_period", ""))):
        return False, "INVALID_REFERENCE_PERIOD"
    # Manifests are operator attestations, not independent legal verification.
    return True, "OPERATOR_ATTESTED_RIGHTS_NOT_INDEPENDENTLY_VERIFIED"


def reconcile(root):
    root = Path(root)
    coverage_path = root / COVERAGE
    master_path = root / MASTER
    if not coverage_path.is_file() or not master_path.is_file():
        raise FileNotFoundError("Current 31-city master and coverage files required")
    cityrows = read_csv(coverage_path)
    cities = {str(row.get("city", "")).strip() for row in cityrows if row.get("city")}
    if len(cities) != 31 or len(cityrows) != 31:
        raise ValueError("Expected exactly 31 unique configured municipalities")
    radar = defaultdict(dict)
    for row in read_csv(master_path):
        city = str(row.get("city", "")).strip()
        ident = canonical(row.get("application_id", ""))
        if city in cities and ident and row.get("record_kind", "").upper() == "APPLICATION":
            radar[city].setdefault(ident, row)
    references = defaultdict(dict)
    periods = defaultdict(set)
    rejects = []
    folder = root / IMPORTS
    for path in sorted(folder.glob("*.csv")) if folder.is_dir() else []:
        slug = path.stem
        mf = folder / (slug + ".source.json")
        try:
            meta = json.loads(mf.read_text(encoding="utf-8"))
            city = str(meta.get("city", ""))
            ok, reason = manifest_check(meta, city)
            if not ok or city not in cities:
                rejects.append({"file": path.name, "reason": reason if not ok else "UNCONFIGURED_CITY"})
                continue
            rows = read_csv(path)
            if not {"application_id", "city"}.issubset(rows[0].keys() if rows else set()):
                rejects.append({"file": path.name, "reason": "MISSING_REQUIRED_COLUMNS_OR_EMPTY"})
                continue
            if any(row.get("city", "").strip() != city or not canonical(row.get("application_id")) for row in rows):
                rejects.append({"file": path.name, "reason": "INVALID_CITY_OR_APPLICATION_ID"})
                continue
            period = meta["reference_period"]
            periods[city].add(period)
            for row in rows:
                ident = canonical(row["application_id"])
                # Duplicate IDs in the same reference dataset do not inflate coverage.
                references[city].setdefault(ident, {**row, "_period": period,
                    "_source": meta["source_url"]})
        except (OSError, ValueError, TypeError, csv.Error) as exc:
            rejects.append({"file": path.name, "reason": type(exc).__name__})
    detail, summary = [], []
    for city in sorted(cities):
        base, ref = radar[city], references[city]
        matched = set(base) & set(ref)
        for ident in sorted(set(ref) | set(base)) if periods[city] else []:
            a, b = base.get(ident, {}), ref.get(ident, {})
            status = ("MATCHED_EXACT_ID" if a and b else
                      "REFERENCE_ONLY_REVIEW" if b else "RADAR_ONLY_NOT_REFERENCE_GAP")
            note = ""
            if a and b:
                mismatches = []
                if a.get("address") and b.get("address") and canonical(a["address"]) != canonical(b["address"]):
                    mismatches.append("ADDRESS_DIFF_REVIEW")
                if a.get("scope") and b.get("scope") and canonical(a["scope"]) != canonical(b["scope"]):
                    mismatches.append("SCOPE_TEXT_DIFF_NOT_PROOF_OF_ERROR")
                note = "|".join(mismatches)
            detail.append({"city":city,"application_id":b.get("application_id") or a.get("application_id"),
                "reference_period":b.get("_period", ""),"reference_source":b.get("_source", ""),
                "comparison":status,"radar_address":a.get("address", ""),
                "reference_address":b.get("address", ""),"radar_scope":a.get("scope", ""),
                "reference_scope":b.get("scope", ""),"notes":note})
        entries=[x for x in detail if x["city"]==city]
        summary.append({"city":city,
            "reference_state":"OPERATOR_ATTESTED_REFERENCE_AVAILABLE" if periods[city] else "NO_AUTHORIZED_REFERENCE",
            "reference_unique_ids":len(ref),"matched_exact_ids":len(matched),
            "reference_only_ids":len(set(ref)-set(base)),"radar_unique_ids":len(base),
            "radar_only_ids":len(set(base)-set(ref)) if periods[city] else "",
            "matched_pct_of_reference":round(100*len(matched)/len(ref),2) if ref else "",
            "scope_mismatches":sum("SCOPE_TEXT_DIFF" in x["notes"] for x in entries),
            "address_mismatches":sum("ADDRESS_DIFF" in x["notes"] for x in entries),
            "reference_periods":"|".join(sorted(periods[city])),
            "limitations":"Different reporting periods/types and reference incompleteness may explain gaps. No commercial rights independently verified."})
    write_csv(root / DETAIL,FIELDS,detail)
    write_csv(root / SCORE,SUMMARY,summary)
    report={"status":"OFFLINE_31_CITY_REFERENCE_RECONCILIATION",
        "configured_cities":31,"cities_with_reference":sum(bool(periods[c]) for c in cities),
        "reference_only_review_candidates":sum(int(x["reference_only_ids"]) for x in summary),
        "input_exports_rejected":rejects,
        "commercial_leads_created":0,"paid_ai_calls":0,"automatic_http_requests":0,
        "rights_attestations_independently_verified":False,
        "warning":"Reference-only IDs are investigation candidates. Unknown source periods/types can make comparison incomplete; do not claim citywide coverage. No unlicensed municipal fetch or AI promotion.",
        "output_files":[DETAIL,SCORE,STATUS]}
    (root/STATUS).write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--results",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(reconcile(args.results),indent=2))


if __name__=="__main__":
    main()
