"""Connect the actual 16+8 regional project universe to paid DeepSeek review.

The old Top 10 ranked only core-city inputs before the expansion adapters
ran. This module supplies the *same existing* budget-governed, source-checked
DeepSeek reviewer with a fingerprinted 24-city pool and writes one final
combined cross-region Top 10. It never authorizes outreach, declares a
purchasing contact, or asserts that 24 municipal sources are citywide complete.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from gta_commercial_qualification_review import (
    _score, _sector, _stage, ai_fingerprint,
)

QUEUE = "GTA_RADAR_COMBINED_24_CITY_RESEARCH_QUEUE.csv"
BASE_TOP10 = "GTA_RADAR_COMBINED_24_CITY_RESEARCH_TOP10.csv"
FINAL_TOP10 = "GTA_RADAR_COMBINED_24_CITY_TOP10.csv"
FINAL_STATUS = "GTA_RADAR_COMBINED_24_CITY_AI_TOP10_STATUS.json"
MAX_REVIEW = 24
MAX_PER_CITY = 6

OUTPUT_FIELDS = (
    "rank","ai_review_status","ai_reviewed","deepseek_decision",
    "deepseek_source_quote_verified","deepseek_reason","deepseek_next_check",
    "deepseek_buyer_function_hypothesis",
    "ai_source_review_date","source_model_research_status",
    "canonical_id","city","cohort","application_id","address","project_title",
    "scope","current_status","applicant_or_agent_source_claim",
    "published_contact_name","published_contact_email","contact_role",
    "source_date","source_date_basis",
    "source_event_age_band_not_publication",
    "webpage_posted_date_not_first_disclosure","source_observation",
    "official_evidence_urls","source_lanes","original_publication_verified",
    "purchasing_contact_verified","open_supplier_contract_verified",
    "verification_required",
)


def _read(root, name):
    p = Path(root) / name
    if not p.is_file():
        return []
    if p.is_symlink() or p.stat().st_size > 45_000_000:
        raise ValueError("UNSAFE_COMBINED_AI_INPUT:" + name)
    with p.open(encoding="utf-8-sig", newline="") as fp:
        return list(csv.DictReader(fp))


def _source_url(row):
    for token in str(row.get("official_evidence_urls") or "").split("|"):
        url = token.strip()
        try:
            parsed = urlsplit(url)
            if (parsed.scheme == "https" and parsed.hostname and
                    not parsed.username and not parsed.password and
                    not parsed.fragment):
                return url[:400]
        except ValueError:
            pass
    return ""


def _model_row(row):
    # Input may not have a usable current original source (e.g. an old
    # tenant/permit signal). Never send those as project-specific evidence.
    if (row.get("record_kind") != "APPLICATION" or
            not row.get("application_id") or not row.get("address") or
            len(row.get("scope") or "") < 42 or not _source_url(row)):
        return None
    if str(row.get("scope") or "").lstrip().upper().startswith((
            "INACTIVE ", "CLOSED ", "WITHDRAWN ", "CANCELLED ", "CANCELED ")):
        return None
    ident = row["canonical_id"]
    description = row["scope"]
    result = {
        "record_id": ident, "origin": "COMBINED_24",
        "cohort": row["cohort"], "city": row["city"],
        "address": row["address"], "application_id": row["application_id"],
        "project_description": description,
        "source_url": _source_url(row), "source_date": row.get("source_date") or "",
        "date_basis": row.get("source_date_basis") or "DATE_UNVERIFIED",
        "radar_first_seen_local": row.get("first_seen_local") or "",
        "source_stage": row.get("current_status") or "",
        "sector": _sector(description),
        "lifecycle_review": _stage(row.get("current_status")),
        "source_specificity": "GENERIC_SOURCE_PORTAL",
        "freshness_points": 0,
        "ai_conflicts": [], "exact_project_roles": [],
        "was_previously_reported": False,
        "buyer_verified": False, "public_contact_verified": False,
        "open_supplier_package_verified": False,
    }
    try:
        age = (dt.date.today() - dt.date.fromisoformat(result["source_date"])).days
        if 0 <= age <= 7:
            result["freshness_points"] = 15
        elif 0 <= age <= 30:
            result["freshness_points"] = 10
        elif 0 <= age <= 90:
            result["freshness_points"] = 4
    except (ValueError, TypeError):
        pass
    return _score(result)


def _source_event_band(row, day):
    """Ranking tier for dated source events, NOT first-publication proof."""
    try:
        age = (day - dt.date.fromisoformat(row.get("source_date") or "")).days
    except (ValueError, TypeError):
        return 3
    if 0 <= age <= 30:
        return 0
    if 31 <= age <= 90:
        return 1
    if 91 <= age <= 365:
        return 2
    return 3


def candidates(results, *, limit=MAX_REVIEW, today=None, universe=24):
    """Source-backed review pool; protects both original and expansion cohorts.

    Include up to 8 eligible expansion-city projects, up to 8 core projects,
    then highest evidence-scored remaining projects. No quotas when a cohort
    has no genuinely eligible source files. Use at most 6 per city.
    """
    root = Path(results)
    queue = QUEUE if universe == 24 else "GTA_RADAR_COMBINED_28_CITY_RESEARCH_QUEUE.csv"
    if not (root/queue).is_file():
        raise ValueError("COMBINED_RESEARCH_QUEUE_MISSING")
    rows = _read(root, queue)
    if not rows:
        # A quiet day must yield an honest zero-row Top 10 rather than
        # fallback to stale legacy candidates or try a paid API call.
        return []
    day = today or dt.date.today()
    models = []
    seen = set()
    for entry in rows:
        model = _model_row(entry)
        if model is None or model["record_id"] in seen:
            continue
        seen.add(model["record_id"])
        # Avoid using the wall clock inside scoring: cached historical unit
        # replay and real current run should agree for the same run day.
        age = None
        try:
            age = (day - dt.date.fromisoformat(model["source_date"])).days
        except (ValueError, TypeError):
            pass
        model["freshness_points"] = (
            15 if age is not None and 0 <= age <= 7 else
            10 if age is not None and 0 <= age <= 30 else
            4 if age is not None and 0 <= age <= 90 else 0)
        _score(model)
        models.append(model)
    models.sort(key=lambda x: (
        _source_event_band(x, day),
        -x["internal_research_priority_score_not_sale_probability"],
        x["city"], x["record_id"]))
    selected, used, city_counts = [], set(), Counter()
    cap = min(max(0, int(limit)), MAX_REVIEW)
    for cohort in (("ADDED_4", "EXPANSION_8", "CORE_16") if universe == 28
                   else ("EXPANSION_8", "CORE_16")):
        count = 0
        for row in models:
            if count >= min(8, cap) or len(selected) >= cap:
                break
            if row["cohort"] != cohort or row["record_id"] in used:
                continue
            if city_counts[row["city"]] >= MAX_PER_CITY:
                continue
            selected.append(row); used.add(row["record_id"])
            city_counts[row["city"]] += 1; count += 1
    for row in models:
        if len(selected) >= cap:
            break
        if row["record_id"] not in used and city_counts[row["city"]] < MAX_PER_CITY:
            selected.append(row); used.add(row["record_id"])
            city_counts[row["city"]] += 1
    return selected


def finalize(results, *, state=None, pool=None, today=None, universe=24):
    root = Path(results)
    day = today or dt.date.today()
    queue = QUEUE if universe == 24 else "GTA_RADAR_COMBINED_28_CITY_RESEARCH_QUEUE.csv"
    base_top = BASE_TOP10 if universe == 24 else "GTA_RADAR_COMBINED_28_CITY_RESEARCH_TOP10.csv"
    final_top = FINAL_TOP10 if universe == 24 else "GTA_RADAR_COMBINED_28_CITY_TOP10.csv"
    final_status = FINAL_STATUS if universe == 24 else "GTA_RADAR_COMBINED_28_CITY_AI_TOP10_STATUS.json"
    inputs = _read(root, queue)
    deterministic = _read(root, base_top)
    if not (root/queue).is_file() or not (root/base_top).is_file():
        raise ValueError("COMBINED_RESEARCH_INPUT_FILES_NOT_FOUND")
    state = state or {}
    pool = pool if pool is not None else candidates(root, today=day, universe=universe)
    review = state.get("reviews") or []
    matched = (
        state.get("status") == "AI_TOP10_REVIEW_ONLY" and
        state.get("input_fingerprint") == ai_fingerprint(pool) and
        state.get("reviewed_count") == len(pool) and
        state.get("applies_to_top10") is True and
        state.get("recheck_date") == day.isoformat() and
        len(review) == len(pool) and
        len({x.get("record_id") for x in review if isinstance(x,dict)})
            == len(pool)
    )
    decisions = {x["record_id"]: x for x in review} if matched else {}
    entries = {r["canonical_id"]: r for r in inputs}
    ranking = []
    if matched:
        for model in pool:
            key = model["record_id"]
            item = entries.get(key)
            if item is None:
                matched = False
                break
            decision = decisions.get(key) or {}
            if not decision:
                matched = False
                break
            label = decision.get("decision", "NEUTRAL")
            cited = bool(decision.get("cited_live_source"))
            # An explicit negative model decision must be enforced as an
            # eligibility gate, not a small score penalty. Exclude conflicting
            # exact-project identities from Top10 until source resolution.
            # Fewer than ten defensible projects is preferable to padding.
            if label in ("DEPRIORITIZE", "CHECK_CONFLICT"):
                continue
            # PREFER without an independently fetched literal quote gains
            # no bonus. AI never verifies buyers or an open supplier package.
            delta = 5 if label == "PREFER" and cited else 0
            ranking.append((model[
                "internal_research_priority_score_not_sale_probability"]+delta,
                item, decision))
    if matched:
        ranking.sort(key=lambda x: (
            _source_event_band(x[1], day), -x[0],
            x[1]["city"], x[1]["canonical_id"]))
        selected, per_city = [], Counter()
        for _, row, decision in ranking:
            if per_city[row["city"]] >= 4:
                continue
            selected.append((row, decision))
            per_city[row["city"]] += 1
            if len(selected) == 10:
                break
        origin = "DEEPSEEK_REVIEW_ALL_CANDIDATES_APPLIED_RESEARCH_ONLY"
    else:
        # A single invalid, blocked or partial model response must never be
        # represented as an AI-approved Top 10; replace any stale artifact.
        selected = [(r,{}) for r in deterministic]
        origin = "DETERMINISTIC_FALLBACK_AI_NOT_APPLIED"
    output = []
    for i, (row, decision) in enumerate(selected, 1):
        citation = decision.get("cited_live_source") or {}
        hyp = decision.get("buyer_function_hypothesis") or {}
        item = {key: row.get(key, "") for key in OUTPUT_FIELDS}
        item.update({
            "rank": i, "ai_review_status": origin,
            "ai_reviewed": str(matched),
            "deepseek_decision": decision.get("decision","") if matched else "",
            "deepseek_source_quote_verified": str(bool(citation)) if matched else "False",
            "deepseek_reason": decision.get("reason","") if matched else "",
            "deepseek_next_check": decision.get("next_check","") if matched else "",
            "deepseek_buyer_function_hypothesis":
                hyp.get("function","") if isinstance(hyp, dict) and matched else "",
            "ai_source_review_date": day.isoformat() if matched else "",
            "source_model_research_status": state.get("status","NO_AI_RESPONSE"),
            "original_publication_verified":"False",
            "purchasing_contact_verified":"False",
            "open_supplier_contract_verified":"False",
        })
        output.append(item)
    with (root/final_top).open("w",encoding="utf-8-sig",newline="") as fp:
        writer=csv.DictWriter(fp,fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for item in output:
            writer.writerow({k:("'" + str(item[k]) if str(item[k]).lstrip().startswith(
                ("=", "+", "-", "@", "\t", "\r")) else item[k])
                for k in OUTPUT_FIELDS})
    summary = {
        "status":origin, "candidate_pool_count":len(pool),
        "candidate_pool_cities":dict(Counter(x["city"] for x in pool)),
        "candidate_pool_cohorts":dict(Counter(x["cohort"] for x in pool)),
        "model_reviewed_count": state.get("reviewed_count",0),
        "model_attempt_status":state.get("status","NO_AI_RESPONSE"),
        "model_decisions_applied": matched,
        "model_research_scope":("COMBINED_28" if universe == 28 else "COMBINED_16_PLUS_8"),
        "top10_count":len(output),
        "ai_rejected_or_held_count": (
            sum(x.get("decision") in ("DEPRIORITIZE", "CHECK_CONFLICT")
                for x in review) if matched else 0),
        "top10_unfilled_slots_due_to_evidence_gates": (
            10-len(output) if matched else 0),
        "top10_cities":dict(Counter(x["city"] for x in output)),
        "top10_cohorts":dict(Counter(x["cohort"] for x in output)),
        "buyer_contacts_verified":0,
        "new_publications_verified":0,
        "live_open_supplier_contracts_verified":0,
        "publisher_citywide_coverage_verified":0,
        "customer_releasable":False,
        "warning":"All AI decisions are internal research hypotheses. A model "
            "response, contact route or municipal filed date never proves an "
            "unawarded supplier contract, buyer identity or first publication.",
    }
    (root/final_status).write_text(json.dumps(summary,indent=2),
                                   encoding="utf-8")
    combined_status_path = root / ("GTA_RADAR_COMBINED_28_CITY_STATUS.json"
        if universe == 28 else "GTA_RADAR_COMBINED_24_CITY_STATUS.json")
    try:
        combined = json.loads(combined_status_path.read_text(encoding="utf-8"))
        if isinstance(combined, dict) and combined.get("configured_city_count")==universe:
            combined.update({
                "paid_ai_review_scope":("COMBINED_28" if universe == 28 else "COMBINED_16_PLUS_8"),
                "standard_paid_ai_top10_already_runs_in_upstream_daily_stage":False,
                "standard_paid_ai_top10_includes_expansion":matched,
                "combined_model_decisions_applied":matched,
                "combined_ai_top10_status":origin,
                "combined_final_top10_csv":final_top,
                "combined_research_top10_is_offline_not_deepseek_approved":not matched,
                "verified_buyers":0, "verified_new_publications":0,
                "verified_open_supplier_contracts":0,
            })
            combined_status_path.write_text(json.dumps(combined,indent=2),
                                           encoding="utf-8")
    except (OSError, ValueError, TypeError):
        # The separate AI status file still documents the model outcome;
        # never invent a success flag when a prior status is malformed.
        pass
    return summary
