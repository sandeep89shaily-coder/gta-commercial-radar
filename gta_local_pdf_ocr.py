"""Optional offline OCR for a locally saved, explicitly selected council PDF.

Requires installed poppler pdftoppm and Tesseract binaries. Never downloads a
model/source, accesses a website, calls paid AI, or overwrites original PDFs.
OCR is uncertain evidence, not an official decision or verified buyer.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from gta_registered_document_evidence import TERMS

MAX_BYTES = 15_000_000
MAX_PAGES = 3
TIMEOUT_SEC = 35
MAX_IMAGE_BYTES = 12_000_000
MAX_EXCERPTS = 20
OUTPUT = "GTA_RADAR_LOCAL_OCR_REVIEW.json"


def _local_pdf(workspace, name):
    root = Path(workspace).resolve()
    raw = Path(name)
    candidate = raw if raw.is_absolute() else root / raw
    if any(part.is_symlink() for part in (candidate, *candidate.parents)):
        raise ValueError("SYMLINK_PDF_HELD")
    path = candidate.resolve()
    if not path.is_relative_to(root) or path.suffix.lower() != ".pdf":
        raise ValueError("PDF_MUST_BE_IN_WORKSPACE")
    if not path.is_file() or not 100 <= path.stat().st_size <= MAX_BYTES:
        raise ValueError("PDF_NOT_FOUND_OR_UNBOUNDED")
    return path


def scan(workspace, name, *, render=None, recognize=None, max_pages=MAX_PAGES):
    """OCR only text-poor pages; injectable functions make safety testable."""
    path = _local_pdf(workspace, name)
    if not 1 <= max_pages <= MAX_PAGES:
        raise ValueError("OCR_PAGE_LIMIT_EXCEEDED")
    data = path.read_bytes()
    if not data.startswith(b"%PDF-"):
        raise ValueError("INVALID_PDF_SIGNATURE")
    reader = PdfReader(io.BytesIO(data), strict=False)
    if reader.is_encrypted:
        raise ValueError("ENCRYPTED_PDF_HELD")
    result = {
        "status": "OCR_REVIEW_ONLY",
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "source_local_filename": path.name,
        "total_pdf_pages": len(reader.pages),
        "pages_considered": min(max_pages, len(reader.pages)),
        "pages_ocr_attempted": 0,
        "pages_ocr_succeeded": 0,
        "pages_skipped_digital_text": 0,
        "ocr_excerpts": [],
        "publisher_first_publication_verified": False,
        "project_verified": False,
        "buyer_verified": False,
        "paid_ai_usd": 0,
    }
    if render is None and shutil.which("pdftoppm") is None:
        result["status"] = "OCR_RENDERER_NOT_INSTALLED"
        return result
    if recognize is None and shutil.which("tesseract") is None:
        result["status"] = "OCR_ENGINE_NOT_INSTALLED"
        return result
    with tempfile.TemporaryDirectory() as folder:
        temp = Path(folder)
        for index in range(result["pages_considered"]):
            existing = " ".join((reader.pages[index].extract_text() or "").split())
            if len(existing) >= 40:
                result["pages_skipped_digital_text"] += 1
                continue
            result["pages_ocr_attempted"] += 1
            try:
                if render:
                    image = render(path, index + 1, temp)
                else:
                    prefix = temp / ("page_" + str(index + 1))
                    subprocess.run(
                        ["pdftoppm", "-f", str(index + 1), "-l", str(index + 1),
                         "-singlefile", "-r", "120", "-png", str(path), str(prefix)],
                        capture_output=True, timeout=TIMEOUT_SEC, check=True)
                    image = prefix.with_suffix(".png")
                image = Path(image).resolve()
                if (not image.is_relative_to(temp.resolve())
                        or not image.is_file() or image.stat().st_size > MAX_IMAGE_BYTES):
                    raise ValueError("UNSAFE_OR_OVERSIZED_RENDERED_PAGE")
                if recognize:
                    text = recognize(image)
                else:
                    proc = subprocess.run(
                        ["tesseract", str(image), "stdout", "--psm", "3"],
                        capture_output=True, timeout=TIMEOUT_SEC, check=True)
                    text = proc.stdout.decode("utf-8", "replace")
                if not isinstance(text, str):
                    raise ValueError("OCR_INVALID_TEXT")
                result["pages_ocr_succeeded"] += 1
                compact = " ".join(text[:100_000].split())
                for hit in TERMS.finditer(compact):
                    if len(result["ocr_excerpts"]) >= MAX_EXCERPTS:
                        break
                    result["ocr_excerpts"].append({
                        "page": index + 1, "keyword": hit.group(0).lower(),
                        "excerpt": compact[max(0,hit.start()-95):hit.end()+120],
                        "evidence_level": "UNVERIFIED_OCR_TEXT",
                    })
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                result.setdefault("page_errors", []).append({
                    "page": index + 1, "error_type": type(exc).__name__,
                })
            if len(result["ocr_excerpts"]) >= MAX_EXCERPTS:
                result["status"] = "OCR_EVIDENCE_CAPPED"
                break
    if result["pages_ocr_attempted"] and not result["pages_ocr_succeeded"]:
        result["status"] = "OCR_ATTEMPTED_NO_PAGES_SUCCEEDED"
    elif not result["ocr_excerpts"] and result["pages_ocr_succeeded"]:
        result["status"] = "OCR_NO_RELEVANT_TEXT_REVIEW_HOLD"
    elif not result["pages_ocr_attempted"]:
        result["status"] = "DIGITAL_TEXT_PRESENT_OCR_NOT_NEEDED"
    return result


def run(workspace, pdf, output):
    result = scan(workspace, pdf)
    out = Path(output)
    if out.suffix.lower() != ".json":
        raise ValueError("OCR_JSON_OUTPUT_REQUIRED")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, indent=2), encoding="utf-8")
    tmp.replace(out)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace", required=True)
    p.add_argument("--pdf", required=True, help="Explicit local PDF path inside workspace")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    print(json.dumps(run(a.workspace, a.pdf, a.out), indent=2))
