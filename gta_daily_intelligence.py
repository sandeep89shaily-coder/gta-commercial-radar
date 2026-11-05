"""Normal daily GTA Radar intelligence: meetings, official documents and sourced research.

Runs AFTER V6's daily collectors and selective project/contacts DeepSeek pass.
All paid stages use the SAME v5_ai_budget.sqlite and radar_config ceiling.
Never elevates a mere agenda link, building address or AI hint into a verified
project, purchasing authority, unawarded package or newly published event.
No outreach, supplier contact, unauthorized video capture or extra databases.
"""
from __future__ import annotations

import csv
import datetime as dt
import html
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from radar_config import DEEPSEEK_DAILY_LIMIT_USD
from gta_document_audit_union import union
from gta_freshness import assess as freshness_assess

PROJECT_INPUT = "GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv"
AUDIT = "GTA_RADAR_INTEGRATED_INTELLIGENCE_STATUS.json"
DETAIL = "GTA_RADAR_INTEGRATED_INTELLIGENCE.csv"
DASHBOARD = "GTA_RADAR_INTEGRATED_INTELLIGENCE.html"
DOC_LEDGER = "GTA_RADAR_DOCUMENT_AI_SEEN.json"
DOC_BACKLOG = "GTA_RADAR_DOCUMENT_AI_PENDING.csv"
MEETING_LINK_LEDGER = "GTA_RADAR_MEETING_LINK_FIRST_SEEN.json"
REPORT_CATEGORIES = ("PROJECT", "SOURCE_INDEX_LINK_REVIEW", "MUNICIPAL_AGENDA_LINK_REVIEW", "MUNICIPAL_DOCUMENT_REVIEW")
FIELDS = ("kind", "project_id", "address", "city", "description", "source_url",
          "official_source_portal_url",
          "freshness", "source_date", "date_basis", "observed_at",
          "research_status", "organization_hint", "public_contact_hint",
          "ai_next_step", "verification_required")
COMMERCIAL = re.compile(
    r"\b(industrial|warehouse|manufactur\w*|factory|commercial|office|retail|"
    r"development|redevelop\w*|construct\w*|site.plan|planning.application|"
    r"new.facility|logistics|data.cent(?:re|er)|expansion|tenant.fit.out)\b", re.I)


