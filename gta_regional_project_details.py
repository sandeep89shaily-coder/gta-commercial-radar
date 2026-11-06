"""Bounded official project-detail evidence for GTA Radar's existing regional feed.

Stage 1: York / Peel / Waterloo deep-link pilot. No AI, PDFs, redirect
following, inferred publication dates, or procurement claims. Runs after the
nine-authority index collector; consumes its CSV and keeps its own ledger.
"""
from __future__ import annotations
import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup
from gta_regional_early_intelligence import _fetch, _safe_url

INPUT = "GTA_RADAR_REGIONAL_EARLY_RECORDS.csv"
OUTPUT = "GTA_RADAR_REGIONAL_PROJECT_DETAILS.csv"
CHANGES = "GTA_RADAR_REGIONAL_PROJECT_DETAILS_NEW_OR_CHANGED.csv"
STATUS = "GTA_RADAR_REGIONAL_PROJECT_DETAILS_STATUS.json"
LEDGER = "GTA_RADAR_REGIONAL_PROJECT_DETAIL_SEEN.json"
PILOT = ("York", "Peel", "Waterloo")
MAX_PER_AUTHORITY = 6
MAX_PROJECTS = 18
COLUMNS = (
    "project_id", "authority", "project_title", "project_url", "index_url",
    "source_signal_id", "project_type", "stage_evidence", "budget_evidence",
    "explicit_source_date", "source_date_basis", "evidence_excerpt",
    "document_links_count", "official_pdf_urls_json", "first_seen_local", "observation",
    "source_verification", "commercial_status", "verification_required",
)
RELEVANT = re.compile(
    r"\b(?:construction|expansion|replacement|upgrade|widening|design|"
    r"reservoir|pumping|watermain|wastewater|stormwater|water treatment|"
    r"sewage|bridge|industrial|employment|rehabilitation|capital project|"
    r"environmental assessment|road improvement|new facility|infrastructure|"
    r"\bphase\s+[1-9]|\bsecond phase|\bon hold|\bremaining improvements|"
    r"\bresurfacing|\breconstruction)\b",
    re.I,
)
AMOUNT = re.compile(r"(?<!\w)(?:CAD\s*)?\$\s*\d[\d,]*(?:\.\d+)?\s*(?:million|billion|M|B)?\b", re.I)
STAGES = (
    ("CONSTRUCTION", re.compile(r"\b(?:under construction|construction began|construction started|construction is underway)\b", re.I)),
    ("PRECONSTRUCTION", re.compile(r"\b(?:detailed design|preliminary design|design phase|tender(?:ing)?|procurement)\b", re.I)),
    ("ASSESSMENT", re.compile(r"\b(?:environmental assessment|public information centre|feasibility study)\b", re.I)),
)
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WATERLOO_CDN_HOST="media-003-ca.cdn.govstack.com"
WATERLOO_CDN_PATH="/regionofwaterloo-018-ca/media/"

def _approved_document_url(url, project_url, authority):
    """Publisher-linked, fixed-host PDF only, not general cross-site scraping."""
    try:
        p=urlparse(url)
        if (p.scheme!="https" or p.port not in (None,443) or p.username or
            p.password or p.query or p.fragment or not p.path.lower().endswith(".pdf")):
            return False
        if _safe_url(url,project_url):
            return True
        return (authority=="Waterloo" and
                urlparse(project_url).hostname=="www.regionofwaterloo.ca" and
                p.hostname==WATERLOO_CDN_HOST and
                p.path.startswith(WATERLOO_CDN_PATH))
    except ValueError:
        return False

