"""Bounded official-host PDF retrieval from the existing source-index evidence.

Only an explicitly requested manual --fetch attempts network access.  The
previous index snapshot must have been captured successfully by Radar; no
third-party eSCRIBE filestream, generated URLs, redirects, robots bypass, or
automatic source discovery.  Documents remain review-only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import re
import socket
from pathlib import Path
from urllib.parse import urlsplit

import requests
from pypdf import PdfReader
from pypdf.errors import PdfReadError

import robots_policy
from gta_municipal_platform_registry import build as registry_build
from toronto_pdf_download import public_dns

USER_AGENT = "GTARadarResearch/1.0 (official municipal document review)"
MAX_PDF_BYTES = 12_000_000
MAX_FILES = 3
MAX_PAGES = 30
TIMEOUT = (8, 25)
OUTPUT_PREFIX = "GTA_RADAR_OFFICIAL_PDF_"
COMMERCIAL_TERMS = re.compile(
    r"\b(?:industrial|manufactur\w*|warehouse|commercial|"
    r"data[ -]?cent(?:er|re)|rezon\w*|site[ -]?plan|"
    r"employment[ -]?land|factory|logistics|facility[ -]?expansion)\b", re.I
)


def _source(source_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", source_id):
        raise ValueError("INVALID_SOURCE_ID")
    sources = [x for x in registry_build()["sources"] if x["source_id"] == source_id]
    if len(sources) != 1:
        raise ValueError("SOURCE_NOT_REGISTERED")
    return sources[0]


def allowed_pdf(url, index_url):
    """Only direct PDFs from exactly the registered municipal index host."""
    try:
        p = urlsplit(str(url))
        base = urlsplit(str(index_url))
        return (p.scheme == "https" and p.hostname == base.hostname
                and p.port in (None, 443) and not p.username and not p.password
                and not p.fragment and not p.query
                and p.path.lower().endswith(".pdf"))
    except (ValueError, TypeError):
        return False


def fetch_pdf(url, index_url, *, session=None, resolver=None, policy_reader=None):
    """Return verified document bytes or fail closed; never follow redirects."""
    if not allowed_pdf(url, index_url):
        raise ValueError("NOT_DIRECT_OFFICIAL_HOST_PDF")
    host = urlsplit(url).hostname
    if not public_dns(host, resolver or socket.getaddrinfo):
        raise PermissionError("PDF_PUBLIC_DNS_NOT_ESTABLISHED")
    own = session is None
    sess = session or requests.Session()
    if own:
        sess.trust_env = False
    try:
        permitted, reason = robots_policy.evaluate(
            sess, url, USER_AGENT, timeout=TIMEOUT, policy_reader=policy_reader)
        if not permitted:
            raise PermissionError("PDF_ROBOTS_" + reason)
        with sess.get(url, timeout=TIMEOUT, stream=True, allow_redirects=False,
                      headers={"User-Agent": USER_AGENT, "Accept": "application/pdf"}) as response:
            if response.status_code in (401, 403, 429):
                raise PermissionError("PDF_ACCESS_DENIED_" + str(response.status_code))
            if response.status_code != 200 or response.history or response.url != url:
                raise ValueError("PDF_HTTP_REDIRECT_OR_URL_CHANGED")
            mime = response.headers.get("Content-Type", "").lower().split(";")[0].strip()
            if mime not in ("application/pdf", "application/octet-stream"):
                raise ValueError("NOT_PDF_MIME")
            declared = response.headers.get("Content-Length", "")
            if declared:
                try:
                    if int(declared) > MAX_PDF_BYTES:
                        raise ValueError("PDF_TOO_LARGE")
                except ValueError:
                    raise ValueError("PDF_INVALID_OR_TOO_LARGE_LENGTH") from None
            buf = bytearray()
            for part in response.iter_content(chunk_size=65536):
                if part:
                    buf.extend(part)
                    if len(buf) > MAX_PDF_BYTES:
                        raise ValueError("PDF_TOO_LARGE")
            document = bytes(buf)
            if len(document) < 100 or not document.startswith(b"%PDF-"):
                raise ValueError("PDF_HEADER_INVALID")
            return document
    finally:
        if own:
            sess.close()


def review_bytes(document):
    """Inspect up to MAX_PAGES with original page numbers and bounded excerpts."""
    reader = PdfReader(io.BytesIO(document), strict=False)
    if reader.is_encrypted:
        raise ValueError("PDF_ENCRYPTED")
    pages = min(len(reader.pages), MAX_PAGES)
    found = []
    for page_number in range(pages):
        text = " ".join((reader.pages[page_number].extract_text() or "").split())
        for match in COMMERCIAL_TERMS.finditer(text):
            if len(found) >= 20:
                break
            found.append({
                "page": page_number + 1,
                "keyword": match.group(0).lower(),
                "excerpt": text[max(0, match.start()-90): match.end()+125],
                "verification": "UNVERIFIED_DOCUMENT_TEXT",
            })
        if len(found) >= 20:
            break
    return {"pages_inspected": pages, "total_pages": len(reader.pages),
            "mentions": found, "scan_ocr_required": not bool(found)}


def run(results, source_id, *, fetch=False, getter=None):
    """Read saved link evidence and optionally fetch at most three official PDFs."""
    results = Path(results)
    results.mkdir(parents=True, exist_ok=True)
    item = _source(source_id)
    slug = source_id.upper()
    input_path = results / ("GTA_RADAR_PLATFORM_INDEX_" + slug + "_EVIDENCE.json")
    status_file = results / (OUTPUT_PREFIX + slug + "_STATUS.json")
    manifest_file = results / (OUTPUT_PREFIX + slug + "_REVIEW.json")
    report = {
        "source_id": source_id,
        "city": item["city"],
        "status": "NOT_FETCHED_EXPLICIT_OPT_IN_REQUIRED",
        "observed_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "pdfs_fetched": 0, "pages_inspected": 0,
        "verified_publications": 0, "verified_projects": 0,
        "verified_buyers": 0, "paid_ai_usd": 0,
        "documents": [],
    }
    if not input_path.is_file():
        report["status"] = "MISSING_EXACT_INDEX_EVIDENCE"
    elif fetch:
        try:
            data = json.loads(input_path.read_text(encoding="utf-8"))
            if (not isinstance(data, dict) or data.get("source_id") != source_id
                    or data.get("city") != item["city"]
                    or data.get("original_index_url") != item["official_index_url"]
                    or not isinstance(data.get("document_links"), list)):
                raise ValueError("UNTRUSTED_OR_UNMATCHED_INDEX_EVIDENCE")
            eligible = []
            for link in data["document_links"][:60]:
                if not isinstance(link, dict) or link.get("city") != item["city"]:
                    continue
                target = link.get("url")
                if allowed_pdf(target, item["official_index_url"]) and target not in eligible:
                    eligible.append(target)
                if len(eligible) >= MAX_FILES:
                    break
            for target in eligible:
                row = {"source_url": target, "status": "SOURCE_HELD", "mentions": []}
                try:
                    document = (getter or fetch_pdf)(target, item["official_index_url"])
                    if not isinstance(document, bytes) or len(document) > MAX_PDF_BYTES:
                        raise ValueError("INVALID_PDF_BYTES")
                    if not document.startswith(b"%PDF-"):
                        raise ValueError("INVALID_PDF_HEADER")
                    detail = review_bytes(document)
                    digest = hashlib.sha256(document).hexdigest()
                    # Evidence content is deliberately stored separately from
                    # primary project databases and original source collectors.
                    directory = results / "OFFICIAL_DOCUMENT_CAPTURE" / slug
                    directory.mkdir(parents=True, exist_ok=True)
                    path = directory / (digest + ".pdf")
                    if not path.exists():
                        temp = path.with_suffix(".part")
                        temp.write_bytes(document)
                        temp.replace(path)
                    row.update({
                        "status": "PDF_REVIEW_ONLY", "sha256": digest,
                        "saved_path": str(path), "bytes": len(document),
                        **detail,
                    })
                    report["pdfs_fetched"] += 1
                    report["pages_inspected"] += detail["pages_inspected"]
                except (PermissionError, OSError, ValueError, TypeError,
                        PdfReadError, RuntimeError, requests.RequestException) as exc:
                    row.update({"status": "SOURCE_HELD", "failure": type(exc).__name__,
                                "reason": str(exc)[:160]})
                report["documents"].append(row)
            report["status"] = ("DOCUMENTS_FETCHED_REVIEW_ONLY" if report["pdfs_fetched"]
                                else "NO_VALID_OFFICIAL_PDFS_RETRIEVED")
            if not eligible:
                report["status"] = "NO_DIRECT_OFFICIAL_HOST_PDF_LINKS"
            # Keep last successful evidence when all current fetches fail.
            if report["pdfs_fetched"]:
                temp = manifest_file.with_suffix(".json.tmp")
                temp.write_text(json.dumps(report, indent=2), encoding="utf-8")
                temp.replace(manifest_file)
        except (ValueError, TypeError, OSError, KeyError) as exc:
            report["status"] = "INDEX_EVIDENCE_REJECTED_PREVIOUS_REVIEW_PRESERVED"
            report["error_type"] = type(exc).__name__
    status_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", required=True)
    p.add_argument("--source-id", required=True)
    p.add_argument("--fetch", action="store_true")
    args = p.parse_args()
    summary = run(args.results, args.source_id, fetch=args.fetch)
    print(json.dumps({k:v for k,v in summary.items() if k != "documents"}, indent=2))