def _csv(path):
    path = Path(path)
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _json(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_csv(path, rows, fields=FIELDS):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _url(value):
    try:
        parsed = urlparse(str(value or "").strip())
        return (parsed.scheme == "https" and bool(parsed.hostname)
                and not parsed.username and not parsed.password
                and parsed.port in (None, 443))
    except ValueError:
        return False


def _observed_recent(value, today):
    try:
        observed = dt.date.fromisoformat(str(value or "")[:10])
        return 0 <= (today - observed).days <= 1
    except ValueError:
        return False


def _paid_key_exists():
    import v5_investigator as v5
    return bool(v5.key_from_windows())


def _valid_new_projects(results, today):
    """Only current free watchlist events, never V8's historical backlog."""
    source = _csv(Path(results) / PROJECT_INPUT)
    return [r for r in source
            if r.get("observation") in ("FIRST_OBSERVED", "RECORD_CHANGED")
            and freshness_assess(r, today)["paid_freshness_eligible"]
            and _url(r.get("record_source_url"))]


def _build_document_worklist(union_csv, out, seen, *, paid, ai_processor, ranker=None):
    """Analyze changed PDF bytes at most once after a recorded successful AI result.

    Same bytes at same URL do not get paid AI again on future days. Earlier
    failed/budget-deferred documents remain eligible to retry. No false
    publication timestamp is inferred from downloading a PDF today.
    """
    fields=("url", "status", "reason", "http_status", "bytes", "sha256",
            "saved_path", "city", "source_page", "first_captured_at")
    backlog=Path(out).parent/DOC_BACKLOG
    # Persist captured but not-yet-processed documents, including documents
    # that vanish from the city's index before a later research run.
    candidates={}
    for r in [*_csv(backlog),*_csv(union_csv)]:
        if (r.get("status")!="CAPTURED" or not r.get("sha256")
                or not _url(r.get("url")) or
                not Path(r.get("saved_path") or "").is_file()):
            continue
        key=(r["url"],r["sha256"])
        # Preserve first Radar capture date even when the PDF waits several
        # days for its AI budget. A research date is NOT a publication date.
        prior=candidates.get(key,{})
        r=dict(r)
        r["first_captured_at"]=(prior.get("first_captured_at")
             or r.get("first_captured_at") or
             dt.date.today().isoformat())
        candidates[key]=r
    queued=[r for r in candidates.values() if r["sha256"] not in seen]
    _write_csv(backlog, queued, fields)
    from gta_document_priority import assess as standard_ranker
    ranker=ranker or standard_ranker
    rated=[]
    for r in queued:
        evaluation=ranker(r)
        rated.append((r,evaluation))
    _write_csv(Path(out)/"DOCUMENT_RELEVANCE_TRIAGE.csv",[
        {**row,"relevance_score":quality.get("score",0),
         "relevance_class":quality.get("class",""),
         "relevance_reason":quality.get("reason",""),
         "eligible_for_paid_ai":quality.get("eligible_for_paid_ai",False)}
        for row,quality in rated],
        (*fields,"relevance_score","relevance_class","relevance_reason","eligible_for_paid_ai"))
    eligible=[(r,q) for r,q in rated if q.get("eligible_for_paid_ai")]
    eligible.sort(key=lambda pair:(-int(pair[1].get("score") or 0),
                                  pair[0].get("first_captured_at",""),
                                  pair[0].get("url","")))
    # Rank content relevance before spending; keep a small city-diversity
    # tie break only *within* equal relevance, not ahead of relevance.
    selected=[r for r,q in eligible[:2]]
    to_analyze = Path(out) / "NEW_DOCUMENTS_FOR_REVIEW.csv"
    _write_csv(to_analyze, selected,
               ("url", "status", "reason", "http_status", "bytes", "sha256", "saved_path", "city", "source_page", "first_captured_at"))
    if selected:
        summary = ai_processor(to_analyze, Path(out) / "DOCUMENT_AI", Path(out).parent,
                               paid=paid, limit=2)
        audit = _csv(Path(out) / "DOCUMENT_AI" / "TORONTO_AI_DOCUMENT_BATCH_AUDIT.csv")
        for row in audit:
            if row.get("status") == "AI_REVIEW_ONLY_NOT_SALE_READY":
                seen[row.get("sha256_download","")] = {
                    "source_url":row["source_url"],
                    "result_file":row.get("result_file",""),
                }
    else:
        summary = {"status":"NO_NEW_DOCUMENT_BYTES","review_outputs":0,
                   "ai_calls_reported":0,"errors":0}
    remaining=[r for r in queued if r["sha256"] not in seen]
    _write_csv(backlog, remaining, fields)
    summary["document_ai_backlog_pending"]=len(remaining)
    summary["document_ai_relevance_eligible"]=len(eligible)
    summary["document_ai_irrelevant_or_text_unavailable"]=len(rated)-len(eligible)
    summary["document_relevance_audit"]=str(Path(out)/"DOCUMENT_RELEVANCE_TRIAGE.csv")
    summary["document_ai_backlog_csv"]=str(backlog)
    return selected, summary, seen


def integrate(results, *, today=None, meeting_pipeline=None, document_discover=None,
              agenda_pipeline=None, verified_reports=None, document_ai=None,
              multicity_capture=None, document_ranker=None,
              application_monitor=None, gis_monitor=None, other_gis_monitor=None, municipal_monitor=None, toronto_csv_monitor=None, guelph_gis_monitor=None, burlington_gis_monitor=None, burlington_pdf_monitor=None, staged_durham_monitor=None, official_export_monitor=None, regional_early_monitor=None, regional_detail_monitor=None, regional_document_monitor=None, ggh_expansion_monitor=None, ggh_york_gis_monitor=None, project_ai=None, buyer_ai=None, procurement=None, buyer_batch=None,
              graph=None, api_key_check=None, allow_paid=True):
    """Run integrated bounded stages and expose individual failure provenance.

    Injectable functions make offline and Windows CI fully network/AI-free.
    """
    from RUN_MEETING_BUYER_PIPELINE import pipeline as meeting_default
    from municipal_meeting_capture import OFFICIAL as municipal_official
    from gta_verified_source_pipeline import discover as discover_default, fetch_discovered
    from toronto_meeting_pdf_pipeline import run as agenda_default
    from toronto_verified_report_queue import run as report_default
    from toronto_ai_document_batch import process as document_default
    from municipal_document_capture import run as multicity_capture_default
    from gta_document_project_candidates import update as update_doc_candidates
    from gta_execute_ai_project_research import execute as project_default
    from gta_integrated_buyer_investigation import run as buyer_default
    from gta_live_procurement_evidence import execute as procurement_default
    from gta_buyer_procurement_batch import evaluate as batch_default, write as write_batch
    from gta_unified_intelligence import build as graph_default
    from gta_early_applications import run as applications_default
    from gta_official_gis_applications import run as gis_default
    from gta_additional_city_gis import run as other_gis_default
    from gta_municipal_project_feed import run as municipal_default
    from gta_toronto_open_data import run as toronto_csv_default
    from gta_guelph_gis import run as guelph_gis_default
    from gta_burlington_gis import run as burlington_gis_default
    from gta_burlington_summary_pdf import run as burlington_pdf_default
    from gta_staged_durham_sources import run as staged_durham_default
    from gta_official_download_discovery import run as official_export_default
    from gta_collection_truth import build as collection_acceptance_default
    from gta_city_coverage_report import build as measured_coverage_default
    from gta_three_city_recovery_gate import build as three_city_gate_default
    from gta_three_city_official_csv import run as three_city_official_csv_default
    from gta_regional_early_intelligence import run as regional_early_default
    from gta_regional_project_details import run as regional_details_default
    from gta_regional_document_evidence import run as regional_document_default
    from gta_ggh_early_planning import run as ggh_expansion_default
    from gta_ggh_york_official_gis import run as ggh_york_gis_default
    from gta_ggh_source_access_recovery import run as ggh_source_access_default
    from gta_markham_circulations import run as markham_default

    root = Path(results)
    if not root.is_dir():
        raise FileNotFoundError("Existing GTA_RADAR_RESULTS folder required")
    if not (root / PROJECT_INPUT).is_file():
        raise FileNotFoundError("This run's public-record watch is missing")
    today = today or dt.date.today()
    review = root / "DAILY_INTEGRATED_REVIEW"
    review.mkdir(parents=True, exist_ok=True)
    meeting_pipeline = meeting_pipeline or meeting_default
    document_discover = document_discover or discover_default
    agenda_pipeline = agenda_pipeline or agenda_default
    verified_reports = verified_reports or report_default
    document_ai = document_ai or document_default
    multicity_capture = multicity_capture or multicity_capture_default
    # Fully injected offline tests must never acquire network side effects.
    # Production runs use the real municipal adapter by default.
    municipal_fn = municipal_monitor or (
        municipal_default if application_monitor is None else
        (lambda root, *, today=None: {"source_status":[],"application_id_rows":0,
                                      "project_only_signals":0,"new_or_changed":0}))
    toronto_csv_fn = toronto_csv_monitor or (
        toronto_csv_default if application_monitor is None else
        (lambda root, *, today=None: {"status":"NOT_RUN_IN_INJECTED_TEST",
                                     "commercial_candidates":0,"new_or_changed":0}))
    guelph_gis_fn = guelph_gis_monitor or (
        guelph_gis_default if application_monitor is None else
        (lambda root, *, today=None: {"source_status":[],"commercial_candidates":0,
                                       "new_or_changed":0}))
    burlington_gis_fn = burlington_gis_monitor or (
        burlington_gis_default if application_monitor is None else
        (lambda root, *, today=None: {"status":"SKIPPED_TEST","project_only_signals":0,
                                       "new_or_changed":0}))
    burlington_pdf_fn = burlington_pdf_monitor or (
        burlington_pdf_default if application_monitor is None else
        (lambda root, *, today=None: {"status":"SKIPPED_TEST","report_quarters":0,
                                       "application_id_rows":0}))
    staged_durham_fn = staged_durham_monitor or (
        staged_durham_default if application_monitor is None else
        (lambda root, *, today=None: {"sources":[],"total_rows":0,
          "new_or_changed_reference_records":0,"paid_ai_calls":0,
          "sales_lead_publication":False}))
    official_export_fn = official_export_monitor or (
        official_export_default if application_monitor is None else
        (lambda root, *, today=None: {"status":"SKIPPED_TEST","sources":[],
                                        "application_records":0,"paid_ai_calls":0}))
    ggh_expansion_fn = ggh_expansion_monitor or (
        ggh_expansion_default if application_monitor is None else
        (lambda root, *, today=None: {"cities_configured":12,
          "cities_with_application_ids":0,"application_id_rows":0,
          "new_or_changed":0,"source_status":[],"status":"SKIPPED_OFFLINE_TEST"}))
    regional_early_fn = regional_early_monitor or (
        regional_early_default if application_monitor is None else
        (lambda root, *, today=None: {"authorities_configured":9,
          "authorities_with_records":0,"authorities_failed":0,
          "records":0,"new_or_changed":0,"source_status":[],
          "status":"SKIPPED_OFFLINE_TEST"}))
    regional_detail_fn = regional_detail_monitor or (
        regional_details_default if application_monitor is None else
        (lambda root, *, today=None: {"status":"SKIPPED_OFFLINE_TEST",
          "selected_project_links":0,"project_detail_records":0,
          "new_or_changed":0,"failed_links":0,"source_status":{}}))
    regional_document_fn = regional_document_monitor or (
        regional_document_default if application_monitor is None else
        (lambda root, *, today=None: {"status":"SKIPPED_OFFLINE_TEST",
          "selected_pdf_links":0,"documents_with_text":0,
          "new_or_changed":0,"failed_documents":0}))
    ggh_york_gis_fn = ggh_york_gis_monitor or (
        ggh_york_gis_default if application_monitor is None else
        (lambda root, *, today=None: {"cities_configured":2,
         "cities_with_application_ids":0,"application_id_rows":0,
         "new_or_changed":0,"source_status":[],
         "status":"SKIPPED_OFFLINE_TEST"}))
    application_monitor = application_monitor or applications_default
    gis_monitor = gis_monitor or gis_default
    other_gis_monitor = other_gis_monitor or other_gis_default
    project_ai = project_ai or project_default
    buyer_ai = buyer_ai or buyer_default
    procurement = procurement or procurement_default
    buyer_batch = buyer_batch or batch_default
    graph = graph or graph_default
    api_key_check = api_key_check or _paid_key_exists
    has_paid_key = bool(api_key_check()) if allow_paid else False
    log = []
    state = {
        "mode":"AUTOMATIC_DAILY_MEETING_DOCUMENT_PROJECT_BUYER_RESEARCH",
        "date_local":today.isoformat(),
        "started_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "deepseek_shared_ceiling_usd":DEEPSEEK_DAILY_LIMIT_USD,
        "deepseek_document_project_buyer_stages_authorized":has_paid_key,
        "additional_paid_research_permitted":allow_paid,
        "manual_purchaser_and_supplier_verification_required":True,
        "official_meeting_dates_verified":False,
        "automated_sales_outreach":False,
        "stages":log,
    }

    def step(name, function, *, required=False):
        try:
            result = function()
            log.append({"stage":name,"status":"SUCCESS","details":result})
            return result
        except Exception as error:
            log.append({"stage":name,"status":"FAILED",
                        "error":type(error).__name__+": "+str(error)[:200],
                        "required":required})
            return {}

    meeting_results={}
    for city in municipal_official:
        meeting_results[city]=step("meeting_"+city.lower(),
            lambda city=city:meeting_pipeline(city,review/"MEETINGS"/city,
                                              include_procurement=False))
    # The index link is not evidence of a new project, nor a posting date.
    # Keep separate first-observed URL ledger; never reissue unchanged URLs
    # as new municipal discoveries on every daily report.
    meeting_seen=_json(root/MEETING_LINK_LEDGER)
    new_agenda_links=[]
    for city,stage in meeting_results.items():
        manifest=stage.get("meeting_index") if isinstance(stage,dict) else ""
        record=_json(manifest) if manifest else {}
        for item in record.get("agenda_candidates",[]):
            if not isinstance(item,dict):continue
            url=item.get("url","")
            if not _url(url) or url in meeting_seen:continue
            seen_at=dt.datetime.now(dt.timezone.utc).isoformat()
            meeting_seen[url]={"city":city,"first_seen_utc":seen_at}
            new_agenda_links.append({"city":city,"url":url,
                                     "title":item.get("title",""),
                                     "first_seen_utc":seen_at})
    temp=root/(MEETING_LINK_LEDGER+".tmp")
    temp.write_text(json.dumps(meeting_seen,indent=2),encoding="utf-8")
    temp.replace(root/MEETING_LINK_LEDGER)

    early_apps=step("sixteen_city_early_planning_applications",
        lambda:application_monitor(root,today=today))
    gis=step("toronto_brampton_official_structured_application_layers",
        lambda:gis_monitor(root,today=today))
    other_gis=step("hamilton_kitchener_official_gis_applications",
        lambda:other_gis_monitor(root,today=today))
    municipal=step("source_aware_municipal_project_feed",
        lambda:municipal_fn(root,today=today))
    toronto_csv=step("toronto_official_ckan_development_applications",
        lambda:toronto_csv_fn(root,today=today))
    guelph_gis=step("guelph_official_active_development_gis",
        lambda:guelph_gis_fn(root,today=today))
    burlington_gis=step("burlington_official_development_project_gis",
        lambda:burlington_gis_fn(root,today=today))
    burlington_pdf=step("burlington_official_quarterly_planning_statistics",
        lambda:burlington_pdf_fn(root,today=today))
    ggh_expansion=step("ggh_early_planning_twelve_city_pilot",
        lambda:ggh_expansion_fn(root,today=today),required=False)
    state["ggh_early_planning_expansion"]={k:ggh_expansion.get(k) for k in
        ("cities_configured","cities_with_application_ids","application_id_rows",
         "new_or_changed","source_status","warning")}
    ggh_york_gis=step("ggh_richmond_hill_newmarket_official_gis",
        lambda:ggh_york_gis_fn(root,today=today),required=False)
    state["ggh_york_official_gis"]={k:ggh_york_gis.get(k) for k in
        ("cities_configured","cities_with_application_ids","application_id_rows",
         "new_or_changed","source_status","warning")}
    ggh_source_access=step("ggh_blocked_official_source_access_recovery",
        lambda:ggh_source_access_default(root,today=today),required=False)
    state["ggh_source_access_recovery"]={k:ggh_source_access.get(k) for k in
        ("municipalities","ready_to_send_requests","emails_sent",
         "automated_access_granted_by_municipality","request_csv",
         "request_markdown","warning")}
    regional_early=step("regional_early_intelligence_nine_authorities",
        lambda:regional_early_fn(root,today=today),required=False)
    state["regional_early_intelligence"]={k:regional_early.get(k) for k in
        ("authorities_configured","authorities_with_records","authorities_failed",
         "records","new_or_changed","source_status","warning")}
    regional_details=step("regional_project_detail_evidence_three_authority_pilot",
        lambda:regional_detail_fn(root,today=today),required=False)
    state["regional_project_details"]={k:regional_details.get(k) for k in
        ("status","authorities","selected_project_links","project_detail_records",
         "new_or_changed","failed_links","source_status","warning")}
    regional_documents=step("regional_official_pdf_project_evidence_three_authority_pilot",
        lambda:regional_document_fn(root,today=today),required=False)
    state["regional_document_evidence"]={k:regional_documents.get(k) for k in
        ("status","selected_pdf_links","documents_with_text","new_or_changed",
         "failed_documents","failures","warning")}
    staged_durham=step("staged_durham_four_monthly_reference_feeds",
        lambda:staged_durham_fn(root,today=today))
    official_export=step("official_download_alternative_access_audit",
        lambda:official_export_fn(root,today=today))
    state["official_download_access"]={k:official_export.get(k) for k in
        ("status","sources","access_restricted","application_records","warning")}
    state["staged_durham"]={k:staged_durham.get(k) for k in
        ("total_rows","new_or_changed_reference_records","sources","sales_lead_publication")}
    state["burlington_quarterly_official"]={k:burlington_pdf.get(k) for k in (
        "status","report_quarters","latest_period","latest_new_applications","error")}
    state["burlington_official_gis"]={k:burlington_gis.get(k) for k in (
        "status","project_only_signals","application_id_rows","new_or_changed","error")}
    state["guelph_official_gis"]={k:guelph_gis.get(k) for k in (
        "commercial_candidates","new_or_changed","source_status")}
    state["toronto_official_open_data"]={k:toronto_csv.get(k) for k in (
        "status","scanned_rows","commercial_candidates","new_or_changed","error")}
    state["municipal_feed"]={k:municipal.get(k) for k in (
        "application_id_rows","project_only_signals","new_or_changed","source_status")}
    state["other_city_official_gis"]={k:other_gis.get(k) for k in (
        "sources_configured","sources_successful","commercial_candidates",
        "new_or_changed","source_status")}
    state["official_structured_applications"]={k:gis.get(k) for k in (
        "status","sources_configured","sources_successful",
        "application_candidates","new_or_changed","source_status")}
    state["early_applications"]={k:early_apps.get(k) for k in
        ("cities_configured","indexes_fetched","indexes_failed",
         "cities_with_parsed_ids","application_candidate_rows",
         "new_or_changed_application_records","new_links","baseline_only",
         "new_or_changed_csv","warning")}

    docdir = review / "TORONTO_DOCUMENTS"
    docdir.mkdir(parents=True, exist_ok=True)
    indexes = _csv(Path(__file__).parent / "config" / "official_document_indexes.csv")
    # Policy-checked official indexes; non-Toronto sources are explicitly
    # handled as link-only monitoring until equivalent PDF retrieval is proven.
    discovered = step("official_document_discovery",
                      lambda:document_discover(indexes, docdir,
                                               max_indexes=4, max_documents=12))
    captured = step("official_pdf_capture",
                    lambda:fetch_discovered(discovered["discovered_csv"],docdir,limit=3)
                    if discovered.get("discovered_csv") else
                    {"status":"NO_DISCOVERED_DOCUMENTS","captured":0})

    agenda = step("toronto_agenda_pdfs",
        lambda:agenda_pipeline(Path(__file__).parent / "config" / "toronto_verified_meeting_seeds.csv",
                              docdir,fetch=True,max_agendas=2,max_pdfs=3))
    reports = step("toronto_verified_report_pdfs",
        lambda:verified_reports(Path(__file__).parent / "config" / "toronto_verified_report_queue.csv",
                                docdir,fetch=True,max_files=2))

    # Fifteen non-Toronto official-host meeting and early-application pages; eSCRIBE and Laserfiche
    # third-party documents require a separately verified adapter.
    other_docdir=review/"OTHER_CITY_DOCUMENTS"
    multicity=step("other_city_official_pdf_capture",
        lambda:multicity_capture(meeting_results,other_docdir))
    pdf_union = docdir / "COMBINED_PDF_FETCH_AUDIT.csv"
    union_result = step("deduplicate_pdf_evidence",
        lambda:union([docdir / "AUTOMATIC_PDF_FETCH_AUDIT.csv",
                      docdir / "TORONTO_PDF_FETCH_AUDIT.csv",
                      docdir / "VERIFIED_REPORT_FETCH_AUDIT.csv",
                      other_docdir / "MULTICITY_PDF_FETCH_AUDIT.csv"],pdf_union),
        required=True)

    markham=step("markham_circulated_application_pdf_records",
        lambda:markham_default(pdf_union,root,today=today))
    state["markham_circulation"]={k:markham.get(k) for k in (
        "source_pdfs_parsed","rows_extracted","first_run_baseline",
        "new_or_changed","pdfs_unreadable_or_invalid","warning")}
    coverage=step("measured_sixteen_city_application_coverage",
        lambda:measured_coverage_default(root,early_apps,gis,other_gis,markham,municipal,toronto_csv,guelph_gis),
        required=True)
    state["measured_city_coverage"]={k:coverage.get(k) for k in (
        "cities_configured","cities_with_extracted_application_candidates",
        "cities_without_extracted_applications","verified_citywide_complete_coverage",
        "warning")}
    assisted_csv=step("authorized_official_csv_intake_three_city",
        lambda:three_city_official_csv_default(root),required=True)
    state["assisted_official_csv"]={k:assisted_csv.get(k) for k in
        ("application_id_rows","new_or_changed","automated_source_recovered",
         "source_authenticity_verified","source_status")}
    three_city_gap=step("three_city_early_planning_application_gate",
        lambda:three_city_gate_default(root),required=True)
    state["three_city_early_planning"]={k:three_city_gap.get(k) for k in
        ("cities_targeted","cities_with_application_candidates",
         "cities_without_application_candidates","cities_verified_citywide_complete",
         "records")}
    collection_acceptance=step("canonical_collection_quality_acceptance",
        lambda:collection_acceptance_default(root),required=True)
    state["collection_acceptance"]={k:collection_acceptance.get(k) for k in (
        "total_source_rows","unique_application_files","unique_project_only_signals",
        "excluded_inactive_or_closed","new_or_changed_commercial_manual_review",
        "cities_with_application_files","cities_with_only_project_signals",
        "cities_without_any_project_signal","warning")}
    done = _json(root / DOC_LEDGER)
    selected_docs = []
    if pdf_union.is_file():
        doc_result = step("document_deepseek_review",
            lambda:_build_document_worklist(pdf_union,review,done,
                                            paid=has_paid_key,ai_processor=document_ai,
                                            ranker=document_ranker))
        if doc_result:
            selected_docs, summary, done = doc_result
            state["document_ai"] = summary
            # Persist only successfully reviewed hashes; budget-blocked and
            # failed model work remains eligible in subsequent runs.
            temp = root / (DOC_LEDGER + ".tmp")
            temp.write_text(json.dumps(done,indent=2),encoding="utf-8")
            temp.replace(root / DOC_LEDGER)

    doc_candidates=step("persistent_document_project_candidacy",
        lambda:update_doc_candidates(root,selected_docs,
            review/"DOCUMENT_AI"/"TORONTO_AI_DOCUMENT_BATCH_AUDIT.csv",
            today=today),required=True)
    state["document_project_candidates"]=doc_candidates

    fresh = _valid_new_projects(root,today)
    candidate_file = review / "FRESH_RESEARCH_CANDIDATES.csv"
    if fresh:
        _write_csv(candidate_file,fresh,list(dict.fromkeys(k for r in fresh for k in r)))
    else:
        _write_csv(candidate_file,[],("project_id","address","source_id",
                                      "source_keys","record_source_url","description"))
    state["new_source_dated_project_candidates"]=len(fresh)
    all_daily=_csv(root/PROJECT_INPUT)
    no_link=[r for r in all_daily if r.get("observation") in
        ("FIRST_OBSERVED","RECORD_CHANGED")
        and freshness_assess(r,today)["paid_freshness_eligible"]
        and not _url(r.get("record_source_url"))]
    state["project_source_link_audit"]={
        "recent_or_material_events_without_official_record_link":len(no_link),
        "not_researched_second_pass_without_direct_evidence":len(no_link),
        "source_link_policy":"No generic municipal landing URL promoted as exact project record. Initial native DeepSeek pass may research by file ID; second pass requires direct source evidence."}
    _write_csv(review/"PROJECTS_AWAITING_OFFICIAL_SOURCE_LINK.csv",no_link,
        ("project_id","city","source_id","source_keys","address","description",
         "source_record_date","record_source_url","record_source_url_basis"))
    if fresh and has_paid_key:
        project_result = step("deeper_project_deepseek",
            lambda:project_ai(candidate_file,root,review,paid=True,max_projects=2))
    else:
        project_result = {"status":"NO_ELIGIBLE_SOURCE_DATED_PROJECTS" if not fresh
                          else "MISSING_DEEPSEEK_KEY"}
    state["deeper_project_research"]=project_result

    if has_paid_key:
        state["buyer_research"] = step("buyer_roles_deepseek",
            lambda:buyer_ai(review,root,paid=True))
    else:
        state["buyer_research"]={"status":"MISSING_DEEPSEEK_KEY"}
    state["procurement"] = step("public_procurement_source_check",
        lambda:procurement(None,review,limit=10,review=review,results=root))
    state["buyer_worklist"] = step("buyer_and_supplier_triage",
        lambda:write_batch(buyer_batch(root,review,top=10),review))
    state["source_graph"] = step("evidence_linked_project_graph",
        lambda:graph(root,review))

    # Combine actual project's daily events, document leads and earlier source
    # link *observations*, without mixing up publication and observation dates.
    combined = []
    ai_by_id={r.get("project_id"):r for r in _csv(root / "GTA_RADAR_V8_INVESTIGATIONS.csv")
              if r.get("project_id") and r.get("investigated_local_date")==today.isoformat()}
    for p in _csv(root / PROJECT_INPUT):
        ident=p.get("project_id","")
        current=ai_by_id.get(ident,{})
        combined.append({
            "kind":"PROJECT","project_id":ident,
            "address":p.get("address",""),"city":p.get("city",""),
            "description":p.get("description",""),
            "source_url":p.get("record_source_url",""),
            "official_source_portal_url":p.get("official_source_portal_url",""),
            "freshness":p.get("freshness_band",""),
            "source_date":p.get("source_record_date",""),
            "date_basis":p.get("freshness_date_basis") or p.get("date_basis",""),
            "observed_at":p.get("first_seen_local",""),
            "research_status":current.get("status","NOT_RESEARCHED_THIS_RUN"),
            "organization_hint":current.get("operator") or current.get("related_company") or "",
            "public_contact_hint":current.get("contact") or current.get("related_company_contact") or "",
            "ai_next_step":"PROJECT_AND_ROLE_RESEARCH_IF_SOURCE_DATED_AND_RELEVANT",
            "verification_required":"Exact project, buyer role, current supplier/award status",
        })
    # Expose newly noticed agenda links even if they are not yet dated,
    # extracted or connected to permit identities.
    for agenda_link in new_agenda_links:
        combined.append({
            "kind":"MUNICIPAL_AGENDA_LINK_REVIEW","project_id":"",
            "city":agenda_link["city"],"address":"",
            "description":str(agenda_link["title"] or "Municipal meeting or agenda link")[:240],
            "source_url":agenda_link["url"],
            "freshness":"NEW_TO_RADAR_INDEX_NOT_VERIFIED_PUBLICATION",
            "source_date":"","date_basis":"RADAR_OBSERVED_NOT_PUBLISHER_DATE",
            "observed_at":agenda_link["first_seen_utc"],
            "research_status":"LINK_ONLY_DOCUMENT_NOT_YET_PARSED",
            "ai_next_step":"RETRIEVE_ORIGINAL_REPORT_THEN_AI_EXTRACT_IF_MATERIAL",
            "verification_required":"Verify this is a substantive new commercial project and determine posting date",
        })
    feed = _json(root / "EARLY_SIGNAL_FEED_AUDIT.json")
    for signal in feed.get("candidate_links",[])[:250]:
        if (not isinstance(signal,dict)
                or not _observed_recent(signal.get("first_seen_utc"),today)
                or not _url(signal.get("url"))
                or not COMMERCIAL.search(str(signal.get("title","")))):
            continue
        combined.append({
            "kind":"SOURCE_INDEX_LINK_REVIEW","project_id":"",
            "city":str(signal.get("feed","")),"address":"",
            "description":str(signal.get("title",""))[:240],
            "source_url":signal.get("url",""),
            "freshness":"INDEX_OBSERVED_RECENTLY_NOT_PUBLISHED_EVENT",
            "source_date":"","date_basis":"OBSERVATION_TIMESTAMP_ONLY",
            "observed_at":signal.get("first_seen_utc",""),
            "research_status":"OFFICIAL_LINK_PROJECT_IDENTITY_UNVERIFIED",
            "ai_next_step":"NO_PAID_AI_FOR_LINK_ONLY_FETCH_ORIGINAL_DOCUMENT_FIRST",
            "verification_required":"Read original agenda, establish actual project and posting date",
        })
    # Single, source-deduplicated, quality-gated application review queue.
    # The legacy raw CSVs remain available as evidence but must not inflate
    # the combined daily report with baseline, closed or project-only signals.
    for app in _csv(root/"GTA_RADAR_COLLECTION_NEW_OR_CHANGED_REVIEW.csv"):
        combined.append({
            "kind":"CANONICAL_NEW_OR_CHANGED_APPLICATION_REVIEW",
            "project_id":app.get("canonical_id",""),
            "city":app.get("city",""),
            "application_id":app.get("application_id",""),
            "address":app.get("address",""),
            "description":app.get("description",""),
            "source_url":(app.get("evidence_urls","").split("; ")[0]
                          if app.get("evidence_urls") else ""),
            "source_date":app.get("date",""),
            "date_basis":app.get("date_basis","DATE_UNVERIFIED"),
            "observed_at":app.get("first_seen_local",""),
            "freshness":"RADAR_FIRST_OBSERVED_OR_CHANGED_NOT_PUBLICATION",
            "research_status":"DEDUPLICATED_COMMERCIAL_CANDIDATE_MANUAL_VERIFICATION",
            "ai_next_step":"VERIFY_PRIMARY_EVIDENCE_BEFORE_PAID_AI",
            "verification_required":app.get("verification_required",""),
        })
    ai_reviews=_csv(review/"DOCUMENT_AI"/"TORONTO_AI_DOCUMENT_BATCH_AUDIT.csv")
    docs_by_url={r.get("source_url"):r for r in ai_reviews}
    for d in selected_docs:
        analysis=docs_by_url.get(d.get("url"),{})
        model=_json(analysis.get("result_file","")).get("model_output",{})
        if not isinstance(model,dict):
            model={}
        combined.append({
            "kind":"MUNICIPAL_DOCUMENT_REVIEW","project_id":"",
            "address":str(model.get("address") or "")[:140],
            "city":d.get("city") or "Toronto",
            "description":str(model.get("proposed_scope") or "Official municipal PDF — review new project and procurement content")[:350],
            "source_url":d.get("url",""),
            "freshness":"DOCUMENT_CAPTURED_PUBLICATION_DATE_UNKNOWN",
            "source_date":"","date_basis":"PDF_CAPTURE_DATE_NOT_PUBLICATION",
            "observed_at":today.isoformat(),
            "research_status":analysis.get("status","DOCUMENT_CAPTURED_AI_NOT_ATTEMPTED"),
            "organization_hint":str(model.get("developer") or model.get("owner") or "")[:160],
            "public_contact_hint":"",
            "ai_next_step":"EVIDENCE_BOUND_DOCUMENT_AI_THEN_PROJECT_IDENTITY_REVIEW",
            "verification_required":"Check source page, PDF page and quotes, project identity, publication date and roles",
        })
    _write_csv(root / DETAIL, combined)
    dated = root / ("GTA_RADAR_INTEGRATED_INTELLIGENCE_"+today.strftime("%Y%m%d")+".csv")
    _write_csv(dated,combined)
    esc = lambda v:html.escape(str(v or ""),quote=True)
    lines = [
        "<!doctype html><html><head><meta charset='utf-8'><title>GTA Radar integrated intelligence</title>",
        "<style>body{font:15px Segoe UI,Arial,sans-serif;max-width:1120px;margin:30px auto;padding:0 18px;color:#1c2833}article{padding:14px;border:1px solid #ddd;border-radius:9px;margin:10px 0}small{color:#4e6273}a{color:#086487}</style></head><body>",
        "<h1>GTA Radar — Integrated Daily Intelligence</h1>",
        "<p>Freshness First. Evidence Always. Permits, municipal source index links and document research in ONE review queue. "
        "Source dates are not necessarily first publication dates. AI findings and named companies are UNVERIFIED. "
        "No purchasing authority, open supplier contract, award or competitive first detection is claimed.</p>",
        "<p><a href='"+DETAIL+"'>Download combined CSV</a> · "
        "<a href='GTA_RADAR_EARLY_APPLICATION_CANDIDATES.csv'>16-city HTML application baseline</a> · "
        "<a href='GTA_RADAR_STRUCTURED_APPLICATIONS_TORONTO_BRAMPTON.csv'>Toronto/Brampton official structured application baseline</a> · "
        "<a href='GTA_RADAR_STRUCTURED_APPLICATION_SOURCE_STATUS.json'>Toronto/Brampton GIS source status</a> · "
        "<a href='GTA_RADAR_MARKHAM_CIRCULATED_APPLICATIONS.csv'>Markham dated circulation applications</a> · "
        "<a href='GTA_RADAR_CITY_COVERAGE_AUDIT.csv'>Measured coverage by city (not configured links)</a> · "
        "<a href='GTA_RADAR_GGH_EXPANSION_APPLICATIONS.csv'>GGH twelve-city expansion planning application pilot (review only)</a> · "
        "<a href='GTA_RADAR_GGH_EXPANSION_SOURCE_STATUS.json'>GGH expansion source diagnostics</a> · "
        "<a href='GTA_RADAR_GGH_OFFICIAL_GIS_APPLICATIONS.csv'>Richmond Hill and Newmarket official GIS applications</a> · "
        "<a href='GTA_RADAR_GGH_OFFICIAL_GIS_NEW_OR_CHANGED.csv'>Changed York GGH GIS applications</a> · "
        "<a href='GTA_RADAR_GGH_OFFICIAL_GIS_STATUS.json'>York GGH GIS source diagnostics</a> · "
        "<a href='GTA_RADAR_GGH_SOURCE_ACCESS_REQUESTS.md'>Official municipal source access request drafts (unsent)</a> · "
        "<a href='GTA_RADAR_GGH_SOURCE_ACCESS_REQUESTS.csv'>Official municipal source access recovery table</a> · "
        "<a href='GTA_RADAR_GGH_SOURCE_ACCESS_RECOVERY_STATUS.json'>Source access request status</a> · "
        "<a href='GTA_RADAR_REGIONAL_EARLY_RECORDS.csv'>Nine-authority regional project and policy signals (baseline only)</a> · "
        "<a href='GTA_RADAR_REGIONAL_EARLY_SOURCE_STATUS.json'>Regional source-level diagnostics</a> · "
        "<a href='GTA_RADAR_REGIONAL_PROJECT_DETAILS.csv'>Regional project detail evidence (pilot)</a> · "
        "<a href='GTA_RADAR_REGIONAL_PROJECT_DETAILS_NEW_OR_CHANGED.csv'>Regional detail changes requiring review</a> · "
        "<a href='GTA_RADAR_REGIONAL_PROJECT_DETAILS_STATUS.json'>Regional detail extraction and failures</a> · "
        "<a href='GTA_RADAR_REGIONAL_DOCUMENT_EVIDENCE.csv'>Official regional PDF evidence (pilot)</a> · "
        "<a href='GTA_RADAR_REGIONAL_DOCUMENT_EVIDENCE_NEW_OR_CHANGED.csv'>Changed regional PDF evidence</a> · "
        "<a href='GTA_RADAR_REGIONAL_DOCUMENT_EVIDENCE_STATUS.json'>Regional PDF extraction diagnostics</a> · "
        "<a href='GTA_RADAR_THREE_CITY_EARLY_PLANNING_GAPS.csv'>P0 Burlington Vaughan Kitchener application collector gaps</a> · "
        "<a href='GTA_RADAR_OFFICIAL_CSV_IMPORT_APPLICATIONS.csv'>Assisted official CSV application imports (unverified provenance)</a> · "
        "<a href='GTA_RADAR_COLLECTION_MASTER.csv'>Canonical deduplicated application inventory</a> · "
        "<a href='GTA_RADAR_COLLECTION_NEW_OR_CHANGED_REVIEW.csv'>Quality-gated new or changed applications for manual review</a> · "
        "<a href='GTA_RADAR_COLLECTION_HEALTH.csv'>16-city source and quality diagnostics</a> · "
        "<a href='GTA_RADAR_GUELPH_GIS_APPLICATIONS.csv'>Guelph official GIS applications</a> · "
        "<a href='GTA_RADAR_GUELPH_GIS_STATUS.json'>Guelph GIS diagnostics</a> · "
        "<a href='GTA_RADAR_BURLINGTON_GIS_PROJECTS.csv'>Burlington official GIS project signals (not application IDs)</a> · "
        "<a href='GTA_RADAR_BURLINGTON_QUARTERLY_ACTIVITY.csv'>Burlington planning application quarterly statistics (aggregate only)</a> · "
        "<a href='GTA_RADAR_STAGED_DURHAM_EVIDENCE.csv'>Durham official reference staging (not verified leads)</a> · "
        "<a href='GTA_RADAR_STAGED_DURHAM_STATUS.json'>Durham staged source diagnostics</a> · "
        "<a href='GTA_RADAR_OFFICIAL_DOWNLOAD_ACCESS_STATUS.json'>Mississauga and St. Catharines official export access status (not collected records)</a> · "
        "<a href='GTA_RADAR_MUNICIPAL_PROJECT_FEED.csv'>Official municipal project feed</a> · "
        "<a href='GTA_RADAR_MUNICIPAL_PROJECT_FEED_STATUS.json'>Municipal feed source diagnostics</a> · "
        "<a href='GTA_RADAR_TORONTO_OPEN_DATA_APPLICATIONS.csv'>Toronto official CKAN applications</a> · "
        "<a href='GTA_RADAR_TORONTO_OPEN_DATA_STATUS.json'>Toronto CKAN source status</a> · "
        "<a href='GTA_RADAR_ADDITIONAL_CITY_GIS_APPLICATIONS.csv'>Hamilton/Kitchener application baseline</a> · "
        "<a href='GTA_RADAR_ADDITIONAL_CITY_GIS_STATUS.json'>Hamilton/Kitchener source status</a> · "
        "<a href='GTA_RADAR_EARLY_APPLICATION_SOURCE_STATUS.json'>HTML source audit</a> · "
        "<a href='GTA_RADAR_DOCUMENT_PROJECT_CANDIDATES.csv'>AI municipal report candidates (review only)</a> · "
        "<a href='GTA_RADAR_DOCUMENT_AI_PENDING.csv'>Unprocessed PDF research backlog</a> · "
        "<a href='GTA_RADAR_DISCOVERY_RUN_STATUS.json'>Read run status / missing sources</a></p>",
    ]
    for row in combined:
        lines.extend(["<article><b>"+esc(row["kind"])+" — "+esc(row["address"] or row["description"][:90])+"</b>",
                      "<p>"+esc(row["description"])+"</p><small>"+esc(row["freshness"])+
                      " · "+esc(row["date_basis"])+
                      " · "+esc(row["research_status"])+"</small>",
                      "<p>Verification required: "+esc(row["verification_required"])+"</p>"])
        if _url(row["source_url"]):
            lines.append("<a rel='noopener noreferrer' href='"+esc(row["source_url"])+"'>Original source</a>")
        elif _url(row.get("official_source_portal_url","")):
            lines.append("<a rel='noopener noreferrer' href='"+
                         esc(row["official_source_portal_url"])+
                         "'>Official source catalogue (not an exact project record)</a>")
        lines.append("</article>")
    lines.append("</body></html>")
    (root / DASHBOARD).write_text("".join(lines),encoding="utf-8")
    failed=[x["stage"] for x in log if x["status"]=="FAILED"]
    state.update({
        "status":"PARTIAL_REVIEW_REQUIRED" if failed else "INTEGRATED_REVIEW_READY",
        "failed_stages":failed,
        "meeting_sources_attempted":list(municipal_official),
        "municipal_official_index_count":len(municipal_official),
        "municipal_agenda_links_new_to_radar":len(new_agenda_links),
        "meeting_documents_fetched_outside_toronto":multicity.get("direct_pdf_captured",0),
        "non_toronto_pdf_cities_configured":multicity.get("cities_configured",0),
        "new_pdf_document_candidates":doc_candidates.get("added_this_run",0),
        "persistent_document_project_candidates":doc_candidates.get("document_candidates_total",0),
        "other_city_document_capture":{k:multicity.get(k) for k in
            ("cities_configured","cities_attempted","successful_document_cities",
             "direct_pdf_attempted","direct_pdf_captured","audit_csv","coverage_warning")},
        "municipal_document_capture_city_status":multicity.get("city_audit",[]),
        "ai_policy":"Use no model for URL checking/structured parsing; AI for actual readable documents, ambiguous identity and source-backed projects; authorized captions only; shared budget",
        "source_indexes_checked":discovered.get("indexes_checked",0),
        "pdfs_captured_in_union":union_result.get("captured",0),
        "combined_records":len(combined),
        "permit_planning_events":sum(r["kind"]=="PROJECT" for r in combined),
        "early_applications_new_or_changed_for_review":sum(
            r["kind"]=="CANONICAL_NEW_OR_CHANGED_APPLICATION_REVIEW" for r in combined),
        "early_application_city_status":early_apps.get("city_status",[]),
        "early_application_baseline_count":early_apps.get("application_candidate_rows",0),
        "cities_with_application_candidates_measured":coverage.get(
            "cities_with_extracted_application_candidates",0),
        "cities_without_extracted_application_candidates":coverage.get(
            "cities_without_extracted_applications",16),
        "additional_hamilton_kitchener_gis_candidates":other_gis.get("commercial_candidates",0),
        "additional_hamilton_kitchener_sources_successful":other_gis.get("sources_successful",0),
        "toronto_brampton_structured_gis_candidates":gis.get("application_candidates",0),
        "toronto_brampton_structured_gis_new_or_changed":gis.get("new_or_changed",0),
        "toronto_brampton_structured_gis_status":gis.get("status","NOT_AVAILABLE"),
        "markham_circulation_pdf_application_count":markham.get("rows_extracted",0),
        "markham_circulation_new_or_changed":markham.get("new_or_changed",0),
        "early_application_index_fetch_succeeded":early_apps.get("indexes_fetched",0),
        "early_application_index_fetch_failed":early_apps.get("indexes_failed",0),
        "municipal_documents_for_review":sum(r["kind"]=="MUNICIPAL_DOCUMENT_REVIEW" for r in combined),
        "new_source_index_links_for_review":sum(r["kind"]=="SOURCE_INDEX_LINK_REVIEW" for r in combined),
        "new_municipal_agenda_links_for_review":sum(r["kind"]=="MUNICIPAL_AGENDA_LINK_REVIEW" for r in combined),
        "combined_csv":str(root / DETAIL),
        "combined_html":str(root / DASHBOARD),
        "ended_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
    })
    (root / AUDIT).write_text(json.dumps(state,indent=2,default=str),encoding="utf-8")
    return state


if __name__ == "__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--results",required=True)
    args=p.parse_args()
    print(json.dumps(integrate(args.results),indent=2,default=str))
