"""One manual Monday run: existing Radar + all four isolated intelligence pilots.

Runs the existing collector once, then read-only pilot stages on that workspace.
Industrial ERO fetch is robots-gated, limited to <=10 notices; AI harness stays
free/preflight because the core collector already owns the shared paid budget.
Each stage gets a log and status; failed stages never become verified leads.
"""
from __future__ import annotations
import argparse
import datetime as dt
import html
import json
import subprocess
import sys
from pathlib import Path

from v6_daily_pipeline import find_workspace

ROOT = Path(__file__).resolve().parent
REPORT = "MONDAY_FULL_RADAR_STATUS.json"
INDEX = "MONDAY_FULL_RADAR_REPORT.html"


def stages(workspace, results, *, industrial_limit=10, skip_collection=False):
    ws, out = str(workspace), str(results)
    # A source fetch is allowed only within a true operator-initiated
    # collection run, never a --skip-collection historical review.
    council_args = ["gta_council_integrated_manual.py",
                    "--workspace", ws, "--results", out]
    if not skip_collection:
        council_args.append("--fetch-brampton-featured")
        council_args.append("--fetch-brampton-official-gis")
        council_args.append("--fetch-mississauga-pdc")
        council_args.append("--fetch-mississauga-official-gis")
        council_args.append("--fetch-toronto-official-agendas")
        council_args.append("--fetch-toronto-schedule")
        council_args.append("--fetch-toronto-planning-notices")
    base = [
        ("daily_radar", ["gta_total_intelligence_run.py", "--workspace", ws], True),
        ("industrial_equipment", ["gta_industrial_equipment_run.py",
                                  "--workspace", ws, "--limit", str(industrial_limit)], False),
        ("commercial_activation", ["gta_commercial_activation_run.py",
                                   "--workspace", ws], False),
        ("facility_evidence", ["gta_facility_review_run.py",
                               "--workspace", ws, "--results", out], False),
        ("toronto_20_source_research", ["gta_toronto_20_commercial_review.py",
                                       "--out", str(results / "TORONTO_20_COMMERCIAL_REVIEW")], False),
        ("council_agenda_intelligence", council_args, False),
        # Source-backed investment/company/contact discovery has commercial
        # priority over broad optional AI research. Both use the identical
        # V5+legacy ledger; put it first so later general analysis cannot
        # exhaust the shared ceiling before contact research is attempted.
        ("industrial_investment_and_contacts",
         ["gta_investment_contact_daily_bridge.py", "--results", out] +
         (["--paid"] if not skip_collection else []), False),
        # The project harness remains capped and idempotent; its paid requests
        # run AFTER the industrial/contact lane, never in historical review.
        ("ai_harness_adaptive" if not skip_collection else "ai_harness_free",
         ["gta_agent_harness.py", "--results", out] +
         (["--paid", "--max-projects", "10"] if not skip_collection else []),
         False),
    ]
    if skip_collection:
        base = base[1:]
    return base


