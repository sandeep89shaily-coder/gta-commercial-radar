"""Official City of Toronto current *planning notices*, distinct from TMMIS.

The public Notices Management register includes real Planning Act notices and
the City's own 'Notice Date', exact application numbers, sites and proposals.
The notice date is NOT proven first-publication time and neither notice nor
planner contact proves a buyer, tender or available supplier work.

Manual, bounded, policy-checked public fetch. No browser automation, paging,
API ID guessing, paid AI, auto lead promotion or primary Radar DB mutations.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import html
import json
import re
import socket
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import requests

import robots_policy
from toronto_pdf_download import public_dns

INDEX_URL = "https://secure.toronto.ca/nm/notices/current.do"
HOST = "secure.toronto.ca"
AGENT = "GTARadarResearch/1.0 (official current planning notices)"
TIMEOUT = (7, 20)
MAX_HTML = 3_000_000
MAX_DETAILS = 10
LEDGER = "TORONTO_CURRENT_PLANNING_NOTICE_LEDGER.json"
REVIEW_CSV = "TORONTO_CURRENT_PLANNING_NOTICES_REVIEW.csv"
STATUS = "TORONTO_CURRENT_PLANNING_NOTICES_STATUS.json"
FIELDS = (
    "city", "official_notice_id", "official_notice_url",
    "application_id", "notice_type", "notice_title", "location_from_notice_title",
    "municipal_notice_date", "description_excerpt", "public_city_planner_email",
    "index_sha256", "detail_sha256", "first_observed_utc",
    "last_observed_utc", "change_event", "source_evidence_level",
    "original_first_publication_verified", "project_verified",
    "buyer_verified", "open_procurement_verified"
)
DETAIL_PATH = re.compile(r"^/nm/api/individual/notice/([1-9]\d{0,8})\.do$")
APP_ID = re.compile(
    r"\b\d{2}\s+\d{5,7}\s+[A-Z]{3}\s+\d{2}\s+"
    r"(?:OZ|SA|SB|CD|RH|CO|SP)\b", re.I
)
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@toronto\.ca\b", re.I)
LISTED_DATE = re.compile(r"^20\d\d-\d\d-\d\d$")
LONG_DATE = re.compile(
    r"^(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+\d{1,2},?\s+20\d{2}$", re.I
)
PLANNING_TITLE = re.compile(
    r"^(?:Notice of Application\b|"
    r"Notice of Intention to Remove a Holding Symbol\b|"
    r"Notice of Public Meeting\b.*\b(?:Demolition|Planning Act)\b)", re.I
)
INDUSTRY = re.compile(
    r"\b(?:hotel|commercial|industrial|warehouse|manufactur\w*|"
    r"restaurant|retail|office|mixed.use|business|data.cent(?:er|re)|"
    r"factory|employment)\b", re.I
)


def valid_url(url):
    if not isinstance(url, str):
        return False
    p = urlsplit(url)
    return (p.scheme == "https" and p.hostname == HOST
            and not p.username and not p.password
            and p.port in (None, 443) and not p.fragment and not p.query
            and (url == INDEX_URL or bool(DETAIL_PATH.fullmatch(p.path))))


class VisibleHTML(HTMLParser):
    """Collect only literal visible text, top-level headings and exact anchors."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tokens = []
        self.links = []
        self.headings = []
        self._skip = 0
        self._link_href = None
        self._link_parts = []
        self._link_start = 0
        self._heading_tag = None
        self._heading_parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self._skip += 1
        if self._skip:
            return
        if tag == "a":
            self._link_href = dict(attrs).get("href")
            self._link_parts = []
            self._link_start = len(self.tokens)
        elif tag in ("h2", "h3", "h4"):
            self._heading_tag = tag
            self._heading_parts = []

    def handle_data(self, data):
        if self._skip:
            return
        token = " ".join(data.split())
        if not token:
            return
        self.tokens.append(token)
        if self._link_href is not None:
            self._link_parts.append(token)
        if self._heading_tag:
            self._heading_parts.append(token)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self._skip:
            self._skip -= 1
            return
        if self._skip:
            return
        if tag == "a":
            if self._link_href:
                self.links.append((
                    self._link_href, " ".join(self._link_parts),
                    self._link_start))
            self._link_href = None
            self._link_parts = []
        elif tag == self._heading_tag and self._heading_tag:
            heading = " ".join(self._heading_parts)
            self.headings.append((tag, heading, len(self.tokens)))
            self._heading_tag = None
            self._heading_parts = []


