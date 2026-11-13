"""Mississauga eSCRIBE Planning & Development agenda PDF item extraction.

Offline source-bound adapter for already saved official PDF. Official 2026 PDC
agendas contain numbered matters (e.g. 6.1), description, Owner and File lines.
No source download, OCR, paid AI, application matching or publication claims.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from pypdf import PdfReader

MAX_BYTES = 45_000_000
MAX_PAGES = 400
MAX_TOC_PAGES = 12
OUT = "MISSISSAUGA_PDC_AGENDA_ITEMS_REVIEW.csv"
AUDIT = "MISSISSAUGA_PDC_AGENDA_ITEMS_STATUS.json"
ITEM = re.compile(r"^\*?\s*(\d{1,2}\.\d{1,3})\s*\*?$")
FILE = re.compile(r"^(?:File|Originator.s file)\s*:\s*(.+)$", re.I)
OWNER = re.compile(r"^(?:Owner|Applicant)\s*:\s*(.+)$", re.I)
REPORT = re.compile(r"(?:INFORMATION|RECOMMENDATION|REPORT|PUBLIC MEETING)", re.I)
TOPIC = re.compile(r"\b(?:industrial|warehouse|manufactur\w*|commercial|"
                   r"business park|logistics|production|facility|factory|"
                   r"employment|retail|office|data cent(?:er|re))\b", re.I)
ADDRESS = re.compile(r"\b\d{1,6}[A-Z]?(?:\s*(?:&|and|,|-)\s*\d{1,6}[A-Z]?)?"
                     r"\s+(?:[A-Za-z0-9.'-]+\s+){0,5}"
                     r"(?:Street|St|Road|Rd|Drive|Dr|Avenue|Ave|Boulevard|"
                     r"Blvd|Way|Lane|Ln|Court|Ct|Crescent|Cres|Parkway|Pkwy)\b", re.I)
APPLICATION = re.compile(r"(?:OZ/OPA|OZ|OPA|T-OZ|SP|SPM|DARC)\s*[-/]?\s*"
                         r"\d{2,4}[-/]\d{1,5}(?:\s+W\d{1,2})?", re.I)
FIELDS = ("city", "source_pdf_url", "pdf_sha256", "item_number",
          "report_heading", "description", "address_raw", "owner_raw",
          "application_id", "pdf_page_1based", "screening",
          "evidence_level", "first_published_at", "project_verified",
          "buyer_verified", "procurement_verified")


def official_pdf(url):
    p = urlsplit(str(url or ""))
    if (p.scheme != "https" or p.hostname != "pub-mississauga.escribemeetings.com"
            or p.username or p.password or p.port not in (None, 443)
            or p.fragment or p.path.lower() != "/filestream.ashx"):
        raise ValueError("NOT_OFFICIAL_MISSISSAUGA_ESCRIBE_DOCUMENT")
    from urllib.parse import parse_qs
    values = parse_qs(p.query, keep_blank_values=True)
    identifier = values.get("DocumentId", values.get("documentid", []))
    if (len(identifier) != 1 or not identifier[0].isdigit()
            or int(identifier[0]) < 1):
        raise ValueError("OFFICIAL_DOCUMENT_ID_REQUIRED")
    return url


def _text_pages(path):
    file = Path(path)
    if not file.is_file() or not 100 <= file.stat().st_size <= MAX_BYTES:
        raise ValueError("BOUNDED_SAVED_PDF_REQUIRED")
    if not file.open("rb").read(5) == b"%PDF-":
        raise ValueError("INVALID_PDF_SIGNATURE")
    pdf = PdfReader(str(file), strict=False)
    if pdf.is_encrypted or not 1 <= len(pdf.pages) <= MAX_PAGES:
        raise ValueError("INVALID_ENCRYPTED_OR_OVERSIZED_PDF")
    pages = []
    for index, page in enumerate(pdf.pages[:MAX_TOC_PAGES], 1):
        pages.append((index, (page.extract_text() or "").splitlines()))
    return pages


def parse_pages(pages, source_url, pdf_sha):
    official_pdf(source_url)
    # A PDC agenda has an initial list of matters, sometimes followed by
    # hundreds of pages of appended staff reports. Avoid secondary 6.1 labels
    # inside those reports and do not parse minutes as new agenda items.
    found_matters = False
    collected = []
    active = None
    for page_num, lines in pages:
        for raw in lines:
            line = " ".join(str(raw).split())
            if not line:
                continue
            if re.search(r"\bMATTERS TO BE CONSIDERED\b", line, re.I):
                found_matters = True
                continue
            if found_matters and re.fullmatch(r"(?:\d+[.]?\s*)?ADJOURNMENT", line, re.I):
                if active:
                    collected.append(active)
                active = None
                break
            if not found_matters:
                continue
            code = ITEM.fullmatch(line)
            if code:
                if active:
                    collected.append(active)
                active = {"item_number": code.group(1), "page": page_num,
                          "lines": []}
                continue
            if active:
                active["lines"].append(line)
        else:
            continue
        # We saw the Agenda ADJOURNMENT marker; reports follow, but are not a
        # new item in this initial agenda contents pass.
        break
    if active:
        collected.append(active)
    rows = []
    seen = set()
    for item in collected:
        code = item["item_number"]
        if code in seen:
            raise ValueError("DUPLICATE_AGENDA_ITEM_REQUIRES_REVIEW")
        seen.add(code)
        lines = item["lines"][:60]
        if not lines:
            continue
        # Exact source text, not model-generated identities.
        heading = lines[0][:300]
        owners = [m.group(1) for line in lines if (m := OWNER.match(line))]
        files = [m.group(1) for line in lines if (m := FILE.match(line))]
        file_ids = []
        for raw in files:
            file_ids.extend(APPLICATION.findall(raw))
        addresses = []
        multi_site = False
        for line in lines[1:]:
            match = ADDRESS.search(line)
            if match:
                addresses.append(match.group(0))
                # Multi-unit/multi-address planning applications cannot be
                # safely assigned to the first number observed.
                if re.search(r"\b\d{1,6}\s*(?:&|and|,|-)\s*\d{1,6}\b", line, re.I):
                    multi_site = True
                if len(ADDRESS.findall(line)) > 1:
                    multi_site = True
        address = (addresses[0] if not multi_site and
                   len(set(addresses)) == 1 else "")
        application_id = file_ids[0] if len(set(file_ids)) == 1 else ""
        description = " ".join(lines[1:5])[:550]
        topic = TOPIC.search(heading + " " + description)
        if topic and address and application_id:
            lane = "COMMERCIAL_TITLE_REVIEW_ONLY"
        elif topic:
            lane = "COMMERCIAL_TOPIC_NO_EXACT_SITE_OR_FILE_HOLD"
        else:
            lane = "OTHER_AGENDA_ITEM"
        rows.append({
            "city": "Mississauga", "source_pdf_url": source_url,
            "pdf_sha256": pdf_sha, "item_number": code,
            "report_heading": heading, "description": description,
            "address_raw": address,
            "owner_raw": owners[0] if len(set(owners)) == 1 else "",
            "application_id": application_id,
            "pdf_page_1based": item["page"],
            "screening": lane,
            "evidence_level": "ACTUAL_SAVED_PDF_AGENDA_CONTENT_NOT_INDEPENDENTLY_VERIFIED",
            "first_published_at": "", "project_verified": False,
            "buyer_verified": False, "procurement_verified": False
        })
    return rows, found_matters


def run(pdf, pdf_url, out):
    official_pdf(pdf_url)
    source = Path(pdf)
    pages = _text_pages(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    rows, found = parse_pages(pages, pdf_url, digest)
    target = Path(out)
    target.mkdir(parents=True, exist_ok=True)
    with (target / OUT).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            safe = {k: ("'" + v if isinstance(v, str) and
                    v.lstrip().startswith(("=", "+", "-", "@")) else v)
                    for k, v in row.items()}
            writer.writerow(safe)
    report = {
        "status": ("REVIEW_ONLY_ITEM_EXTRACTION" if found and rows
                   else "AGENDA_TOC_NOT_RECOVERED_NO_SUCCESS_CLAIM"),
        "source_pdf_url": pdf_url, "pdf_sha256": digest,
        "toc_items": len(rows), "application_ids_extracted": sum(
            bool(r["application_id"]) for r in rows),
        "commercial_title_candidates": sum(
            r["screening"] == "COMMERCIAL_TITLE_REVIEW_ONLY" for r in rows),
        "source_pdf_pages_scanned": len(pages),
        "source_contents_read": True,
        "publication_dates_verified": 0, "verified_project_matches": 0,
        "verified_procurement": 0, "ai_usd": 0,
        "warning": "Agenda item contents are source text, not proof of project status. Dates and application/permit matches require separate original-source verification."
    }
    (target / AUDIT).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--pdf", required=True)
    p.add_argument("--pdf-url", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    print(json.dumps(run(args.pdf, args.pdf_url, args.out), indent=2))
