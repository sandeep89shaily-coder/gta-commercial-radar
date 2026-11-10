"""Offline, read-only reconciliation of authorized municipal export role claims.

Only a matching municipality + literal application ID + civic address can produce
a REVIEW CANDIDATE. The matching record is not an independent confirmation of
an applicant, owner, tender, buyer or publication date. Any missing/conflicting
site evidence is held rather than filled in by address/organization guessing.
This module NEVER modifies the source files, collector database or daily runner.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from gta_facility_intelligence import normalize_address, normalized_city, https

EXPORT = "GTA_RADAR_OFFICIAL_CSV_IMPORT_APPLICATIONS.csv"
COMPARISONS = (
    ("five_city_official", "GTA_RADAR_FIVE_CITY_OFFICIAL_APPLICATIONS.csv"),
    ("additional_official_gis", "GTA_RADAR_ADDITIONAL_CITY_GIS_APPLICATIONS.csv"),
    ("early_applications", "GTA_RADAR_EARLY_APPLICATION_CANDIDATES.csv"),
    ("planning_master", "GTA_RADAR_COLLECTION_MASTER.csv"),
)
MATCHES = "GTA_RADAR_OFFICIAL_APPLICATION_EXACT_SITE_ROLE_REVIEW.csv"
HOLDS = "GTA_RADAR_OFFICIAL_APPLICATION_IDENTITY_HOLDS.csv"
STATUS = "GTA_RADAR_OFFICIAL_APPLICATION_IDENTITY_STATUS.json"
MAX_ROWS = 50000
FIELDS = (
    "city", "application_id", "import_project_id", "import_source_url",
    "comparison_source", "comparison_record_id", "comparison_source_url",
    "exact_site_address", "site_unit", "match_basis",
    "applicant_unverified", "property_owner_unverified",
    "planning_reviewer_unverified", "role_source_fields",
    "same_application_verified", "organization_role_verified",
    "buyer_verified", "procurement_verified", "first_publication_verified",
    "review_action",
)
HOLD_FIELDS = (
    "city", "application_id", "import_project_id", "comparison_sources",
    "reason", "details", "source_url", "review_action",
)
REQUIRED = {
    "export": {"city", "application_id", "address", "provenance", "source_url"},
    "five_city_official": {"city", "application_id", "address", "project_id"},
    "additional_official_gis": {"city", "application_id", "address", "project_id"},
    "early_applications": {"city", "application_id", "project_id"},
    "planning_master": {"city", "canonical_id", "record_kind"},
}
PLACEHOLDER = {"", "n/a", "unknown", "none", "not verified", "tbd", "null"}
TERMINAL = re.compile(r"\b(?:withdrawn|cancelled|canceled|refused|rejected|"
                      r"closed|completed|awarded|expired|revoked)\b", re.I)
EXPECTED_PROVENANCE = "USER_SUPPLIED_OFFICIAL_EXPORT_NOT_INDEPENDENTLY_AUTHENTICATED"
CITY_SCOPE = {"Vaughan", "Kitchener"}
REVIEW_ACTION = (
    "Open and verify BOTH exact original application records; verify applicant/"
    "owner/reviewer role from project-specific evidence; independently check "
    "public posting date, purchaser and procurement stage."
)

def clean(value):
    return " ".join(str(value if value is not None else "").split()).strip()

def application_key(value):
    """Only case/spacing normalization; punctuation and numeric zeros matter."""
    value = clean(value)
    if len(value) < 4 or len(value) > 120 or not re.search(r"\d", value):
        return ""
    if not (re.search(r"[A-Za-z]", value) or re.search(r"[/.-]", value)):
        return ""
    return re.sub(r"\s+", "", value).upper()

def role_name(value):
    value = clean(value)
    if (not value or len(value) > 250 or value.casefold() in PLACEHOLDER
            or not any(letter.isalpha() for letter in value)):
        return ""
    return value

def read(path, family):
    if not path.is_file():
        return None
    if path.stat().st_size > 20_000_000:
        raise ValueError("OVERSIZED_SOURCE_EXPORT:" + path.name)
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            header = set(reader.fieldnames or [])
            missing = REQUIRED[family] - header
            if missing:
                raise ValueError("INVALID_SOURCE_SCHEMA:" + family + ":" +
                                 ",".join(sorted(missing)))
            rows = []
            for row in reader:
                if len(rows) >= MAX_ROWS:
                    raise ValueError("SOURCE_EXPORT_TOO_MANY_ROWS:" + family)
                rows.append(row)
            return rows
    except (csv.Error, UnicodeError) as exc:
        raise ValueError("UNREADABLE_SOURCE_EXPORT:" + family) from exc

def _csv_safe(value):
    value = str(value if value is not None else "")
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value

def write(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({f: _csv_safe(row.get(f, "")) for f in fields})

def _comparison_record(family, row):
    if family == "planning_master" and row.get("record_kind") != "APPLICATION_ID":
        return None
    city = normalized_city(row.get("city"))
    if city not in CITY_SCOPE:
        return None
    ident = application_key(row.get("application_id"))
    if not ident:
        return None
    civic, unit = normalize_address(row.get("address"))
    record_id = clean(row.get("canonical_id" if family == "planning_master"
                               else "project_id"))
    # No fabricated exact deep link. These URLs are unverified source hints.
    source_url = (clean(row.get("record_source_url")) or
                  clean(row.get("source_url")) or
                  clean(row.get("evidence_urls")).split(" | ")[0].split("; ")[0])
    return {"city": city, "application_id": ident, "civic": civic,
            "unit": unit, "family": family, "record_id": record_id,
            "source_url": https(source_url)}

def reconcile(export_rows, other_sources):
    """Candidate review links, holds, and audit counters; never auto-merges."""
    idx = defaultdict(list)
    counts = Counter()
    for family, rows in other_sources.items():
        for raw in rows:
            entry = _comparison_record(family, raw)
            if not entry:
                counts["comparison_row_excluded_or_missing_id"] += 1
                continue
            idx[(entry["city"], entry["application_id"])].append(entry)
            counts["comparison_rows_eligible"] += 1
    matches, holds = [], []
    # An assisted export should have one row per file ID (the upstream
    # importer enforces this). Refuse rather than choose among duplicates.
    export_key_counts = Counter(
        (normalized_city(x.get("city")), application_key(x.get("application_id")))
        for x in export_rows
    )
    def hold(row, reason, entries=(), details=""):
        counts["hold:" + reason] += 1
        holds.append({
            "city": clean(row.get("city")), "application_id": clean(row.get("application_id")),
            "import_project_id": clean(row.get("project_id")),
            "comparison_sources": ";".join(sorted({r["family"] for r in entries})),
            "reason": reason, "details": details[:400],
            "source_url": https(row.get("source_url")),
            "review_action": REVIEW_ACTION,
        })
    for row in export_rows:
        counts["export_rows_scanned"] += 1
        city = normalized_city(row.get("city"))
        file_id = application_key(row.get("application_id"))
        if city not in CITY_SCOPE or not file_id:
            hold(row, "UNSUPPORTED_CITY_OR_INVALID_APPLICATION_ID")
            continue
        if export_key_counts[(city, file_id)] > 1:
            hold(row, "DUPLICATE_ASSISTED_EXPORT_APPLICATION_ID_REVIEW")
            continue
        if TERMINAL.search(clean(row.get("current_status"))):
            hold(row, "HISTORICAL_OR_TERMINAL_APPLICATION_STATUS")
            continue
        if clean(row.get("provenance")) != EXPECTED_PROVENANCE:
            hold(row, "ASSISTED_SOURCE_PROVENANCE_NOT_ACCEPTED")
            continue
        roles = {
            "applicant_unverified": role_name(row.get("applicant_name_unverified")),
            "property_owner_unverified": role_name(row.get("property_owner_unverified")),
            "planning_reviewer_unverified": role_name(row.get("planning_reviewer_unverified")),
        }
        if not any(roles.values()):
            hold(row, "NO_EXPLICIT_ORGANIZATION_ROLE_FIELDS")
            continue
        candidates = idx.get((city, file_id), [])
        if not candidates:
            hold(row, "NO_EXACT_CITY_AND_APPLICATION_ID_IN_OTHER_SOURCE")
            continue
        civic, unit = normalize_address(row.get("address"))
        if not civic:
            hold(row, "UNVERIFIED_IMPORT_CIVIC_SITE", candidates)
            continue
        # A municipal application ID can be reused across separate civic sites.
        # Any disagreement among known sites blocks the entire candidate group.
        known_sites = {r["civic"] for r in candidates if r["civic"]}
        if known_sites and known_sites != {civic}:
            hold(row, "CONFLICTING_CIVIC_SITE_FOR_EXACT_ID", candidates,
                 "Imported site " + civic + "; other sites " +
                 ";".join(sorted(known_sites))[:230])
            continue
        if not known_sites:
            hold(row, "OTHER_SOURCE_LACKS_CIVIC_SITE", candidates)
            continue
        aligned, unit_conflicts, missing_sites = [], [], []
        for other in candidates:
            if not other["civic"]:
                missing_sites.append(other)
            elif other["unit"] != unit:
                # Different or unspecified suite cannot establish the same unit.
                unit_conflicts.append(other)
            else:
                aligned.append(other)
        if unit_conflicts:
            hold(row, "UNIT_CONFLICT_OR_UNSPECIFIED_UNIT", candidates)
            continue
        if not aligned:
            hold(row, "NO_FULL_SITE_MATCH", candidates)
            continue
        seen = set()
        for other in aligned:
            record_key = (other["family"], other["record_id"], other["source_url"])
            if record_key in seen:
                counts["duplicate_source_context_suppressed"] += 1
                continue
            seen.add(record_key)
            matches.append({
                "city": city, "application_id": clean(row.get("application_id")),
                "import_project_id": clean(row.get("project_id")),
                "import_source_url": https(row.get("source_url")),
                "comparison_source": other["family"],
                "comparison_record_id": other["record_id"],
                "comparison_source_url": other["source_url"],
                "exact_site_address": civic, "site_unit": unit,
                "match_basis": "EXACT_CITY_ID_AND_CIVIC_SITE_REVIEW_ONLY",
                **roles,
                "role_source_fields": clean(row.get("role_source_fields")),
                "same_application_verified": "NO",
                "organization_role_verified": "NO",
                "buyer_verified": "NO",
                "procurement_verified": "NO",
                "first_publication_verified": "NO",
                "review_action": REVIEW_ACTION,
            })
            counts["match_rows_review_only"] += 1
        if missing_sites:
            hold(row, "OTHER_SOURCES_WITHOUT_CIVIC_SITE_HELD", missing_sites)
    return matches, holds, dict(sorted(counts.items()))

def run(results, out=None, *, today=None):
    root = Path(results)
    if not root.is_dir():
        raise FileNotFoundError("RADAR_RESULTS_FOLDER_NOT_FOUND")
    destination = Path(out) if out is not None else root / "FACILITY_DOSSIER_PILOT"
    if destination.resolve() == root.resolve():
        raise ValueError("SOURCE_RESULT_FOLDER_IS_NOT_VALID_REPORT_DESTINATION")
    export_rows = read(root / EXPORT, "export")
    inputs_present = {}
    sources = {}
    for family, filename in COMPARISONS:
        rows = read(root / filename, family)
        inputs_present[family] = rows is not None
        sources[family] = rows or []
    # Don't overwrite existing dossier artifacts unless the source export
    # exists and its schema has passed the strict gates above.
    if export_rows is None:
        return {"status": "ASSISTED_OFFICIAL_EXPORT_MISSING",
                "source_export": str(root / EXPORT),
                "files_written": 0, "verified_buyers": 0,
                "comparison_files_present": inputs_present}
    matches, holds, counters = reconcile(export_rows, sources)
    destination.mkdir(parents=True, exist_ok=True)
    write(destination / MATCHES, matches, FIELDS)
    write(destination / HOLDS, holds, HOLD_FIELDS)
    status = {
        "status": "EXACT_ID_SITE_ROLE_REVIEW_ONLY",
        "as_of": str(today or dt.date.today()),
        "source_export_rows": len(export_rows),
        "comparison_files_present": inputs_present,
        "comparison_input_rows": {k: len(v) for k, v in sources.items()},
        "candidate_role_links": len(matches),
        "distinct_import_applications_with_matches": len({
            (m["city"], application_key(m["application_id"])) for m in matches
        }),
        "held_records": len(holds), "hold_reasons": dict(Counter(
            item["reason"] for item in holds)),
        "counts": counters, "files_written": 3,
        "official_source_independently_authenticated": False,
        "same_application_verified": 0,
        "organization_roles_verified": 0,
        "verified_buyers": 0, "open_supplier_contracts_verified": 0,
        "publication_dates_verified": 0,
        "no_source_files_modified": True,
        "limits": ("Exact city + literal application number + civic site is a "
                   "manual research hypothesis. Municipality exports are "
                   "not independently authenticated; organization names, "
                   "first publication, purchasing authority and open work "
                   "remain unverified. Never send automatic outreach."),
        "output_csv": str(destination / MATCHES),
        "holds_csv": str(destination / HOLDS),
    }
    (destination / STATUS).write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status

def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--results", required=True)
    cli.add_argument("--out")
    args = cli.parse_args()
    print(json.dumps(run(args.results, args.out), indent=2))

if __name__ == "__main__":
    main()