def _document_priority(label):
    name=_clean(label).lower()
    if re.search(r"construction notice|tender|construction update",name):
        return 0
    if re.search(r"project update|budget|report to council|public information|design",name):
        return 1
    if re.search(r"notice of commencement|public consultation",name):
        return 2
    if re.search(r"appendix|appendices|environmental study report",name):
        return 4
    return 3


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _evidence(html, source):
    if not isinstance(html, str) or len(html.encode("utf-8")) > 3_000_000:
        raise ValueError("INVALID_OR_OVERSIZED_DETAIL_HTML")
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup.find("article")
    if main is None:
        raise ValueError("NO_OFFICIAL_MAIN_CONTENT")
    for element in main.select("nav,footer,script,style,form"):
        element.decompose()
    heading = main.find("h1")
    title = _clean(heading.get_text(" ", strip=True)) if heading else ""
    chunks = []
    for tag in main.find_all(["p", "li", "td", "h2", "h3"]):
        # Avoid duplicate title/headings and nested container text.
        if tag.find(["p", "li", "td", "h2", "h3"]):
            continue
        value = _clean(tag.get_text(" ", strip=True))
        if 24 <= len(value) <= 800 and RELEVANT.search(value):
            chunks.append(value)
    if not chunks:
        raise ValueError("NO_PROJECT_SCOPE_EVIDENCE")
    evidence = " ".join(chunks[:6])[:1500]
    # Evidence of a project is required, not merely a keyword in a site header.
    if not RELEVANT.search(evidence):
        raise ValueError("NO_PROJECT_SCOPE_EVIDENCE")
    stage = next((label for label, pattern in STAGES if pattern.search(evidence)), "STAGE_UNVERIFIED")
    budget = ""
    for chunk in chunks[:16]:
        if AMOUNT.search(chunk) and re.search(r"\b(?:budget|cost|estimated|investment|funding|capital)\b",chunk,re.I):
            budget = chunk[:450]
            break
    # Accept machine-readable dates only when attached to page content.
    # The date is a page date, not proof of when the project was first announced.
    page_date = ""
    for tag in main.find_all("time"):
        value = str(tag.get("datetime") or "")[:10]
        if DATE.fullmatch(value):
            try:
                dt.date.fromisoformat(value)
            except ValueError:
                continue
            page_date = value
            break
    # Distinguish all referenced PDF links from the strict official-host queue.
    # PDFs hosted on unrelated cloud/CDN domains require independent authorization.
    pdf_count = 0
    accepted_pdfs = []
    source_url = source.get("source_url", "")
    authority = source.get("authority", "")
    eligible = []
    for tag in main.find_all("a", href=True):
        candidate = urljoin(source_url, str(tag["href"]).strip()) if source_url else ""
        if not candidate or not urlparse(candidate).path.lower().endswith(".pdf"):
            continue
        pdf_count += 1
        if _approved_document_url(candidate, source_url, authority):
            label = tag.get_text(" ", strip=True)
            eligible.append((_document_priority(label), candidate))
    for _, candidate in sorted(eligible, key=lambda item: item[0]):
        if candidate not in accepted_pdfs:
            accepted_pdfs.append(candidate)
        if len(accepted_pdfs) >= 8:
            break
    return {
        "project_title": title[:220] if title else source.get("project_title", "")[:220],
        "stage_evidence": stage,
        "budget_evidence": budget,
        "explicit_source_date": page_date,
        "source_date_basis": "OFFICIAL_PAGE_TIME_ELEMENT_NOT_FIRST_PUBLICATION" if page_date else "NO_VERIFIED_DATE",
        "evidence_excerpt": evidence,
        "document_links_count": pdf_count,
        "official_pdf_urls_json": json.dumps(accepted_pdfs),
    }


def _read(path):
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: ("'" + value if isinstance(value, str) and
                value.startswith(("=", "+", "-", "@")) else value)
                for key, value in row.items() if key in COLUMNS})


def _eligible(row):
    authority = row.get("authority", "")
    url = row.get("source_url", "")
    index = row.get("official_index_url", "")
    if authority not in PILOT or not url or not index or not _safe_url(url, index):
        return False
    # Do not fetch generic regional indexes as if they were project details.
    parsed, origin = urlparse(url), urlparse(index)
    if parsed.path.rstrip("/") == origin.path.rstrip("/"):
        return False
    if parsed.path.lower().endswith((".pdf", ".zip", ".doc", ".docx", ".csv", ".xlsx")):
        return False
    if not _clean(row.get("project_title")):
        return False
    return True


