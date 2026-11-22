"""Link already-captured official municipal PDFs to Radar's document evidence.

This fills the gap between the normal daily official PDF capture audits and
the explicit manual council-PDF manifest. It only reads captured documents,
checks original SHA256 and trusted city-host provenance, and extracts bounded
page-cited text. NO new network, OCR, paid calls, buyer, project or first-posting
assertions. Exact application IDs are *text-mention review*, not identity proof.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, unquote

from pypdf import PdfReader
from gta_registered_document_evidence import TERMS

OUT = "COUNCIL_CAPTURED_PDF_BRIDGE"
AUDITS = (
    "DAILY_INTEGRATED_REVIEW/TORONTO_DOCUMENTS/COMBINED_PDF_FETCH_AUDIT.csv",
    "DAILY_INTEGRATED_REVIEW/OTHER_CITY_DOCUMENTS/MULTICITY_PDF_FETCH_AUDIT.csv",
    # The full November 22 export stores verified PDF audits here, not in
    # DAILY_INTEGRATED_REVIEW. Both locations are searched; SHA deduplicates.
    "TOTAL_INTELLIGENCE_REVIEW/MEETING_DOCUMENTS/Toronto/COMBINED_PDF_FETCH_AUDIT.csv",
    "TOTAL_INTELLIGENCE_REVIEW/MEETING_DOCUMENTS/Toronto/AUTOMATIC_PDF_FETCH_AUDIT.csv",
)
HOSTS = {
    "Toronto": ("www.toronto.ca", "toronto.ca"),
    "Brampton": ("www1.brampton.ca", "www.brampton.ca", "brampton.ca"),
    "Mississauga": ("www.mississauga.ca", "mississauga.ca"),
}
MAX_FILES = 35
MAX_SIZE = 15_000_000
MAX_PAGES = 50
MAX_SEGMENTS = 12
HOLD_WORDS = ("calendar", "at a glance", "meeting dates", "schedule")


def _existing_file(results, declared):
    """Convert Windows capture path to a file inside existing RESULTS."""
    value = str(declared or "").replace("\\", "/")
    prefix = "GTA_RADAR_RESULTS/"
    if prefix not in value:
        return None
    relative = value.split(prefix, 1)[1]
    candidate = (Path(results).resolve() / relative).resolve()
    if not candidate.is_relative_to(Path(results).resolve()):
        return None
    return candidate if candidate.is_file() and candidate.suffix.lower() == ".pdf" else None


def _application_ids(results):
    ids = set()
    for file in ("GTA_RADAR_PRIVATE_TOP_10.csv",
                 "GTA_RADAR_PRIVATE_DEVELOPMENT_REVIEW.csv"):
        path = Path(results) / file
        if not path.is_file():
            continue
        with path.open(encoding="utf-8-sig", newline="") as fp:
            for row in csv.DictReader(fp):
                for raw in re.split(r"[;|,]", str(
                        row.get("application_ids") or
                        row.get("application_id") or "")):
                    raw = raw.strip()
                    if len(raw) >= 6 and any(c.isdigit() for c in raw):
                        ids.add(raw)
    return sorted(ids, key=len, reverse=True)


def review(results, *, now=None):
    root = Path(results)
    if not root.is_dir():
        raise FileNotFoundError("EXISTING_RESULTS_REQUIRED")
    report = root / OUT
    report.mkdir(parents=True, exist_ok=True)
    entries, seen = [], set()
    ids = _application_ids(root)
    for audit in AUDITS:
        path = root / audit
        if not path.is_file():
            continue
        with path.open(encoding="utf-8-sig", newline="") as fp:
            for row in csv.DictReader(fp):
                if row.get("status") != "CAPTURED":
                    continue
                url = str(row.get("url") or "")
                parsed = urlsplit(url)
                city = row.get("city") or (
                    "Toronto" if any(part in ("/" + audit).upper()
                    for part in ("/TORONTO_DOCUMENTS/", "/MEETING_DOCUMENTS/TORONTO/"))
                    else "")
                if city not in HOSTS or parsed.scheme != "https" or (
                        parsed.hostname or "").lower() not in HOSTS[city]:
                    continue
                sha = str(row.get("sha256") or "").lower()
                if not re.fullmatch("[a-f0-9]{64}", sha) or sha in seen:
                    continue
                seen.add(sha)
                if len(entries) >= MAX_FILES:
                    break
                target = _existing_file(root, row.get("saved_path"))
                item = {
                    "city": city, "url": url, "source_page": row.get("source_page", ""),
                    "sha256": sha, "status": "HOLD",
                    "pages_examined": 0, "segments": [],
                    "exact_application_id_mentions_review": [],
                    "publisher_first_publication_verified": False,
                    "exact_project_match_verified": False,
                    "purchasing_buyer_verified": False,
                    "supplier_contract_open_verified": False,
                }
                entries.append(item)
                if target is None:
                    item["status"] = "CAPTURED_PDF_NOT_PRESENT"
                    continue
                if target.stat().st_size > MAX_SIZE:
                    item["status"] = "PDF_SIZE_LIMIT"
                    continue
                body = target.read_bytes()
                if hashlib.sha256(body).hexdigest() != sha:
                    item["status"] = "CAPTURED_SOURCE_SHA_MISMATCH"
                    continue
                if any(word in unquote(url).lower() for word in HOLD_WORDS):
                    item["status"] = "PROCEDURAL_DOCUMENT_HELD"
                    continue
                try:
                    reader = PdfReader(io.BytesIO(body), strict=False)
                    if reader.is_encrypted:
                        item["status"] = "ENCRYPTED_PDF_HELD"
                        continue
                    item["status"] = "CAPTURED_SOURCE_TEXT_REVIEW_ONLY"
                    for i, page in enumerate(reader.pages[:MAX_PAGES]):
                        text = " ".join((page.extract_text() or "").split())
                        item["pages_examined"] += 1
                        for match in TERMS.finditer(text):
                            if len(item["segments"]) >= MAX_SEGMENTS:
                                break
                            excerpt = text[max(0, match.start()-90):
                                           min(len(text),match.end()+140)]
                            item["segments"].append({
                                "page": i+1, "keyword": match.group().lower(),
                                "excerpt": excerpt,
                                "evidence_level": "OFFICIAL_PDF_TEXT_MENTION_NOT_PROJECT_PROOF"})
                        for app_id in ids:
                            if app_id.lower() in text.lower():
                                if app_id not in item["exact_application_id_mentions_review"]:
                                    item["exact_application_id_mentions_review"].append(app_id)
                        if len(item["segments"]) >= MAX_SEGMENTS:
                            break
                    if not item["segments"]:
                        item["status"] = "NO_RELEVANT_EXTRACTABLE_TEXT_HOLD"
                except (ValueError, OSError, TypeError, KeyError, RuntimeError) as exc:
                    item["status"] = "PDF_PARSE_HELD_" + type(exc).__name__
    output = {
        "mode": "OFFLINE_VERIFIED_CAPTURE_REVIEW",
        "source_audits": list(AUDITS),
        "captured_official_pdfs_inspected": len(entries),
        "pdfs_with_keyword_evidence": sum(bool(x["segments"]) for x in entries),
        "page_cited_segments": sum(len(x["segments"]) for x in entries),
        "exact_application_id_text_mentions_for_review": sum(
            len(x["exact_application_id_mentions_review"]) for x in entries),
        "independently_verified_project_links": 0,
        "verified_publisher_first_publications": 0,
        "verified_buyers": 0, "verified_open_supplier_contracts": 0,
        "new_paid_calls": 0, "network_calls": 0,
        "city_counts": {
            city: sum(x["city"] == city for x in entries) for city in HOSTS},
        "warning": ("A literal application ID inside a saved official PDF is a "
                    "candidate, not a verified chain to today's application or "
                    "a publication timestamp; assess source context manually."),
        "documents": entries,
    }
    (report / "CAPTURED_PDF_EVIDENCE_REVIEW.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    with (report / "CAPTURED_PDF_EVIDENCE_REVIEW.csv").open(
            "w", encoding="utf-8-sig", newline="") as fp:
        cols = ("city", "url", "sha256", "status", "pages_examined",
                "segment_count", "application_id_mentions", "first_quote")
        w = csv.DictWriter(fp, fieldnames=cols)
        w.writeheader()
        for x in entries:
            w.writerow({
                "city": x["city"], "url": x["url"], "sha256": x["sha256"],
                "status": x["status"], "pages_examined": x["pages_examined"],
                "segment_count": len(x["segments"]),
                "application_id_mentions": "; ".join(
                    x["exact_application_id_mentions_review"]),
                "first_quote": (x["segments"][0]["excerpt"]
                                if x["segments"] else ""),
            })
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", required=True)
    args = p.parse_args()
    r = review(args.results)
    print(json.dumps({k:v for k,v in r.items() if k!="documents"}, indent=2))


if __name__ == "__main__":
    main()
