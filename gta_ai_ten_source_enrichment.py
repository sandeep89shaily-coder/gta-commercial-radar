"""Targeted source enrichment for existing ten-capability Radar dossiers.

Model summaries are NEVER evidence: only fetched source pages can support
claims. Reuse shared V8 ledger, exact project identity and dated checkpoints.
No separate database, new crawler, automatic outreach or website scraping.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import v8_deepseek_native as native
from gta_top10_live_source_recheck import _identity

SOURCE_STAGES = (
    "buyer_contact_path", "procurement_award_status",
    "project_lifecycle_supersession", "cross_source_project_matching",
    "technical_documents_equipment", "early_investment_signals",
)
MAX_RETRIEVED = 2
LIMIT_TEXT = 1750


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    temp.replace(path)


def _query(row, stage, previous):
    address = row["address"].split(",")[0].strip()[:70]
    city = row["city"][:40]
    permit = row.get("application_id") or ""
    companies = previous.get("company_entity_relationships", {}).get("claims", [])
    names = [str(c.get("subject") or "").strip()[:90]
             for c in companies if c.get("subject") and c.get("literal_quote")]
    if stage == "buyer_contact_path":
        if not names:
            return ""
        return f'"{names[0]}" official company contact email phone'
    if stage == "procurement_award_status":
        return f'"{address}" {city} construction tender contract awarded HVAC contractor'
    if stage == "project_lifecycle_supersession":
        return f'"{address}" {city} current revised proposal replaces earlier project'
    if stage == "cross_source_project_matching":
        return f'"{permit or address}" {city} planning rezoning building permit'
    if stage == "technical_documents_equipment":
        return f'"{address}" {city} mechanical equipment planning drawing project PDF'
    if stage == "early_investment_signals":
        return f'"{address}" {city} investment plant expansion construction announcement'
    return ""


def _check_identity(stage, body, row, previous):
    # Exact application ID and matched-site text are separate evidence classes.
    identity, excerpt = _identity(body, row)
    if identity:
        return identity
    if stage == "buyer_contact_path":
        companies = previous.get("company_entity_relationships", {}).get(
            "claims", [])
        # Contact site must literally name a company that appeared in a
        # source-backed project claim; this still does NOT validate its buyer.
        for claim in companies:
            company = str(claim.get("subject") or "").strip()
            if len(company) > 4 and company.casefold() in body.casefold():
                return "SAME_NAMED_COMPANY_CONTACT_CONTEXT_NOT_BUYER"
    return ""


def enrich(root, row, stage, previous, sources, key, db, day, legacy,
           transport=None):
    if stage not in SOURCE_STAGES:
        return [], "NOT_REQUIRED"
    query = _query(row, stage, previous)
    if not query:
        return [], "REQUIRED_IDENTIFIED_COMPANY_MISSING"
    stamp = hashlib.sha256(json.dumps(
        [row["record_id"], row["city"], row["application_id"], stage,
         query, day.isoformat()], sort_keys=True).encode()).hexdigest()[:28]
    path = Path(root) / "AI_TEN_STAGE_SOURCE_CHECKPOINTS" / (
        "STAGE_" + stamp + ".json")
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return list(data.get("sources") or []), str(data.get("status") or "UNKNOWN")
        except (ValueError, OSError):
            return [], "CHECKPOINT_UNREADABLE_NO_RETRY"
    ledger_day = day.isoformat()
    status = {"status": "PENDING", "stage": stage, "sources": [],
              "searched_query": query, "issues": [],
              "source_publication_date": "UNKNOWN"}
    search_name = "ai10_source_search_" + stamp
    if not native.ledger_claim(db, ledger_day, search_name,
                               native.SEARCH_COST, legacy):
        status["status"] = "SEARCH_LEDGER_HELD_OR_ALREADY_DONE"
        _write(path, status)
        return [], status["status"]
    try:
        found = native.request("/v1/tools/search",
                               {"query": query, "count": 8,
                                "need_content": True}, key, transport)
        results = found.get("results") if isinstance(found, dict) else None
        if not isinstance(results, list):
            raise ValueError("INVALID_SEARCH_RESPONSE")
        native.ledger_finish(db, ledger_day, search_name,
                             "DONE" if results else "NONBILLABLE",
                             native.SEARCH_COST if results else 0)
    except native.DeepSeekAccountBalanceError:
        native.ledger_finish(db, ledger_day, search_name, "NONBILLABLE")
        status["status"] = "HTTP_402"
        _write(path, status)
        return [], status["status"]
    except Exception as exc:
        native.ledger_finish(db, ledger_day, search_name, "UNKNOWN")
        status["status"] = "SEARCH_UNCERTAIN_CHARGE_NO_RETRY"
        status["issues"].append(type(exc).__name__)
        _write(path, status)
        return [], status["status"]
    urls = []
    already = {x["url"] for x in sources}
    for result in results:
        if not isinstance(result, dict):
            continue
        url = str(result.get("url") or "")
        if native.safe_url(url) and url not in already and url not in urls:
            urls.append(url)
        if len(urls) >= MAX_RETRIEVED:
            break
    for index, url in enumerate(urls):
        bill = "ai10_source_fetch_" + stamp + "_" + str(index)
        if not native.ledger_claim(db, ledger_day, bill,
                                   native.FETCH_COST, legacy):
            status["issues"].append("FETCH_LEDGER_HELD")
            continue
        try:
            response = native.request(
                "/v1/tools/fetch", {"url": url}, key, transport)
            body = str(response.get("content") or "")[:15000] if (
                isinstance(response, dict)) else ""
            native.ledger_finish(db, ledger_day, bill,
                                 "DONE" if body else "NONBILLABLE",
                                 native.FETCH_COST if body else 0)
        except native.DeepSeekAccountBalanceError:
            native.ledger_finish(db, ledger_day, bill, "NONBILLABLE")
            status["issues"].append("HTTP_402")
            break
        except Exception as exc:
            native.ledger_finish(db, ledger_day, bill, "UNKNOWN")
            status["issues"].append("FETCH_" + type(exc).__name__)
            continue
        identity = _check_identity(stage, body, row, previous)
        if not identity:
            status["issues"].append("FETCHED_PAGE_NO_PROJECT_OR_COMPANY_MATCH")
            continue
        # Keep the entire bounded passage, rather than a model-written
        # summary. Quote matching is checked again at model ingestion.
        if stage == "buyer_contact_path":
            # Company-only context may be relevant even without site address.
            body = " ".join(body.split())[:LIMIT_TEXT]
        else:
            # Highlight the address vicinity to avoid unrelated site claims.
            address = row["address"].split(",")[0].strip()
            match = re.search(re.escape(address).replace(r"\ ", r"\s+"),
                              body, re.I)
            start = max(0, match.start() - 250) if match else 0
            body = " ".join(body[start:start + LIMIT_TEXT].split())
        status["sources"].append({
            "url": url, "identity": identity, "content": body,
            "source_checked_on": day.isoformat(),
            "publication_date": "UNKNOWN",
            "project_role_verified": False,
        })
    status["status"] = (
        "FETCHED_SOURCE_CONTEXT" if status["sources"]
        else "NO_INDEPENDENT_MATCHING_SOURCE")
    _write(path, status)
    return status["sources"], status["status"]
