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
REPORT_CATEGORIES = ("PROJECT", "SOURCE_INDEX_LINK_REVIEW", "MUNICIPAL_DOCUMENT_REVIEW")
FIELDS = ("kind", "project_id", "address", "city", "description", "source_url",
          "freshness", "source_date", "date_basis", "observed_at",
          "research_status", "organization_hint", "public_contact_hint",
          "verification_required")
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


def _build_document_worklist(union_csv, out, seen, *, paid, ai_processor):
    """Analyze changed PDF bytes at most once after a recorded successful AI result.

    Same bytes at same URL do not get paid AI again on future days. Earlier
    failed/budget-deferred documents remain eligible to retry. No false
    publication timestamp is inferred from downloading a PDF today.
    """
    source = [r for r in _csv(union_csv)
              if r.get("status") == "CAPTURED"
              and r.get("sha256") and _url(r.get("url"))
              and Path(r.get("saved_path") or "").is_file()]
    queued = [r for r in source if r["sha256"] not in seen]
    selected = queued[:2]
    to_analyze = Path(out) / "NEW_DOCUMENTS_FOR_REVIEW.csv"
    _write_csv(to_analyze, selected,
               ("url", "status", "reason", "http_status", "bytes", "sha256", "saved_path"))
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
    return selected, summary, seen


def integrate(results, *, today=None, meeting_pipeline=None, document_discover=None,
              agenda_pipeline=None, verified_reports=None, document_ai=None,
              project_ai=None, buyer_ai=None, procurement=None, buyer_batch=None,
              graph=None, api_key_check=None, allow_paid=True):
    """Run integrated bounded stages and expose individual failure provenance.

    Injectable functions make offline and Windows CI fully network/AI-free.
    """
    from RUN_MEETING_BUYER_PIPELINE import pipeline as meeting_default
    from gta_verified_source_pipeline import discover as discover_default, fetch_discovered
    from toronto_meeting_pdf_pipeline import run as agenda_default
    from toronto_verified_report_queue import run as report_default
    from toronto_ai_document_batch import process as document_default
    from gta_execute_ai_project_research import execute as project_default
    from gta_integrated_buyer_investigation import run as buyer_default
    from gta_live_procurement_evidence import execute as procurement_default
    from gta_buyer_procurement_batch import evaluate as batch_default, write as write_batch
    from gta_unified_intelligence import build as graph_default

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

    for city in ("Toronto","Brampton"):
        step("meeting_"+city.lower(),
             lambda city=city: meeting_pipeline(city, review / "MEETINGS" / city,
                                               include_procurement=False))

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

    pdf_union = docdir / "COMBINED_PDF_FETCH_AUDIT.csv"
    union_result = step("deduplicate_pdf_evidence",
        lambda:union([docdir / "AUTOMATIC_PDF_FETCH_AUDIT.csv",
                      docdir / "TORONTO_PDF_FETCH_AUDIT.csv",
                      docdir / "VERIFIED_REPORT_FETCH_AUDIT.csv"],pdf_union),
        required=True)

    done = _json(root / DOC_LEDGER)
    selected_docs = []
    if pdf_union.is_file():
        doc_result = step("document_deepseek_review",
            lambda:_build_document_worklist(pdf_union,review,done,
                                            paid=has_paid_key,ai_processor=document_ai))
        if doc_result:
            selected_docs, summary, done = doc_result
            state["document_ai"] = summary
            # Persist only successfully reviewed hashes; budget-blocked and
            # failed model work remains eligible in subsequent runs.
            temp = root / (DOC_LEDGER + ".tmp")
            temp.write_text(json.dumps(done,indent=2),encoding="utf-8")
            temp.replace(root / DOC_LEDGER)

    fresh = _valid_new_projects(root,today)
    candidate_file = review / "FRESH_RESEARCH_CANDIDATES.csv"
    if fresh:
        _write_csv(candidate_file,fresh,list(dict.fromkeys(k for r in fresh for k in r)))
    else:
        _write_csv(candidate_file,[],("project_id","address","source_id",
                                      "source_keys","record_source_url","description"))
    state["new_source_dated_project_candidates"]=len(fresh)
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
            "freshness":p.get("freshness_band",""),
            "source_date":p.get("source_record_date",""),
            "date_basis":p.get("freshness_date_basis") or p.get("date_basis",""),
            "observed_at":p.get("first_seen_local",""),
            "research_status":current.get("status","NOT_RESEARCHED_THIS_RUN"),
            "organization_hint":current.get("operator") or current.get("related_company") or "",
            "public_contact_hint":current.get("contact") or current.get("related_company_contact") or "",
            "verification_required":"Exact project, buyer role, current supplier/award status",
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
            "verification_required":"Read original agenda, establish actual project and posting date",
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
            "city":"Toronto",
            "description":str(model.get("proposed_scope") or "Official municipal PDF — review new project and procurement content")[:350],
            "source_url":d.get("url",""),
            "freshness":"DOCUMENT_CAPTURED_PUBLICATION_DATE_UNKNOWN",
            "source_date":"","date_basis":"PDF_CAPTURE_DATE_NOT_PUBLICATION",
            "observed_at":today.isoformat(),
            "research_status":analysis.get("status","DOCUMENT_CAPTURED_AI_NOT_ATTEMPTED"),
            "organization_hint":str(model.get("developer") or model.get("owner") or "")[:160],
            "public_contact_hint":"",
            "verification_required":"Check PDF page and claim quotations, project identity, publishing date and roles",
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
        lines.append("</article>")
    lines.append("</body></html>")
    (root / DASHBOARD).write_text("".join(lines),encoding="utf-8")
    failed=[x["stage"] for x in log if x["status"]=="FAILED"]
    state.update({
        "status":"PARTIAL_REVIEW_REQUIRED" if failed else "INTEGRATED_REVIEW_READY",
        "failed_stages":failed,
        "meeting_sources_attempted":["Toronto","Brampton"],
        "source_indexes_checked":discovered.get("indexes_checked",0),
        "pdfs_captured_in_union":union_result.get("captured",0),
        "combined_records":len(combined),
        "permit_planning_events":sum(r["kind"]=="PROJECT" for r in combined),
        "municipal_documents_for_review":sum(r["kind"]=="MUNICIPAL_DOCUMENT_REVIEW" for r in combined),
        "new_source_index_links_for_review":sum(r["kind"]=="SOURCE_INDEX_LINK_REVIEW" for r in combined),
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
