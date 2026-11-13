"""Bounded, offline Brampton council agenda PDF bookmark extraction.

Brampton publicly documents that agendas are consolidated bookmarked PDFs.
Never download URLs, invoke AI, or promote bookmark names to verified projects.
Actual PDF bytes and stable PDF bookmark destinations are required.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from pypdf import PdfReader

MAX_BYTES = 45_000_000
MAX_PAGES = 500
MAX_BOOKMARKS = 600
GENERIC_SECTION = re.compile(r"^(?:[0-9]+(?:[.][0-9]+)*[.]?\s*)?(?:planning and development|planning and development committee|general business|other business)$", re.I)
MAX_DEPTH = 10
LEDGER = "BRAMPTON_AGENDA_PDF_VERSIONS.json"
CSV = "BRAMPTON_AGENDA_BOOKMARK_ITEMS_REVIEW.csv"
REPORT = "BRAMPTON_AGENDA_BOOKMARK_AUDIT.json"
FIELDS = ("meeting_url", "agenda_pdf_url", "pdf_sha256", "item_path",
          "bookmark_title", "page_1based", "depth", "screening",
          "evidence_level", "original_publication_date",
          "project_verified", "buyer_verified", "procurement_verified")
TERMS = re.compile(
    r"\b(?:industrial|manufactur\w*|warehouse|factory|logistics|"
    r"commercial|development|site.plan|planning|zoning|rezon\w*|"
    r"official.plan|business.park|employment.land|data.cent(?:er|re)|"
    r"expansion|facility|distribution.centre)\b", re.I
)
EXCLUDE = re.compile(r"\b(?:minutes|agenda|land acknowledgement|"
                     r"declarations of interest|call to order|confirmation of|"
                     r"closed session|procedural by.law)\b", re.I)


def _official_url(raw):
    p = urlsplit(str(raw or ""))
    if (p.scheme != "https" or not p.hostname or p.username or p.password
            or p.port not in (None, 443) or p.fragment):
        raise ValueError("VALID_PUBLIC_HTTPS_URL_REQUIRED")
    host = p.hostname.lower()
    if host not in ("brampton.ca", "www.brampton.ca", "www1.brampton.ca",
                    "pub-brampton.escribemeetings.com"):
        raise ValueError("BRAMPTON_SOURCE_HOST_REQUIRED")
    return p.geturl()


def _outline(reader):
    """Iterate pypdf outline hierarchy without inventing missing item codes."""
    rows = []
    def walk(nodes, ancestors, depth):
        if depth > MAX_DEPTH:
            raise ValueError("OUTLINE_DEPTH_LIMIT")
        last_title = None
        for node in nodes:
            if isinstance(node, list):
                # pypdf nests children after their parent: never borrow a
                # bookmark title from another branch or preceding sibling.
                if last_title is None:
                    raise ValueError("ORPHANED_OUTLINE_CHILDREN")
                walk(node, ancestors + (last_title,), depth + 1)
                continue
            if len(rows) >= MAX_BOOKMARKS:
                raise ValueError("OUTLINE_BOOKMARK_LIMIT")
            title = " ".join(str(getattr(node, "title", "")).split())[:350]
            if not title:
                raise ValueError("UNLABELED_OUTLINE_DESTINATION")
            try:
                page = reader.get_destination_page_number(node)
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                raise ValueError("UNRESOLVABLE_BOOKMARK_DESTINATION") from exc
            if not isinstance(page, int) or not 0 <= page < len(reader.pages):
                raise ValueError("BOOKMARK_PAGE_OUT_OF_RANGE")
            last_title = title
            rows.append(dict(title=title, page=page + 1, depth=depth,
                             path=" / ".join((*ancestors, title))[:900]))
    walk(reader.outline, (), 0)
    return rows


def _read_ledger(path):
    if not path.exists():
        return {}
    saved = json.loads(path.read_text(encoding="utf-8"))
    if saved.get("version") != 1 or not isinstance(saved.get("meetings"), dict):
        raise ValueError("UNRECOGNIZED_AGENDA_LEDGER")
    return saved["meetings"]


def inspect(pdf_path, *, meeting_url, agenda_pdf_url, results, now=None):
    meeting_url = _official_url(meeting_url)
    agenda_pdf_url = _official_url(agenda_pdf_url)
    file = Path(pdf_path)
    if not file.is_file():
        raise ValueError("SAVED_OFFICIAL_AGENDA_PDF_REQUIRED")
    size = file.stat().st_size
    if size < 100 or size > MAX_BYTES:
        raise ValueError("PDF_SIZE_OUT_OF_BOUNDS")
    current_time = now or dt.datetime.now(dt.timezone.utc)
    if current_time.tzinfo is None:
        raise ValueError("TIMEZONE_AWARE_TIMESTAMP_REQUIRED")
    now_utc = current_time.astimezone(dt.timezone.utc).isoformat()
    data = file.read_bytes()
    if not data.startswith(b"%PDF-"):
        raise ValueError("NOT_A_PDF")
    digest = hashlib.sha256(data).hexdigest()
    reader = PdfReader(file, strict=False)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
        raise ValueError("ENCRYPTED_EMPTY_OR_OVERSIZED_PDF")
    outline = _outline(reader)
    target = Path(results)
    target.mkdir(parents=True, exist_ok=True)
    ledger_path = target / LEDGER
    before = _read_ledger(ledger_path)
    old = before.get(meeting_url)
    if old and old.get("agenda_pdf_url") != agenda_pdf_url:
        # The official publisher may revise an agenda URL. Do not overwrite
        # evidence silently; manual reconciliation is required.
        raise ValueError("MEETING_PDF_SOURCE_CHANGED_REVIEW_REQUIRED")
    if not old:
        event = "FIRST_LOCAL_BASELINE_NOT_FIRST_PUBLICATION"
    elif old.get("pdf_sha256") == digest:
        event = "UNCHANGED_SAVED_PDF"
    else:
        event = "SAVED_AGENDA_PDF_REVISION_NOT_NEW_PROJECT"
    rows = []
    for bookmark in outline:
        title = bookmark["title"]
        category = ("AGENDA_BOOKMARK_RESEARCH_CANDIDATE" if TERMS.search(title)
                    and not EXCLUDE.search(title)\n                    and not GENERIC_SECTION.fullmatch(title)\n                    else "AGENDA_BOOKMARK_OTHER")
        rows.append({
            "meeting_url": meeting_url, "agenda_pdf_url": agenda_pdf_url,
            "pdf_sha256": digest, "item_path": bookmark["path"],
            "bookmark_title": title, "page_1based": bookmark["page"],
            "depth": bookmark["depth"], "screening": category,
            "evidence_level": "LOCAL_PDF_BOOKMARK_NO_PROJECT_VERIFICATION",
            "original_publication_date": "", "project_verified": False,
            "buyer_verified": False, "procurement_verified": False
        })
    # The item list is provenance-only: bookmark titles aren't proof the
    # referenced content establishes a particular proposal or status.
    ledger = dict(before)
    ledger[meeting_url] = {
        "meeting_url": meeting_url, "agenda_pdf_url": agenda_pdf_url,
        "pdf_sha256": digest, "first_observed_utc": (
            old["first_observed_utc"] if old else now_utc),
        "last_observed_utc": now_utc,
        "version_hashes": list(dict.fromkeys((
            list(old.get("version_hashes", [])) if old else []) + [digest]))
    }
    with (target / CSV).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for item in rows:
            out = dict(item)
            for key, value in out.items():
                if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                    out[key] = "'" + value
            writer.writerow(out)
    report = {
        "meeting_url": meeting_url, "agenda_pdf_url": agenda_pdf_url,
        "pdf_sha256": digest, "bytes": size, "page_count": len(reader.pages),
        "event": event, "bookmarks_parsed": len(rows),
        "bookmarks_screened_for_research": sum(
            r["screening"] == "AGENDA_BOOKMARK_RESEARCH_CANDIDATE"
            for r in rows),
        "first_observed_utc": ledger[meeting_url]["first_observed_utc"],
        "last_observed_utc": now_utc,
        "saved_pdf_versions_seen": len(ledger[meeting_url]["version_hashes"]),
        "first_publications_verified": 0, "project_records_verified": 0,
        "procurement_opportunities_verified": 0, "deepseek_spend_usd": 0,
        "warning": "Saved local Brampton PDF bookmarks only; index origin, meeting date, original publication and specific project facts require separate verification. Revisions are not new-project events."
    }
    (target / REPORT).write_text(json.dumps(report, indent=2), encoding="utf-8")
    temp = ledger_path.with_suffix(".tmp")
    temp.write_text(json.dumps({"version": 1, "meetings": ledger}, indent=2),
                    encoding="utf-8")
    os.replace(temp, ledger_path)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--meeting-url", required=True)
    parser.add_argument("--agenda-pdf-url", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.pdf, meeting_url=args.meeting_url,
                             agenda_pdf_url=args.agenda_pdf_url,
                             results=args.out), indent=2))


if __name__ == "__main__":
    main()
