"""Source-checked Brampton PDC featured application collector (research only).

The City of Brampton publicly links to its PDC engagement page:
https://letsconnect.brampton.ca/yourcityplans
It publishes selected planning applications, not a complete listing. Neither the
meeting date nor our first observation proves original publication or tender.
Only explicit --fetch may use network. No paid AI and no main Radar DB writes.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import re
import socket
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import requests

import robots_policy
from toronto_pdf_download import public_dns

SOURCE = "https://letsconnect.brampton.ca/yourcityplans"
AGENT = "GTARadarResearch/1.0 (public Brampton PDC application evidence)"
TIMEOUT = (7, 20)
MAX_HTML_BYTES = 2_000_000
MAX_ITEMS = 40
LEDGER = "BRAMPTON_PDC_FEATURED_APPLICATION_LEDGER.json"
CSV = "BRAMPTON_PDC_FEATURED_APPLICATIONS_REVIEW.csv"
STATUS = "BRAMPTON_PDC_FEATURED_APPLICATION_STATUS.json"
FIELDS = (
    "city", "application_id", "meeting_date_text", "applicant_or_agent_text",
    "ward_text", "location_text", "purpose_text", "source_url", "source_sha256",
    "first_observed_utc", "last_observed_utc", "change_event",
    "evidence_level", "original_publication_date_verified",
    "project_verified", "buyer_verified", "open_procurement_verified"
)
FEATURED = re.compile(
    r"Featured\s+Application\s*:\s*"
    r"([A-Za-z]+\s+\d{1,2},\s*20\d{2})", re.I)
FILE_ID = re.compile(r"\b(?:City\s+File)\s*:\s*([A-Z]{2,5}-20\d{2}-\d{3,6})\b", re.I)
WARD = re.compile(r"\bWard\s+\d{1,2}\b", re.I)
NEXT = re.compile(r"\b(?:About\s+the\s+PDC|Featured\s+Application)\s*:?", re.I)
RETAIL = re.compile(r"\b(?:commercial|industrial|office|warehouse|factory|"
                    r"employment|manufactur\w*|business|retail)\b", re.I)


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.tokens = []
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.hidden += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self.hidden:
            self.hidden -= 1
    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.tokens.append(data.strip())


def parse(markup):
    """Extract explicit source text only; ambiguous or incomplete cards held."""
    if not isinstance(markup, str) or len(markup.encode("utf-8")) > MAX_HTML_BYTES:
        raise ValueError("HTML_MISSING_OR_TOO_LARGE")
    visible = _VisibleText()
    visible.feed(markup)
    plain = " ".join(" ".join(visible.tokens).split())
    starts = list(FEATURED.finditer(plain))
    if len(starts) > MAX_ITEMS:
        raise ValueError("TOO_MANY_FEATURED_APPLICATIONS")
    by_id = {}
    held = 0
    for i, heading in enumerate(starts):
        excerpt = plain[heading.end():starts[i + 1].start() if i + 1 < len(starts) else len(plain)]
        # A repeat of the same page content in responsive desktop/mobile
        # components is allowed if actual source fields are identical.
        terminator = NEXT.search(excerpt)
        if terminator:
            excerpt = excerpt[:terminator.start()]
        found = FILE_ID.search(excerpt)
        location = re.search(r"\bLocation\b\s*(.*?)\s+\bPurpose\b", excerpt, re.I)
        purpose = re.search(r"\bPurpose\b\s*(.*)$", excerpt, re.I)
        if not found or not location or not purpose:
            held += 1
            continue
        identity = found.group(1).upper()
        source_intro = excerpt[:found.start()]
        applicant = " ".join(source_intro.strip(" ,–-").split())[:280]
        loc = " ".join(location.group(1).split())[:350]
        ptext = " ".join(purpose.group(1).split())[:1400]
        if not applicant or not loc or len(ptext) < 20:
            held += 1
            continue
        ward = WARD.search(excerpt)
        detail = {
            "city": "Brampton", "application_id": identity,
            "meeting_date_text": heading.group(1),
            "applicant_or_agent_text": applicant,
            "ward_text": ward.group(0) if ward else "",
            "location_text": loc, "purpose_text": ptext,
            "source_url": SOURCE,
            "evidence_level": "OFFICIAL_LINKED_ENGAGEMENT_PAGE_REVIEW_ONLY",
            "original_publication_date_verified": False,
            "project_verified": False, "buyer_verified": False,
            "open_procurement_verified": False
        }
        previous = by_id.get(identity)
        if previous:
            if any(previous[k] != detail[k] for k in
                   ("meeting_date_text", "applicant_or_agent_text", "location_text", "purpose_text")):
                held += 1
                by_id.pop(identity, None)
                continue
        else:
            by_id[identity] = detail
    return list(by_id.values()), held, bool(starts)


def _read_ledger(path):
    if not path.is_file():
        return {}
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("version") != 1 or not isinstance(obj.get("items"), dict):
        raise ValueError("UNRECOGNIZED_FEATURED_APPLICATION_LEDGER")
    return obj["items"]


def _download(*, session=None, resolver=socket.getaddrinfo, policy_reader=None):
    host = urlsplit(SOURCE).hostname
    if not public_dns(host, resolver):
        raise ValueError("SOURCE_DNS_UNAVAILABLE_OR_NONPUBLIC")
    session = session or requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": AGENT, "Accept": "text/html"})
    allowed, reason = robots_policy.evaluate(
        session, SOURCE, AGENT, timeout=TIMEOUT, policy_reader=policy_reader)
    if not allowed:
        raise PermissionError("SOURCE_ROBOTS_" + reason)
    with session.get(SOURCE, timeout=TIMEOUT, allow_redirects=False, stream=True) as result:
        if result.status_code != 200 or result.url != SOURCE:
            raise ValueError("SOURCE_HTTP_OR_REDIRECT_" + str(result.status_code))
        mime = result.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if mime not in ("text/html", "application/xhtml+xml"):
            raise ValueError("NOT_HTML_SOURCE")
        buf = bytearray()
        for chunk in result.iter_content(chunk_size=65536):
            if chunk:
                buf.extend(chunk)
                if len(buf) > MAX_HTML_BYTES:
                    raise ValueError("SOURCE_HTML_TOO_LARGE")
        return bytes(buf).decode("utf-8", "replace")


def run(folder, *, fetch=False, markup=None, now=None, session=None,
        resolver=socket.getaddrinfo, policy_reader=None):
    out = Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    at = now or dt.datetime.now(dt.timezone.utc)
    if at.tzinfo is None:
        raise ValueError("TIMEZONE_AWARE_NOW_REQUIRED")
    stamp = at.astimezone(dt.timezone.utc).isoformat()
    result = {
        "city": "Brampton", "source_url": SOURCE,
        "checked_utc": stamp, "status": "HOLD",
        "cards_parsed": 0, "commercial_keyword_cards_review_only": 0,
        "newly_observed_cards_not_new_publications": 0,
        "changed_cards_not_new_projects": 0, "first_publications_verified": 0,
        "verified_projects": 0, "verified_buyers": 0,
        "paid_ai_calls": 0, "cumulative_records_preserved": 0,
        "warning": "Featured applications are selected examples, not complete or current citywide coverage. Meeting date is not publication date; no open contract claims."
    }
    try:
        if markup is None:
            if not fetch:
                result["status"] = "DRY_RUN_EXPLICIT_FETCH_REQUIRED"
                return result
            markup = _download(session=session, resolver=resolver,
                               policy_reader=policy_reader)
        fingerprint = hashlib.sha256(markup.encode("utf-8")).hexdigest()
        cards, holds, headings_found = parse(markup)
        result.update(source_sha256=fingerprint, incomplete_cards_held=holds,
                      cards_parsed=len(cards),
                      commercial_keyword_cards_review_only=sum(
                          bool(RETAIL.search(x["purpose_text"])) for x in cards))
        if not headings_found or not cards:
            result["status"] = "SOURCE_STRUCTURE_UNVERIFIED_OR_EMPTY_HOLD"
            result["warning"] += " No ledger mutation on zero-parse source."
            return result
        ledger_path = out / LEDGER
        prior = _read_ledger(ledger_path)
        future = dict(prior)
        delta = []
        for card in cards:
            appid = card["application_id"]
            old = prior.get(appid)
            cardhash = hashlib.sha256(json.dumps({
                key: card[key] for key in ("meeting_date_text",
                    "applicant_or_agent_text", "location_text", "purpose_text")
            }, sort_keys=True).encode()).hexdigest()
            event = ("FIRST_LOCAL_OBSERVATION_NOT_NEW_PUBLICATION" if old is None
                     else "SOURCE_CARD_TEXT_CHANGED_NOT_NEW_PROJECT"
                     if old.get("source_card_sha256") != cardhash
                     else "UNCHANGED")
            row = dict(card, source_sha256=fingerprint,
                       first_observed_utc=old.get("first_observed_utc", stamp) if old else stamp,
                       last_observed_utc=stamp, change_event=event)
            future[appid] = {
                "application_id": appid, "first_observed_utc": row["first_observed_utc"],
                "last_observed_utc": stamp, "source_card_sha256": cardhash,
                "latest_source_sha256": fingerprint
            }
            delta.append(row)
        with (out / CSV).open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            writer.writeheader()
            for row in delta:
                safe = {k: ("'" + v if isinstance(v, str) and
                         v.lstrip().startswith(("=", "+", "-", "@")) else v)
                         for k, v in row.items()}
                writer.writerow(safe)
        temp = out / (LEDGER + ".tmp")
        temp.write_text(json.dumps({"version": 1, "items": future}, indent=2),
                        encoding="utf-8")
        temp.replace(ledger_path)
        result.update(
            status="FEATURED_APPLICATIONS_REVIEW_ONLY",
            newly_observed_cards_not_new_publications=sum(
                x["change_event"].startswith("FIRST_LOCAL") for x in delta),
            changed_cards_not_new_projects=sum(
                x["change_event"].startswith("SOURCE_CARD_TEXT") for x in delta),
            cumulative_records_preserved=len(future))
    except Exception as exc:
        # Inaccessible publisher or changed HTML is NOT a successful zero.
        result["status"] = "SOURCE_BLOCKED_OR_PARSER_FAILURE_NO_LEDGER_MUTATION"
        result["failure_type"] = type(exc).__name__
        result["failure_reason"] = str(exc)[:180]
    finally:
        (out / STATUS).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--out", required=True)
    cli.add_argument("--fetch", action="store_true", help="Explicitly check official public source")
    args = cli.parse_args()
    print(json.dumps(run(args.out, fetch=args.fetch), indent=2))


if __name__ == "__main__":
    main()
