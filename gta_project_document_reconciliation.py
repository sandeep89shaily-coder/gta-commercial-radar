"""Offline source-to-project document matching with conservative procurement gates.

Only exact application identifiers from official, city-specific source records
may establish an application join. A source-to-project join is NOT proof of
first-publication date, developer identity or available supplier contracts.
"""
from __future__ import annotations
import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

OUT = "PROJECT_DOCUMENT_RECONCILIATION"
PROJECTS = "GTA_RADAR_PRIVATE_DEVELOPMENT_REVIEW.csv"
SOURCES = (
    ("TORONTO_OFFICIAL_NOTICE", "COUNCIL_INTELLIGENCE_REVIEW/TORONTO_OFFICIAL_PLANNING_NOTICES/TORONTO_CURRENT_PLANNING_NOTICES_REVIEW.csv", "Toronto"),
    ("BRAMPTON_OFFICIAL_ENGAGEMENT", "COUNCIL_INTELLIGENCE_REVIEW/BRAMPTON_FEATURED_PDC/BRAMPTON_PDC_FEATURED_APPLICATIONS_REVIEW.csv", "Brampton"),
)
PDF_REPORT = "COUNCIL_CAPTURED_PDF_BRIDGE/CAPTURED_PDF_EVIDENCE_REVIEW.json"
QUALIFIED = "GTA_RADAR_VERIFIED_PROCUREMENT_EVIDENCE.csv"

def read_csv(path):
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))

def normalize_id(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())

def project_index(projects):
    index = defaultdict(list)
    for project in projects:
        for candidate in re.split(r"[;|,]", project.get("application_ids") or ""):
            normalized = normalize_id(candidate)
            if len(normalized) >= 6 and any(c.isdigit() for c in normalized):
                index[(project.get("city", "").casefold(), normalized)].append(project)
    return index

def procurement_gate(row):
    """Require explicit independent evidence for every distinct buying assertion."""
    fields = ("project_source_url", "purchaser_name", "purchaser_role",
              "purchaser_source_url", "open_package_description",
              "open_package_source_url", "open_package_asof")
    if any(not str(row.get(key) or "").strip() for key in fields):
        return False, "MISSING_PURCHASING_OR_OPEN_PACKAGE_EVIDENCE"
    urls = [row[k].strip() for k in ("project_source_url",
                                    "purchaser_source_url", "open_package_source_url")]
    if any(not u.startswith("https://") for u in urls):
        return False, "UNSAFE_OR_NON_PUBLIC_SOURCE"
    # A manual source-documented evidence record is a review candidate,
    # never an automatic declaration of verified or unawarded status.
    return False, "HUMAN_VERIFICATION_REQUIRED"

def review(results):
    root = Path(results)
    if not root.is_dir():
        raise FileNotFoundError("EXISTING_RADAR_RESULTS_REQUIRED")
    out = root / OUT
    out.mkdir(parents=True, exist_ok=True)
    projects = read_csv(root / PROJECTS)
    index = project_index(projects)
    records = []
    counts = Counter()
    for kind, rel, city in SOURCES:
        for src in read_csv(root / rel):
            if str(src.get("city") or "").casefold() != city.casefold():
                continue
            identifier = str(src.get("application_id") or "").strip()
            normalized = normalize_id(identifier)
            if not normalized:
                continue
            counts["official_application_records"] += 1
            matches = index.get((city.casefold(), normalized), [])
            unique = {p.get("opportunity_id") or p.get("address"): p for p in matches}
            if len(unique) == 1:
                status = "OFFICIAL_APPLICATION_ID_JOIN_REVIEW"
                counts["exact_official_application_id_joins"] += 1
            elif len(unique) > 1:
                status = "AMBIGUOUS_APPLICATION_ID_REVIEW"
                counts["ambiguous_joins"] += 1
            else:
                status = "NO_MATCH_IN_PRIVATE_PROJECT_EXPORT"
                counts["unmatched_official_application_records"] += 1
            records.append({
                "kind": kind, "city": city, "application_id": identifier,
                "join_status": status,
                "matched_opportunity_ids": sorted(unique),
                "official_source_url": src.get("official_notice_url") or src.get("source_url") or "",
                "first_publication_verified": False,
                "project_buyer_verified": False,
                "open_supplier_contract_verified": False,
            })
    pdf = root / PDF_REPORT
    if pdf.is_file():
        saved = json.loads(pdf.read_text(encoding="utf-8"))
        for document in saved.get("documents", []):
            city = document.get("city", "")
            for identifier in document.get("exact_application_id_mentions_review", []):
                norm = normalize_id(identifier)
                matched = {
                    p.get("opportunity_id") or p.get("address"): p
                    for p in index.get((city.casefold(), norm), [])
                }
                status = ("OFFICIAL_PDF_EXACT_ID_TEXT_MENTION_REVIEW" if len(matched) == 1
                          else "AMBIGUOUS_PDF_ID_MENTION_REVIEW" if matched
                          else "PDF_ID_MENTION_NOT_IN_PROJECT_EXPORT")
                counts["pdf_exact_id_mentions"] += 1
                records.append({
                    "kind": "CAPTURED_OFFICIAL_PDF", "city": city,
                    "application_id": identifier, "join_status": status,
                    "matched_opportunity_ids": sorted(matched),
                    "official_source_url": document.get("url", ""),
                    "first_publication_verified": False,
                    "project_buyer_verified": False,
                    "open_supplier_contract_verified": False,
                })
    qualified_rows = read_csv(root / QUALIFIED)
    for item in qualified_rows:
        accepted, reason = procurement_gate(item)
        item["procurement_gate"] = "PASS" if accepted else reason
    summary = {
        "status": "OFFLINE_PROJECT_DOCUMENT_AND_BUYER_GATE_REVIEW",
        "private_projects_checked": len(projects),
        "official_application_records": counts["official_application_records"],
        "exact_official_application_id_joins_for_review": counts["exact_official_application_id_joins"],
        "unmatched_official_application_records": counts["unmatched_official_application_records"],
        "ambiguous_joins": counts["ambiguous_joins"],
        "pdf_exact_id_mentions_for_review": counts["pdf_exact_id_mentions"],
        "independently_verified_first_publication_dates": 0,
        "verified_open_supplier_packages": 0,
        "verified_procurement_buyers": 0,
        "procurement_evidence_submitted": len(qualified_rows),
        "procurement_evidence_auto_approved": 0,
        "paid_calls": 0, "network_calls": 0,
        "warning": "An official ID join proves correspondence between records only; no automatic buyer, contract or first-publication inference.",
    }
    (out / "RECONCILIATION_SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out / "APPLICATION_JOIN_REVIEW.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    (out / "PROCUREMENT_GATE_REVIEW.json").write_text(json.dumps(qualified_rows, indent=2), encoding="utf-8")
    return summary

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    print(json.dumps(review(args.results), indent=2))

if __name__ == "__main__":
    main()
