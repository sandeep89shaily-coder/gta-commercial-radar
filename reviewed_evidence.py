"""Verification gate: only dated, official, HUMAN-confirmed evidence can make a lead sale-ready.

Nothing here reads an AI dossier. AI output (model_suggestions, 'verified' flags,
'sale_ready': true, ...) is a hint for where to look; it carries zero weight.
A project becomes SALE_READY_VERIFIED only when REVIEWED_EVIDENCE.json holds, for
every milestone field, an official source with a verbatim excerpt that a named
human reviewer confirmed, plus an affirmative, recent, supplier-status check.

Early discovery (Radar's own first-seen time vs source publication) is measured
separately and is NOT a condition of being sale-ready.

File format: see REVIEWED_EVIDENCE_TEMPLATE.json. The file is written by people;
this module only reads it and never modifies it.
"""
from __future__ import annotations
import datetime as dt
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from commercial_research_policy import directory_url

REVIEW_FILE = "REVIEWED_EVIDENCE.json"
LEDGER_FILE = "RADAR_DISCOVERY_LEDGER.sqlite"

# The eight things a buyer of a lead needs. radar_first_observed is deliberately absent.
MILESTONE_FIELDS = ("project_source", "project_identity", "scope_evidence", "buyer_org_evidence",
                    "buying_authority_evidence", "contact_route_evidence", "procurement_evidence",
                    "source_first_publication")

SOURCE_CLASSES = ("OFFICIAL_GOVERNMENT", "COMPANY_OWNED", "REGULATORY_FILING", "PRESS_RELEASE_BY_PARTY")
AUTHORITY_BASES = ("OWNER_OPERATOR_OF_SITE", "DOCUMENTED_PROCUREMENT_ROLE",
                   "PUBLISHED_TENDER_CONTACT", "SIGNING_AUTHORITY_DOCUMENTED")
CONTACT_KINDS = ("PUBLIC_BUSINESS_PHONE", "PUBLIC_BUSINESS_EMAIL", "PUBLIC_CONTACT_FORM",
                 "PUBLIC_PROCUREMENT_PAGE")
CONTACT_PURPOSES = ("GENERAL_BUSINESS", "PROCUREMENT", "SUPPLIER_ONBOARDING", "ENGINEERING_OR_FACILITIES")
PROCUREMENT_BASES = ("OPEN_TENDER_NOTICE", "OFFICIAL_STATEMENT_PACKAGES_NOT_AWARDED",
                     "PLANNING_STAGE_PRE_PROCUREMENT")
SUPPLIER_STATUSES = ("UPCOMING", "TENDERING", "AWARDED", "ALREADY_CONTRACTED", "UNKNOWN",
                     "INDEPENDENTLY_CHECKED_UNSELECTED")      # last value: legacy name for UPCOMING
QUALIFYING_SUPPLIER_STATUSES = ("UPCOMING", "TENDERING", "INDEPENDENTLY_CHECKED_UNSELECTED")
MAX_PROCUREMENT_AGE_DAYS = 60
MIN_EXCERPT_CHARS = 25
_AI_REVIEWER = re.compile(r"\b(ai|a\.i\.|llm|gpt|claude|deepseek|model|assistant|bot|automated|auto)\b", re.I)
_ADDRESS_LIKE = re.compile(r"^\s*\d+[A-Za-z]?\s+[\w .'-]+\b(st|street|ave|avenue|rd|road|dr|drive|blvd|boulevard|"
                           r"crt|court|way|lane|ln|cres|crescent|pkwy|parkway|hwy|highway|line)\b\.?", re.I)


def looks_like_street_address(text):
    """True for strings such as '318 Orenda Rd' that are a place, not an organization."""
    return bool(_ADDRESS_LIKE.match(str(text or "")))


def _date(value):
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _https(url):
    try:
        p = urlparse(str(url))
    except ValueError:
        return False
    host = p.hostname or ""
    return (p.scheme == "https" and bool(host) and "." in host and not p.username and not p.password
            and not re.fullmatch(r"[\d.]+", host) and not directory_url(url))


def _contains(excerpt, needle):
    squash = lambda s: re.sub(r"\s+", " ", str(s or "")).casefold().strip()
    return bool(squash(needle)) and squash(needle) in squash(excerpt)


