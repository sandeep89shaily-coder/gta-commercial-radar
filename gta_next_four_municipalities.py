"""Four additional municipal planning notice pilots, evidence-only and manual.

Ajax, Whitby, Clarington and Brantford remain OUTSIDE the verified sixteen-city
coverage denominator.  Public landing pages and observed links are not a filed
application, verified publication date, available contract, or a buyer.
Uses the existing robots/DNS/HTTPS/no-redirect HTML transport.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from gta_early_applications import _fetch, _clean

SOURCES = {
    "Ajax": "https://ajax.ca/news-notices-topic/development-planning-notices/",
    "Whitby": "https://www.whitby.ca/town-hall/council-and-committee-meetings/participation-at-public-meetings/",
    "Clarington": "https://www.clarington.net/news/",
    "Brantford": "https://buildbrantford-002-ca.govstack.com/planning-and-development-services/planning-applications-data/",
}
LEDGER = "GTA_RADAR_NEXT_FOUR_MUNICIPALITIES_SEEN.json"
STATUS = "GTA_RADAR_NEXT_FOUR_MUNICIPALITIES_STATUS.json"
ALL = "GTA_RADAR_NEXT_FOUR_MUNICIPALITIES_REVIEW.csv"
CHANGES = "GTA_RADAR_NEXT_FOUR_MUNICIPALITIES_CHANGED_REVIEW.csv"
FIELDS = ("city", "record_id", "record_kind", "application_id", "project_title",
          "description", "source_url", "official_notice_url", "first_seen_local",
          "observation", "potential_commercial", "publication_date_verified",
          "verified_buyer", "verified_open_procurement", "verification_required")

# A number in an arbitrary article or a street address is NOT an application
# number.  Accept only a file/application label immediately before an ID.
FILE_ID = re.compile(
    r"(?<![A-Za-z0-9])(?:SPA|SPC|SP|ZBA|Z|OPA|OZ|LD|PLZBLA|PLOPA|SUB|"
    r"D1[0-6])[-\s]?\d{1,8}(?:[-/]\d{1,6})?(?![A-Za-z0-9])", re.I)
LABELED = re.compile(
    r"\b(?:file(?:\s+(?:number|no\.?))?|application(?:\s+(?:number|no\.?))?)"
    r"\s*[:#-]?\s*", re.I)
NOTICE = re.compile(
    r"public.meeting.notice|notice.of.(?:application|public.meeting|complete)|"
    r"proposed.(?:development|industrial|commercial|outdoor.event)|"
    r"development.proposal|planning.application", re.I)
COMMERCIAL = re.compile(
    r"\b(?:industrial|employment|warehouse|distribution|manufactur\w*|"
    r"commercial|retail|office|data.cent(?:re|er)|hotel|restaurant|"
    r"mixed.use|factory|business.park|logistics|medical|clinic)\b", re.I)
ADDRESS = re.compile(
    r"\b\d{1,5}\s+[A-Za-z][A-Za-z0-9 .'-]{3,75}\s"
    r"(?:Road|Rd|Street|St|Drive|Dr|Avenue|Ave|Boulevard|Blvd|Lane|Way)\b",
    re.I)
LIMIT_PER_CITY = 5


def _safe(url, source):
    try:
        a, b = urlparse(url), urlparse(source)
        return (a.scheme == "https" and a.hostname == b.hostname
                and a.port in (None, 443) and not a.username
                and not a.password and not a.fragment and not a.query
                and a.path.startswith("/") and a.path != "//")
    except ValueError:
        return False


def _links(city, html, source):
    if city == "Brantford":
        # Its published mapping page is not an HTML application list.
        return []
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    links = []
    for a in main.find_all("a", href=True):
        label = _clean(a.get_text(" ", strip=True))
        href = urljoin(source, a["href"].strip())
        if not _safe(href, source) or href == source or href in links:
            continue
        path = urlparse(href).path.lower()
        if path.endswith((".pdf", ".doc", ".docx", ".zip", ".csv")):
            continue
        if city == "Ajax" and "/news-notices/" not in path:
            continue
        if city == "Clarington" and "/news/posts/" not in path:
            continue
        if city == "Whitby" and not NOTICE.search(label + " " + path):
            continue
        if not NOTICE.search(label + " " + path):
            continue
        links.append(href)
        if len(links) >= LIMIT_PER_CITY:
            break
    return links


def _file_numbers(text):
    found = []
    for label in LABELED.finditer(text):
        candidate = FILE_ID.match(text[label.end():label.end() + 45].lstrip(" :#-"))
        if candidate:
            ident = candidate.group(0).upper().replace(" ", "")
            if ident not in found:
                found.append(ident)
    return found[:8]


def _make(city, title, description, source, notice, ident=""):
    title = _clean(title)[:190]
    description = _clean(description)[:850]
    if len(title) < 9:
        return None
    if not _safe(notice, source):
        raise ValueError("UNSAFE_NOTICE_URL")
    kind = "APPLICATION_ID" if ident else "PROJECT_NOTICE_SIGNAL"
    identity = ident if ident else notice + "|" + title.casefold()
    digest = hashlib.sha256((city + "|" + identity).encode()).hexdigest()[:22]
    return {
        "city": city, "record_id": "NEXT4:" + city.upper().replace(" ", "_") + ":" + digest,
        "record_kind": kind, "application_id": ident,
        "project_title": title, "description": description,
        "source_url": source, "official_notice_url": notice,
        "potential_commercial": bool(COMMERCIAL.search(title + " " + description)),
        "publication_date_verified": False, "verified_buyer": False,
        "verified_open_procurement": False,
        "verification_required": (
            "Verify original file identity, public posting date, application stage, "
            "commercial scope, current owner/contact role and unawarded procurement."
        ),
    }


def _notice(city, html, source, notice):
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup.find("article") or soup
    for item in main.select("script,style,nav,footer,form"):
        item.decompose()
    headline = main.find("h1")
    title = _clean(headline.get_text(" ", strip=True)) if headline else ""
    if not title:
        title = "Official planning notice"
    body = _clean(main.get_text(" ", strip=True))
    if not NOTICE.search(title + " " + body[:1000]):
        return []
    ids = _file_numbers(body)
    if ids:
        return [r for r in
                (_make(city, title, body[:850], source, notice, ident)
                 for ident in ids)
                if r]
    # Historical or unnumbered article remains a project-only signal;
    # no application ID, date or purchaser is inferred from a posting.
    row = _make(city, title, body[:850], source, notice)
    return [row] if row else []


def _inline_whitby(html, source):
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    out = []
    for li in main.find_all("li"):
        text = _clean(li.get_text(" ", strip=True))
        if not (24 <= len(text) <= 1100 and ADDRESS.search(text)
                and re.search(r"\b(?:planning|zoning|official.plan|"
                              r"site.plan|amendment|development)\b", text, re.I)):
            continue
        title = text[:190]
        ids = _file_numbers(text)
        for ident in ids or [""]:
            row = _make("Whitby", title, text, source, source, ident)
            if row:
                out.append(row)
        if len(out) >= 15:
            break
    return out


def _read_old_csv(path):
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path, records):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in records:
            # Protect review CSV consumers from spreadsheet formula injection.
            writer.writerow({k: ("'" + str(row.get(k, "")) if
                                str(row.get(k, "")).lstrip().startswith(("=", "+", "-", "@"))
                                else row.get(k, ""))
                             for k in FIELDS})


def run(results, *, today=None, sources=None, fetcher=None):
    root = Path(results)
    root.mkdir(parents=True, exist_ok=True)
    date = (today or dt.date.today()).isoformat()
    catalog = SOURCES if sources is None else sources
    current = root / LEDGER
    old = json.loads(current.read_text(encoding="utf-8")) if current.is_file() \
        else {"schema": 1, "cities": {}}
    if old.get("schema") != 1 or not isinstance(old.get("cities"), dict):
        raise ValueError("NEXT_FOUR_LEDGER_SCHEMA_MISMATCH")
    previous_rows = _read_old_csv(root / ALL)
    updated = dict(old["cities"])
    all_rows, changes, diagnostics = [], [], []
    for city, source in catalog.items():
        item = {"city": city, "official_index": source, "status": "FAILED",
                "application_id_rows": 0, "project_only_signals": 0,
                "new_or_changed_review_only": 0, "verified_new_publications": 0,
                "verified_open_procurement": 0, "fetched_notice_pages": 0,
                "notice_page_errors": []}
        try:
            if city not in SOURCES or source != SOURCES[city]:
                raise ValueError("UNKNOWN_OR_CHANGED_OFFICIAL_CITY_SOURCE")
            html = (fetcher or _fetch)(source)
            links = _links(city, html, source)
            found = _inline_whitby(html, source) if city == "Whitby" else []
            for link in links:
                try:
                    page = (fetcher or _fetch)(link)
                    found.extend(_notice(city, page, source, link))
                    item["fetched_notice_pages"] += 1
                except Exception as exc:
                    item["notice_page_errors"].append({
                        "url": link, "error": type(exc).__name__ + ":" + str(exc)[:150]})
            # Fail closed on partial notice retrieval.  No new or changed event
            # is accepted and the prior per-city baseline remains untouched.
            if item["notice_page_errors"]:
                raise ValueError("PARTIAL_OFFICIAL_NOTICE_FETCH")
            unique = {row["record_id"]: row for row in found}
            prior = old["cities"].get(city, {})
            history = dict(prior.get("seen", {}))
            baseline = not bool(prior.get("baseline_complete"))
            for row in sorted(unique.values(), key=lambda x: x["record_id"]):
                digest = hashlib.sha256(json.dumps({
                    k: row[k] for k in ("project_title", "description", "record_kind",
                                        "application_id", "potential_commercial")
                }, sort_keys=True).encode()).hexdigest()
                past = history.get(row["record_id"])
                if baseline:
                    observation = "INITIAL_BASELINE_NOT_NEW_PUBLICATION"
                elif past is None:
                    observation = "FIRST_OBSERVED_UNDATED_HELD"
                elif past["digest"] != digest:
                    observation = "RECORD_CHANGED_REVIEW"
                else:
                    observation = "UNCHANGED"
                row["first_seen_local"] = past["first_seen_local"] if past else date
                row["observation"] = observation
                history[row["record_id"]] = {
                    "digest": digest, "first_seen_local": row["first_seen_local"]}
                all_rows.append(row)
                if observation in ("FIRST_OBSERVED_UNDATED_HELD", "RECORD_CHANGED_REVIEW"):
                    changes.append(row)
            if unique:
                updated[city] = {"baseline_complete": True, "seen": history}
            item.update({
                "status": ("INITIAL_BASELINE" if baseline else "COLLECTED")
                          if unique else "INDEX_ONLY_NO_PROJECT_APPLICATION_RECORDS",
                "application_id_rows": sum(x["record_kind"] == "APPLICATION_ID"
                                           for x in unique.values()),
                "project_only_signals": sum(x["record_kind"] == "PROJECT_NOTICE_SIGNAL"
                                            for x in unique.values()),
                "new_or_changed_review_only": sum(r["city"] == city for r in changes),
                "fetched_notice_pages": len(links),
            })
        except Exception as exc:
            item["error"] = type(exc).__name__ + ":" + str(exc)[:200]
            retained = [r for r in previous_rows if r.get("city") == city]
            all_rows.extend(retained)
            item["retained_prior_rows"] = len(retained)
        diagnostics.append(item)
    _write_csv(root / ALL, all_rows)
    _write_csv(root / CHANGES, changes)
    if updated != old["cities"]:
        tmp = current.with_suffix(".tmp")
        tmp.write_text(json.dumps({"schema": 1, "cities": updated}, indent=2),
                       encoding="utf-8")
        tmp.replace(current)
    report = {
        "mode": "MANUAL_FREE_NEXT_FOUR_MUNICIPALITY_REVIEW_PILOT",
        "cities_configured": len(catalog),
        "cities_with_application_ids": sum(s["application_id_rows"] > 0 for s in diagnostics),
        "application_id_rows": sum(s["application_id_rows"] for s in diagnostics),
        "project_only_signals": sum(s["project_only_signals"] for s in diagnostics),
        "new_or_changed_review_only": len(changes),
        "verified_fresh_commercial_leads": 0,
        "verified_buyer_contacts": 0, "verified_open_procurement": 0,
        "verified_citywide_coverage": 0, "paid_ai_calls": 0,
        "source_status": diagnostics,
        "warning": (
            "All project and application rows require original-source human review. "
            "First observations and changing page text do not prove a new public "
            "filing, purchasing intent or unawarded work. Citywide coverage 0/4."
        ),
    }
    (root / STATUS).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