def execute(workspace=None, *, industrial_limit=10, skip_collection=False,
            runner=None):
    if not 0 <= int(industrial_limit) <= 10:
        raise ValueError("industrial_limit must be between 0 and 10")
    ws = Path(find_workspace(workspace))
    results = ws / "GTA_RADAR_RESULTS"
    results.mkdir(parents=True, exist_ok=True)
    out = results / "MONDAY_FULL_RADAR"
    logs = out / "LOGS"
    logs.mkdir(parents=True, exist_ok=True)
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    report = {
        "mode": "MANUAL_COMPLETE_RADAR_REVIEW",
        "started_utc": started,
        "workspace": str(ws),
        "collection_performed": not skip_collection,
        "fresh_collection_verified": False,
        "industrial_official_fetch_maximum": industrial_limit,
        "ai_harness_mode": "ADAPTIVE_RESEARCH_SHARED_BUDGET" if not skip_collection else "FREE_PREFLIGHT",
        "buyer_verified_by_integration": False,
        "open_supplier_contract_verified_by_integration": False,
        "outreach_performed": False,
        "status": "RUNNING",
        "stages": [],
    }
    manifest = out / REPORT
    index = out / INDEX

    def save():
        manifest.write_text(json.dumps(report, indent=2), encoding="utf-8")

    def inspect_daily_stage():
        # Include sanitized primary diagnostics in the archived manifest. A
        # previous run's saved JSON must never be presented as today's stage.
        names=(("discovery", "GTA_RADAR_DISCOVERY_RUN_STATUS.json"),
               ("integrated", "GTA_RADAR_INTEGRATED_INTELLIGENCE_STATUS.json"),
               ("collector", "GTA_RADAR_V6_RUN.json"))
        details={}
        threshold=dt.datetime.fromisoformat(started).timestamp()-3
        for key, filename in names:
            path=results / filename
            try:
                if path.stat().st_mtime < threshold:
                    details[key]={"status":"OLDER_SAVED_EVIDENCE_NOT_TODAYS_RUN"}
                    continue
                data=json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data,dict):
                    raise ValueError("EXPECTED_JSON_OBJECT")
                if key=="discovery":
                    details[key]={k:data.get(k) for k in (
                        "status","completed","collection_exit_code",
                        "collector_status","code_check_status",
                        "meeting_document_pipeline_complete","optional_stage_failures",
                        "required_stage_failures")}
                elif key=="integrated":
                    details[key]={k:data.get(k) for k in (
                        "status","failed_stages","required_failed_stages",
                        "optional_failed_stages","blocked_sources",
                        "combined_records","cities_with_application_candidates_measured")}
                    details[key]["stage_errors"]=[{
                        "stage":str(s.get("stage",""))[:110],
                        "required":bool(s.get("required")),
                        "status":str(s.get("status",""))[:30],
                        "error":str(s.get("error",""))[:250]}
                        for s in data.get("stages",[]) if isinstance(s,dict)
                        and s.get("status") in ("FAILED","BLOCKED")][:35]
                else:
                    details[key]={k:data.get(k) for k in (
                        "status","projects","investigated","queue_stop_reason")}
            except (OSError, ValueError, TypeError) as exc:
                details[key]={"status":"NO_CURRENT_STAGE_DIAGNOSTIC",
                              "error_type":type(exc).__name__}
        return details

    def render():
        tr = "".join(
            "<tr><td>" + html.escape(row["name"]) +
            "</td><td>" + html.escape(row["status"]) +
            "</td><td>" + html.escape(str(row.get("exit_code", ""))) +
            "</td><td>" + html.escape(row["log"]) + "</td></tr>"
            for row in report["stages"]
        )
        index.write_text(
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>GTA Radar manual full run</title>"
            "<style>body{font:15px Arial;margin:2rem;max-width:1100px}"
            "table{border-collapse:collapse;width:100%}"
            "th,td{padding:9px;border:1px solid #bbb;text-align:left}</style>"
            "</head><body><h1>GTA Radar — all-pilot manual run</h1>"
            "<p>Status: <b>" + html.escape(report["status"]) + "</b></p>"
            "<p>Collector: " + ("fresh output required" if not skip_collection else
                                 "SKIPPED; saved evidence may be older") + "</p>"
            "<p>Source events are not verified buyers, openings or available contracts.</p>"
            "<table><tr><th>Stage</th><th>Status</th><th>Exit</th><th>Log</th></tr>"
            + tr + "</table>"
            "<p>Review the individual pilot CSV/HTML reports under GTA_RADAR_RESULTS."
            " AI research may run within the pre-existing shared local budget guard, "
            "but local reservations are not proof of provider charges. "
            "No automated outreach or scheduling.</p>"
            "</body></html>", encoding="utf-8"
        )

    save()
    run = runner or subprocess.run
    for name, args, critical in stages(
            ws, results, industrial_limit=industrial_limit,
            skip_collection=skip_collection):
        log = logs / (name + ".log")
        cmd = [sys.executable, str(ROOT / args[0]), *args[1:]]
        # Running paid company research after a failed primary collector
        # could re-label historical research as today's discovery. Do not.
        # Historical-only review is allowed but MUST have no --paid flag.
        if (name == "industrial_investment_and_contacts" and
                not skip_collection and not report["fresh_collection_verified"]):
            log.write_text("SKIPPED_NO_FRESH_COLLECTION; NO_SPEND\n",
                           encoding="utf-8")
            report["stages"].append({
                "name": name, "status": "SKIPPED_NO_FRESH_COLLECTION",
                "exit_code": None, "critical": False,
                "log": str(log)})
            report["investment_contact_diagnostics"] = {
                "status": "SKIPPED_NO_FRESH_COLLECTION",
                "paid_calls": 0, "verified_buyers": 0,
                "outreach_authorized": False}
            save()
            continue
        try:
            with log.open("w", encoding="utf-8") as stream:
                result = run(cmd, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
            exit_code = result.returncode
            failure = ""
        except (OSError, ValueError) as exc:
            exit_code = 125
            failure = type(exc).__name__ + ": " + str(exc)[:200]
            log.write_text(failure, encoding="utf-8")
        row = {
            "name": name, "status": "PASSED" if exit_code == 0 else "FAILED",
            "exit_code": exit_code, "critical": critical,
            "log": str(log),
        }
        if failure:
            row["error"] = failure
        report["stages"].append(row)
        if name == "council_agenda_intelligence":
            council_file = results / "COUNCIL_INTELLIGENCE_REVIEW" / "COUNCIL_INTEGRATED_REVIEW_STATUS.json"
            try:
                if council_file.stat().st_mtime < dt.datetime.fromisoformat(started).timestamp() - 3:
                    raise ValueError("OLDER_COUNCIL_EVIDENCE_NOT_TODAY")
                council_data = json.loads(council_file.read_text(encoding="utf-8"))
                report["council_review_diagnostics"] = {
                    key: council_data.get(key) for key in (
                        "status", "documents_considered", "documents_parsed",
                        "source_documents_missing", "source_documents_failed",
                        "source_documents_held", "source_manifest_status",
                        "agenda_to_application_permit_chains_verified",
                        "publisher_first_publications_verified", "paid_ai_usd")
                }
                report["council_review_diagnostics"]["index"] = council_data.get("official_index_audit", {})
                report["council_review_diagnostics"]["brampton_featured"] = council_data.get(
                    "brampton_featured_public_applications", {})
                report["council_review_diagnostics"]["brampton_official_gis_planning"] = council_data.get(
                    "brampton_official_gis_planning", {})
                report["council_review_diagnostics"]["brampton_gis_existing_radar_reconciliation"] = council_data.get(
                    "brampton_gis_existing_radar_reconciliation", {})
                report["council_review_diagnostics"]["mississauga_discovered_pdc"] = council_data.get(
                    "mississauga_discovered_pdc", {})
                report["council_review_diagnostics"]["toronto_exact_agenda_retrieval"] = council_data.get(
                    "toronto_exact_agenda_retrieval", {})
                report["council_review_diagnostics"]["toronto_official_meeting_schedule"] = council_data.get(
                    "toronto_official_meeting_schedule", {})
                report["council_review_diagnostics"]["toronto_schedule_to_agenda_item_link"] = council_data.get(
                    "toronto_schedule_to_agenda_item_link", {})
                report["council_review_diagnostics"]["toronto_official_planning_notices"] = council_data.get(
                    "toronto_official_planning_notices", {})
                report["council_review_diagnostics"]["mississauga_match"] = {
                    key: council_data.get("mississauga_20_case_comparison", {}).get(key)
                    for key in ("cases_reviewed", "missing_case_count",
                                "three_source_identity_review_candidates",
                                "early_detection_advantage_proven")
                }
            except (OSError, ValueError, TypeError, KeyError) as exc:
                report["council_review_diagnostics"] = {
                    "status": "NO_CURRENT_COUNCIL_STAGE_DIAGNOSTIC",
                    "error_type": type(exc).__name__
                }
        if name == "council_agenda_intelligence" and not skip_collection:
            # The AI shortlist assessor executes BEFORE the larger project
            # research harness, while the seven-stage collection remains
            # unchanged. One shared ledger and the same cross-process lock
            # guard all model requests. Never claim a model hypothesis is a
            # verified buyer, open contract or first-publication date.
            if report.get("fresh_collection_verified"):
                try:
                    from gta_ai_top10_reranker import run as run_ai_preselection
                    pre = run_ai_preselection(results, paid=True)
                    report["ai_top10_preselection"] = {
                        "status": pre["status"],
                        "candidate_count": pre["candidate_count"],
                        "reviewed_count": pre["reviewed_count"],
                        "paid_model_calls": pre["paid_model_calls"],
                        "source_snapshot_only": True,
                        "applies_to_top10": pre.get("applies_to_top10", False),
                        "verified_buyers": 0,
                        "verified_supplier_contracts": 0,
                    }
                except (OSError, ValueError, TypeError, ImportError, RuntimeError) as exc:
                    report["ai_top10_preselection"] = {
                        "status": "SAFE_FALLBACK_DETERMINISTIC_ONLY",
                        "error_type": type(exc).__name__,
                        "verified_buyers": 0,
                    }
            else:
                report["ai_top10_preselection"] = {
                    "status": "SKIPPED_NO_FRESH_COLLECTION"}
        if name in ("ai_harness_adaptive", "ai_harness_free"):
            # Exit code 0 is not evidence that DeepSeek ran or was billed.
            # The harness's own manifest explicitly reports attempts and
            # model results; never equate ledger holds with API charges.
            ai_manifest = results / "AGENT_HARNESS_REVIEW" / "AI_HARNESS_STATUS.json"
            try:
                data = json.loads(ai_manifest.read_text(encoding="utf-8"))
                report["ai_harness_diagnostics"] = {
                    "status": data.get("status", "UNKNOWN"),
                    "mode": data.get("mode", "UNKNOWN"),
                    "research_attempts": data.get("executor", {}).get("attempted", 0),
                    "research_completed": data.get("executor", {}).get("completed", 0),
                    "model_calls_billed_verified": False,
                    "local_guard_used_or_held_usd_not_billing": data.get(
                        "executor", {}).get("budget_used_or_held_usd"),
                }
            except (OSError, ValueError, TypeError) as exc:
                report["ai_harness_diagnostics"] = {
                    "status": "HARNESS_REPORT_MISSING_OR_UNREADABLE",
                    "error_type": type(exc).__name__,
                }
        if name == "industrial_investment_and_contacts":
            bridge_path = (results / "GTA_RADAR_INVESTMENT_CONTACT_BRIDGE" /
                           "INVESTMENT_CONTACT_INTEGRATION_STATUS.json")
            try:
                if bridge_path.stat().st_mtime < (
                        dt.datetime.fromisoformat(started).timestamp() - 3):
                    raise ValueError("OLDER_INVESTMENT_BRIDGE_REPORT")
                info = json.loads(bridge_path.read_text(encoding="utf-8"))
                report["investment_contact_diagnostics"] = {
                    "status": info.get("status", "UNKNOWN"),
                    "project": info.get("project", "UNKNOWN"),
                    "discovery": info.get("discovery", {}),
                    "qualification": info.get("qualification", {}),
                    "contacts": info.get("contacts", {}),
                    "buyer_verified": False,
                    "open_supplier_contract_verified": False,
                    "outreach_authorized": False,
                }
            except (OSError, ValueError, TypeError) as exc:
                report["investment_contact_diagnostics"] = {
                    "status": "NO_CURRENT_INVESTMENT_CONTACT_REPORT",
                    "error_type": type(exc).__name__}
        if name == "daily_radar":
            # Discovery itself refuses missing/stale daily output. Its success
            # does not mean evidence/commercial gates have been satisfied.
            report["fresh_collection_verified"] = exit_code == 0
            report["daily_radar_diagnostics"] = inspect_daily_stage()
        save()
        print(name + ": " + row["status"] + " | " + str(log), flush=True)

    # Provide an independent, read-only breakdown of the *local software*
    # guard. Reservations and estimates are NOT DeepSeek provider invoices.
    # The SQLite files are opened read-only and remain unchanged.
    if not skip_collection:
        try:
            from gta_ai_budget_guard_diagnostic import run as run_ai_guard_diagnostic
            audit = run_ai_guard_diagnostic(results)
            report["deepseek_guard_diagnostic"] = {
                "status": audit["status"],
                "provider_billing_verified": False,
                "provider_actual_billed_usd": None,
                "shared_completed_estimate_usd": audit["shared_ledger"].get(
                    "completed_estimate_usd"),
                "shared_unresolved_reserved_usd": audit["shared_ledger"].get(
                    "unresolved_reserved_usd"),
                "local_guard_usage_usd_not_provider_billing": audit[
                    "shared_ledger"].get("local_guard_usage_usd"),
            }
        except (OSError, ValueError, TypeError, ImportError) as exc:
            report["deepseek_guard_diagnostic"] = {
                "status": "BUDGET_GUARD_AUDIT_HELD",
                "error_type": type(exc).__name__,
                "provider_billing_verified": False,
            }

    # Read-only quality report is part of post-run evidence accounting, not a
    # new collector/stage. Preserve the established seven-stage contract.
    if not skip_collection:
        try:
            from gta_source_quality_v1 import run as run_source_quality
            quality = run_source_quality(results)
            report["source_quality"] = {
                "status": quality["status"],
                "municipalities_with_records": quality.get("municipalities_with_records", 0),
                "citywide_verified": 0,
                "buyer_leads_verified": 0,
                "report": str(results / "GTA_RADAR_SOURCE_QUALITY_V1.json"),
            }
        except (OSError, ValueError, ImportError) as exc:
            report["source_quality"] = {
                "status": "SOURCE_QUALITY_REPORT_FAILED",
                "error_type": type(exc).__name__,
            }
    else:
        report["source_quality"] = {"status": "NOT_RUN_HISTORICAL_MODE"}

    # The existing daily collector already captures vetted official PDF
    # files, but the council agenda parser only consumed an owner-created
    # input manifest. Preserve that strict parser AND bridge its existing
    # SHA-checked capture audits into a separate page-cited evidence queue.
    # No new downloads, no guessed publication dates or project joins.
    if not skip_collection:
        try:
            from gta_council_captured_pdf_bridge import review as review_captured_pdf
            cpdf = review_captured_pdf(results)
            report["council_captured_pdf_evidence"] = {
                "status": "CAPTURED_SOURCE_EVIDENCE_REVIEW_ONLY",
                "captured_official_pdfs_inspected":
                    cpdf["captured_official_pdfs_inspected"],
                "pdfs_with_keyword_evidence":
                    cpdf["pdfs_with_keyword_evidence"],
                "page_cited_segments": cpdf["page_cited_segments"],
                "exact_application_id_text_mentions_for_review":
                    cpdf["exact_application_id_text_mentions_for_review"],
                "verified_project_links": 0,
                "new_paid_calls": 0,
            }
        except (OSError, ValueError, TypeError, ImportError) as exc:
            report["council_captured_pdf_evidence"] = {
                "status": "CAPTURED_PDF_BRIDGE_HELD",
                "error_type": type(exc).__name__}
    else:
        report["council_captured_pdf_evidence"] = {
            "status": "NOT_RUN_HISTORICAL_MODE"}

    # Read-only registry and explicitly registered PDF evidence review.
    # No new source fetch, extra stage, AI spend, or outreach.
    try:
        from gta_municipal_platform_registry import run as run_platform_registry
        platforms = run_platform_registry(results)
        report["platform_registry"] = {
            "status": platforms["status"],
            "source_count": platforms["source_count"],
            "known_platform_sources": platforms["known_platform_sources"],
        }
    except (OSError, ValueError, ImportError) as exc:
        report["platform_registry"] = {
            "status": "PLATFORM_REGISTRY_HELD",
            "error_type": type(exc).__name__,
        }
    if not skip_collection:
        try:
            from gta_registered_document_evidence import run as run_document_evidence
            review = run_document_evidence(ws, results)
            report["registered_document_evidence"] = {
                "status": review["status"],
                "documents_registered": review.get("documents_registered", 0),
                "segments_for_manual_review": review.get("segments_for_manual_review", 0),
                "project_leads_verified": 0,
            }
        except (OSError, ValueError, ImportError) as exc:
            report["registered_document_evidence"] = {
                "status": "REGISTERED_DOCUMENT_EVIDENCE_HELD",
                "error_type": type(exc).__name__,
            }
    else:
        report["registered_document_evidence"] = {
            "status": "NOT_RUN_HISTORICAL_MODE",
        }

    # Saved captions can be reviewed without fetching or transcribing media.
    # Missing explicit manifest means no caption evidence; historical-only runs
    # do not reinterpret saved material as today's newly collected source.
    if not skip_collection:
        try:
            from gta_local_caption_evidence import run as run_caption_evidence
            captions = run_caption_evidence(ws, results)
            report["local_caption_evidence"] = {
                "status": captions["status"],
                "caption_files": captions.get("caption_files", 0),
                "mentions_for_review": captions.get("mentions_for_review", 0),
                "verified_projects": 0,
            }
        except (OSError, ValueError, ImportError) as exc:
            report["local_caption_evidence"] = {
                "status": "CAPTION_REVIEW_HELD",
                "error_type": type(exc).__name__,
            }
    else:
        report["local_caption_evidence"] = {
            "status": "NOT_RUN_HISTORICAL_MODE",
        }

    # Correlate existing application IDs with saved council excerpts, never
    # promote text mentions to verified projects, applicants or purchasing leads.
    if not skip_collection:
        try:
            from gta_cross_source_evidence_reconciliation import run as run_reconciliation
            recon = run_reconciliation(results)
            report["cross_source_reconciliation"] = {
                "status": recon["status"],
                "mentions_considered": recon["mentions_considered"],
                "exact_id_review_candidates": recon["exact_id_review_candidates"],
                "unmatched_or_ambiguous_mentions": recon["unmatched_or_ambiguous_mentions"],
                "independently_verified_project_links": 0,
            }
        except (OSError, ValueError, ImportError) as exc:
            report["cross_source_reconciliation"] = {
                "status": "RECONCILIATION_HELD",
                "error_type": type(exc).__name__,
            }
    else:
        report["cross_source_reconciliation"] = {
            "status": "NOT_RUN_HISTORICAL_MODE",
        }

    # Reconcile exact-ID source-backed AI research from the preceding harness
    # into review-only project roles, status conflicts and supplier priority.
    # No API call, company entity verification or changed collector DB.
    try:
        from gta_ai_project_evidence_bridge import run as run_ai_bridge
        ai_bridge = run_ai_bridge(results)
        report["ai_project_evidence_bridge"] = {
            "status": ai_bridge["status"],
            "project_candidates": ai_bridge.get("project_candidates", 0),
            "source_supported_role_claims": ai_bridge.get(
                "source_supported_role_claims_not_legal_verification", 0),
            "address_or_lifecycle_conflict_candidates": ai_bridge.get(
                "projects_with_address_or_lifecycle_conflicts", 0),
            "verified_buyers": 0, "verified_open_supplier_packages": 0,
            "paid_ai_usd": 0,
        }
    except (OSError, ValueError, TypeError, ImportError) as exc:
        report["ai_project_evidence_bridge"] = {
            "status": "AI_SOURCE_EVIDENCE_BRIDGE_HELD",
            "error_type": type(exc).__name__,
        }

    # Build an evidence graph from existing facility/research and council
    # review files. Company names remain unverified, project-scoped mentions;
    # no contacts, buyer assertions, source fetches or paid AI.
    if not skip_collection:
        try:
            from gta_project_company_evidence_graph import run as run_role_graph
            role_graph = run_role_graph(results)
            report["project_company_evidence_graph"] = {
                "status": role_graph["status"],
                "project_candidates": role_graph["project_candidates"],
                "organization_mentions": role_graph["organization_mentions"],
                "claimed_relationships": role_graph["claimed_relationships"],
                "role_conflicts": role_graph["role_conflicts"],
                "council_id_context_links": role_graph["council_id_context_links"],
                "ai_source_supported_role_claims": role_graph.get(
                    "ai_source_supported_role_claims", 0),
                "ai_review_conflict_candidates": role_graph.get(
                    "ai_review_conflict_candidates", 0),
                "verified_project_company_roles": 0,
                "verified_buyers": 0,
            }
        except (OSError, ValueError, ImportError) as exc:
            report["project_company_evidence_graph"] = {
                "status": "PROJECT_COMPANY_GRAPH_HELD",
                "error_type": type(exc).__name__,
            }
    else:
        report["project_company_evidence_graph"] = {
            "status": "NOT_RUN_HISTORICAL_MODE",
        }

    # Source-backed buyer/supplier research queue. Operator attestations live
    # outside exported run results and never authorize outreach or live claims.
    if not skip_collection:
        try:
            from gta_supplier_verification_gate import run as run_supplier_gate
            verification = run_supplier_gate(results, ws)
            report["company_procurement_review"] = {
                "status": verification["status"],
                "source_graph_role_claims": verification.get("source_graph_role_claims", 0),
                "reviewer_attested_role_claims": verification.get("reviewer_attested_role_claims", 0),
                "reviewer_attested_open_tender_needing_live_recheck":
                    verification.get("reviewer_attested_open_tender_needing_live_recheck", 0),
                "held_or_conflicting_decisions":
                    verification.get("held_or_conflicting_decisions", 0),
                "verified_buyers": 0,
                "verified_open_supplier_contracts": 0,
                "outreach_authorized": False,
            }
        except (OSError, ValueError, TypeError, ImportError) as exc:
            report["company_procurement_review"] = {
                "status": "COMPANY_PROCUREMENT_GATE_HELD",
                "error_type": type(exc).__name__,
            }
    else:
        report["company_procurement_review"] = {
            "status": "NOT_RUN_HISTORICAL_MODE",
        }

    # Zero-cost cross-source internal analyst shortlist. This is a research
    # priority list, NOT a customer lead file or a verified buyer/contact list.
    # It is generated after the AI bridge and supplier review, using current
    # source-event dates and explicit unknown procurement status.
    try:
        from gta_commercial_qualification_review import run as qualify_review
        q = qualify_review(results)
        report["commercial_qualification_worklist"] = {
            "status": q["status"],
            "source_rows": q["source_rows"],
            "internal_top_10_count": q["internal_top_10_count"],
            "verified_buyers": 0,
            "verified_open_supplier_contracts": 0,
            "paid_ai_calls": 0,
            "outreach_authorized": False,
        }
    except (OSError, ValueError, TypeError, ImportError) as exc:
        report["commercial_qualification_worklist"] = {
            "status": "INTERNAL_COMMERCIAL_WORKLIST_HELD",
            "error_type": type(exc).__name__,
        }

    passed = sum(x["status"] == "PASSED" for x in report["stages"])
    failed = [x["name"] for x in report["stages"]
              if x["status"] == "FAILED"]
    report["stage_successes"] = passed
    report["failed_stages"] = failed
    integrated_diag=report.get("daily_radar_diagnostics",{}).get("integrated",{})
    report["optional_source_warnings"]={
        "optional_failed_stages":integrated_diag.get("optional_failed_stages") or [],
        "blocked_sources":integrated_diag.get("blocked_sources") or [],
        "details":integrated_diag.get("stage_errors") or []}
    has_warnings=bool(report["optional_source_warnings"]["optional_failed_stages"]
                      or report["optional_source_warnings"]["blocked_sources"])
    report["status"] = (
        "ALL_STAGES_RAN_WITH_SOURCE_WARNINGS_REVIEW_ONLY"
        if not failed and not skip_collection and has_warnings
        else "ALL_STAGES_RAN_REVIEW_ONLY" if not failed and not skip_collection
        else "REVIEW_COMPLETED_WITH_FAILURES" if failed
        else "SAVED_DATA_REVIEW_ONLY_NO_NEW_COLLECTION"
    )
    report["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    report["report_html"] = str(index)
    save()
    render()
    # Create one dated, bounded export *after* the final integration manifest
    # is written. Never include SQLite, API keys or live collector credentials.
    # Failure to package is reported, not disguised as a complete run.
    try:
        from gta_daily_result_archive import create as create_archive
        package = create_archive(results)
        report["archive_status"] = "CREATED_REVIEW_ONLY"
        report["run_archive"] = package["archive"]
        report["run_archive_freshness_gate"] = package["freshness_gate"]
        print("DATED REVIEW ZIP: " + package["archive"], flush=True)
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        report["archive_status"] = "FAILED_NOT_PACKAGED"
        report["archive_error"] = type(exc).__name__ + ": " + str(exc)[:250]
        print("ARCHIVE FAILED: " + report["archive_error"], flush=True)
    save()
    render()
    print("FULL RUN REPORT: " + str(index), flush=True)
    print("FULL RUN MANIFEST: " + str(manifest), flush=True)
    return 0 if not failed and report["archive_status"] == "CREATED_REVIEW_ONLY" else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", help="Existing Desktop/new data workspace")
    parser.add_argument("--industrial-limit", type=int, default=10)
    parser.add_argument("--skip-collection", action="store_true",
                        help="Explicit historical-only review; cannot claim fresh run")
    parser.add_argument("--unattended", action="store_true",
                        help="Accepted for the batch shortcut; controls console pause only")
    args = parser.parse_args()
    try:
        return execute(args.workspace, industrial_limit=args.industrial_limit,
                       skip_collection=args.skip_collection)
    except (OSError, ValueError, FileNotFoundError) as exc:
        print("Cannot start Radar: " + type(exc).__name__ + ": " + str(exc))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
