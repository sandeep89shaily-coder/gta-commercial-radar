"""Source-evidenced Toronto TMMIS agenda item extraction from SAVED official HTML.

No network, paid AI, schedule, or production DB write. Actual downloaded HTML is
required. Exact agenda item codes and official attachment URLs are captured, but
a link/title never establishes first publication, project identity, or procurement.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from toronto_tmmis_documents import agenda_url, ATTACHMENT

ITEM = re.compile(r"^([A-Z]{1,5}\d{1,3}\.\d{1,4}[a-z]?)\s*[-–:]\s*(.{8,})$", re.I)
CODE_ONLY = re.compile(r"^[A-Z]{1,5}\d{1,3}\.\d{1,4}[a-z]?$", re.I)
TERMS = re.compile(
    r"\b(?:industrial|warehouse|manufactur\w*|factory|commercial|office|"
    r"site.plan|rezon\w*|zoning|development|employment.land|data.cent(?:er|re)|"
    r"distribution.centre|logistics|production.line|capital.project)\b", re.I
)
EXCLUSIONS = re.compile(
    r"\b(?:condolence|confirmation of minutes|declaration of interest|"
    r"call to order|appointment to fill|review of the order paper)\b", re.I
)
CSV = "TORONTO_AGENDA_ITEMS_REVIEW.csv"
JSON = "TORONTO_AGENDA_ITEMS_EVIDENCE.json"
FIELDS = ("item_code", "item_title", "meeting_url", "source_html_sha256",
          "source_heading", "attachment_urls", "attachment_count",
          "screening", "evidence_level", "original_publication_date",
          "project_identity_verified", "buyer_verified", "procurement_verified")


def _pdf_url(raw, base):
    target = urljoin(base, html.unescape(raw).strip())
    p = urlsplit(target)
    if (p.scheme != "https" or p.hostname != "www.toronto.ca"
            or p.username or p.password or p.port not in (None, 443)
            or p.fragment or p.query or not ATTACHMENT.fullmatch(p.path)):
        return None
    return target


class AgendaItems(HTMLParser):
    """Interpret explicit item headings and links until the next item heading.

    Uses plain HTMLParser (not JS), and avoids inferring item boundaries from
    addresses or incidental references in body paragraphs.
    """
    def __init__(self, meeting_url):
        super().__init__(convert_charrefs=True)
        self.meeting_url = meeting_url
        self.heading_depth = 0
        self.heading_chunks = []
        self.heading_tag = None
        self.link = None
        self.link_chunks = []
        self.items = []
        self.active = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in ("h2", "h3", "h4", "h5", "h6"):
            self.heading_depth += 1
            self.heading_tag = tag
            self.heading_chunks = []
        if tag == "a":
            self.link = dict(attrs).get("href")
            self.link_chunks = []

    def handle_data(self, data):
        if self.heading_depth:
            self.heading_chunks.append(data)
        if self.link is not None:
            self.link_chunks.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "a":
            if self.active is not None and self.link:
                url = _pdf_url(self.link, self.meeting_url)
                if url:
                    self.active["attachments"].add(url)
            self.link = None
            self.link_chunks = []
        if tag in ("h2", "h3", "h4", "h5", "h6") and self.heading_depth:
            heading = " ".join(" ".join(self.heading_chunks).split())
            found = ITEM.fullmatch(heading)
            if found:
                code, title = found.groups()
                normalized = code.upper()
                if CODE_ONLY.fullmatch(normalized):
                    self.active = {
                        "code": normalized, "title": title[:300],
                        "heading": heading[:350], "attachments": set()}
                    self.items.append(self.active)
            self.heading_depth -= 1
            self.heading_tag = None
            self.heading_chunks = []


def parse(html_body, meeting_url):
    if not agenda_url(meeting_url):
        raise ValueError("OFFICIAL_TORONTO_TMMIS_AGENDA_URL_REQUIRED")
    if not isinstance(html_body, str) or len(html_body) > 8_000_000:
        raise ValueError("INVALID_OR_OVERSIZED_SAVED_HTML")
    parser = AgendaItems(meeting_url)
    parser.feed(html_body)
    fingerprint = hashlib.sha256(html_body.encode("utf-8")).hexdigest()
    seen = set()
    result = []
    for item in parser.items:
        code = item["code"]
        # On a single agenda one code should appear at most once. Duplicate
        # explicit headings mean the parsing boundary is ambiguous.
        if code in seen:
            raise ValueError("DUPLICATE_ITEM_CODE_REQUIRES_REVIEW")
        seen.add(code)
        title = item["title"]
        # Keyword screening on the exact title only. No project or sector
        # assertion until source attachment pages are read and checked.
        lane = ("RESEARCH_CANDIDATE_TITLE_ONLY" if TERMS.search(title)
                and not EXCLUSIONS.search(title) else "OTHER_AGENDA_ITEM")
        result.append({
            "item_code": code, "item_title": title,
            "meeting_url": meeting_url, "source_html_sha256": fingerprint,
            "source_heading": item["heading"],
            "attachment_urls": sorted(item["attachments"]),
            "attachment_count": len(item["attachments"]),
            "screening": lane,
            "evidence_level": "OFFICIAL_SAVED_AGENDA_HEADING_ONLY",
            "original_publication_date": None,
            "project_identity_verified": False,
            "buyer_verified": False, "procurement_verified": False})
    return result


def build(saved_html, meeting_url, output_dir):
    source = Path(saved_html)
    if not source.is_file() or source.stat().st_size > 8_000_000:
        raise ValueError("SAVED_AGENDA_HTML_REQUIRED_UNDER_8_MB")
    original = source.read_text(encoding="utf-8")
    items = parse(original, meeting_url)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / CSV).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for item in items:
            row = dict(item, attachment_urls=" | ".join(item["attachment_urls"]))
            for key, value in row.items():
                if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                    row[key] = "'" + value
            writer.writerow(row)
    result = {
        "meeting_url": meeting_url,
        "source_html_sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
        "source_type": "SAVED_OFFICIAL_AGENDA_HTML",
        "items": items, "item_count": len(items),
        "research_candidate_titles": sum(
            i["screening"] == "RESEARCH_CANDIDATE_TITLE_ONLY" for i in items),
        "attachments_listed_not_downloaded": sum(i["attachment_count"] for i in items),
        "publication_dates_verified": 0, "verified_projects": 0,
        "verified_buyers": 0, "verified_open_procurements": 0,
        "paid_ai_cost_usd": 0,
        "warning": "Extracted exact agenda headings and matching attachment links from saved HTML; not a live publisher coverage claim. Do not treat title keyword matches as actual construction projects or early publication evidence."
    }
    (destination / JSON).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saved-html", required=True)
    parser.add_argument("--meeting-url", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = build(args.saved_html, args.meeting_url, args.out)
    print(json.dumps({k: output[k] for k in (
        "meeting_url", "item_count", "research_candidate_titles",
        "attachments_listed_not_downloaded", "verified_projects",
        "paid_ai_cost_usd")}, indent=2))


if __name__ == "__main__":
    main()
