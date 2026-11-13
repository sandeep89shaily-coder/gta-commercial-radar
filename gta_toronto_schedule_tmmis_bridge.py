"""Validate Toronto TMMIS agenda item lists against City Clerk schedule rows.

Only known Planning and Housing Committee PH meeting numbers from the City
Clerk's 2022–2026 open-data schedule are tried (max 3). A derived URL is NOT
accepted as an agenda source until the independent official response confirms
committee, meeting number, date, and actual item IDs. No speculative leads.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import html
import io
import json
import re
import socket
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import requests

import robots_policy
from toronto_pdf_download import public_dns

HOST = "secure.toronto.ca"
AGENT = "GTARadarResearch/1.0 (official TMMIS meeting item verification)"
TIMEOUT = (8, 25)
MAX_BYTES = 6_000_000
MAX_MEETINGS = 3
LEDGER = "TORONTO_PH_AGENDA_ITEM_FIRST_OBSERVED_LEDGER.json"
OUTPUT = "TORONTO_PH_AGENDA_ITEMS_REVIEW.csv"
STATUS = "TORONTO_PH_AGENDA_SOURCE_MATCH_STATUS.json"
CSV_FIELDS = (
    "city", "meeting_date", "meeting_number", "item_code", "item_title",
    "source_list_url", "item_detail_url_derived_unfetched",
    "official_source_sha256", "first_observed_utc", "last_observed_utc",
    "change_event", "publication_date_verified", "project_verified",
    "buyer_verified", "open_procurement_verified", "evidence_level"
)
SOURCE_HEADER = "CITY_CLERK_PUBLISHED_SCHEDULE_ONLY"
TERM = "2022-2026"
COMMITTEE = "Planning and Housing Committee"
ROW_RE = re.compile(r"^PH(\d{1,3})\.(\d{1,4})$", re.I)
NUM_RE = re.compile(r"^(?:PH)?(\d{1,3})$", re.I)
HEADING_RE = re.compile(r"\bPlanning\s+and\s+Housing\s+Committee\s*[-–]\s*Meeting\s+(\d{1,3})\b", re.I)
DATE_RE = re.compile(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(20\d{2})\b", re.I)


def agenda_items_url(year, number):
    if year != 2026 or not 1 <= number <= 99:
        raise ValueError("UNSUPPORTED_TMMIS_TERM_OR_MEETING_NUMBER")
    return "https://secure.toronto.ca/council/agenda-items.do?meeting=2026.PH" + str(number)


def select(schedule_csv, *, limit=MAX_MEETINGS):
    """Derive *candidate* URLs only; nothing is trusted until official HTML match."""
    if not 1 <= limit <= MAX_MEETINGS:
        raise ValueError("MEETING_LIMIT_INVALID")
    file = Path(schedule_csv)
    if not file.is_file() or file.stat().st_size > MAX_BYTES:
        raise ValueError("OFFICIAL_SCHEDULE_REVIEW_REQUIRED")
    reader = csv.DictReader(io.StringIO(file.read_text(encoding="utf-8-sig")))
    required = {"meeting_date", "committee", "meeting_number", "term", "schedule_evidence"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise ValueError("SCHEDULE_REVIEW_CSV_SCHEMA_INVALID")
    rows = []
    seen = set()
    for row in reader:
        if (row.get("committee", "").strip() != COMMITTEE or
                row.get("term", "").strip() != TERM or
                row.get("schedule_evidence", "").strip() != SOURCE_HEADER):
            continue
        day = dt.date.fromisoformat(row.get("meeting_date", ""))
        if day.year != 2026:
            continue
        matched = NUM_RE.fullmatch(row.get("meeting_number", "").strip())
        if not matched:
            continue
        number = int(matched.group(1))
        if (day, number) in seen:
            continue
        seen.add((day, number))
        rows.append({
            "meeting_date": day.isoformat(), "meeting_number": number,
            "candidate_url": agenda_items_url(day.year, number)
        })
    # Schedule prefiltered around the run date; rank newest meetings first.
    rows.sort(key=lambda item: (item["meeting_date"], item["meeting_number"]),
              reverse=True)
    return rows[:limit]


class _Text(HTMLParser):
    def __init__(self, number):
        super().__init__(convert_charrefs=True)
        self.number = number
        self.tokens = []
        self.h5 = False
        self.h5_text = []
        self.active_code = None
        self.items = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        if tag == "h5":
            self.h5 = True
            self.h5_text = []
    def handle_endtag(self, tag):
        if tag == "h5" and self.h5:
            title = " ".join(" ".join(self.h5_text).split())[:500]
            if self.active_code and len(title) >= 8:
                self.items.append((self.active_code, title))
                self.active_code = None
            self.h5 = False
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1
    def handle_data(self, data):
        if self.skip:
            return
        normalized = " ".join(data.split())
        if not normalized:
            return
        self.tokens.append(normalized)
        if self.h5:
            self.h5_text.append(normalized)
        else:
            match = ROW_RE.fullmatch(normalized)
            if match and int(match.group(1)) == self.number:
                self.active_code = normalized.upper()


def parse(markup, *, meeting_date, meeting_number):
    if not isinstance(markup, str) or len(markup.encode("utf-8")) > MAX_BYTES:
        raise ValueError("TMMIS_ITEM_HTML_MISSING_OR_OVERSIZED")
    doc = _Text(meeting_number)
    doc.feed(markup)
    whole = " ".join(doc.tokens)
    header = HEADING_RE.search(whole)
    if not header or int(header.group(1)) != meeting_number:
        raise ValueError("OFFICIAL_MEETING_TITLE_NUMBER_MISMATCH")
    date_match = DATE_RE.search(whole)
    if not date_match:
        raise ValueError("OFFICIAL_MEETING_DATE_MISSING")
    actual_date = dt.datetime.strptime(
        " ".join(date_match.groups()), "%B %d %Y").date()
    if actual_date.isoformat() != meeting_date:
        raise ValueError("OFFICIAL_MEETING_DATE_MISMATCH")
    if not doc.items:
        raise ValueError("OFFICIAL_TMMIS_ITEMS_MISSING_OR_STRUCTURE_CHANGED")
    result = []
    seen = set()
    for code, title in doc.items:
        if code in seen:
            raise ValueError("DUPLICATE_ITEM_CODE_HOLD")
        seen.add(code)
        result.append({"item_code": code, "item_title": title})
    return result


def fetch_one(url, *, session=None, resolver=socket.getaddrinfo,
              policy_reader=None):
    if (urlsplit(url).hostname != HOST or
            not re.fullmatch(
                r"https://secure\.toronto\.ca/council/agenda-items\.do\?meeting=2026\.PH\d{1,2}",
                url)):
        raise ValueError("OFFICIAL_SOURCE_ONLY")
    if not public_dns(HOST, resolver):
        raise ValueError("PUBLIC_DNS_UNAVAILABLE")
    session = session or requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": AGENT, "Accept": "text/html"})
    allowed, reason = robots_policy.evaluate(
        session, url, AGENT, timeout=TIMEOUT, policy_reader=policy_reader)
    if not allowed:
        raise PermissionError("OFFICIAL_SOURCE_POLICY_" + str(reason))
    with session.get(url, timeout=TIMEOUT, stream=True,
                     allow_redirects=False) as resp:
        if resp.status_code != 200 or resp.url != url:
            raise ValueError("OFFICIAL_HTTP_OR_REDIRECT_" + str(resp.status_code))
        mime = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if mime not in ("text/html", "application/xhtml+xml"):
            raise ValueError("UNEXPECTED_OFFICIAL_MIME")
        buf = bytearray()
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                buf.extend(chunk)
                if len(buf) > MAX_BYTES:
                    raise ValueError("OFFICIAL_HTML_OVERSIZE")
        if not buf:
            raise ValueError("EMPTY_OFFICIAL_HTML")
        return bytes(buf).decode("utf-8", "replace")


def run(schedule_csv, output, *, source_status, fetch=False, fetcher=None,
        now=None):
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    instant = now or dt.datetime.now(dt.timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("UTC_AWARE_TIME_REQUIRED")
    observed = instant.astimezone(dt.timezone.utc).isoformat()
    report = {
        "status": "HOLD", "checked_utc": observed,
        "schedule_source_status": source_status,
        "meeting_candidates_from_official_schedule": 0,
        "official_meeting_pages_matched": 0,
        "original_tmmis_items_extracted": 0,
        "meeting_page_results": [],
        "verified_project_count": 0,
        "first_publisher_publication_dates_verified": 0,
        "buyer_verified": 0, "open_procurement_verified": 0,
        "paid_ai_calls": 0,
        "warning": "Schedule-derived candidate URLs are not official records until independent same-date and number validation of the returned TMMIS page. Meeting date is not original agenda posting date."
    }
    try:
        if source_status != "RECENT_SCHEDULE_REVIEW_ONLY":
            report["status"] = "CURRENT_OFFICIAL_SCHEDULE_NOT_VALIDATED_HOLD"
            return report
        candidates = select(schedule_csv)
        report["meeting_candidates_from_official_schedule"] = len(candidates)
        if not candidates:
            report["status"] = "NO_RECENT_PLANNING_HOUSING_MEETINGS_IN_SCHEDULE"
            return report
        if not fetch:
            report["status"] = "MANUAL_TMMIS_FETCH_NOT_AUTHORIZED"
            return report
        old_file = root / LEDGER
        if old_file.exists():
            old_data = json.loads(old_file.read_text(encoding="utf-8"))
            if old_data.get("version") != 1 or not isinstance(old_data.get("items"), dict):
                raise ValueError("UNKNOWN_TMMIS_FIRST_SEEN_LEDGER")
            old = old_data["items"]
        else:
            old = {}
        history = dict(old)
        extracted = []
        for candidate in candidates:
            url = candidate["candidate_url"]
            entry = {"meeting_number": candidate["meeting_number"],
                     "meeting_date": candidate["meeting_date"],
                     "candidate_url": url, "status": "HOLD"}
            try:
                markup = (fetcher or fetch_one)(url)
                actual = parse(markup,
                               meeting_date=candidate["meeting_date"],
                               meeting_number=candidate["meeting_number"])
                fingerprint = hashlib.sha256(markup.encode("utf-8")).hexdigest()
                entry.update(status="OFFICIAL_SAME_MEETING_VERIFIED_ITEMS_REVIEW",
                             source_sha256=fingerprint, count=len(actual))
                report["official_meeting_pages_matched"] += 1
                for item in actual:
                    code = item["item_code"]
                    hashed = hashlib.sha256(item["item_title"].encode("utf-8")).hexdigest()
                    prior = old.get("2026." + code)
                    event = ("FIRST_OBSERVED_ITEM_NOT_FIRST_PUBLISHED" if not prior
                             else "TITLE_CHANGED_NOT_NEW_ITEM"
                             if prior.get("title_sha256") != hashed else "UNCHANGED")
                    first = prior.get("first_observed_utc", observed) if prior else observed
                    extracted.append({
                        "city": "Toronto", "meeting_date": candidate["meeting_date"],
                        "meeting_number": candidate["meeting_number"],
                        "item_code": code, "item_title": item["item_title"],
                        "source_list_url": url,
                        "item_detail_url_derived_unfetched":
                            "https://secure.toronto.ca/council/agenda-item.do?item=2026." + code,
                        "official_source_sha256": fingerprint,
                        "first_observed_utc": first, "last_observed_utc": observed,
                        "change_event": event,
                        "publication_date_verified": False,
                        "project_verified": False, "buyer_verified": False,
                        "open_procurement_verified": False,
                        "evidence_level": "OFFICIAL_TMMIS_SAME_MEETING_ITEM_LIST"
                    })
                    history["2026." + code] = {
                        "first_observed_utc": first,
                        "last_observed_utc": observed,
                        "title_sha256": hashed
                    }
                report["original_tmmis_items_extracted"] += len(actual)
            except Exception as exc:
                entry.update(status="TMMIS_MEETING_BLOCKED_OR_MISMATCH_HOLD",
                             reason=type(exc).__name__ + ": " + str(exc)[:120])
            report["meeting_page_results"].append(entry)
        if not extracted:
            report["status"] = "NO_OFFICIAL_TMMIS_MEETING_CONTENT_VERIFIED"
            return report
        with (root / OUTPUT).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for row in extracted:
                writer.writerow({
                    key: ("'" + value if isinstance(value, str) and
                          value.lstrip().startswith(("=", "+", "-", "@")) else value)
                    for key, value in row.items()
                })
        temporary = root / (LEDGER + ".tmp")
        temporary.write_text(json.dumps({
            "version": 1, "checked_utc": observed, "items": history
        }, indent=2), encoding="utf-8")
        temporary.replace(root / LEDGER)
        report["status"] = ("OFFICIAL_ITEM_LIST_REVIEW_ONLY" if
                            report["official_meeting_pages_matched"] == len(candidates)
                            else "PARTIAL_SOURCE_MATCH_REVIEW_ONLY")
    except Exception as exc:
        report["status"] = "BRIDGE_SOURCE_FAILED_HOLD"
        report["error_type"] = type(exc).__name__
        report["error_reason"] = str(exc)[:180]
    finally:
        (root / STATUS).write_text(json.dumps(report, indent=2),
                                   encoding="utf-8")
    return report
