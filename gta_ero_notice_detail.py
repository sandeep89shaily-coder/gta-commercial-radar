"""Bounded ERO notice detail retrieval. Optional, read-only, no AI.

Fetch ONLY exact official /notice/NNN-NNNN URLs from the existing Radar ledger.
Fail closed when robots policy is inaccessible, forbids access, or page parsing
cannot verify the ERO ID, site location and proposal text.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
import time
from html import unescape
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

USER_AGENT = "GTACommercialRadarResearch/1.0 (public-record evidence pilot)"
ROBOTS_URL = "https://ero.ontario.ca/robots.txt"
MAX_HTML_BYTES = 1_500_000
MAX_NOTICES = 10
MIN_REQUEST_GAP_SECONDS = 2.0

CITY_ALIASES = {
    "etobicoke": "Toronto", "north york": "Toronto",
    "scarborough": "Toronto", "east york": "Toronto",
    "downsview": "Toronto", "york": "Toronto",
    "st catharines": "St Catharines",
}

def exact_ero_url(number, url):
    p = urlsplit(str(url or ""))
    return (
        re.fullmatch(r"\d{3}-\d{4}", str(number or "")) is not None
        and p.scheme == "https" and p.hostname == "ero.ontario.ca"
        and p.port in (None, 443) and not p.username and not p.password
        and p.path.rstrip("/") == "/notice/" + number
        and not p.query and not p.fragment
    )

def _label_value(text, name):
    match = re.search(re.escape(name) + r"\s*:?\s*([A-Za-z][A-Za-z ]{0,40})",
                      text, re.I)
    return match.group(1).strip() if match else ""

def _date_after(text, name):
    m = re.search(re.escape(name) + r"\s*:?\s*([A-Za-z]+ \d{1,2}, \d{4})", text, re.I)
    if not m:
        return ""
    try:
        return dt.datetime.strptime(m.group(1), "%B %d, %Y").date().isoformat()
    except ValueError:
        return ""

def _section(soup, heading, max_chars=25000):
    for tag in soup.find_all(("h2", "h3", "h4")):
        if " ".join(tag.stripped_strings).strip().casefold() != heading.casefold():
            continue
        out = []
        rank = int(tag.name[1])
        for sibling in tag.next_siblings:
            name = getattr(sibling, "name", None)
            if name and re.fullmatch(r"h[1-6]", name) and int(name[1]) <= rank:
                break
            if name in ("script", "style", "noscript", "form"):
                continue
            if hasattr(sibling, "get_text"):
                t = sibling.get_text("\n", strip=True)
            else:
                t = str(sibling).strip()
            if t:
                out.append(t)
        result = "\n".join(out)
        if result:
            return result[:max_chars]
    return ""

def parse_notice_html(page_html, expected_number, source_url):
    """Return only fields visibly present in exact official notice HTML."""
    if not exact_ero_url(expected_number, source_url):
        raise ValueError("INVALID_ERO_URL")
    if not isinstance(page_html, str) or not page_html.strip():
        raise ValueError("EMPTY_NOTICE")
    soup = BeautifulSoup(page_html[:MAX_HTML_BYTES], "html.parser")
    for tag in soup(["script", "style", "noscript", "form"]):
        tag.decompose()
    heading = soup.find("h1")
    if not heading:
        raise ValueError("MISSING_NOTICE_TITLE")
    title = " ".join(heading.stripped_strings)
    visible = soup.get_text(" ", strip=True)
    if not re.search(r"(?<!\d)" + re.escape(expected_number) + r"(?!\d)", visible):
        raise ValueError("ERO_ID_NOT_IN_NOTICE")
    stage_match = re.search(r"\bNotice stage\s+(Proposal|Decision|Bulletin)\b",
                            visible, re.I)
    if not stage_match:
        raise ValueError("NOTICE_STAGE_MISSING")
    stage = stage_match.group(1).title()
    proposal = _section(soup, "Proposal details")
    if not proposal or len(proposal) < 25:
        raise ValueError("PROPOSAL_DETAILS_MISSING")
    # Only the explicitly labelled *site address* is accepted for site matching;
    # never use the proponent/mailing address as a fallback.
    site = _section(soup, "Site address", max_chars=500)
    if not site:
        raise ValueError("EXPLICIT_SITE_ADDRESS_MISSING")
    lines = [re.sub(r"\s+", " ", x).strip() for x in site.splitlines() if x.strip()]
    if len(lines) < 2:
        raise ValueError("EXPLICIT_SITE_CITY_MISSING")
    address = lines[0]
    city_match = re.match(r"^([A-Za-z .'-]+),\s*(?:ON|Ontario)\b", lines[1], re.I)
    if not city_match:
        raise ValueError("EXPLICIT_SITE_CITY_MISSING")
    city = city_match.group(1).strip()
    city = CITY_ALIASES.get(city.casefold(), city)
    proponent = _section(soup, "Proponent(s)", max_chars=300)
    proponent = proponent.splitlines()[0].strip() if proponent else ""
    return {
        "ero_number": expected_number, "official_notice_url": source_url,
        "proponent": proponent or title.split(" - ", 1)[0].strip(),
        "site_address": address, "city": city, "notice_stage": stage,
        "proposal_posted": _date_after(visible, "Proposal posted"),
        "decision_posted": _date_after(visible, "Decision posted"),
        "proposal_details": proposal,
        "source_text_sha256": hashlib.sha256(page_html.encode("utf-8")).hexdigest(),
        "content_provenance": "FETCHED_EXACT_ERO_OFFICIAL_NOTICE",
    }

def _bounded_get(session, url):
    response = session.get(
        url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain"},
        timeout=(8, 20), allow_redirects=False, stream=True
    )
    try:
        if response.status_code != 200:
            raise ValueError("HTTP_" + str(response.status_code))
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type and "text/plain" not in content_type:
            raise ValueError("UNEXPECTED_CONTENT_TYPE")
        payload = bytearray()
        for piece in response.iter_content(chunk_size=65536):
            payload.extend(piece)
            if len(payload) > MAX_HTML_BYTES:
                raise ValueError("BODY_TOO_LARGE")
        return payload.decode("utf-8", errors="replace")
    finally:
        response.close()

def fetch_notice_details(cards, *, max_notices=5, session=None, sleep=time.sleep):
    """Opt-in bounded fetch; checked robots.txt required before any notices."""
    max_notices = max(0, min(int(max_notices), MAX_NOTICES))
    if max_notices == 0:
        return [], [{"status": "ZERO_LIMIT"}]
    owned = session is None
    session = session or requests.Session()
    audit = []
    notices = []
    try:
        try:
            robots = _bounded_get(session, ROBOTS_URL)
            policy = RobotFileParser()
            policy.parse(robots.splitlines())
            if not policy.can_fetch(USER_AGENT, "https://ero.ontario.ca/notice/026-0424"):
                return notices, [{"status": "ROBOTS_DISALLOW_ALL"}]
        except (requests.RequestException, OSError, ValueError) as e:
            return notices, [{
                "status": "ROBOTS_POLICY_UNAVAILABLE",
                "reason": type(e).__name__ + ": " + str(e)[:100],
            }]
        inspected = 0
        for number, card in sorted(cards.items(), reverse=True):
            if inspected >= max_notices:
                break
            url = card.get("official_notice_url", "")
            if not exact_ero_url(number, url):
                audit.append({"ero_number": number, "status": "INVALID_OFFICIAL_URL"})
                continue
            inspected += 1
            if not policy.can_fetch(USER_AGENT, url):
                audit.append({"ero_number": number, "status": "ROBOTS_DISALLOW_NOTICE"})
                continue
            if inspected > 1:
                sleep(MIN_REQUEST_GAP_SECONDS)
            try:
                page = _bounded_get(session, url)
                record = parse_notice_html(page, number, url)
                record["retrieved_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
                notices.append(record)
                audit.append({
                    "ero_number": number, "status": "DETAIL_RETRIEVED",
                    "source_text_sha256": record["source_text_sha256"],
                })
            except (requests.RequestException, OSError, ValueError) as e:
                audit.append({
                    "ero_number": number, "status": "DETAIL_REJECTED",
                    "reason": type(e).__name__ + ": " + str(e)[:120],
                })
        return notices, audit
    finally:
        if owned:
            session.close()
