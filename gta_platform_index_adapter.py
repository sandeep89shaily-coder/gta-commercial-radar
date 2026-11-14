"""Reusable, opt-in source-index intake for explicitly registered municipality pages.

This is a bounded manual HTML index adapter, NOT a third-party eSCRIBE API
adapter. It never guesses endpoints, bypasses robots/403, downloads linked
documents, or promotes links to projects. Existing collectors stay unchanged.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import socket
from pathlib import Path
from urllib.parse import urlsplit

import requests

import robots_policy
from gta_municipal_platform_registry import build as platform_registry
from municipal_meeting_capture import _agenda_candidates
from toronto_pdf_download import public_dns

AGENT = "GTARadarResearch/1.0 (municipal index research; contact publisher for access)"
MAX_BYTES = 1_500_000
TIMEOUT = (8, 20)
STATUS = "GTA_RADAR_PLATFORM_INDEX_PILOT_STATUS.json"
EVIDENCE = "GTA_RADAR_PLATFORM_INDEX_PILOT_EVIDENCE.json"


def _exact_index(url):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname
            or parsed.username or parsed.password or parsed.fragment
            or parsed.port not in (None, 443)
            or parsed.hostname.casefold() in ("localhost", "127.0.0.1", "::1")):
        raise ValueError("REGISTERED_HTTPS_INDEX_REQUIRED")
    return url


def fetch_index(url, *, session=None, resolver=None, policy_reader=None):
    """Fetch one exact registered HTML URL after policy and DNS checks."""
    url = _exact_index(url)
    host = urlsplit(url).hostname
    if not public_dns(host, resolver or socket.getaddrinfo):
        raise PermissionError("PUBLIC_DNS_NOT_ESTABLISHED")
    own = session is None
    sess = session or requests.Session()
    if own:
        sess.trust_env = False
    try:
        allowed, reason = robots_policy.evaluate(
            sess, url, AGENT, timeout=TIMEOUT, policy_reader=policy_reader)
        if not allowed:
            raise PermissionError("ROBOTS_" + str(reason))
        with sess.get(url, timeout=TIMEOUT, stream=True, allow_redirects=False,
                      headers={"User-Agent": AGENT, "Accept": "text/html"}) as resp:
            if resp.status_code in (401, 403, 429):
                raise PermissionError("SOURCE_ACCESS_DENIED_" + str(resp.status_code))
            if resp.status_code != 200 or resp.history:
                raise ValueError("SOURCE_HTTP_OR_REDIRECT_" + str(resp.status_code))
            actual = urlsplit(resp.url)
            expected = urlsplit(url)
            if (actual.scheme != expected.scheme or
                    actual.hostname != expected.hostname or
                    actual.path != expected.path or
                    actual.query != expected.query):
                raise ValueError("SOURCE_ORIGIN_CHANGED")
            content_type = resp.headers.get("Content-Type", "").lower().split(";")[0].strip()
            if content_type not in ("text/html", "application/xhtml+xml"):
                raise ValueError("SOURCE_MIME_NOT_HTML")
            chunks = bytearray()
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    chunks.extend(chunk)
                    if len(chunks) > MAX_BYTES:
                        raise ValueError("SOURCE_HTML_TOO_LARGE")
            return bytes(chunks)
    finally:
        if own:
            sess.close()


def run(results, source_id, *, fetch=False, getter=None, now=None):
    """Only explicit manual fetch=True performs network; preserve good snapshots."""
    results = Path(results)
    results.mkdir(parents=True, exist_ok=True)
    registry = platform_registry()
    matches = [x for x in registry["sources"] if x["source_id"] == source_id]
    if len(matches) != 1:
        raise ValueError("SOURCE_ID_NOT_IN_OFFICIAL_REGISTRY")
    item = matches[0]
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", source_id):
        raise ValueError("INVALID_SOURCE_ID_FOR_OUTPUT")
    evidence_file = "GTA_RADAR_PLATFORM_INDEX_" + source_id.upper() + "_EVIDENCE.json"
    status_file = "GTA_RADAR_PLATFORM_INDEX_" + source_id.upper() + "_STATUS.json"
    at = now or dt.datetime.now(dt.timezone.utc).isoformat()
    status = {
        "status": "NOT_FETCHED_MANUAL_OPT_IN_REQUIRED",
        "source_id": source_id,
        "city": item["city"],
        "platform": item["platform"],
        "original_index_url": item["official_index_url"],
        "checked_utc": at,
        "official_document_links_read": 0,
        "documents_downloaded": 0,
        "publisher_first_publications_verified": 0,
        "verified_projects": 0,
        "buyers_verified": 0,
        "paid_ai_usd": 0,
    }
    if fetch:
        try:
            source = item["official_index_url"]
            data = (getter or fetch_index)(source)
            if not isinstance(data, bytes) or len(data) > MAX_BYTES:
                raise ValueError("UNEXPECTED_HTML_BYTES")
            markup = data.decode("utf-8", "replace")
            # Reuse the existing strict municipal agenda document qualification.
            candidates = _agenda_candidates(markup, item["city"], source)
            document = {
                "source_id": source_id, "city": item["city"],
                "original_index_url": source,
                "index_sha256": hashlib.sha256(data).hexdigest(),
                "checked_utc": at,
                "document_links": candidates,
                "links_only_not_downloaded": True,
                "source_first_publication_verified": False,
                "verified_project_count": 0,
            }
            # Atomic replacement only after successful exact-source processing;
            # previous good evidence is never destroyed by blocked fetches.
            outfile = results / evidence_file
            tmp = outfile.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(document, indent=2), encoding="utf-8")
            tmp.replace(outfile)
            status.update({
                "status": "INDEX_FETCHED_DOCUMENT_LINKS_REVIEW_ONLY"
                          if candidates else "INDEX_FETCHED_ZERO_ELIGIBLE_LINKS",
                "official_document_links_read": len(candidates),
                "index_sha256": document["index_sha256"],
            })
        except (OSError, ValueError, TypeError, PermissionError,
                requests.RequestException) as exc:
            status.update({
                "status": "SOURCE_BLOCKED_OR_FAILED_PREVIOUS_EVIDENCE_PRESERVED",
                "reason": type(exc).__name__,
                "detail": str(exc)[:180],
            })
    (results / status_file).write_text(json.dumps(status, indent=2),
                                  encoding="utf-8")
    return status


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--fetch", action="store_true",
                        help="Explicitly opt in to one protected index fetch")
    parser.add_argument("--fetch-direct-pdfs", action="store_true",
                        help="After a successful --fetch, retrieve at most three same-official-host direct PDFs")
    a = parser.parse_args()
    if a.fetch_direct_pdfs and not a.fetch:
        parser.error("--fetch-direct-pdfs requires --fetch")
    status = run(a.results, a.source_id, fetch=a.fetch)
    if a.fetch_direct_pdfs:
        if status["status"] == "INDEX_FETCHED_DOCUMENT_LINKS_REVIEW_ONLY":
            from gta_official_platform_pdf_intake import run as run_pdfs
            status["pdf_intake"] = {
                k: v for k, v in run_pdfs(
                    a.results, a.source_id, fetch=True).items() if k != "documents"
            }
        else:
            status["pdf_intake"] = {"status": "NOT_RUN_INDEX_NOT_VERIFIED"}
    print(json.dumps(status, indent=2))
