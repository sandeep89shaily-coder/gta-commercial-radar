"""Bounded, permission-checked Toronto TMMIS public agenda fetch.

Only explicitly registered *exact* real official meeting URLs are eligible;
meeting IDs are never guessed or enumerated. Read-only, manual full-run only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import socket
from pathlib import Path

import requests

import robots_policy
from toronto_pdf_download import public_dns
from toronto_tmmis_documents import agenda_url
from gta_toronto_agenda_item_extraction import build as extract_items

MAX_HTML_BYTES = 8_000_000
MAX_MEETINGS = 3
AGENT = "GTARadarResearch/1.0 (explicit public Toronto TMMIS agenda research)"
TIMEOUT = (8, 25)
STATUS = "TORONTO_TMMIS_EXACT_AGENDA_CAPTURE_STATUS.json"


def fetch_one(url, *, session=None, resolver=socket.getaddrinfo,
              policy_reader=None, authorized=False):
    result = {"meeting_url": url, "status": "HOLD", "reason": "",
              "html_bytes": 0, "source_html_sha256": "",
              "first_published_at_verified": False}
    if not agenda_url(url):
        result["reason"] = "INVALID_OFFICIAL_MEETING_URL"
        return result, None
    if not authorized:
        result["reason"] = "EXPLICIT_MANUAL_FETCH_REQUIRED"
        return result, None
    if not public_dns("secure.toronto.ca", resolver):
        result["reason"] = "PUBLIC_DNS_UNAVAILABLE"
        return result, None
    session = session or requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": AGENT, "Accept": "text/html"})
    allowed, reason = robots_policy.evaluate(
        session, url, AGENT, timeout=TIMEOUT, policy_reader=policy_reader)
    if not allowed:
        result["reason"] = "SOURCE_POLICY_" + reason
        return result, None
    try:
        with session.get(url, timeout=TIMEOUT, allow_redirects=False,
                         stream=True) as response:
            if response.status_code != 200 or response.url != url:
                result["reason"] = "HTTP_OR_REDIRECT_" + str(response.status_code)
                return result, None
            mime = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if mime not in ("text/html", "application/xhtml+xml"):
                result["reason"] = "UNEXPECTED_CONTENT_TYPE"
                return result, None
            data = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    data.extend(chunk)
                    if len(data) > MAX_HTML_BYTES:
                        result["reason"] = "AGENDA_HTML_TOO_LARGE"
                        return result, None
            if not data:
                result["reason"] = "AGENDA_HTML_EMPTY"
                return result, None
            markup = bytes(data).decode("utf-8", "replace")
            result.update(status="FETCHED_FOR_ITEM_REVIEW",
                          reason="OK",
                          html_bytes=len(data),
                          source_html_sha256=hashlib.sha256(
                              markup.encode("utf-8")).hexdigest())
            return result, markup
    except (requests.RequestException, OSError) as exc:
        result["reason"] = "FETCH_FAILED_" + type(exc).__name__
        return result, None


def run(urls, output, *, authorized=False, fetcher=None):
    if not isinstance(urls, (list, tuple)) or not 1 <= len(urls) <= MAX_MEETINGS:
        raise ValueError("ONE_TO_THREE_EXACT_MEETING_URLS_REQUIRED")
    if any(not agenda_url(url) for url in urls):
        raise ValueError("NON_TMMIS_AGENDA_URL_REFUSED")
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    seen = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        outcome, markup = (fetcher or fetch_one)(url, authorized=authorized)
        if outcome["status"] == "FETCHED_FOR_ITEM_REVIEW" and markup is not None:
            name = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
            folder = root / "meetings" / name
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "official_agenda_saved.html").write_text(markup, encoding="utf-8")
            try:
                parsed = extract_items(folder / "official_agenda_saved.html", url, folder)
                if parsed["item_count"] == 0:
                    outcome["status"] = "AGENDA_STRUCTURE_NOT_RECOVERED"
                else:
                    outcome["status"] = "AGENDA_ITEMS_REVIEW_ONLY"
                    outcome["items"] = parsed["item_count"]
                    outcome["research_candidate_titles"] = parsed["research_candidate_titles"]
                    outcome["report_path"] = str(folder)
            except (OSError, ValueError, TypeError) as exc:
                outcome["status"] = "AGENDA_ITEM_PARSER_FAILURE"
                outcome["reason"] = type(exc).__name__
        rows.append(outcome)
    summary = {
        "status": "REVIEW_ONLY_OFFICIAL_TMMIS_AGENDA_FETCH",
        "meetings_considered": len(rows),
        "meetings_with_items": sum(r["status"] == "AGENDA_ITEMS_REVIEW_ONLY"
                                  for r in rows),
        "meeting_results": rows,
        "verified_original_publication_dates": 0,
        "verified_projects": 0,
        "verified_buyers": 0,
        "verified_open_procurement": 0,
        "paid_ai_calls": 0,
        "warning": "Exact official TMMIS agendas only. Meeting dates and first observed timestamps do not establish original publication or newly available work."
    }
    (root / STATUS).write_text(json.dumps(summary, indent=2),
                               encoding="utf-8")
    return summary


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--meeting-url", nargs="+", required=True)
    cli.add_argument("--out", required=True)
    cli.add_argument("--fetch", action="store_true")
    args = cli.parse_args()
    result = run(args.meeting_url, args.out, authorized=args.fetch)
    print(json.dumps({k: result[k] for k in (
        "status", "meetings_considered", "meetings_with_items",
        "paid_ai_calls")}, indent=2))


if __name__ == "__main__":
    main()