def _parser(text):
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_HTML:
        raise ValueError("NOTICE_HTML_MISSING_OR_OVERSIZE")
    parsed = VisibleHTML()
    parsed.feed(text)
    return parsed


def parse_index(markup):
    parsed = _parser(markup)
    candidates = []
    for href, label, token_index in parsed.links:
        from urllib.parse import urljoin
        url = urljoin(INDEX_URL, html.unescape(href).strip())
        if not valid_url(url) or url == INDEX_URL:
            continue
        match = DETAIL_PATH.fullmatch(urlsplit(url).path)
        if not match or not PLANNING_TITLE.search(label):
            continue
        candidates.append({
            "notice_id": match.group(1), "notice_url": url,
            "title": label.strip(), "start": token_index
        })
    if not candidates:
        return []
    candidates.sort(key=lambda row: row["start"])
    items = {}
    for i, item in enumerate(candidates):
        end = (candidates[i + 1]["start"] if i + 1 < len(candidates)
               else min(len(parsed.tokens), item["start"] + 80))
        text_slice = parsed.tokens[item["start"]:end][:80]
        notice_date = ""
        for n, token in enumerate(text_slice[:-1]):
            if token == "Notice Date" and LISTED_DATE.fullmatch(text_slice[n + 1]):
                notice_date = text_slice[n + 1]
                break
        if not notice_date:
            # No first-published claim and no uncontrolled date inference.
            continue
        doc = {k: item[k] for k in ("notice_id", "notice_url", "title")}
        doc["municipal_notice_date"] = notice_date
        old = items.get(doc["notice_id"])
        if old is not None and old != doc:
            raise ValueError("CONFLICTING_OFFICIAL_NOTICE_INDEX_ROWS")
        items[doc["notice_id"]] = doc
    # First sort by municipality's expressly labelled Notice Date, not Radar
    # observation and not date of originally publishing the project.
    return sorted(items.values(), key=lambda row: (
        row["municipal_notice_date"], int(row["notice_id"])), reverse=True)


def _date(text):
    if not LONG_DATE.fullmatch(text.strip()):
        raise ValueError("MISSING_OR_UNRECOGNIZED_OFFICIAL_NOTICE_DATE")
    return dt.datetime.strptime(text.replace(",", ""), "%B %d %Y").date().isoformat()


def parse_detail(markup, source):
    if not isinstance(source, dict) or not valid_url(source.get("notice_url")):
        raise ValueError("OFFICIAL_NOTICE_DETAIL_REQUIRED")
    parsed = _parser(markup)
    headings = parsed.headings
    title = next((text for tag, text, _ in headings if tag == "h2"
                  and PLANNING_TITLE.search(text)), "")
    if title != source.get("title"):
        raise ValueError("NOTICE_HEADING_DIFFERS_FROM_INDEX")
    by_heading = {}
    for i, (tag, label, end) in enumerate(headings):
        if tag not in ("h3", "h4"):
            continue
        next_start = (headings[i + 1][2] if i + 1 < len(headings)
                      else len(parsed.tokens))
        # Heading start positions are captured after text of heading; nothing
        # outside the heading's own immediately following section is accepted.
        by_heading.setdefault(label.casefold(), []).extend(
            parsed.tokens[end:next_start])
    date_text = (by_heading.get("date") or [""])[0]
    official_date = _date(date_text)
    if official_date != source["municipal_notice_date"]:
        raise ValueError("LISTING_DATE_DIFFERS_FROM_DETAIL_NOTICE_DATE")
    content = " ".join(by_heading.get("description", []))[:7000]
    if not content:
        raise ValueError("NO_OFFICIAL_NOTICE_DESCRIPTION")
    app_ids = {re.sub(r"\s+", " ", match.group(0).upper())
               for match in APP_ID.finditer(content)}
    for chunk in by_heading.get("planning application number", []):
        app_ids.update(re.sub(r"\s+", " ", match.group(0).upper())
                       for match in APP_ID.finditer(chunk))
    # Only single-file notices enter the initial review; distinct projects in
    # one notice are a separate multi-application join problem.
    if len(app_ids) != 1:
        raise ValueError("MISSING_OR_AMBIGUOUS_OFFICIAL_APPLICATION_ID")
    emails = [mail for mail in EMAIL.findall(content)
              if not mail.lower().startswith(("registrar", "cityclerk"))]
    contact = emails[0] if emails else ""
    # City planner contact is for source verification, never a buyer role.
    location = title.rsplit(" - ", 1)[-1][:300]
    return {
        "application_id": next(iter(app_ids)),
        "notice_title": title,
        "location_from_notice_title": location,
        "description_excerpt": content[:1000],
        "public_city_planner_email": contact,
        "municipal_notice_date": official_date,
        "notice_type": (
            "HOLDING_SYMBOL_REMOVAL_REVIEW" if "Holding Symbol" in title
            else "PLANNING_NOTICE_OF_APPLICATION" if
            title.lower().startswith("notice of application")
            else "PUBLIC_MEETING_NOTICE_REVIEW"
        ),
        "commercial_keyword_source_text": bool(INDUSTRY.search(content))
    }


