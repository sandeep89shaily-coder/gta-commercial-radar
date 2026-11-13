"""Explicit, policy-checked Mississauga eSCRIBE PDF fetch and item analysis.

Manual only. Direct PDF URL MUST originate from the City's published calendar/
official council record; we do not guess DocumentIds or enumerate the service.
Dry-run unless --fetch is specified. No redirected/private/robots-denied fetch.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import socket
import tempfile
from pathlib import Path

import requests
from pypdf import PdfReader

import robots_policy
from toronto_pdf_download import public_dns
from gta_mississauga_pdc_agenda import official_pdf, run as extract_pdf

AGENT = "GTARadarResearch/1.0 (explicit official agenda research)"
HOST = "pub-mississauga.escribemeetings.com"
MAX_BYTES = 45_000_000
TIMEOUT = (8, 25)
AUDIT = "MISSISSAUGA_PDC_EXPLICIT_FETCH_AUDIT.json"


def fetch_one(url, target, *, session=None, resolver=socket.getaddrinfo,
              policy_reader=None, authorized=False):
    result = {"url": url, "status": "HOLD", "reason": "",
              "bytes": 0, "sha256": "", "saved_path": "",
              "original_publisher_publication_date_verified": False}
    try:
        official_pdf(url)
    except ValueError:
        result["reason"] = "NOT_OFFICIAL_ALLOWED_PDF_URL"
        return result
    if not authorized:
        result["reason"] = "EXPLICIT_FETCH_REQUIRED"
        return result
    if not public_dns(HOST, resolver):
        result["reason"] = "DNS_UNAVAILABLE_OR_NONPUBLIC"
        return result
    session = session or requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": AGENT, "Accept": "application/pdf"})
    allowed, reason = robots_policy.evaluate(session, url, AGENT,
                                             timeout=TIMEOUT, policy_reader=policy_reader)
    if not allowed:
        result["reason"] = reason
        return result
    temp = None
    try:
        with session.get(url, timeout=TIMEOUT, allow_redirects=False, stream=True) as response:
            if response.status_code != 200 or response.url != url:
                result["reason"] = "HTTP_OR_REDIRECT_" + str(response.status_code)
                return result
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower().strip()
            if content_type not in ("application/pdf", "application/octet-stream"):
                result["reason"] = "UNEXPECTED_CONTENT_TYPE"
                return result
            length = response.headers.get("Content-Length")
            if length:
                try:
                    if int(length) > MAX_BYTES:
                        result["reason"] = "PDF_TOO_LARGE"
                        return result
                except ValueError:
                    result["reason"] = "BAD_CONTENT_LENGTH"
                    return result
            destination = Path(target)
            destination.parent.mkdir(parents=True, exist_ok=True)
            sha = hashlib.sha256()
            count = 0
            prefix = b""
            with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".part",
                                             delete=False) as handle:
                temp = Path(handle.name)
                for piece in response.iter_content(chunk_size=65536):
                    if not piece:
                        continue
                    count += len(piece)
                    if count > MAX_BYTES:
                        result["reason"] = "PDF_TOO_LARGE"
                        return result
                    prefix = (prefix + piece)[:8] if len(prefix) < 8 else prefix
                    sha.update(piece)
                    handle.write(piece)
            if count < 100 or not prefix.startswith(b"%PDF-"):
                result["reason"] = "NOT_A_PDF"
                return result
            try:
                with temp.open("rb") as stream:
                    pdf = PdfReader(stream, strict=False)
                    if pdf.is_encrypted or len(pdf.pages) < 1:
                        raise ValueError("Encrypted or empty PDF")
            except Exception:
                result["reason"] = "CORRUPT_OR_ENCRYPTED_PDF"
                return result
            os.replace(temp, destination)
            temp = None
            result.update(status="CAPTURED", reason="OK", bytes=count,
                          sha256=sha.hexdigest(), saved_path=str(destination.resolve()))
            return result
    except (requests.RequestException, OSError) as error:
        result["reason"] = "FETCH_FAILED_" + type(error).__name__
        return result
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def batch(urls, folder, *, authorized=False, session=None,
          resolver=socket.getaddrinfo, policy_reader=None):
    if not isinstance(urls, (list, tuple)) or not 1 <= len(urls) <= 5:
        raise ValueError("ONE_TO_FIVE_EXPLICIT_OFFICIAL_URLS_REQUIRED")
    target = Path(folder)
    target.mkdir(parents=True, exist_ok=True)
    outcomes = []
    seen = set()
    for raw in urls:
        if raw in seen:
            continue
        seen.add(raw)
        filename = hashlib.sha256(str(raw).encode("utf-8")).hexdigest()[:32] + ".pdf"
        result = fetch_one(raw, target / "source_pdfs" / filename,
                           session=session, resolver=resolver,
                           policy_reader=policy_reader, authorized=authorized)
        if result["status"] == "CAPTURED":
            # Extraction output isolated per document; no cross-PDF overwrites.
            result["item_extraction"] = extract_pdf(
                result["saved_path"], raw, target / "items" / filename[:-4])
        outcomes.append(result)
    review = {
        "files_requested": len(urls), "unique_urls_considered": len(outcomes),
        "captured": sum(r["status"] == "CAPTURED" for r in outcomes),
        "blocked_or_held": sum(r["status"] != "CAPTURED" for r in outcomes),
        "records": outcomes, "verified_project_count": 0,
        "verified_early_publication_dates": 0, "paid_ai_calls": 0,
        "warning": "Explicit, permitted direct PDF URL fetch only. An eSCRIBE document ID does not prove first publication, exact project identity, or a live supplier opportunity."
    }
    (target / AUDIT).write_text(json.dumps(review, indent=2), encoding="utf-8")
    return review


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--pdf-url", required=True, nargs="+")
    cli.add_argument("--out", required=True)
    cli.add_argument("--fetch", action="store_true",
                     help="Opt in to policy-checked network retrieval")
    args = cli.parse_args()
    result = batch(args.pdf_url, args.out, authorized=args.fetch)
    print(json.dumps({k: result[k] for k in (
        "files_requested", "captured", "blocked_or_held",
        "verified_project_count", "paid_ai_calls")}, indent=2))