def run(results, *, today=None, fetcher=None, max_per_authority=MAX_PER_AUTHORITY):
    root = Path(results)
    root.mkdir(parents=True, exist_ok=True)
    day = (today or dt.date.today()).isoformat()
    previous_path = root / LEDGER
    prior = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else {"schema":1, "seen":{}}
    if prior.get("schema") != 1 or not isinstance(prior.get("seen"), dict):
        raise ValueError("UNKNOWN_REGIONAL_DETAIL_LEDGER")
    old = prior["seen"]
    updated = dict(old)
    seen_urls = set()
    selected = []
    counters = {authority:0 for authority in PILOT}
    for row in _read(root / INPUT):
        if not _eligible(row):
            continue
        authority = row["authority"]
        if counters[authority] >= min(max_per_authority, MAX_PER_AUTHORITY):
            continue
        url = row["source_url"]
        if url in seen_urls:
            continue
        counters[authority] += 1
        seen_urls.add(url)
        selected.append(row)
        if len(selected) >= MAX_PROJECTS:
            break
    records, changes, failures = [], [], []
    stats = {authority:{"selected":counters[authority],"extracted":0,"failed":0} for authority in PILOT}
    for row in selected:
        authority = row["authority"]
        url = row["source_url"]
        try:
            detail = _evidence((fetcher or _fetch)(url), row)
            pid = "REGIONAL_DETAIL:" + hashlib.sha256((authority+"|"+url).encode()).hexdigest()[:24]
            record = {
                "project_id":pid,
                "authority":authority,
                "project_url":url,
                "index_url":row["official_index_url"],
                "source_signal_id":row.get("record_id", ""),
                "project_type":row.get("signal_type", ""),
                **detail,
                "source_verification":"OFFICIAL_HOST_DETAIL_HTML_EXTRACTED",
                "commercial_status":"PROJECT_REVIEW_ONLY_NOT_VERIFIED_OPEN_CONTRACT",
                "verification_required":"Confirm exact project identity, official dates, responsible organization, current status, contract packages and buyer",
            }
            digest = hashlib.sha256(json.dumps({k:record[k] for k in
                ("project_title","stage_evidence","budget_evidence","explicit_source_date",
                 "evidence_excerpt","document_links_count","official_pdf_urls_json")},sort_keys=True).encode()).hexdigest()
            before = old.get(pid)
            baseline = not any(k.startswith("REGIONAL_DETAIL:") for k in old)
            observation = ("INITIAL_BASELINE" if baseline else "FIRST_OBSERVED" if before is None
                           else "RECORD_CHANGED" if before["digest"] != digest else "UNCHANGED")
            record.update(first_seen_local=before["first_seen_local"] if before else day,
                          observation=observation)
            records.append(record)
            if observation in ("FIRST_OBSERVED", "RECORD_CHANGED"):
                changes.append(record)
            updated[pid] = {"digest":digest,"first_seen_local":record["first_seen_local"]}
            stats[authority]["extracted"] += 1
        except Exception as error:
            stats[authority]["failed"] += 1
            failures.append({"authority":authority,"project_url":url,
                             "error":type(error).__name__+":"+str(error)[:160]})
    _write(root / OUTPUT, records)
    _write(root / CHANGES, changes)
    if updated != old:
        temp = previous_path.with_suffix(".tmp")
        temp.write_text(json.dumps({"schema":1,"seen":updated},indent=2),encoding="utf-8")
        temp.replace(previous_path)
    summary = {
        "status":"PILOT_COLLECTED" if records else "NO_VERIFIABLE_PROJECT_DETAILS",
        "authorities":list(PILOT),
        "selected_project_links":len(selected),
        "project_detail_records":len(records),
        "new_or_changed":len(changes),
        "failed_links":len(failures),
        "source_status":stats,
        "failures":failures,
        "paid_ai_calls":0,
        "verified_procurement_opportunities":0,
        "warning":"Project pages are not proof of new source publication, unawarded work or procurement. This pilot does not yet download PDFs or claim complete regional coverage.",
    }
    (root / STATUS).write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary
