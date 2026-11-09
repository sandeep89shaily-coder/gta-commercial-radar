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
    "town of bradford west gwillimbury": "Bradford West Gwillimbury",
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
    """Read an ERO section by *document order*, not immediate HTML siblings.

    On ERO's rendered pages, headings and their paragraphs can be enclosed in
    separate nested <div> wrappers. A heading.next_siblings traversal then
    returns no content, even though the visible proposal details are present.
    Stop on the next equal/higher-level heading; never cross into other notices
    or unrelated sections.
    """
    from bs4 import NavigableString
    for tag in soup.find_all(("h2", "h3", "h4", "h5")):
        if " ".join(tag.stripped_strings).strip().casefold() != heading.casefold():
            continue
        rank = int(tag.name[1])
        parts = []
        for node in tag.next_elements:
            name = getattr(node, "name", None)
            if name and re.fullmatch(r"h[1-6]", name) and int(name[1]) <= rank:
                break
            if not isinstance(node, NavigableString):
                continue
            if tag in node.parents or node.find_parent(("script", "style", "noscript", "form")):
                continue
            word = " ".join(str(node).split()).strip()
            if word:
                parts.append(word)
            if sum(len(x) for x in parts) > max_chars + 500:
                break
        if parts:
            return "\n".join(parts)[:max_chars]
    # Some ERO field templates use a styled field label rather than an h2/h3.
    # Fall back only to exact visible label lines, with explicit section-ending
    # labels. Never infer a proposal from the generic notice summary.
    terminators = {
        "proposal details": {"supporting materials", "comment", "decision details",
                             "view materials in person", "contact"},
        "site address": {"site location map", "proponent(s)", "proposal details",
                         "decision details", "supporting materials"},
        "proponent(s)": {"proposal details", "decision details", "supporting materials",
                         "comment", "location details"},
    }
    stops = terminators.get(heading.casefold())
    if stops:
        lines = [x.strip() for x in soup.get_text("\n", strip=True).splitlines() if x.strip()]
        for i, line in enumerate(lines):
            if line.casefold() != heading.casefold():
                continue
            end = next((j for j in range(i+1, len(lines))
                        if lines[j].casefold() in stops), None)
            if end is None:
                continue  # Unbounded page/footer text is not valid source evidence.
            portion = "\n".join(lines[i+1:end])[:max_chars]
            if portion:
                return portion
    return ""

def _page_shape(page_html):
    """Safe diagnostics only: DOM heading labels, not scraped page bodies."""
    soup = BeautifulSoup(page_html[:MAX_HTML_BYTES], "html.parser")
    heading_labels = [" ".join(tag.stripped_strings)[:80]
                      for tag in soup.find_all(("h1", "h2", "h3", "h4", "h5"))[:25]]
    visible = soup.get_text(" ", strip=True)
    return {
        "html_sha256": hashlib.sha256(page_html.encode("utf-8")).hexdigest(),
        "heading_samples": heading_labels,
        "proposal_details_label_seen": bool(
            re.search(r"\bProposal details\b", visible, re.I)),
        "site_address_label_seen": bool(
            re.search(r"\bSite address\b", visible, re.I)),
    }


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
    # ERO site addresses may contain a lot/concession line between the street
    # and locality (e.g. Five Star Farms, 1660 Union Avenue, Kingsville).
    # Search only within the bounded labelled SITE ADDRESS section and never
    # use a proponent/mailing address or a page footer as a fallback.
    city_match = next(
        (m for part in lines[1:8]
         if (m := re.match(r"^([A-Za-z .'-]+),\s*(?:ON|Ontario)\b", part, re.I))),
        None
    )
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
            page = None
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
                failure = {
                    "ero_number": number, "status": "DETAIL_REJECTED",
                    "reason": type(e).__name__ + ": " + str(e)[:120],
                }
                if page is not None and isinstance(e, ValueError):
                    failure["page_shape"] = _page_shape(page)
                audit.append(failure)
        return notices, audit
    finally:
        if owned:
            session.close()