def _common(entry, field, as_of, reasons):
    """Checks every milestone field must pass."""
    if not isinstance(entry, dict):
        reasons.append("no evidence supplied")
        return False
    ok = True
    if entry.get("source_class") not in SOURCE_CLASSES:
        reasons.append("source_class must be one of " + ", ".join(SOURCE_CLASSES)); ok = False
    if not _https(entry.get("official_url")):
        reasons.append("official_url must be an https page on a real site (not a directory)"); ok = False
    if len(str(entry.get("excerpt") or "").strip()) < MIN_EXCERPT_CHARS:
        reasons.append(f"excerpt must quote at least {MIN_EXCERPT_CHARS} characters from the source"); ok = False
    if entry.get("reviewer_confirmed") is not True:
        reasons.append("reviewer_confirmed must be true"); ok = False
    retrieved = _date(entry.get("retrieved_at"))
    if retrieved is None or retrieved > as_of:
        reasons.append("retrieved_at must be a real date not in the future"); ok = False
    return ok


def _field_rules(field, entry, as_of, reasons):
    ok = True
    excerpt = entry.get("excerpt", "")
    if field in ("buyer_org_evidence", "buying_authority_evidence"):
        org = str(entry.get("organization") or "").strip()
        if not org or looks_like_street_address(org):
            reasons.append("organization must be a company name, not empty or a street address"); ok = False
        elif not _contains(excerpt, org):
            reasons.append("organization name must appear in the quoted excerpt"); ok = False
    if field == "buying_authority_evidence":
        if entry.get("authority_basis") not in AUTHORITY_BASES:
            reasons.append("authority_basis must be one of " + ", ".join(AUTHORITY_BASES)); ok = False
        who = str(entry.get("person_or_role") or "").strip()
        if who and not _contains(excerpt, who):
            reasons.append("person_or_role must appear in the quoted excerpt"); ok = False
    if field == "contact_route_evidence":
        if entry.get("contact_kind") not in CONTACT_KINDS:
            reasons.append("contact_kind must be one of " + ", ".join(CONTACT_KINDS)); ok = False
        if entry.get("contact_purpose") not in CONTACT_PURPOSES:
            reasons.append("contact_purpose must be one of " + ", ".join(CONTACT_PURPOSES)
                           + " (a media contact is not a purchasing route)"); ok = False
        if not _https(entry.get("contact_url")):
            reasons.append("contact_url must be an https page"); ok = False
    if field == "procurement_evidence":
        if entry.get("procurement_basis") not in PROCUREMENT_BASES:
            reasons.append("procurement_basis must be one of " + ", ".join(PROCUREMENT_BASES)
                           + " (absence of an award notice is not evidence)"); ok = False
        checked = _date(entry.get("checked_at"))
        if checked is None or checked > as_of:
            reasons.append("checked_at must be a real date not in the future"); ok = False
        elif (as_of - checked).days > MAX_PROCUREMENT_AGE_DAYS:
            reasons.append(f"procurement check is older than {MAX_PROCUREMENT_AGE_DAYS} days; repeat it"); ok = False
    if field == "source_first_publication":
        published = _date(entry.get("published_at"))
        if published is None or published > as_of:
            reasons.append("published_at must be a real date not in the future"); ok = False
    return ok


