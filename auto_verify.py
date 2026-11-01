"""Automatic, deterministic verification of evidence claims against the real source page.

Claims may come from a person, from AI research, or from a collector. Nothing is
trusted until code has fetched the official page (robots-checked) and confirmed that
the quoted text is actually on it. No AI is used here, so a fabricated or mistaken
quote cannot pass.

What can be automated (AUTOMATABLE_FIELDS in reviewed_evidence): project source,
project identity on an official government page, scope, the owner organization named
by its own press release or website, a public contact route, and first-publication
date. What cannot: buying authority and supplier availability. Those are judgments;
this module confirms the quote exists and hands them to a human as a ready-to-confirm
draft, flagged NEEDS_HUMAN_CONFIRMATION.

Writes ONLY AUTO_VERIFIED_EVIDENCE.json (its own file). Human-maintained
REVIEWED_EVIDENCE.json is never touched; the gate overlays the two.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse

import requests

import robots_policy
import reviewed_evidence as gate
from gta_verified_source_pipeline import AGENT

VERSION = "auto_verify/1"
AUTO_FILE = "AUTO_VERIFIED_EVIDENCE.json"
MAX_BYTES = 2_000_000
OFFICIAL_DOMAINS = (
    "gc.ca", "canada.ca", "gov.on.ca", "ontario.ca", "toronto.ca", "brampton.ca", "mississauga.ca",
    "peelregion.ca", "york.ca", "halton.ca", "durham.ca", "hamilton.ca", "regionofwaterloo.ca",
    "niagararegion.ca", "burlington.ca", "oakville.ca", "milton.ca", "markham.ca", "vaughan.ca",
    "richmondhill.ca", "caledon.ca", "pickering.ca", "ajax.ca", "oshawa.ca", "whitby.ca",
    "kitchener.ca", "waterloo.ca", "cambridge.ca", "guelph.ca", "stcatharines.ca", "merx.com")
WIRE_DOMAINS = ("newswire.ca", "prnewswire.com", "globenewswire.com", "businesswire.com")
_CORP_WORDS = {"inc", "ltd", "limited", "corp", "corporation", "company", "co", "operative", "cooperative",
               "group", "holdings", "canada", "the", "of", "and", "lp", "llp", "ulc"}
_DATE_PATTERNS = (
    r"meta-date:\s*(\d{4}-\d{2}-\d{2})",
    r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})',
    r'article:published_time"?\s+content="(\d{4}-\d{2}-\d{2})',
    r"<time[^>]*datetime=\"(\d{4}-\d{2}-\d{2})",
)


def norm(text):
    """Case-fold and keep only letters/digits as single-spaced words (tolerates markdown and spacing)."""
    return re.sub(r"[^0-9a-z]+", " ", str(text or "").casefold()).strip()


def excerpt_present(page_text, excerpt):
    e = norm(excerpt)
    return len(e) >= 20 and e in norm(page_text)


def _registrable(host):
    host = (host or "").lower()
    for domain in OFFICIAL_DOMAINS + WIRE_DOMAINS:
        if host == domain or host.endswith("." + domain):
            return domain
    labels = host.split(".")
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def _distinctive_tokens(organization):
    return [t for t in norm(organization).split() if t not in _CORP_WORDS]


def classify_source(url, page_text, organization):
    """OFFICIAL_GOVERNMENT | PRESS_RELEASE_BY_PARTY | COMPANY_OWNED | None."""
    host = urlparse(url).hostname or ""
    site = _registrable(host)
    if site in OFFICIAL_DOMAINS:
        return "OFFICIAL_GOVERNMENT"
    org = norm(organization)
    page = norm(page_text)
    if site in WIRE_DOMAINS:
        # The wire page must say the organization itself issued it.
        if org and (f"news provided by {org}" in page or f"source {org}" in page):
            return "PRESS_RELEASE_BY_PARTY"
        return None
    tokens = _distinctive_tokens(organization)
    label = site.split(".")[0].replace("-", "")
    candidates = {"".join(tokens[:n]) for n in (1, 2, 3) if len(tokens) >= n}
    if label and label in candidates and org and org in page:
        return "COMPANY_OWNED"           # exact match on the company's own name, no look-alike extras
    return None


def parse_published_date(page_text):
    for pattern in _DATE_PATTERNS:
        m = re.search(pattern, page_text or "")
        if m:
            try:
                return dt.date.fromisoformat(m.group(1)).isoformat()
            except ValueError:
                continue
    return None


def fetch_page(url, session=None, today=None):
    """Robots-checked fetch. Returns {'ok', 'reason', 'url', 'text', 'sha256', 'fetched_at'}."""
    session = session or requests.Session()
    fetched_at = (today or dt.date.today()).isoformat()
    if urlparse(url).scheme != "https":
        return {"ok": False, "reason": "NOT_HTTPS"}
    allowed, reason = robots_policy.evaluate(session, url, AGENT)
    if not allowed:
        return {"ok": False, "reason": reason}
    try:
        r = session.get(url, timeout=25, headers={"User-Agent": AGENT}, allow_redirects=True)
    except requests.RequestException as exc:
        return {"ok": False, "reason": "FETCH_ERROR:" + type(exc).__name__}
    if r.status_code != 200:
        return {"ok": False, "reason": f"HTTP_{r.status_code}"}
    final = getattr(r, "url", url) or url
    if _registrable(urlparse(final).hostname) != _registrable(urlparse(url).hostname):
        return {"ok": False, "reason": "REDIRECTED_TO_OTHER_SITE"}
    raw = bytes(r.content[:MAX_BYTES]) if isinstance(getattr(r, "content", None), (bytes, bytearray)) else (r.text or "").encode()[:MAX_BYTES]
    return {"ok": True, "reason": "", "url": final, "text": raw.decode("utf-8", "replace"),
            "sha256": hashlib.sha256(raw).hexdigest(), "fetched_at": fetched_at}


def verify_claim(field, claim, organization, fetcher, today=None):
    """Return (entry, problems, automated). `entry` is always a complete evidence record."""
    today = today or dt.date.today()
    url = str(claim.get("official_url") or "")
    excerpt = str(claim.get("excerpt") or "")
    problems = []
    page = fetcher(url)
    if not page.get("ok"):
        return None, [f"could not fetch the source ({page.get('reason')})"], False
    text = page["text"]
    if not excerpt_present(text, excerpt):
        problems.append("the quoted excerpt is not on the page")
    source_class = classify_source(page["url"], text, organization)
    if source_class is None:
        problems.append(f"page is not an official, government or own-organization source for {organization or 'the project'}")
    entry = {"source_class": source_class or "UNVERIFIED_SOURCE", "official_url": page["url"], "excerpt": excerpt,
             "retrieved_at": today.isoformat()}
    for key in ("organization", "authority_basis", "person_or_role", "contact_url", "contact_kind",
                "contact_purpose", "procurement_basis", "checked_at"):
        if claim.get(key):
            entry[key] = claim[key]
    if field in ("buyer_org_evidence", "buying_authority_evidence") and organization:
        entry["organization"] = organization
        if norm(organization) not in norm(excerpt):
            problems.append("organization name is not in the quoted excerpt")
    if field == "source_first_publication":
        found = parse_published_date(text)
        claimed = claim.get("published_at")
        if not found:
            problems.append("could not read a publication date from the page")
        elif claimed and str(claimed)[:10] != found:
            problems.append(f"claimed publication date {claimed} does not match the page ({found})")
        else:
            entry["published_at"] = found
    if field == "project_identity":
        tokens = [str(t) for t in claim.get("identity_tokens") or []]
        if source_class != "OFFICIAL_GOVERNMENT":
            problems.append("project identity is only automated from an official government page")
        if not tokens or not all(norm(t) in norm(excerpt) and norm(t) in norm(text) for t in tokens):
            problems.append("identity tokens (permit number or address) must appear in the excerpt and the page")
    if field == "contact_route_evidence":
        value = str(claim.get("contact_value") or "")
        if not value or norm(value) not in norm(text):
            problems.append("the published contact detail was not found on the page")
        if _registrable(urlparse(str(claim.get("contact_url") or "")).hostname) != _registrable(urlparse(page["url"]).hostname):
            problems.append("contact page must be on the same site as the source")
    automated = field in gate.AUTOMATABLE_FIELDS and not problems
    if automated:
        entry.update({"verification_method": gate.AUTOMATED_METHOD, "match_confirmed": True,
                      "verifier_version": VERSION, "content_sha256": page["sha256"],
                      "fetched_at": page["fetched_at"]})
    else:
        entry["reviewer_confirmed"] = False        # a human must confirm this one
    return entry, problems, automated


def build_review(spec, fetcher, today=None):
    """spec: project_id, address, project_name, organization, supplier_status,
    service_categories, claims{field: {...}}. Returns (review, report)."""
    today = today or dt.date.today()
    organization = str(spec.get("organization") or "")
    evidence, report = {}, {}
    for field in gate.MILESTONE_FIELDS:
        claim = (spec.get("claims") or {}).get(field)
        if not claim:
            report[field] = {"status": "NO_CLAIM", "problems": ["no source proposed yet"]}
            continue
        entry, problems, automated = verify_claim(field, claim, organization, fetcher, today)
        if entry is not None:
            evidence[field] = entry
        if automated:
            report[field] = {"status": "AUTO_VERIFIED", "problems": []}
        elif entry is not None and not problems and field in gate.HUMAN_ONLY_FIELDS:
            report[field] = {"status": "NEEDS_HUMAN", "problems": ["quote confirmed on the page; a person must confirm the judgment"]}
        else:
            report[field] = {"status": "FAILED", "problems": problems or ["not automatable"]}
    review = {"project_id": spec["project_id"], "address": spec.get("address", ""),
              "project_name": spec.get("project_name", ""),
              "supplier_status": spec.get("supplier_status", "UNKNOWN"),
              "service_categories": spec.get("service_categories", []), "evidence": evidence}
    return review, report


def write_auto_file(folder, reviews, today=None):
    """Update ONLY this module's own file, atomically. Never touches REVIEWED_EVIDENCE.json."""
    path = Path(folder) / AUTO_FILE
    existing = {}
    if path.is_file():
        try:
            existing = {r["project_id"]: r for r in json.loads(path.read_text(encoding="utf-8")).get("reviews", [])}
        except (OSError, ValueError, KeyError, TypeError):
            existing = {}
    for review in reviews:
        existing[review["project_id"]] = review
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"written_by": VERSION, "reviews": list(existing.values())}, indent=2), encoding="utf-8")
    if path.exists():
        history=Path(folder)/'AUTO_VERIFIED_EVIDENCE_HISTORY'
        history.mkdir(parents=True,exist_ok=True)
        stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        shutil.copy2(path,history/(stamp+'.json'))
    os.replace(tmp, path)
    return path


def main(argv=None):
    p = argparse.ArgumentParser(description="Verify claimed evidence against the real official pages (no AI, no paid calls).")
    p.add_argument("--spec", required=True, help="JSON file: {'projects': [spec, ...]}")
    p.add_argument("--results", required=True, help="Results folder to receive AUTO_VERIFIED_EVIDENCE.json")
    a = p.parse_args(argv)
    specs = json.loads(Path(a.spec).read_text(encoding="utf-8-sig")).get("projects", [])
    session = requests.Session()
    reviews = []
    for spec in specs:
        review, report = build_review(spec, lambda u: fetch_page(u, session))
        reviews.append(review)
        print(f"\n{spec['project_id']}")
        for field, info in report.items():
            print(f"  {info['status']:13s} {field}" + ("  - " + "; ".join(info["problems"]) if info["problems"] else ""))
    if reviews:
        print("\nWritten:", write_auto_file(a.results, reviews))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
