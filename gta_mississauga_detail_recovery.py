"""Policy-safe Mississauga planning application detail-page intelligence.

The current 30 official HTML index records contain project links but not the
publisher's page dates, applicant names or city-planner contacts. Inspect only
those same-host linked pages, respecting existing robots/DNS/redirect policy.
Page Posted/Updated dates are NOT first construction disclosure/filing dates,
and a named municipal planner is not the construction purchasing buyer.

First successful detail collection is a baseline, never a new client lead.
Individual page errors preserve previous verified observations.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, NavigableString
from gta_early_applications import _fetch

INDEX = "GTA_RADAR_EARLY_APPLICATION_CANDIDATES.csv"
OUTPUT = "GTA_RADAR_MISSISSAUGA_DETAIL_APPLICATIONS.csv"
CHANGES = "GTA_RADAR_MISSISSAUGA_DETAIL_CHANGED_REVIEW.csv"
STATUS = "GTA_RADAR_MISSISSAUGA_DETAIL_STATUS.json"
LEDGER = "GTA_RADAR_MISSISSAUGA_DETAIL_LEDGER.json"
PREFIX = "/services-and-programs/planning-and-development/development-applications/active-development-applications/"
MAX_PAGES = 35
COLUMNS = (
    "project_id", "city", "application_id", "address", "project_title",
    "description", "current_status", "applicant_name_source_claim",
    "city_planner_name", "city_planner_email",
    "source_record_date", "source_record_date_basis",
    "publisher_page_posted_date", "publisher_page_updated_date",
    "publisher_date_basis", "source_url", "record_source_url",
    "record_source_url_basis", "source_document_titles", "document_link_count",
    "first_seen_detail_local", "observation", "changed_fields",
    "buyer_verified", "public_contact_is_project_buyer",
    "publisher_first_construction_disclosure_verified", "commercial_fit",
    "verification_required",
)
POSTED = re.compile(r"\bPosted\s*:\s*([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})", re.I)
UPDATED = re.compile(r"\bUpdated\s*:\s*([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})", re.I)
PLANNER = re.compile(
    r"City\s+Planner\s+([A-Za-z][A-Za-z .'\-]{2,90}?)\s+at\s+"
    r"([A-Za-z0-9_.+\-]+@mississauga\.ca)\b", re.I)
STAGES = ("Received", "Under review", "Public meeting", "Approved", "Appealed")


def _clean(value):
    return " ".join(str(value or "").split())


def _date(text):
    try:
        return dt.datetime.strptime(_clean(text), "%B %d, %Y").date().isoformat()
    except ValueError:
        return ""


def _normal_id(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _safe_link(url):
    try:
        parsed = urlsplit(str(url or ""))
        return (
            parsed.scheme == "https"
            and parsed.hostname == "www.mississauga.ca"
            and parsed.port in (None, 443)
            and parsed.username is None and parsed.password is None
            and not parsed.query and not parsed.fragment
            and parsed.path.startswith(PREFIX)
            and parsed.path.rstrip("/") != PREFIX.rstrip("/")
        )
    except ValueError:
        return False


def _read(path):
    if not path.is_file():
        return []
    if path.is_symlink() or path.stat().st_size > 8_000_000:
        raise ValueError("UNSAFE_MISSISSAUGA_INDEX_FILE")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write(path, records):
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in records:
            # Do not allow formula-prefixed external source text to execute in Excel.
            writer.writerow({key: ("'" + value if value.lstrip().startswith(
                ("=", "+", "-", "@", "\t", "\r")) else value)
                for key in COLUMNS
                for value in [str(row.get(key, "")) if row.get(key) is not None else ""]})


def _candidate_project(row):
    return (
        row.get("city") == "Mississauga"
        and bool(row.get("project_id") and row.get("application_id"))
        and _safe_link(row.get("record_source_url"))
        and _normal_id(row.get("application_id")) != ""
    )


def _applicant(h1):
    # The City's rendered application card puts status, then applicant,
    # immediately before the single project H1. Keep this heuristic bounded
    # and never turn the string into a legally verified buyer.
    seen = []
    for node in h1.previous_elements:
        if isinstance(node, NavigableString):
            value = _clean(node)
            if value and value not in seen:
                seen.append(value)
        if len(seen) >= 7:
            break
    for value in seen:
        if value in STAGES or len(value) > 110:
            continue
        if value.lower().startswith(("skip to", "menu", "back", "search")):
            continue
        if (re.search(r"\b(?:inc\.?|corp\.?|corporation|ltd\.?|limited|"
                      r"developments?|holdings?|properties|companies)\b", value, re.I)
                and len(value) >= 7):
            return value[:120]
    return ""


def parse_detail(html, source_row, *, today=None):
    day = today or dt.date.today()
    if not isinstance(html, str) or len(html) > 2_000_000:
        raise ValueError("DETAIL_BODY_INVALID_OR_TOO_LARGE")
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "nav", "footer", "header"]):
        node.decompose()
    h1 = soup.find("h1")
    if not h1:
        raise ValueError("OFFICIAL_DETAIL_H1_MISSING")
    title = _clean(h1.get_text(" ", strip=True))
    if _normal_id(source_row["application_id"]) not in _normal_id(title):
        raise ValueError("DETAIL_APPLICATION_ID_NOT_IN_TITLE")
    # Keep the actual application body separate from the site footer.
    body = soup.find("main") or soup
    text = _clean(body.get_text(" ", strip=True))
    match = POSTED.search(text)
    updated = UPDATED.search(text)
    posted_date = _date(match.group(1)) if match else ""
    updated_date = _date(updated.group(1)) if updated else ""
    for date in (posted_date, updated_date):
        if date and dt.date.fromisoformat(date) > day:
            raise ValueError("FUTURE_DETAIL_PAGE_DATE")
    # Prefer the first project-description paragraph after the project H1,
    # not a generic city navigation heading or the document-list labels.
    scope = ""
    for node in h1.find_all_next(["p", "div"], limit=14):
        content = _clean(node.get_text(" ", strip=True))
        if node.name == "div" and node.find(["div", "p"]):
            continue
        if 25 <= len(content) <= 1400 and not content.lower().startswith((
                "posted:", "updated:", "on this page", "for more information")):
            scope = content
            break
    scope = scope or _clean(source_row.get("description"))[:800]
    page_context = _clean(text[text.find(title) + len(title):]) if title in text else text
    planner = PLANNER.search(text)
    status_text = _clean(source_row.get("description", ""))
    stage = next((word for word in STAGES if word.lower() in status_text[:65].lower()), "")
    doc_titles = []
    header = body.find(string=re.compile(r"^\s*Project documents\s*$", re.I))
    if header:
        section = header.parent
        for link in section.find_all_next("a", href=True, limit=140):
            label = _clean(link.get_text(" ", strip=True))
            if label.lower() in ("contact", "view all applications", "ward councillor"):
                break
            if any(x in label.casefold() for x in ("report", "site plan",
                    "notice", "drawings", "survey", "servicing", "landscape",
                    "submission", "study", "letter", "assessment", "impact")):
                if label and label not in doc_titles:
                    doc_titles.append(label[:130])
    # These are source-literal role claims, not buyer verification.
    return {
        "project_id": source_row["project_id"], "city": "Mississauga",
        "application_id": source_row["application_id"],
        "address": title.split(" – ")[0][:180],
        "project_title": title[:240], "description": scope[:850],
        "current_status": stage,
        "applicant_name_source_claim": _applicant(h1),
        "city_planner_name": _clean(planner.group(1)) if planner else "",
        "city_planner_email": planner.group(2) if planner else "",
        "source_record_date": "",
        "source_record_date_basis": "NOT_A_VERIFIED_APPLICATION_FILING_DATE",
        "publisher_page_posted_date": posted_date,
        "publisher_page_updated_date": updated_date,
        "publisher_date_basis": (
            "OFFICIAL_WEBPAGE_POSTED_NOT_FIRST_PROJECT_DISCLOSURE"
            if posted_date else "NO_VERIFIED_WEBPAGE_POSTED_DATE"),
        "source_url": source_row.get("source_url", ""),
        "record_source_url": source_row.get("record_source_url", ""),
        "record_source_url_basis": "EXACT_APPLICATION_ID_IN_OFFICIAL_PAGE_H1",
        "source_document_titles": " | ".join(doc_titles[:18]),
        "document_link_count": str(len(doc_titles)),
        "buyer_verified": "False",
        "public_contact_is_project_buyer": "False",
        "publisher_first_construction_disclosure_verified": "False",
        "commercial_fit": "REVIEW_ONLY",
        "verification_required": (
            "Webpage Posted/Updated is not project first disclosure; verify "
            "actual applicant identity, project lifecycle, supplier scope and "
            "purchasing authority separately."),
    }


def run(results, *, today=None, fetcher=None):
    root = Path(results)
    if not root.is_dir():
        raise FileNotFoundError("EXISTING_RESULTS_REQUIRED")
    day = today or dt.date.today()
    wanted = {}
    for candidate in _read(root / INDEX):
        if _candidate_project(candidate):
            wanted[candidate["project_id"]] = candidate
    items = sorted(wanted.values(), key=lambda x: x["project_id"])[:MAX_PAGES]
    path = root / LEDGER
    previous = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if not isinstance(previous, dict) or previous.get("schema") not in (None, 1):
        raise ValueError("INVALID_DETAIL_LEDGER")
    old = previous.get("records", {})
    if not isinstance(old, dict):
        raise ValueError("INVALID_DETAIL_LEDGER_RECORDS")
    fetched, failures, changes = [], [], []
    for candidate in items:
        url = candidate["record_source_url"]
        try:
            body = (fetcher or _fetch)(url)
            record = parse_detail(body, candidate, today=day)
            digest_columns = ("application_id", "project_title", "description",
                "applicant_name_source_claim", "city_planner_email",
                "publisher_page_posted_date", "publisher_page_updated_date",
                "current_status", "source_document_titles")
            digest = hashlib.sha256(json.dumps(
                {x: record.get(x, "") for x in digest_columns},
                sort_keys=True).encode("utf-8")).hexdigest()
            prior = old.get(candidate["project_id"])
            if prior is None:
                # A first detail-page crawl is NOT publication/discovery proof.
                state = "INITIAL_DETAIL_BASELINE"
            elif prior.get("digest") != digest:
                state = "DETAIL_PAGE_CHANGED_NOT_NEW_PUBLICATION"
            else:
                state = "UNCHANGED"
            record["observation"] = state
            record["changed_fields"] = (
                "DETAIL_PAGE_CONTENT_OR_METADATA_REVIEW" if
                state == "DETAIL_PAGE_CHANGED_NOT_NEW_PUBLICATION" else "")
            record["first_seen_detail_local"] = (
                prior.get("first_seen_detail_local") if prior else day.isoformat())
            old[candidate["project_id"]] = {
                "digest": digest, "first_seen_detail_local": record["first_seen_detail_local"],
                "last_seen_detail_local": day.isoformat(),
                "source_url": url,
            }
            fetched.append(record)
            if state == "DETAIL_PAGE_CHANGED_NOT_NEW_PUBLICATION":
                changes.append(record)
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
            failures.append({
                "project_id": candidate["project_id"], "url": url,
                "error": type(exc).__name__ + ":" + str(exc)[:170]})
    _write(root / OUTPUT, fetched)
    _write(root / CHANGES, changes)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({"schema": 1, "records": old}, indent=2),
                    encoding="utf-8")
    temp.replace(path)
    result = {
        "status": ("DETAIL_PAGES_PARTIAL_OR_HELD" if failures
                   else "OFFICIAL_DETAIL_PAGES_COLLECTED_REVIEW_ONLY" if fetched
                   else "NO_ELIGIBLE_OFFICIAL_DETAIL_LINKS"),
        "asof": day.isoformat(),
        "eligible_index_application_links": len(wanted),
        "pages_attempted": len(items),
        "pages_collected": len(fetched),
        "page_failures": failures[:MAX_PAGES],
        "pages_with_posted_date": sum(bool(x["publisher_page_posted_date"]) for x in fetched),
        "pages_with_named_applicant": sum(bool(x["applicant_name_source_claim"]) for x in fetched),
        "pages_with_planner_email": sum(bool(x["city_planner_email"]) for x in fetched),
        "changed_detail_pages_not_new_projects": len(changes),
        "publisher_first_construction_disclosures_verified": 0,
        "buyers_verified": 0, "open_supplier_packages_verified": 0,
        "paid_ai_calls": 0,
        "warning": ("Page Posted is not original construction announcement; "
                    "applicant and city planner are different from purchasing authority. "
                    "Blocked pages preserve earlier observation history."),
    }
    (root / STATUS).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.results), indent=2))


if __name__ == "__main__":
    main()
