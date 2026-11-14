"""Exact-link eSCRIBE document pilot. Explicit authorization and manual run only.

A document must first occur in Radar's successful official municipal index
snapshot. This adapter does not enumerate IDs, follow redirects, visit portals,
authenticate, defeat robots/403, or infer new projects from document contents.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import re
import socket
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import requests
from pypdf.errors import PdfReadError

import robots_policy
from gta_municipal_platform_registry import build as registry_build
from gta_official_platform_pdf_intake import (
    MAX_PDF_BYTES, TIMEOUT, review_bytes
)
from toronto_pdf_download import public_dns

AGENT = "GTARadarResearch/1.0 (authorized municipal eSCRIBE PDF review)"
MAX_DOCUMENTS = 2
PREFIX = "GTA_RADAR_ESCRIBE_"


def _source(source_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", str(source_id)):
        raise ValueError("INVALID_REGISTERED_SOURCE_ID")
    matches = [r for r in registry_build()["sources"] if r["source_id"] == source_id]
    if len(matches) != 1:
        raise ValueError("SOURCE_NOT_REGISTERED")
    return matches[0]


def exact_document(url, city):
    """Only canonical eSCRIBE public filestream from same official city.

    A valid URL shape is *not* authorization to download.
    """
    if not re.fullmatch(r"[A-Za-z][A-Za-z -]{1,64}", str(city or "")):
        return False
    try:
        p = urlsplit(str(url or ""))
        if (p.scheme != "https" or p.hostname !=
                "pub-" + city.strip().lower().replace(" ", "") + ".escribemeetings.com"
                or p.port not in (None, 443) or p.username or p.password
                or p.fragment or p.path.lower() != "/filestream.ashx"):
            return False
        if not p.query or not re.fullmatch(r"DocumentId=[1-9][0-9]{0,11}", p.query):
            return False
        parsed = parse_qs(p.query, strict_parsing=True)
        return list(parsed) == ["DocumentId"] and len(parsed["DocumentId"]) == 1
    except (ValueError, TypeError):
        return False


def fetch_document(url, city, *, session=None, resolver=None,
                   policy_reader=None):
    if not exact_document(url, city):
        raise ValueError("UNREGISTERED_ESCRIBE_DOCUMENT_SHAPE")
    host = urlsplit(url).hostname
    if not public_dns(host, resolver or socket.getaddrinfo):
        raise PermissionError("ESCRIBE_DNS_NONPUBLIC_OR_UNAVAILABLE")
    own = session is None
    sess = session or requests.Session()
    if own:
        sess.trust_env = False
    try:
        allowed, reason = robots_policy.evaluate(
            sess, url, AGENT, timeout=TIMEOUT, policy_reader=policy_reader)
        if not allowed:
            raise PermissionError("ESCRIBE_ROBOTS_" + str(reason))
        with sess.get(url, stream=True, timeout=TIMEOUT, allow_redirects=False,
                      headers={"User-Agent": AGENT, "Accept": "application/pdf"}) as res:
            if res.status_code in (401, 403, 429):
                raise PermissionError("ESCRIBE_HTTP_ACCESS_DENIED_" + str(res.status_code))
            if res.status_code != 200 or res.history or res.url != url:
                raise ValueError("ESCRIBE_HTTP_OR_REDIRECT_" + str(res.status_code))
            mimetype = res.headers.get("Content-Type", "").split(";", 1)[0].lower().strip()
            if mimetype not in ("application/pdf", "application/octet-stream"):
                raise ValueError("ESCRIBE_UNEXPECTED_MIME")
            size_header = res.headers.get("Content-Length")
            if size_header is not None:
                if not str(size_header).isdigit() or int(size_header) > MAX_PDF_BYTES:
                    raise ValueError("ESCRIBE_DECLARED_SIZE_INVALID")
            buf = bytearray()
            for chunk in res.iter_content(chunk_size=65536):
                if chunk:
                    buf.extend(chunk)
                    if len(buf) > MAX_PDF_BYTES:
                        raise ValueError("ESCRIBE_PDF_SIZE_EXCEEDED")
            if len(buf) < 100 or not buf.startswith(b"%PDF-"):
                raise ValueError("ESCRIBE_PDF_SIGNATURE_INVALID")
            return bytes(buf)
    finally:
        if own:
            sess.close()


def run(results, source_id, *, fetch=False, authorized=False, getter=None):
    """Per-source saved evidence; no changes to main Radar SQLite or collection."""
    root = Path(results)
    root.mkdir(parents=True, exist_ok=True)
    source = _source(source_id)
    slug = source_id.upper()
    index_path = root / ("GTA_RADAR_PLATFORM_INDEX_" + slug + "_EVIDENCE.json")
    status_path = root / (PREFIX + slug + "_STATUS.json")
    review_path = root / (PREFIX + slug + "_REVIEW.json")
    output = {
        "source_id": source_id, "city": source["city"],
        "status": "NOT_RUN_EXPLICIT_FETCH_AND_AUTHORIZATION_REQUIRED",
        "checked_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "downloaded_documents": 0, "reviewed_pages": 0,
        "confirmed_publication_dates": 0, "verified_project_leads": 0,
        "verified_buyers": 0, "paid_ai_usd": 0,
        "documents": [],
    }
    if not fetch or not authorized:
        status_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
        return output
    try:
        if not index_path.is_file() or index_path.stat().st_size > 300_000:
            raise ValueError("MISSING_OR_OVERSIZED_OFFICIAL_INDEX_SNAPSHOT")
        snapshot = json.loads(index_path.read_text(encoding="utf-8"))
        if (not isinstance(snapshot, dict)
                or snapshot.get("source_id") != source_id
                or snapshot.get("city") != source["city"]
                or snapshot.get("original_index_url") != source["official_index_url"]
                or not isinstance(snapshot.get("document_links"), list)):
            raise ValueError("INDEX_SOURCE_PROVENANCE_MISMATCH")
        links = []
        for item in snapshot["document_links"][:60]:
            if not isinstance(item, dict) or item.get("city") != source["city"]:
                continue
            uri = item.get("url")
            if exact_document(uri, source["city"]) and uri not in links:
                links.append(uri)
            if len(links) == MAX_DOCUMENTS:
                break
        for url in links:
            record = {"original_url": url, "status": "SOURCE_HELD"}
            try:
                pdf = (getter or fetch_document)(url, source["city"])
                if (not isinstance(pdf, bytes) or len(pdf) < 100
                        or len(pdf) > MAX_PDF_BYTES or not pdf.startswith(b"%PDF-")):
                    raise ValueError("UNEXPECTED_DOCUMENT_BYTES")
                extraction = review_bytes(pdf)
                digest = hashlib.sha256(pdf).hexdigest()
                directory = root / "OFFICIAL_DOCUMENT_CAPTURE" / slug
                directory.mkdir(parents=True, exist_ok=True)
                filepath = directory / (digest + ".pdf")
                if not filepath.exists():
                    temporary = filepath.with_suffix(".part")
                    temporary.write_bytes(pdf)
                    temporary.replace(filepath)
                record.update({
                    "status": "DOCUMENT_READ_REVIEW_ONLY",
                    "sha256": digest, "bytes": len(pdf),
                    "saved_path": str(filepath), **extraction,
                    "publication_date_verified": False,
                    "buyer_verified": False,
                })
                output["downloaded_documents"] += 1
                output["reviewed_pages"] += extraction["pages_inspected"]
            except (OSError, ValueError, PermissionError, PdfReadError,
                    TypeError, RuntimeError, requests.RequestException) as exc:
                record["reason"] = type(exc).__name__ + ": " + str(exc)[:140]
            output["documents"].append(record)
        output["status"] = (
            "ESCRIBE_DOCUMENTS_RETRIEVED_REVIEW_ONLY"
            if output["downloaded_documents"] else
            "NO_ELIGIBLE_OR_ACCESSIBLE_ESCRIBE_DOCUMENTS"
        )
        if output["downloaded_documents"]:
            temp = review_path.with_suffix(".json.tmp")
            temp.write_text(json.dumps(output, indent=2), encoding="utf-8")
            temp.replace(review_path)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        output["status"] = "INDEX_EVIDENCE_HELD_PREVIOUS_DOCUMENTS_RETAINED"
        output["failure_type"] = type(exc).__name__
    status_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--authorized-public-document-access", action="store_true",
                        help="Operator confirms permitted access for this public source")
    args = parser.parse_args()
    report = run(args.results, args.source_id, fetch=args.fetch,
                 authorized=args.authorized_public_document_access)
    print(json.dumps({k: v for k, v in report.items() if k != "documents"}, indent=2))
