"""Fail-closed customer release gate for genuinely NEW, source-backed opportunities.

This is a human-reviewed, source-snapshot-backed release *separate* from the
historical/source-event ranked client INVESTIGATION shortlist. It performs no
network/AI requests, no outreach and no assertions of an open contract from a
permit or project address. Source snapshots are locally supplied evidence:
hash/quote matching is NOT independent live retrieval authentication.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

CLIENT = "GTA_RADAR_CLIENT_FRESH_NONREPEAT_TOP_10.csv"
INVESTMENT_DIR = "GTA_RADAR_INVESTMENT_DISCOVERY"
REVIEW = "GTA_RADAR_FRESH_RELEASE_REVIEWS.json"
EVIDENCE_DIR = "GTA_RADAR_FRESH_SOURCE_SNAPSHOTS"
WORKLIST = "GTA_RADAR_FRESH_EVIDENCE_WORKLIST.csv"
DECISIONS = "GTA_RADAR_FRESH_RELEASE_DECISIONS.csv"
EARLY = "GTA_RADAR_REVIEWED_FRESH_EARLY_WARNINGS.csv"
OPEN = "GTA_RADAR_REVIEWED_OPEN_PACKAGES.csv"
STATUS = "GTA_RADAR_FRESH_RELEASE_STATUS.json"
MAX_REVIEWS = 100
MAX_SNAPSHOT_BYTES = 500_000
MAX_INVESTMENT_REPORTS = 20
MAX_AGE_DAYS = 7
ROLES = {"OWNER", "DEVELOPER", "OPERATOR", "APPLICANT", "PROJECT_TEAM"}
SCOPE_KINDS = {"NEW_PROJECT", "MATERIAL_NEW_SCOPE"}
PROCUREMENT = {"UNKNOWN_CHECKED", "PRE_TENDER_DOCUMENTED",
               "OPEN_PACKAGE_DOCUMENTED", "AWARDED", "COMPLETED", "CANCELLED"}
OLD_STAGE = re.compile(r"completed|fully occupied|cancelled|withdrawn|closed", re.I)


def _day(raw):
    try:
        if isinstance(raw, dt.date):
            return raw
        value = str(raw or "")
        return dt.date.fromisoformat(value[:10]) if len(value) >= 10 else None
    except ValueError:
        return None


def _https(url):
    try:
        value = urlsplit(str(url or "").strip())
        return (value.scheme == "https" and value.hostname and
                not value.username and not value.password and
                value.port in (None, 443) and len(str(url)) <= 1500)
    except ValueError:
        return False


def _clean(text):
    return " ".join(str(text or "").split()).casefold()


def _ident(candidate):
    values = (
        candidate["record_id"], candidate["city"], candidate["address"],
        candidate["project_name"], candidate["description"], candidate["source_url"],
    )
    return hashlib.sha256(json.dumps(values, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _csv(path):
    if not path.is_file():
        return []
    if path.stat().st_size > 20_000_000 or path.is_symlink():
        raise ValueError("UNSAFE_INPUT_CSV")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _already_reported_index(root, owner):
    """Use both the run's exclusions and the persistent report history."""
    ids, sites = set(), set()
    for folder, name in (
        (root, "GTA_RADAR_CLIENT_PREVIOUSLY_REPORTED.csv"),
        (root, "GTA_RADAR_CLIENT_REPORT_HISTORY.csv"),
        (owner, "GTA_RADAR_CLIENT_REPORT_HISTORY.csv"),
    ):
        for entry in _csv(folder / name):
            project_id = str(entry.get("opportunity_id") or "").strip()
            if project_id:
                ids.add(project_id)
            city = _clean(entry.get("city"))
            address = re.sub(r"[^a-z0-9]", "", _clean(entry.get("address")))
            if city and len(address) >= 10:
                sites.add((city, address))
    return ids, sites