def evaluate_review(review, *, as_of=None):
    """Evaluate ONE reviewed project. Returns a plain-English result dict."""
    as_of = as_of or dt.datetime.now(dt.timezone.utc).date()
    review = review if isinstance(review, dict) else {}
    evidence = review.get("evidence") if isinstance(review.get("evidence"), dict) else {}
    reasons, ok_fields = {}, {}
    for field in MILESTONE_FIELDS:
        problems = []
        entry = evidence.get(field)
        ok = _common(entry, field, as_of, problems)
        if ok:
            ok = _field_rules(field, entry, as_of, problems)
        ok_fields[field] = ok
        if problems:
            reasons[field] = problems
    header = []
    reviewer = str(review.get("reviewed_by") or "").strip()
    if not reviewer or _AI_REVIEWER.search(reviewer):
        header.append("reviewed_by must name a human reviewer (AI or automated names are rejected)")
    reviewed_at = _date(review.get("reviewed_at"))
    if reviewed_at is None or reviewed_at > as_of:
        header.append("reviewed_at must be a real date not in the future")
    status = str(review.get("supplier_status") or "UNKNOWN").upper()
    if status not in SUPPLIER_STATUSES:
        status = "UNKNOWN"
    if status not in QUALIFYING_SUPPLIER_STATUSES:
        header.append(f"supplier_status {status} is not an open opportunity "
                      "(must be UPCOMING or TENDERING with procurement evidence)")
    if header:
        reasons["review"] = header
    header_ok = not header
    buyer_ok = header_ok and ok_fields["buyer_org_evidence"] and ok_fields["buying_authority_evidence"]
    supplier_ok = header_ok and ok_fields["procurement_evidence"]
    missing = [f for f in MILESTONE_FIELDS if not ok_fields[f]]
    sale_ready = header_ok and not missing
    return {"project_id": review.get("project_id", ""), "address": review.get("address", ""),
            "project_name": review.get("project_name", ""), "supplier_status": status,
            "buyer_authority_verified": buyer_ok, "supplier_selection_verified": supplier_ok,
            "contact_route_verified": header_ok and ok_fields["contact_route_evidence"],
            "contact_url": str((evidence.get("contact_route_evidence") or {}).get("contact_url") or "")
                           if ok_fields["contact_route_evidence"] else "",
            "contact_kind": str((evidence.get("contact_route_evidence") or {}).get("contact_kind") or "")
                            if ok_fields["contact_route_evidence"] else "",
            "service_categories": [str(x) for x in (review.get("service_categories") or [])][:8],
            "sale_ready": sale_ready,
            "status": "SALE_READY_VERIFIED" if sale_ready else "RESEARCH_ONLY",
            "missing": missing, "reasons": reasons,
            "reviewed_by": reviewer, "reviewed_at": str(review.get("reviewed_at") or ""),
            "buyer_organization": str((evidence.get("buyer_org_evidence") or {}).get("organization") or ""),
            "source_first_publication": str((evidence.get("source_first_publication") or {}).get("published_at") or "")}


def find_review_file(folder):
    folder = Path(folder)
    for candidate in (folder / REVIEW_FILE, folder.parent / REVIEW_FILE):
        if candidate.is_file():
            return candidate
    return None


def load_reviews(path):
    """Return (reviews, problems). Never raises on a malformed file."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return [], [f"{REVIEW_FILE} could not be read: {type(exc).__name__}"]
    items = data.get("reviews") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return [], [f"{REVIEW_FILE} must contain a 'reviews' list"]
    good, problems = [], []
    for i, item in enumerate(items):
        if isinstance(item, dict) and str(item.get("project_id") or "").strip():
            good.append(item)
        else:
            problems.append(f"review #{i + 1} has no project_id and was ignored")
    return good, problems


def radar_first_seen(folder, project_id):
    """Radar's OWN first-observed timestamp from its ledger, or ''. Never human-supplied."""
    folder = Path(folder)
    for base in (folder, folder.parent):
        db = base / LEDGER_FILE
        if db.is_file():
            try:
                with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True) as con:
                    row = con.execute("SELECT first_seen_at FROM discovery WHERE project_id=?",
                                      (project_id,)).fetchone()
                return row[0] if row else ""
            except sqlite3.Error:
                return ""
    return ""


def evaluate_folder(folder, as_of=None):
    """Evaluate every reviewed project found next to the results. Pure read."""
    path = find_review_file(folder)
    if path is None:
        return {"review_file": "", "problems": [], "results": {}}
    reviews, problems = load_reviews(path)
    results = {}
    for review in reviews:                       # later entries for a project replace earlier ones
        result = evaluate_review(review, as_of=as_of)
        result["radar_first_seen_at"] = radar_first_seen(folder, result["project_id"])
        results[result["project_id"]] = result
    return {"review_file": str(path), "problems": problems, "results": results}


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="Check REVIEWED_EVIDENCE.json in plain English.")
    p.add_argument("--folder", required=True, help="Results or review folder containing the file")
    a = p.parse_args(argv)
    report = evaluate_folder(a.folder)
    if not report["review_file"]:
        print("No REVIEWED_EVIDENCE.json found. No lead can be sale-ready without it.")
        return 1
    print("Reading", report["review_file"])
    for problem in report["problems"]:
        print("  NOTE:", problem)
    for result in report["results"].values():
        print(f"\n{result['project_id']}: {result['status']}")
        for field, why in result["reasons"].items():
            for line in why:
                print(f"  - {field}: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
