"""Carry official discovered Mississauga PDC document links into PDF review.

Consumes ONLY the persistent conservative index-link evidence, with exact
city/source and eSCRIBE PDF allowlist, and strict PDC label qualification.
No ID enumeration or fabricated freshness. No network unless explicitly opted
into the manually run, policy-checked downstream fetcher.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from gta_council_document_delta import LEDGER
from municipal_meeting_capture import OFFICIAL
from gta_mississauga_pdc_agenda import official_pdf, OUT as PDC_CSV
from gta_mississauga_pdc_authorized_fetch import batch as fetch_documents

STATUS = "MISSISSAUGA_DISCOVERED_PDC_CAPTURE_STATUS.json"
MAX_DOCUMENTS = 3
PDC_LABEL = re.compile(
    r"\b(?:planning\s+(?:and|&)\s+development|"
    r"planning\s+development\s+committee|pdc)\b", re.I
)


def select_sources(index_folder, *, limit=MAX_DOCUMENTS):
    if not 1 <= limit <= MAX_DOCUMENTS:
        raise ValueError("PDC_DOCUMENT_LIMIT_OUT_OF_BOUNDS")
    file = Path(index_folder) / LEDGER
    if not file.is_file():
        return [], "OFFICIAL_INDEX_LEDGER_MISSING"
    data = json.loads(file.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("items"), dict):
        raise ValueError("OFFICIAL_INDEX_LEDGER_SCHEMA_INVALID")
    candidates = []
    excluded = 0
    for item in data["items"].values():
        if not isinstance(item, dict):
            continue
        if item.get("city") != "Mississauga":
            continue
        if item.get("discovery_source") != OFFICIAL["Mississauga"]:
            excluded += 1
            continue
        if not PDC_LABEL.search(str(item.get("title") or "")):
            excluded += 1
            continue
        url = item.get("url")
        try:
            official_pdf(url)
        except (ValueError, TypeError):
            excluded += 1
            continue
        # Legacy ledger rows may predate the tightened document classifier.
        # Validate that link content has not yet been verified as a project.
        if item.get("source_content_checked") not in (None, False):
            excluded += 1
            continue
        candidates.append({
            "url": url,
            "index_title": str(item["title"])[:180],
            "index_first_observed": item.get("first_observed_utc", ""),
            "index_last_observed": item.get("last_observed_utc", "")
        })
    if not candidates:
        return [], "NO_DIRECT_PDC_PDF_LINKS_ON_CURRENT_OFFICIAL_INDEX"
    # Re-observation is a priority signal for retrieval, not publication.
    candidates.sort(key=lambda r: (r["index_last_observed"],
                                   r["index_first_observed"], r["url"]), reverse=True)
    result = []
    seen = set()
    for item in candidates:
        if item["url"] not in seen:
            seen.add(item["url"])
            result.append(item)
        if len(result) >= limit:
            break
    return result, "OFFICIAL_PDC_LINKS_AVAILABLE_FOR_PERMISSION_CHECK"


def run(index_folder, output, *, fetch=False, fetcher=None):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "mode": "REVIEW_ONLY_MISSISSAUGA_DISCOVERED_PDC",
        "status": "HOLD",
        "source": "OFFICIAL_INDEX_LINK_LEDGER",
        "eligible_pdc_links": 0,
        "selected_for_fetch": 0,
        "captured_pdfs": 0,
        "parsed_agenda_pdfs": 0,
        "agenda_item_csvs": [],
        "original_publisher_dates_verified": 0,
        "verified_commercial_projects": 0,
        "verified_procurements": 0,
        "paid_ai_calls": 0,
        "warnings": [
            "A known direct PDF URL is not evidence of a new publication.",
            "Official City committee meeting sources may be dynamically rendered or blocked.",
        ]
    }
    try:
        selected, source_status = select_sources(index_folder)
        report["source_status"] = source_status
        report["eligible_pdc_links"] = len(selected)
        report["selected_for_fetch"] = len(selected) if fetch else 0
        report["selected_urls"] = [item["url"] for item in selected]
        if not selected:
            report["status"] = "NO_DIRECT_PDC_URLS_SOURCE_ADAPTER_GAP"
        elif not fetch:
            report["status"] = "EXPLICIT_MANUAL_FETCH_NOT_REQUESTED"
        else:
            downstream = (fetcher or fetch_documents)(
                [item["url"] for item in selected],
                out / "OFFICIAL_PDF_DOCUMENTS",
                authorized=True)
            report["captured_pdfs"] = downstream.get("captured", 0)
            report["fetch_statuses"] = [
                {"url": row.get("url"), "status": row.get("status"),
                 "reason": row.get("reason", "")}
                for row in downstream.get("records", [])
            ]
            for row in downstream.get("records", []):
                parsed = row.get("item_extraction") or {}
                if (row.get("status") == "CAPTURED"
                        and parsed.get("status") == "REVIEW_ONLY_ITEM_EXTRACTION"):
                    url = row.get("url")
                    from hashlib import sha256
                    stem = sha256(url.encode("utf-8")).hexdigest()[:32]
                    path = out / "OFFICIAL_PDF_DOCUMENTS" / "items" / stem / PDC_CSV
                    if path.is_file():
                        report["agenda_item_csvs"].append(str(path))
            report["parsed_agenda_pdfs"] = len(report["agenda_item_csvs"])
            report["status"] = (
                "EXTRACTED_REVIEW_ONLY" if report["parsed_agenda_pdfs"]
                else "PDC_PDF_ACCESS_OR_EXTRACTION_HELD")
    except Exception as exc:
        report["status"] = "PDC_COLLECTOR_FAILED_NO_SUCCESS_CLAIM"
        report["error_type"] = type(exc).__name__
        report["error_reason"] = str(exc)[:180]
    finally:
        (out / STATUS).write_text(json.dumps(report, indent=2),
                                  encoding="utf-8")
    return report


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--index-folder", required=True)
    cli.add_argument("--out", required=True)
    cli.add_argument("--fetch", action="store_true",
                     help="Operator-approved direct PDC PDF fetch through robots gate")
    args = cli.parse_args()
    output = run(args.index_folder, args.out, fetch=args.fetch)
    print(json.dumps({
        k: output[k] for k in ("status", "eligible_pdc_links",
            "captured_pdfs", "parsed_agenda_pdfs", "paid_ai_calls")
    }, indent=2))
