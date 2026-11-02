"""Persistent review-only candidate register for municipally captured PDF reports.

AI may suggest a development, property, or company. None is promoted into a
canonical V6 permit/project record, verified buyer or actionable contract without
exact project identity and external evidence review. Preserves manual decisions.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from pathlib import Path

OUTPUT = "GTA_RADAR_DOCUMENT_PROJECT_CANDIDATES.csv"
FIELDS = (
    "document_candidate_id","city","source_page","pdf_url","pdf_sha256",
    "first_observed_date","last_observed_date","ai_review_status",
    "address_hint_unverified","project_name_hint_unverified",
    "development_type_hint_unverified","project_stage_hint_unverified",
    "scope_hint_unverified","developer_hint_unverified","owner_hint_unverified",
    "application_ids_hint_unverified","supported_page_quote_claims",
    "document_publication_verified","canonical_project_match_status",
    "verified_purchasing_authority","verified_supplier_package",
    "manual_review_decision","manual_notes",
)


def _read_csv(path):
    if not Path(path).is_file():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}


def update(results, selections, document_ai_audit, *, today=None):
    root=Path(results)
    root.mkdir(parents=True,exist_ok=True)
    today = (today or dt.date.today()).isoformat()
    target=root/OUTPUT
    retained={r["document_candidate_id"]:r for r in _read_csv(target)
              if r.get("document_candidate_id")}
    ai_by_url={r.get("source_url"):r for r in _read_csv(document_ai_audit)}
    added=0
    for source in selections:
        url=source.get("url","")
        digest=source.get("sha256","")
        if not url or len(digest)!=64:
            continue
        doc_id="PDF_REVIEW:"+hashlib.sha256((url+"|"+digest).encode()).hexdigest()[:20]
        old=retained.get(doc_id,{})
        ai=ai_by_url.get(url,{})
        state=ai.get("status","DOCUMENT_CAPTURED_NOT_YET_ANALYZED")
        model={}
        supported=[]
        if state=="AI_REVIEW_ONLY_NOT_SALE_READY":
            review=_read_json(ai.get("result_file",""))
            if isinstance(review,dict):
                model=review.get("model_output") or {}
                supported=review.get("supported_claims") or []
        if not isinstance(model,dict):model={}
        if not isinstance(supported,list):supported=[]
        applications=model.get("application_ids") or []
        if not isinstance(applications,list):applications=[]
        row={
            "document_candidate_id":doc_id,
            "city":source.get("city") or old.get("city") or "Toronto",
            "source_page":source.get("source_page") or old.get("source_page",""),
            "pdf_url":url,"pdf_sha256":digest,
            "first_observed_date":old.get("first_observed_date") or source.get("first_captured_at") or today,
            "last_observed_date":today,
            "ai_review_status":state,
            "address_hint_unverified":str(model.get("address") or "")[:240],
            "project_name_hint_unverified":str(model.get("project_name") or "")[:240],
            "development_type_hint_unverified":str(model.get("development_type") or "")[:160],
            "project_stage_hint_unverified":str(model.get("project_stage") or "")[:160],
            "scope_hint_unverified":str(model.get("proposed_scope") or "")[:800],
            "developer_hint_unverified":str(model.get("developer") or "")[:240],
            "owner_hint_unverified":str(model.get("owner") or "")[:240],
            "application_ids_hint_unverified":" | ".join(str(x)[:140] for x in applications[:8]),
            "supported_page_quote_claims":sum(
                isinstance(c,dict) and c.get("validation")=="EXACT_TEXT_PRESENT_HUMAN_REVIEW"
                for c in supported),
            "document_publication_verified":"False",
            "canonical_project_match_status":"UNVERIFIED_NO_AUTO_MERGE",
            "verified_purchasing_authority":"False",
            "verified_supplier_package":"False",
            "manual_review_decision":old.get("manual_review_decision",""),
            "manual_notes":old.get("manual_notes",""),
        }
        if not old:added+=1
        # Do not erase prior model suggestions if an API-budget-blocked retry
        # lacks a new model result; keep the previous successful evidence.
        if old and state!="AI_REVIEW_ONLY_NOT_SALE_READY":
            for field in FIELDS:
                if field.endswith("_hint_unverified") or field=="supported_page_quote_claims":
                    row[field]=old.get(field,row.get(field,""))
            if old.get("ai_review_status")=="AI_REVIEW_ONLY_NOT_SALE_READY":
                row["ai_review_status"]=old["ai_review_status"]
        retained[doc_id]=row
    output=target.with_name(target.name+".tmp")
    with output.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS)
        w.writeheader()
        w.writerows([retained[k] for k in sorted(retained)])
    output.replace(target)
    return {"document_candidates_total":len(retained),"added_this_run":added,
            "ai_analyzed_total":sum(r.get("ai_review_status")=="AI_REVIEW_ONLY_NOT_SALE_READY"
                                    for r in retained.values()),
            "canonical_project_matches_verified":0,
            "review_only_csv":str(target),
            "warning":"AI fields are unverified hints; document capture time is not publication time, and no canonical project record has been modified."}
