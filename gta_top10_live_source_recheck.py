"""Targeted current-source discovery for the preselection pool, not a scraper.

For a fresh owner-initiated paid shortlist review, check official exact-ID
ArcGIS records when accessible, discover newer municipal/company project
pages using the EXISTING DeepSeek Search tool, and Fetch candidate pages.
Search snippets are never evidence. An address-only page is project CONTEXT,
not confirmation of the original application or an active contract.

Each request uses the existing shared v5/V8 ledger, US$1 daily guard,
cross-process lock (held by caller), HTTP402 rejection and immutable dated
project checkpoint. Repeated input/date is free. No contact extraction or
client-facing verified-buyer promotion. Public documents are untrusted data.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import gta_official_arcgis_attributes as arcgis
import v8_deepseek_native as native
from gta_commercial_qualification_review import ai_fingerprint

CHECKPOINT_DIR = "AI_TOP10_LIVE_SOURCE_CHECKS"
SEARCH_LIMIT = 2
FETCH_LIMIT = 2
MAX_RESULTS = 8
MAX_CONTENT = 8000
MAX_EXCERPT = 470
OFFICIAL_SUFFIXES = (
    "toronto.ca", "brampton.ca", "mississauga.ca",
    "burlington.ca", "oakville.ca", "vaughan.ca",
    "markham.ca", "richmondhill.ca", "hamilton.ca",
    "ontario.ca", "arcgis.com",
)
PROJECT_WORDS = re.compile(
    r"\b(development|redevelopment|construction|site.plan|"
    r"planning application|building permit|approved|zoning|"
    r"warehouse|industrial|mixed.use|storeys|stories|"
    r"completed|occupancy|tenant.fit.out|facility)\b", re.I
)


def _official(url):
    try:
        host = (urlsplit(url).hostname or "").casefold()
        return any(host == d or host.endswith("." + d)
                   for d in OFFICIAL_SUFFIXES)
    except ValueError:
        return False


def _identity_pattern(identity):
    # Municipal IDs appear with varying spaces ("25 249692 ESC21CD" versus
    # "25249692ESC21CD"). Require a whole key with only whitespace/hyphens
    # inserted, not a street address or an arbitrary nearby company name.
    raw = str(identity or "")
    if any(c in raw for c in ("|",";",",","/")):
        return None
    compact = re.sub(r"[\s-]+", "", raw)
    if (len(compact) < 8 or len(compact) > 62
            or not compact.isascii() or not compact.isalnum()
            or not any(ch.isdigit() for ch in compact)):
        return None
    expression = r"(?<![A-Za-z0-9])" + r"[ \t-]*".join(
        re.escape(char) for char in compact) + r"(?![A-Za-z0-9])"
    return re.compile(expression, re.I)


def _street(address):
    value = str(address or "").split(",", 1)[0].strip().casefold()
    match = re.match(r"^(\d{1,6})(?:\s*[-/]\s*\d{1,6})?\s+(.+)$", value)
    if not match:
        return ""
    # Prefix number and road name, not the city; address alone cannot prove
    # that another permit/plan is the same project.
    return " ".join(match.group(0).split())[:90]


def _excerpt(content, match, length=MAX_EXCERPT):
    if not content or not match:
        return ""
    start = max(0, match.start() - 175)
    end = min(len(content), start + length)
    return " ".join(content[start:end].split())[:length]


def _identity(text, row):
    if not text:
        return "", ""
    pattern = _identity_pattern(row.get("application_id"))
    match = pattern.search(text) if pattern else None
    if match:
        return "EXACT_APPLICATION_ID_IN_FETCHED_TEXT", _excerpt(text, match)
    address = _street(row.get("address"))
    normal = " ".join(str(text).casefold().split())
    # Project-context-only evidence cannot certify status of this permit.
    if address and address in normal:
        match_address = re.search(re.escape(address), normal)
        if match_address and PROJECT_WORDS.search(normal[
                max(0,match_address.start()-450):match_address.end()+450]):
            return "SAME_ADDRESS_PROJECT_CONTEXT_NOT_LINKED", _excerpt(
                normal, match_address)
    return "", ""


def _queries(row):
    ident = str(row.get("application_id") or "").strip()
    address = _street(row.get("address"))
    city = re.sub(r"[^A-Za-z0-9 -]", " ", str(row.get("city") or ""))[:42]
    queries = []
    if _identity_pattern(ident):
        queries.append('"' + ident[:64] + '" ' + city +
                       " site plan building permit approval status")
    if address:
        queries.append('"' + address[:78] + '" ' + city +
                       " development planning approval construction completed 2026")
    return [q[:175] for q in dict.fromkeys(queries)][:SEARCH_LIMIT]


def _checkpoint(root, row, day):
    identity = ai_fingerprint([row])
    stamp = hashlib.sha256(
        (day.isoformat() + ":" + identity).encode("utf-8")).hexdigest()[:28]
    return root / CHECKPOINT_DIR / ("LIVE_" + stamp + ".json"), stamp


def _claim(db, day, name, amount, legacy):
    return native.ledger_claim(
        db, day.isoformat(), name, amount, legacy,
        daily_limit=native.DAILY_LIMIT)


def _fetch(url, row, key, db, day, legacy, stamp, index, transport, state):
    if not native.safe_url(url):
        return
    name = "top10live_fetch_" + stamp + "_" + str(index)
    if not _claim(db, day, name, native.FETCH_COST, legacy):
        state["issues"].append("FETCH_LEDGER_HELD_OR_PREVIOUS")
        state["complete"] = False
        return
    try:
        answer = native.request("/v1/tools/fetch", {"url": url}, key, transport)
        body = str(answer.get("content") or "")[:MAX_CONTENT] if isinstance(answer,dict) else ""
        native.ledger_finish(db, day.isoformat(), name,
                             "DONE" if body else "NONBILLABLE",
                             native.FETCH_COST if body else 0)
        state["fetch_requests"] += 1
    except native.DeepSeekAccountBalanceError:
        native.ledger_finish(db,day.isoformat(),name,"NONBILLABLE")
        raise
    except Exception as exc:
        # Provider status unknown, reservation must not be treated as $0.
        native.ledger_finish(db,day.isoformat(),name,"UNKNOWN")
        state["issues"].append("FETCH_" + type(exc).__name__)
        state["complete"] = False
        return
    identity, excerpt = _identity(body,row)
    if identity and excerpt:
        state["sources"].append({
            "url": url, "identity": identity,
            "authority": ("OFFICIAL_OR_MUNICIPAL_HOST" if _official(url)
                          else "NONOFFICIAL_PROJECT_CONTEXT"),
            "excerpt": excerpt,
            "retrieved_on": day.isoformat(),
            "date_is_fetch_day_not_publication": True,
        })


def check_one(root, row, key, db, day, legacy, *, transport=None,
              arcgis_transport=None):
    checkpoint, stamp = _checkpoint(Path(root),row,day)
    if checkpoint.exists():
        try:
            saved = json.loads(checkpoint.read_text(encoding="utf-8"))
            if (saved.get("input_fingerprint") == ai_fingerprint([row])
                    and saved.get("checked_on") == day.isoformat()
                    and saved.get("complete") is True):
                return saved, True
        except (OSError, ValueError, TypeError):
            pass
        # A prior request may have completed but its file was not committed;
        # never retry paid work against the same day/ID without reconciliation.
        return {
            "record_id":row["record_id"],"city":row["city"],
            "checked_on":day.isoformat(),"complete":False,
            "issues":["EXISTING_CHECKPOINT_INVALID_OR_INCOMPLETE_NO_RETRY"],
            "sources":[],"search_requests":0,"fetch_requests":0,
        }, True
    state = {
        "record_id":row["record_id"],"city":row["city"],
        "checked_on":day.isoformat(),
        "input_fingerprint":ai_fingerprint([row]),"complete":True,
        "sources":[],"issues":[],"search_requests":0,
        "fetch_requests":0,
        "buyer_verified":False,"procurement_available_verified":False,
    }
    url = row.get("source_url") or ""
    pattern = _identity_pattern(row.get("application_id"))
    if pattern and arcgis.is_official_query(url):
        try:
            raw = arcgis.retrieve(url, row["application_id"],
                                  transport=arcgis_transport)
            matched = pattern.search(raw or "")
            if raw and matched:
                attributes = json.loads(raw).get("attributes") or []
                fields = attributes[0] if attributes and isinstance(
                    attributes[0],dict) else {}
                status = next((str(fields[name]) for name in (
                    "STATUS_DESC","STATUS","STATUS_GROUP",
                    "LATEST_MILESTONE","APPLICATION_STATUS","PERMIT_STATUS")
                    if fields.get(name)), "")
                state["official_current_status_literal"] = status[:180]
                old = " ".join(str(row.get("source_stage") or "").casefold().split())
                new = " ".join(status.casefold().split())
                if old and new and old != new:
                    state["issues"].append(
                        "EXACT_OFFICIAL_APPLICATION_STATUS_DIFFERS_FROM_SAVED_RECORD")
                    state["official_status_change_review"] = {
                        "saved_stage":str(row.get("source_stage") or "")[:180],
                        "retrieved_stage":status[:180],
                        "not_automatic_construction_or_procurement_proof":True,
                    }
                state["sources"].append({
                    "url":url,"identity":"EXACT_OFFICIAL_ARCGIS_APPLICATION",
                    "authority":"OFFICIAL_ARCGIS_EXACT_ID",
                    "excerpt":str(raw)[:950],
                    "official_status_fields": {
                        name:str(fields[name])[:150] for name in (
                            "STATUS_DESC","STATUS","STATUS_GROUP",
                            "LATEST_MILESTONE","APPLICATION_STATUS","PERMIT_STATUS")
                        if fields.get(name)
                    },
                    "retrieved_on":day.isoformat(),
                    "date_is_fetch_day_not_publication":True,
                })
            else:
                state["issues"].append("OFFICIAL_ARCGIS_NO_EXACT_ID")
        except (OSError,ValueError,TypeError) as exc:
            state["issues"].append("OFFICIAL_ARCGIS_"+type(exc).__name__)
    query_list = _queries(row)
    possibilities = {}
    for number, query in enumerate(query_list):
        name = "top10live_search_" + stamp + "_" + str(number)
        if not _claim(db,day,name,native.SEARCH_COST,legacy):
            state["issues"].append("SEARCH_LEDGER_HELD_OR_PREVIOUS")
            state["complete"] = False
            break
        try:
            response = native.request(
                "/v1/tools/search",
                {"query":query,"count":MAX_RESULTS,"need_content":True},
                key, transport)
            found = response.get("results") if isinstance(response,dict) else None
            if not isinstance(found,list):
                raise ValueError("INVALID_SEARCH_RESPONSE")
            native.ledger_finish(db,day.isoformat(),name,
                                 "DONE" if found else "NONBILLABLE",
                                 native.SEARCH_COST if found else 0)
            state["search_requests"] += 1
        except native.DeepSeekAccountBalanceError:
            native.ledger_finish(db,day.isoformat(),name,"NONBILLABLE")
            raise
        except Exception as exc:
            native.ledger_finish(db,day.isoformat(),name,"UNKNOWN")
            state["issues"].append("SEARCH_" + type(exc).__name__)
            state["complete"] = False
            break
        for item in found[:MAX_RESULTS]:
            if not isinstance(item,dict):
                continue
            uri = str(item.get("url") or "")
            if not native.safe_url(uri) or uri in possibilities:
                continue
            # Returned Search content is only an *unverified hint* to Fetch;
            # do not treat a snippet as a current municipal approval.
            snippet = " ".join(str(item.get(k) or "")[:500] for k
                               in ("title","snippet","content"))
            identity, _ = _identity(snippet,row)
            if not identity:
                continue
            score = 3 if identity.startswith("EXACT") else 1
            if _official(uri):
                score += 2
            possibilities[uri] = score

    # First fetch project-specific hits; an unlinked same-address hit is not
    # silently joined to the old permit. Keep the original source as possible
    # fallback only if it has a project-specific URL, never a bare portal.
    ranked = sorted(possibilities,
                    key=lambda uri:(-possibilities[uri],uri))
    for index, uri in enumerate(ranked[:FETCH_LIMIT]):
        _fetch(uri,row,key,db,day,legacy,stamp,index,transport,state)
    state["source_count"] = len(state["sources"])
    state["has_exact_current_application"] = any(
        str(s.get("identity","")).startswith("EXACT") for s in state["sources"])
    state["has_unlinked_address_context"] = any(
        s.get("identity") == "SAME_ADDRESS_PROJECT_CONTEXT_NOT_LINKED"
        for s in state["sources"])
    checkpoint.parent.mkdir(parents=True,exist_ok=True)
    tmp = checkpoint.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
    tmp.replace(checkpoint)
    return state, False