def _inventory(root):
    candidates = {}
    for row in _csv(root / CLIENT):
        key = str(row.get("opportunity_id") or "").strip()
        if not key or not row.get("city") or not row.get("address"):
            continue
        candidate = {
            "record_id": key, "origin": "PERMIT_APPLICATION_INVESTIGATION",
            "city": str(row["city"]), "address": str(row["address"]),
            "project_name": str(row.get("project_name") or ""),
            "description": str(row.get("nature_of_work") or ""),
            "source_url": str(row.get("source_url") or ""),
            "application_ids": str(row.get("application_ids") or ""),
            "source_event_date": str(row.get("source_event_date") or ""),
            "source_date_basis": str(row.get("source_event_date_basis") or ""),
            "existing_stage": str(row.get("stage_gate") or ""),
        }
        candidate["candidate_fingerprint"] = _ident(candidate)
        candidates[key] = candidate

    # Independently discovered projects are research prospects too. Derive
    # stable IDs from project name, city and source; NEVER pretend a company
    # announcement is a municipal project or assign a fictitious civic address.
    folder = root / INVESTMENT_DIR
    if folder.is_dir() and not folder.is_symlink():
        for path in sorted(folder.glob("INVESTMENT_*.json"))[:MAX_INVESTMENT_REPORTS]:
            if path.is_symlink() or path.stat().st_size > 2_000_000:
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            for item in data.get("discovered_projects", [])[:20]:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("project_name") or "").strip()
                city = str(item.get("city") or "").strip()
                urls = [u for u in item.get("sources_used", []) if _https(u)]
                if not (name and city and urls):
                    continue
                original = f"{city}|{name}|{urls[0]}".casefold()
                key = "ANNOUNCEMENT:" + hashlib.sha256(original.encode()).hexdigest()[:20]
                candidate = {
                    "record_id": key, "origin": "INDEPENDENT_ANNOUNCEMENT_INVESTIGATION",
                    "city": city, "address": str(item.get("location_text") or ""),
                    "project_name": name,
                    "description": str(item.get("reported_construction") or name),
                    "source_url": urls[0], "application_ids": "",
                    "source_event_date": "", "source_date_basis": "UNVERIFIED_ANNOUNCEMENT_DATE",
                    "existing_stage": "",
                }
                candidate["candidate_fingerprint"] = _ident(candidate)
                candidates.setdefault(key, candidate)
    return candidates


def _snapshot(folder, reference, today):
    """Only compare quotes with hash-checked, bounded local source snapshots."""
    name = str(reference or "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}\.json", name):
        raise ValueError("BAD_SNAPSHOT_FILE")
    path = folder / name
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise ValueError("MISSING_OR_UNSAFE_SNAPSHOT")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("INVALID_SNAPSHOT")
    url = str(data.get("url") or "")
    body = data.get("text")
    when = _day(data.get("retrieved_on"))
    if not _https(url) or not isinstance(body, str) or not (50 <= len(body) <= 350_000):
        raise ValueError("SNAPSHOT_URL_OR_TEXT_INVALID")
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if data.get("sha256") != sha:
        raise ValueError("SOURCE_SNAPSHOT_HASH_MISMATCH")
    if not when or not 0 <= (today - when).days <= 2:
        raise ValueError("SOURCE_SNAPSHOT_NOT_CURRENT")
    return data


def _support(case, key, source_dir, today, *, literal=None):
    evidence = case.get(key)
    if not isinstance(evidence, dict):
        raise ValueError(f"{key.upper()}_EVIDENCE_MISSING")
    source = _snapshot(source_dir, evidence.get("snapshot"), today)
    quote = str(evidence.get("quote") or "").strip()
    if len(quote) < 16 or len(quote) > 300 or _clean(quote) not in _clean(source["text"]):
        raise ValueError(f"{key.upper()}_QUOTE_NOT_IN_SOURCE")
    if not _https(evidence.get("url")) or evidence["url"] != source["url"]:
        raise ValueError(f"{key.upper()}_SOURCE_URL_MISMATCH")
    if literal and _clean(literal) not in _clean(source["text"]):
        raise ValueError(f"{key.upper()}_IDENTITY_NOT_IN_SOURCE")
    return source, quote


def _is_same_project_publisher_context(candidate, text):
    # Never treat an unrelated dated announcement or same-city corporate
    # webpage as evidence for this exact project.
    app_ids = [a.strip() for a in re.split(r"[;|,]", candidate.get("application_ids") or "")
               if len(a.strip()) >= 8]
    squeeze = lambda value: re.sub(r"[^a-z0-9]", "", str(value).casefold())
    content = squeeze(text)
    if any(squeeze(app) in content for app in app_ids):
        return True
    name = _clean(candidate.get("project_name"))
    address = _clean(candidate.get("address"))
    city = _clean(candidate["city"])
    if candidate["origin"] == "INDEPENDENT_ANNOUNCEMENT_INVESTIGATION":
        return bool(name and len(name) >= 7 and name in _clean(text) and city in _clean(text))
    return bool(address and len(address) >= 10 and
                (address in _clean(text) or squeeze(address) in content))


