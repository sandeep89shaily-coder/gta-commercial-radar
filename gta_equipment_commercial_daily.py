"""Combine ERO equipment notices and announcement investments in ONE daily research index.

Reads only preserved local outputs. No network, DeepSeek, buyer inference,
municipal access bypass or SQLite mutation. Distinguish environmental proposal
dates from project public announcements and keep every contact unverified.
"""
import argparse
import csv
import json
from pathlib import Path

OUTPUT = "GTA_RADAR_EQUIPMENT_COMMERCIAL_INDEX.csv"
STATUS = "GTA_RADAR_EQUIPMENT_COMMERCIAL_INDEX_STATUS.json"
FIELDS = (
    "source_type", "company", "physical_project_address_unverified",
    "municipality", "equipment_or_scope", "investment_amount_unverified",
    "source_date", "source_date_basis", "source_url", "contact_name_verified",
    "contact_professional_title", "contact_email_verified", "contact_source_url",
    "public_company_channel", "purchasing_authority_verified",
    "open_supplier_package_verified", "qualification_status",
)

def _read(path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 50_000_000:
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def run(results):
    root = Path(results)
    if not root.is_dir():
        raise FileNotFoundError("EXISTING_RESULTS_REQUIRED")
    rows = []
    for r in _read(root / "INDUSTRIAL_PILOT" /
                   "GTA_RADAR_INDUSTRIAL_EQUIPMENT_REVIEW.csv"):
        if not r.get("official_notice_url") or not r.get("equipment"):
            continue
        rows.append({
            "source_type": "ERO_INSTRUMENT_PROPOSAL",
            "company": r.get("proponent", ""),
            "physical_project_address_unverified": r.get("site_address", ""),
            "municipality": r.get("city", ""),
            "equipment_or_scope": (r.get("equipment", "") + " / " +
                                   r.get("action", "")).strip(" /"),
            "source_date": r.get("proposal_posted", ""),
            "source_date_basis": "ERO_NOTICE_POSTING_NOT_FIRST_EQUIPMENT_ORDER",
            "source_url": r.get("official_notice_url", ""),
            "qualification_status": "ERO_RESEARCH_RECHECK_PURCHASING_STAGE",
        })
    for r in _read(root / "GTA_RADAR_INVESTMENT_CONTACT_BRIDGE" /
                   "GTA_RADAR_EQUIPMENT_INVESTMENT_OPPORTUNITIES.csv"):
        if not r.get("source_urls") or not r.get("company_source_claim"):
            continue
        rows.append({
            "source_type": "SOURCE_BACKED_INVESTMENT_ANNOUNCEMENT",
            "company": r.get("company_source_claim", ""),
            "physical_project_address_unverified": r.get(
                "project_address_source_claim", ""),
            "municipality": r.get("city", ""),
            "equipment_or_scope": r.get("equipment_or_investment_scope_quote", ""),
            "source_date": "",
            "source_date_basis": "PUBLICATION_DATE_NOT_INDEPENDENTLY_VERIFIED",
            "source_url": r.get("source_urls", ""),
            "contact_name_verified": r.get("public_professional_name", ""),
            "contact_professional_title": r.get("public_professional_title", ""),
            "contact_email_verified": r.get("public_professional_email", ""),
            "contact_source_url": r.get("public_professional_source_url", ""),
            "public_company_channel": r.get("public_company_channel", ""),
            "qualification_status": "RESEARCH_ONLY_NOT_PROVEN_EQUIPMENT_PURCHASE",
        })
    unique = {}
    for row in rows:
        key = (row["source_type"], row["company"], row["source_url"])
        unique.setdefault(key, row)
    rows = list(unique.values())
    path = root / OUTPUT
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            safe = {key: str(row.get(key) or "") for key in FIELDS}
            safe.update({"purchasing_authority_verified": "False",
                         "open_supplier_package_verified": "False"})
            writer.writerow({k: ("'" + v if v.lstrip().startswith(
                ("=", "+", "-", "@", "\\t", "\\r")) else v)
                for k, v in safe.items()})
    summary = {
        "status": "SOURCE_EVIDENCE_RESEARCH_ONLY",
        "sources": {
            "ero": sum(x["source_type"] == "ERO_INSTRUMENT_PROPOSAL" for x in rows),
            "investment": sum(
                x["source_type"] == "SOURCE_BACKED_INVESTMENT_ANNOUNCEMENT"
                for x in rows),
        },
        "candidate_count": len(rows),
        "verified_purchasing_contacts": 0,
        "verified_open_packages": 0,
        "fresh_original_publications_verified": 0,
        "no_network_or_paid_calls": True,
        "output_csv": str(path),
    }
    # Prioritize verified source excerpts and prospective equipment research.
    # This stage is offline, free and does not alter the existing index.
    from gta_industrial_capex_priority import run as industrial_capex_run
    summary["industrial_capex_priority"] = industrial_capex_run(root)
    # No full 2.3 GB federal download in daily collection. Stream only
    # a previously operator-supplied official snapshot, retaining full
    # audit status when absent.
    from gta_federal_industrial_funding import (
        run as federal_grants_run, OUTPUT as federal_output,
    )
    # The original grants.csv is several GB and refreshed infrequently.
    # Never repeat the full import in every municipal daily run. The operator
    # can refresh it explicitly by running gta_federal_industrial_funding.py.
    # Most importantly, an absent snapshot must not erase previously imported
    # official funding candidates or their historical research.
    saved_federal = root / federal_output
    if saved_federal.is_file() and saved_federal.stat().st_size > 100:
        summary["federal_industrial_funding"] = {
            "status": "REUSED_SAVED_OFFICIAL_FUNDING_CANDIDATES",
            "input_path": str(saved_federal),
            "refresh_mode": "MANUAL_OFFICIAL_SNAPSHOT_IMPORT_ONLY",
            "new_candidates_collected_today": 0,
            "paid_ai_calls": 0,
        }
    else:
        summary["federal_industrial_funding"] = federal_grants_run(root)
    from gta_federal_capex_qualification import run as qualify_federal_capex
    summary["federal_capex_qualification"] = qualify_federal_capex(root)
    (root / STATUS).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.results), indent=2))

if __name__ == "__main__":
    main()