def _get_html(url, *, session=None, resolver=socket.getaddrinfo,
              policy_reader=None):
    if not valid_url(url):
        raise ValueError("UNAPPROVED_OFFICIAL_NOTICE_URL")
    if not public_dns(HOST, resolver):
        raise ValueError("SOURCE_DNS_NONPUBLIC_OR_UNAVAILABLE")
    session = session or requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": AGENT, "Accept": "text/html"})
    allowed, reason = robots_policy.evaluate(
        session, url, AGENT, timeout=TIMEOUT, policy_reader=policy_reader)
    if not allowed:
        raise PermissionError("SOURCE_POLICY_" + str(reason))
    with session.get(url, timeout=TIMEOUT, allow_redirects=False,
                     stream=True) as resp:
        if resp.status_code != 200 or resp.url != url:
            raise ValueError("NOTICE_SOURCE_HTTP_OR_REDIRECT_" +
                             str(resp.status_code))
        mime = resp.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if mime not in ("text/html", "application/xhtml+xml"):
            raise ValueError("NOTICE_SOURCE_UNEXPECTED_CONTENT_TYPE")
        buf = bytearray()
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                buf.extend(chunk)
                if len(buf) > MAX_HTML:
                    raise ValueError("NOTICE_SOURCE_OVERSIZE")
        if not buf:
            raise ValueError("NOTICE_SOURCE_EMPTY")
        return bytes(buf).decode("utf-8", "replace")