def _publication_date_quoted(quote, date):
    # Avoid interpreting model/retrieval/permit dates as publisher publication.
    formats = (date.isoformat(), f"{date:%B} {date.day}, {date.year}",
               f"{date:%b} {date.day}, {date.year}",
               f"{date.day} {date:%B} {date.year}")
    return any(_clean(token) in _clean(quote) for token in formats)


def _verify(case, candidate, source_dir, today):
    reasons = []
    def fail(reason):
        reasons.append(reason)
    if case.get("candidate_fingerprint") != candidate["candidate_fingerprint"]:
        fail("CANDIDATE_SOURCE_SNAPSHOT_CHANGED")
    if str(case.get("record_id")) != candidate["record_id"] or (
            _clean(case.get("city")) != _clean(candidate["city"])):
        fail("CANDIDATE_ID_OR_CITY_MISMATCH")
    if _clean(case.get("address")) != _clean(candidate["address"]):
        fail("PROJECT_LOCATION_MISMATCH")
    reviewed = _day(case.get("reviewed_on"))
    if not case.get("reviewer") or not reviewed or not 0 <= (today - reviewed).days <= 2:
        fail("CURRENT_HUMAN_REVIEW_REQUIRED")
    if case.get("decision") != "APPROVE_FOR_EARLY_WARNING":
        fail("NO_APPROVAL_ATTESTATION")
    date = _day((case.get("publication") or {}).get("published_on"))
    if not date or not 0 <= (today - date).days <= MAX_AGE_DAYS:
        fail("ORIGINAL_PUBLICATION_NOT_WITHIN_7_DAYS")
    if (case.get("publication") or {}).get("date_basis") not in (
            "PUBLISHER_DATED_PROJECT_ANNOUNCEMENT",
            "OFFICIAL_POSTING_DATE_ON_ORIGINAL_NOTICE"):
        fail("PUBLISHER_FIRST_PUBLICATION_BASIS_MISSING")
    try:
        pubsrc, pubquote = _support(case, "publication", source_dir, today)
        if not _is_same_project_publisher_context(candidate, pubsrc["text"]):
            fail("PUBLISHER_SOURCE_DOES_NOT_IDENTIFY_SAME_PROJECT")
        if date and not _publication_date_quoted(pubquote, date):
            fail("PUBLICATION_DATE_NOT_QUOTED_IN_PRIMARY_SOURCE")
        if case["publication"].get("is_retrieval_date"):
            fail("RETRIEVAL_DATE_NOT_PUBLICATION")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        fail("PUBLICATION_" + str(exc))
    scope_kind = case.get("scope_kind")
    if scope_kind not in SCOPE_KINDS:
        fail("NEW_PROJECT_OR_NEW_SCOPE_NOT_ESTABLISHED")
    try:
        _support(case, "scope", source_dir, today)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        fail("SCOPE_" + str(exc))
    historical = case.get("historical_review") or {}
    if (not isinstance(historical, dict) or
            not historical.get("reviewed_by") or
            _day(historical.get("reviewed_on")) != reviewed or
            len(str(historical.get("note") or "").strip()) < 30):
        fail("OLDER_PROJECT_VERSION_REVIEW_REQUIRED")
    if scope_kind == "MATERIAL_NEW_SCOPE":
        prior = historical.get("prior_scope_evidence") or {}
        if not isinstance(prior, dict) or len(str(
                historical.get("distinguishing_change") or "")) < 25:
            fail("OLD_AND_NEW_SCOPE_NOT_DISTINGUISHED")
        else:
            try:
                _support({"prior": prior}, "prior", source_dir, today)
                if _clean(prior.get("quote")) == _clean((case.get("scope") or {}).get("quote")):
                    fail("NO_DISTINCT_MATERIAL_SCOPE_CHANGE")
            except (OSError, ValueError, TypeError, KeyError) as exc:
                fail("PRIOR_SCOPE_" + str(exc))
    org = case.get("organization") or {}
    if org.get("role") not in ROLES or not org.get("name"):
        fail("PROJECT_TEAM_OR_OWNER_UNIDENTIFIED")
    else:
        try:
            _support(case, "organization", source_dir, today,
                     literal=org["name"])
        except (OSError, ValueError, TypeError, KeyError) as exc:
            fail("ORGANIZATION_" + str(exc))
    contact = case.get("contact") or {}
    if not contact.get("channel") or not contact.get("role"):
        fail("PUBLIC_BUSINESS_CONTACT_ROUTE_MISSING")
    else:
        try:
            _support(case, "contact", source_dir, today,
                     literal=contact["channel"])
        except (OSError, ValueError, TypeError, KeyError) as exc:
            fail("CONTACT_" + str(exc))
    proc = case.get("procurement") or {}
    status = proc.get("status")
    checked = _day(proc.get("checked_on"))
    if status not in PROCUREMENT or not checked or not 0 <= (today - checked).days <= 2:
        fail("CURRENT_PROCUREMENT_STAGE_CHECK_REQUIRED")
    else:
        try:
            _support(case, "procurement", source_dir, today)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            fail("PROCUREMENT_" + str(exc))
    if status in {"AWARDED", "COMPLETED", "CANCELLED"}:
        fail("PROJECT_ALREADY_AWARDED_CLOSED_OR_CANCELLED")
    if candidate["existing_stage"] and OLD_STAGE.search(candidate["existing_stage"]):
        fail("SAVED_LIFECYCLE_COMPLETED_OR_CLOSED")
    # Procurement UNKNOWN is permitted for an explicitly labeled early
    # warning, not for a buying or unawarded-package claim.
    open_documented = False
    if status == "OPEN_PACKAGE_DOCUMENTED":
        closing = _day(proc.get("closing_on"))
        try:
            document, _ = _support(case, "procurement", source_dir, today)
            text = _clean(document["text"])
            package_id = str(proc.get("package_id") or "")
            purchaser = str(proc.get("purchaser") or "")
            dated = closing and _publication_date_quoted(document["text"], closing)
            contains_status = any(token in text for token in (
                "open tender", "open request for proposals", "rfq open", "bid closes"))
            open_documented = bool(package_id and purchaser and dated and
                _clean(package_id) in text and _clean(purchaser) in text and
                contains_status and closing >= today and reviewed == today)
        except (OSError, ValueError, TypeError, KeyError):
            open_documented = False
        if not open_documented:
            fail("OPEN_PACKAGE_NOT_SUPPORTED_BY_LIVE_DATED_SOURCE_TEXT")
    return reasons, open_documented


