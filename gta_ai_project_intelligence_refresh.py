"""Refresh AI project evidence, company graph and procurement review from saved data.

NO collectors, paid model calls, Search/Fetch, outreach or sales promotion.
Designed for both the end of the paid AI harness and an operator's existing
results workspace without a second seven-stage municipal collection.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from gta_ai_project_evidence_bridge import run as bridge_run
from gta_project_company_evidence_graph import run as graph_run
from gta_supplier_verification_gate import run as supplier_run
from gta_commercial_qualification_review import run as qualification_run

REPORT = "GTA_RADAR_AI_PROJECT_INTEGRATION_STATUS.json"


def run(results, workspace=None, *, today=None):
    root = Path(results)
    if not root.is_dir():
        raise FileNotFoundError("EXISTING_RESULTS_DIRECTORY_REQUIRED")
    bridge = bridge_run(root)
    graph = graph_run(root, today=today)
    gate = supplier_run(root, workspace)
    qualification = qualification_run(root, today=today)
    report = {
        "status": "AI_PROJECT_GRAPH_AND_SUPPLIER_REVIEW_REFRESHED",
        "ai_review_projects": bridge.get("project_candidates", 0),
        "source_supported_ai_role_claims": bridge.get(
            "source_supported_role_claims_not_legal_verification", 0),
        "projects_with_source_conflicts": bridge.get(
            "projects_with_address_or_lifecycle_conflicts", 0),
        "graph_projects": graph.get("project_candidates", 0),
        "graph_role_claims": graph.get("claimed_relationships", 0),
        "ai_top10_quote_supported_role_candidates": graph.get(
            "ai_top10_quote_supported_role_review_candidates", 0),
        "ai_top10_report_role_candidates": qualification.get(
            "ai_exact_application_role_candidates", 0),
        "verified_purchasing_authorities": 0,
        "supplier_role_review_queue": len(gate.get("role_queue", [])),
        "supplier_procurement_review_queue": len(gate.get("tender_queue", [])),
        "internal_commercial_review_top10": qualification["internal_top_10_count"],
        "top10_export_status": qualification["top10_export_status"],
        "canonical_top10_updated": qualification["canonical_top10_updated"],
        "latest_top10_analyst_csv": qualification["outputs"]["top10_analyst_csv"],
        "qualified_sale_ready_leads": 0,
        "verified_buyers": 0, "verified_open_supplier_contracts": 0,
        "new_paid_ai_calls": 0, "live_source_fetches": 0,
        "outreach_authorized": False,
        "source_role_origin": "EXACT_ID_SOURCE_LITERAL_REVIEW_ONLY",
        "warnings": (
            "AI-based organizations remain document-scoped mentions. "
            "Address variants, application chronology and legal purchasing "
            "roles require independent checking before client distribution."
        ),
        "outputs": {
            "bridge": "GTA_RADAR_AI_PROJECT_EVIDENCE_BRIDGE.json",
            "graph": "GTA_RADAR_PROJECT_COMPANY_EVIDENCE_GRAPH.json",
            "procurement_review": "GTA_RADAR_COMPANY_PROCUREMENT_REVIEW_STATUS.json",
            "commercial_analyst_top10": qualification["outputs"]["top10_analyst_csv"],
            "commercial_qualification": "GTA_RADAR_COMMERCIAL_QUALIFICATION_STATUS.json",
        },
    }
    path = root / REPORT
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    tmp.replace(path)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    parser.add_argument("--workspace")
    args = parser.parse_args()
    print(json.dumps(run(args.results, args.workspace), indent=2))