def run(folder, *, fetch=False, getter=None, now=None):
    dest = Path(folder)
    dest.mkdir(parents=True, exist_ok=True)
    moment = now or dt.datetime.now(dt.timezone.utc)
    if moment.tzinfo is None:
        raise ValueError("AWARE_RUN_TIMESTAMP_REQUIRED")
    stamp = moment.astimezone(dt.timezone.utc).isoformat()
    result = {
        "city": "Toronto", "source_url": INDEX_URL,
        "status": "HOLD", "checked_utc": stamp,
        "index_planning_notices": 0, "details_considered": 0,
        "details_parsed_with_exact_application_id": 0,
        "commercial_keyword_source_records_review_only": 0,
        "unparsed_details_held": 0, "first_local_observations": 0,
        "source_notice_dates_recorded": 0,
        "publisher_first_publication_dates_verified": 0,
        "verified_buyers": 0, "verified_open_supplier_contracts": 0,
        "paid_ai_calls": 0,
        "warning": "City Notice Date is not proven first online publication. "
                   "Named City planners are not commercial buyers; "
                   "planning applications are not verified unawarded supplier jobs."
    }
    if not fetch:
        result["status"] = "MANUAL_FETCH_NOT_REQUESTED"
        (dest / STATUS).write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result
    get = getter or _get_html
    try:
        listing = get(INDEX_URL)
        fingerprint = hashlib.sha256(listing.encode("utf-8")).hexdigest()
        links = parse_index(listing)
        result["index_sha256"] = fingerprint
        result["index_planning_notices"] = len(links)
        if not links:
            result["status"] = "NO_ELIGIBLE_DATED_PLANNING_NOTICE_LINKS_SOURCE_HOLD"
            return result
        prior_file = dest / LEDGER
        if prior_file.is_file():
            historic = json.loads(prior_file.read_text(encoding="utf-8"))
            if (historic.get("version") != 1 or
                    not isinstance(historic.get("items"), dict)):
                raise ValueError("UNKNOWN_NOTICE_LEDGER_SCHEMA")
            prior = historic["items"]
        else:
            prior = {}
        future = dict(prior)
        rows = []
        reasons = []
        for item in links[:MAX_DETAILS]:
            result["details_considered"] += 1
            try:
                body = get(item["notice_url"])
                fields = parse_detail(body, item)
                bodyhash = hashlib.sha256(body.encode("utf-8")).hexdigest()
                datahash = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()
                old = prior.get(item["notice_id"])
                event = ("FIRST_RADAR_OBSERVATION_NOT_NEW_PUBLICATION" if not old
                         else "OFFICIAL_NOTICE_TEXT_CHANGED_NOT_NEW_PROJECT"
                         if old.get("data_sha256") != datahash else "UNCHANGED")
                first = old.get("first_observed_utc", stamp) if old else stamp
                rows.append({
                    "city": "Toronto",
                    "official_notice_id": item["notice_id"],
                    "official_notice_url": item["notice_url"],
                    **{key: fields[key] for key in (
                        "application_id", "notice_type", "notice_title",
                        "location_from_notice_title", "municipal_notice_date",
                        "description_excerpt", "public_city_planner_email")},
                    "index_sha256": fingerprint,
                    "detail_sha256": bodyhash,
                    "first_observed_utc": first, "last_observed_utc": stamp,
                    "change_event": event,
                    "source_evidence_level": "TORONTO_OFFICIAL_CURRENT_NOTICE_DETAIL",
                    "original_first_publication_verified": False,
                    "project_verified": False, "buyer_verified": False,
                    "open_procurement_verified": False
                })
                future[item["notice_id"]] = {
                    "application_id": fields["application_id"],
                    "first_observed_utc": first, "last_observed_utc": stamp,
                    "data_sha256": datahash, "detail_sha256": bodyhash
                }
                result["commercial_keyword_source_records_review_only"] += int(
                    fields["commercial_keyword_source_text"])
                result["source_notice_dates_recorded"] += 1
                result["first_local_observations"] += int(not old)
            except Exception as exc:
                reasons.append({"notice_id": item["notice_id"],
                                "reason": type(exc).__name__ + ": " + str(exc)[:100]})
        result["details_parsed_with_exact_application_id"] = len(rows)
        result["unparsed_details_held"] = len(reasons)
        result["held_notice_reasons"] = reasons
        if not rows:
            result["status"] = "ALL_CURRENT_NOTICE_DETAILS_BLOCKED_OR_UNPARSEABLE_HOLD"
            return result
        with (dest / REVIEW_CSV).open("w", encoding="utf-8-sig",
                                      newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow({
                    k: ("'" + v if isinstance(v, str) and
                        v.lstrip().startswith(("=", "+", "-", "@")) else v)
                    for k, v in row.items()
                })
        temporary = dest / (LEDGER + ".tmp")
        temporary.write_text(json.dumps({
            "version": 1, "updated_utc": stamp, "items": future
        }, indent=2), encoding="utf-8")
        temporary.replace(prior_file)
        result["status"] = (
            "OFFICIAL_NOTICE_DETAILS_REVIEW_ONLY" if not reasons
            else "PARTIAL_OFFICIAL_NOTICE_DETAILS_REVIEW_ONLY"
        )
    except Exception as exc:
        result["status"] = "OFFICIAL_NOTICE_SOURCE_OR_PARSER_HOLD"
        result["failure_type"] = type(exc).__name__
        result["failure_reason"] = str(exc)[:180]
    finally:
        (dest / STATUS).write_text(json.dumps(result, indent=2),
                                   encoding="utf-8")
    return result
