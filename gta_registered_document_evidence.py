"""Deterministic, read-only page-cited evidence from registered local council PDFs.

This is an offline digital-PDF pilot, not OCR, transcription, source verification,
project identity resolution, paid AI, or a new collector. Explicit local source
manifest required. Output is review-only, capped and source-hashed.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MANIFEST = "GTA_RADAR_COUNCIL_INPUTS.json"
OUTPUT = "GTA_RADAR_DOCUMENT_EVIDENCE_SEGMENTS.json"
MAX_DOCUMENTS = 20
MAX_BYTES = 15_000_000
MAX_PAGES = 50
MAX_MATCHES = 15
TERMS = re.compile(
    r"\b(?:industrial|manufactur\w*|warehouse|factory|commercial|"
    r"data[ -]?cent(?:er|re)|logistics|employment\s+land|"
    r"office|retail|hotel|facility\s+expansion|site[ -]?plan|"
    r"rezon\w*|cooling|boiler|plant\s+expansion)\b", re.I
)
ALLOWED_CITIES = {"Toronto", "Brampton", "Mississauga"}


def _source_url(item):
    for field in ("agenda_pdf_url", "meeting_url"):
        url = str(item.get(field) or "")
        parsed = urlsplit(url)
        if (parsed.scheme == "https" and parsed.hostname and
                not parsed.username and not parsed.password):
            return url[:600]
    return ""


def _record(root, item):
    city = item.get("city")
    name = item.get("file")
    if city not in ALLOWED_CITIES or not isinstance(name, str) or not name.strip():
        return {"city": str(city or "")[:50], "status": "INVALID_SOURCE_ENTRY", "segments": []}
    declared = Path(name)
    raw = (declared if declared.is_absolute() else root / declared)
    # Reject path traversal and all symlink intermediates.
    if any(part.is_symlink() for part in (raw, *raw.parents)):
        return {"city": city, "status": "SYMLINK_SOURCE_HELD", "segments": []}
    path = raw.resolve()
    if not path.is_relative_to(root) or path.suffix.lower() != ".pdf":
        return {"city": city, "status": "NOT_REGISTERED_WORKSPACE_PDF", "segments": []}
    if not path.is_file():
        return {"city": city, "status": "REGISTERED_PDF_MISSING", "segments": []}
    if path.stat().st_size > MAX_BYTES:
        return {"city": city, "status": "PDF_TOO_LARGE", "segments": []}
    raw_bytes = path.read_bytes()
    digest = hashlib.sha256(raw_bytes).hexdigest()
    result = {"city": city, "source_url": _source_url(item),
              "source_sha256": digest, "status": "PDF_TEXT_REVIEW_ONLY",
              "segments": [], "pages_examined": 0,
              "publisher_first_publication_verified": False,
              "project_identity_verified": False, "buyer_verified": False,
              "procurement_verified": False}
    try:
        import io
        reader = PdfReader(io.BytesIO(raw_bytes), strict=False)
        if reader.is_encrypted:
            result["status"] = "ENCRYPTED_PDF_HELD"
            return result
        count = min(len(reader.pages), MAX_PAGES)
        for index in range(count):
            body = " ".join((reader.pages[index].extract_text() or "").split())
            result["pages_examined"] += 1
            for match in TERMS.finditer(body):
                if len(result["segments"]) >= MAX_MATCHES:
                    break
                snippet = body[max(0, match.start()-95):min(len(body),match.end()+120)]
                result["segments"].append({
                    "page": index + 1, "keyword": match.group(0).lower(),
                    "excerpt": snippet, "evidence_level": "UNVERIFIED_PDF_TEXT_MENTION",
                })
            if len(result["segments"]) >= MAX_MATCHES:
                result["status"] = "REVIEW_CAPPED_SEGMENTS"
                break
        if len(reader.pages) > MAX_PAGES:
            result["status"] = "REVIEW_CAPPED_PAGES"
        if not result["segments"] and result["status"] == "PDF_TEXT_REVIEW_ONLY":
            result["status"] = "NO_COMMERCIAL_TEXT_OR_SCANNED_PAGES_HOLD"
    except (PdfReadError, ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
        result["status"] = "PDF_PARSE_HELD_" + type(exc).__name__
        result["segments"] = []
    return result


def build(workspace, *, now=None):
    root = Path(workspace).resolve()
    manifest = root / MANIFEST
    if not manifest.is_file():
        return {"status": "NO_EXPLICIT_DOCUMENT_MANIFEST", "documents": [],
                "project_leads_verified": 0, "paid_ai_usd": 0}
    if manifest.stat().st_size > 128_000:
        return {"status": "OVERSIZED_DOCUMENT_MANIFEST_HELD", "documents": [],
                "project_leads_verified": 0, "paid_ai_usd": 0}
    try:
        obj = json.loads(manifest.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {"status": "INVALID_DOCUMENT_MANIFEST_HELD", "documents": [],
                "project_leads_verified": 0, "paid_ai_usd": 0}
    entries = obj.get("documents", []) if isinstance(obj, dict) and obj.get("version") == 1 else None
    if not isinstance(entries, list) or len(entries) > MAX_DOCUMENTS:
        return {"status": "INVALID_DOCUMENT_ENTRIES_HELD", "documents": [],
                "project_leads_verified": 0, "paid_ai_usd": 0}
    records = [_record(root, item if isinstance(item, dict) else {}) for item in entries]
    return {
        "status": "OFFLINE_DOCUMENT_REVIEW_ONLY",
        "generated_utc": now or dt.datetime.now(dt.timezone.utc).isoformat(),
        "documents_registered": len(entries),
        "pdfs_examined": sum("pages_examined" in r for r in records),
        "segments_for_manual_review": sum(len(r["segments"]) for r in records),
        "project_leads_verified": 0, "paid_ai_usd": 0,
        "warning": ("Extracted paragraphs are possible project signals, not "
                    "independent evidence of first publication, approval, buyer, "
                    "open tender or actual project identity. Scanned pages need OCR."),
        "documents": records,
    }


def run(workspace, results):
    report = build(workspace)
    (Path(results) / OUTPUT).write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--results", required=True)
    a = parser.parse_args()
    print(json.dumps({k:v for k,v in run(a.workspace,a.results).items()
                      if k != "documents"}, indent=2))