def _write(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for record in rows:
            clean = {k: str(record.get(k) or "") for k in fields}
            # Formulas must not execute when exported CSV is opened in Excel.
            writer.writerow({k: "'" + v if v.lstrip().startswith(
                ("=", "+", "-", "@", "\t", "\r")) else v for k, v in clean.items()})


def run(results, *, workspace=None, today=None):
    root = Path(results)
    if not root.is_dir():
        raise FileNotFoundError("EXISTING_RESULTS_REQUIRED")
    today = _day(today) or dt.date.today()
    owner = Path(workspace) if workspace is not None else root
    inventory = _inventory(root)
    reported_ids, reported_sites = _already_reported_index(root, owner)
    reviews_path = owner / REVIEW
    source_dir = owner / EVIDENCE_DIR
    raw = json.loads(reviews_path.read_text(encoding="utf-8")) if reviews_path.is_file() else {}
    if not isinstance(raw, dict):
        raise ValueError("RELEASE_REVIEW_MANIFEST_MUST_BE_OBJECT")
    cases = raw.get("cases", [])
    if not isinstance(cases, list) or len(cases) > MAX_REVIEWS:
        raise ValueError("INVALID_CASE_LIST")
    cases_by_id = {}
    for entry in cases:
        if not isinstance(entry, dict):
            raise ValueError("INVALID_REVIEW_CASE")
        identity = entry.get("record_id")
        if identity in cases_by_id or not isinstance(identity, str):
            raise ValueError("DUPLICATE_OR_MISSING_REVIEW_CASE_ID")
        cases_by_id[identity] = entry
    outcomes = []
    early = []
    open_cases = []
    counts = Counter()
    for key, candidate in inventory.items():
        review = cases_by_id.get(key)
        if review is None:
            reasons = ["NO_PROJECT_SPECIFIC_SOURCE_EVIDENCE_AND_HUMAN_REVIEW"]
            open_documented = False
        else:
            reasons, open_documented = _verify(review, candidate, source_dir, today)
        site = (_clean(candidate["city"]), re.sub(r"[^a-z0-9]", "",
                                      _clean(candidate["address"])))
        if key in reported_ids or site in reported_sites:
            reasons.append("PROJECT_PREVIOUSLY_REPORTED_TO_CLIENT")
        if reasons:
            counts.update(reasons)
        else:
            status = str(review["procurement"]["status"])
            early.append({
                "record_id": key, "origin": candidate["origin"],
                "city": candidate["city"], "address": candidate["address"],
                "project_description": candidate["description"],
                "publisher_posted_on": review["publication"]["published_on"],
                "publisher_url": review["publication"]["url"],
                "scope_kind": review["scope_kind"], "organization": review["organization"]["name"],
                "organization_role": review["organization"]["role"],
                "public_contact_channel": review["contact"]["channel"],
                "public_contact_role": review["contact"]["role"],
                "procurement_status": status,
                "buyer_authority_verified": False,
                "open_contract_verified_by_radar": False,
                "reviewed_by": review["reviewer"], "reviewed_on": review["reviewed_on"],
                "evidence_label": "OPERATOR_ATTESTED_SOURCE_TEXT_MATCHED_NOT_REMOTE_VERIFIED",
            })
            if open_documented:
                open_cases.append({**early[-1],
                    "package_id": review["procurement"]["package_id"],
                    "closing_on": review["procurement"]["closing_on"],
                    "purchaser_claim": review["procurement"]["purchaser"],
                    "status": "REVIEWED_OPEN_LISTING_REQUIRES_LIVE_RECHECK"})
        outcomes.append({
            "record_id": key, "origin": candidate["origin"],
            "city": candidate["city"], "address": candidate["address"],
            "candidate_fingerprint": candidate["candidate_fingerprint"],
            "source_event_date_not_publication": candidate["source_event_date"],
            "result": "REVIEWED_EARLY_WARNING" if not reasons else "HOLD_RESEARCH_ONLY",
            "rejection_reasons": "|".join(reasons),
            "procurement_stage": (review or {}).get("procurement", {}).get("status", "UNKNOWN"),
        })
    for key in cases_by_id.keys() - inventory.keys():
        counts["REVIEW_CASE_NO_CURRENT_SOURCE_CANDIDATE"] += 1
    candidate_fields = ("record_id", "origin", "city", "address", "project_name", "description",
                        "source_url", "source_event_date", "source_date_basis",
                        "application_ids", "candidate_fingerprint")
    _write(root / WORKLIST, candidate_fields, list(inventory.values()))
    _write(root / DECISIONS, tuple(outcomes[0]) if outcomes else (
        "record_id", "origin", "city", "address", "candidate_fingerprint",
        "source_event_date_not_publication", "result", "rejection_reasons",
        "procurement_stage"), outcomes)
    fields = ("record_id", "origin", "city", "address", "project_description",
              "publisher_posted_on", "publisher_url", "scope_kind",
              "organization", "organization_role", "public_contact_channel",
              "public_contact_role", "procurement_status", "buyer_authority_verified",
              "open_contract_verified_by_radar", "reviewed_by", "reviewed_on",
              "evidence_label")
    _write(root / EARLY, fields, early)
    _write(root / OPEN, (*fields, "package_id", "closing_on",
                         "purchaser_claim", "status"), open_cases)
    result = {
        "status": "OFFLINE_FRESH_RELEASE_GATE_REVIEW_ONLY",
        "date": today.isoformat(), "freshness_limit_days": MAX_AGE_DAYS,
        "candidates_considered": len(inventory),
        "case_reviews_submitted": len(cases_by_id),
        "reviewed_source_matched_early_warnings": len(early),
        "reviewed_open_listings_pending_live_recheck": len(open_cases),
        "independently_live_verified_open_supplier_contracts": 0,
        "independently_live_verified_purchasing_buyers": 0,
        "held_research_candidates": len(inventory) - len(early),
        "hold_reasons": dict(counts),
        "new_network_calls": 0, "new_ai_calls": 0,
        "release_policy": "NO_TOP10_PADDING; primary publisher date within seven days; "
                          "new project or materially new scope; named organization and "
                          "source-matched public contact; procurement checked. "
                          "Historical version checked by a human. Evidence matched "
                          "to SHA-checked local source snapshots; original live "
                          "authenticity still requires reviewer verification.",
        "warnings": [
            "A permit date, crawl date, AI text, same-address source or corporate "
            "contact does not establish a new project or open buying opportunity.",
            "Operator attestations/source snapshots are not independently "
            "authenticated live web responses. Do not advertise live open bids "
            "or purchasing authority based on this offline gate alone.",
        ],
        "outputs": [WORKLIST, DECISIONS, EARLY, OPEN, STATUS],
    }
    (root / STATUS).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    parser.add_argument("--workspace", help="Persistent folder for owner source reviews")
    args = parser.parse_args()
    print(json.dumps(run(args.results, workspace=args.workspace), indent=2))


if __name__ == "__main__":
    main()
