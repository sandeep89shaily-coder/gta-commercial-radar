"""Read-only, evidence-first reconciliation of council text to planning files.

Inputs: existing GTA_RADAR_EARLY_APPLICATION_CANDIDATES.csv and the caption,
PDF and locally transcribed review JSON files from the same Radar workspace.
Exact municipality + exact application ID is needed for a candidate link.
Fuzzy, address, or keyword matches never become identified projects.

No network/LLM/database changes. Outputs remain manual research candidates.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from gta_early_applications import ID_PATTERN

OUTPUT = "GTA_RADAR_CROSS_SOURCE_RECONCILIATION.json"
APPLICATIONS = "GTA_RADAR_EARLY_APPLICATION_CANDIDATES.csv"
CAPTIONS = "GTA_RADAR_CAPTION_EVIDENCE_REVIEW.json"
DOCUMENTS = "GTA_RADAR_DOCUMENT_EVIDENCE_SEGMENTS.json"
TRANSCRIPT = "GTA_RADAR_LOCAL_TRANSCRIPTION_REVIEW.json"
MAX_INPUT_BYTES = 4_000_000
MAX_APPLICATIONS = 10_000
MAX_MENTIONS = 100
MAX_EVIDENCE_PER_MENTION = 15
MAX_TEXT = 800


def normalize_id(value):
    """Conservative exact-ID normalization (case and whitespace only)."""
    return re.sub(r"\s+", "", str(value or "")).upper()


def _json(path):
    if not path.is_file():
        return None
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("EVIDENCE_FILE_TOO_LARGE:" + path.name)
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("EVIDENCE_OBJECT_REQUIRED:" + path.name)
    return payload


def _applications(path):
    if not path.is_file():
        return [], "NO_CURRENT_APPLICATION_CSV"
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("APPLICATION_FILE_TOO_LARGE")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"city", "application_id", "project_id", "record_source_url"}.issubset(reader.fieldnames):
            raise ValueError("APPLICATION_SCHEMA_MISMATCH")
        records = []
        for row in reader:
            if len(records) >= MAX_APPLICATIONS:
                raise ValueError("TOO_MANY_APPLICATION_ROWS")
            city, file_id = str(row["city"] or "").strip(), normalize_id(row["application_id"])
            if not city or not file_id or not ID_PATTERN.fullmatch(str(row["application_id"]).strip()):
                continue
            records.append({
                "city": city, "application_id": file_id,
                "project_id": row["project_id"],
                "source_url": row["record_source_url"],
                "source_url_basis": row.get("record_source_url_basis", ""),
            })
    return records, "APPLICATION_CSV_READ"


def _mentions(root):
    out, source_health = [], {}
    specs = [
        (CAPTIONS, "files", "mentions", "original_recording_url", "CAPTION"),
        (DOCUMENTS, "documents", "segments", "source_url", "PDF"),
    ]
    for filename, group, field, uri, kind in specs:
        data = _json(root / filename)
        if data is None:
            source_health[kind] = "SOURCE_NOT_PRESENT"
            continue
        if not isinstance(data.get(group), list):
            source_health[kind] = "SOURCE_SCHEMA_HELD"
            continue
        source_health[kind] = "SOURCE_READ"
        for record in data[group][:40]:
            if not isinstance(record, dict) or not isinstance(record.get(field), list):
                continue
            if "HELD" in str(record.get("status", "")):
                continue
            for mention in record[field][:MAX_EVIDENCE_PER_MENTION]:
                if not isinstance(mention, dict):
                    continue
                excerpt = str(mention.get("excerpt", ""))[:MAX_TEXT]
                if not excerpt:
                    continue
                out.append({
                    "city": record.get("city", ""),
                    "source_kind": kind, "source_url": record.get(uri, ""),
                    "source_sha256": record.get("source_sha256", ""),
                    "page": mention.get("page"),
                    "start_ms": mention.get("start_ms"),
                    "excerpt": excerpt, "evidence_level": mention.get("evidence_level", ""),
                })
                if len(out) >= MAX_MENTIONS:
                    return out, source_health
    data = _json(root / TRANSCRIPT)
    if data is None:
        source_health["ASR"] = "SOURCE_NOT_PRESENT"
    elif isinstance(data.get("mentions"), list):
        source_health["ASR"] = "SOURCE_READ"
        if data.get("status") == "LOCAL_SPEECH_TRANSCRIPTION_REVIEW_ONLY":
            for mention in data["mentions"][:MAX_MENTIONS-len(out)]:
                if not isinstance(mention, dict):
                    continue
                excerpt = str(mention.get("excerpt", ""))[:MAX_TEXT]
                if not excerpt:
                    continue
                out.append({
                    "city": data.get("city", ""), "source_kind": "ASR",
                    "source_url": data.get("original_recording_url", ""),
                    "source_sha256": data.get("source_audio_sha256", ""),
                    "page": None, "start_ms": mention.get("start_ms"),
                    "excerpt": excerpt, "evidence_level": mention.get("evidence_level", ""),
                })
    else:
        source_health["ASR"] = "SOURCE_SCHEMA_HELD"
    return out, source_health


def build(results, *, now=None):
    root = Path(results)
    applications, app_status = _applications(root / APPLICATIONS)
    mentions, source_statuses = _mentions(root)
    by_key = defaultdict(list)
    for app in applications:
        by_key[(app["city"].casefold(), app["application_id"])].append(app)
    linked, holds = [], []
    for mention in mentions:
        city = str(mention["city"] or "")
        ids = sorted({normalize_id(m.group()) for m in ID_PATTERN.finditer(mention["excerpt"])})
        matches = []
        for ident in ids:
            matches.extend(by_key.get((city.casefold(), ident), []))
        # Several records may use the same file identifier. Fail closed.
        unique = {app["project_id"]: app for app in matches}
        origin = {
            "evidence_id": hashlib.sha256(json.dumps(mention,sort_keys=True).encode()).hexdigest()[:24],
            "city": city, "source_kind": mention["source_kind"],
            "source_url": mention["source_url"],
            "source_sha256": mention["source_sha256"],
            "page": mention["page"], "start_ms": mention["start_ms"],
            "excerpt": mention["excerpt"], "candidate_application_ids": ids,
        }
        if not ids:
            holds.append({**origin, "status": "NO_EXACT_APPLICATION_ID_IN_EXCERPT"})
        elif not unique:
            holds.append({**origin, "status": "NO_SAME_CITY_APPLICATION_ID_MATCH"})
        elif len(unique) != 1:
            holds.append({**origin, "status": "AMBIGUOUS_MULTIPLE_APPLICATION_PROJECTS"})
        else:
            app = next(iter(unique.values()))
            linked.append({
                **origin, "status": "EXACT_ID_CANDIDATE_HUMAN_REVIEW_REQUIRED",
                "application_id": app["application_id"],
                "project_id": app["project_id"],
                "application_source_url": app["source_url"],
                "application_source_url_basis": app["source_url_basis"],
                "source_identity_verified": False,
                "project_verified": False, "buyer_verified": False,
                "approval_verified": False, "procurement_verified": False,
                "publisher_first_publication_verified": False,
            })
    return {
        "status": "READ_ONLY_CROSS_SOURCE_REVIEW",
        "generated_utc": now or dt.datetime.now(dt.timezone.utc).isoformat(),
        "application_input_status": app_status,
        "source_statuses": source_statuses,
        "application_rows_accepted": len(applications),
        "mentions_considered": len(mentions),
        "exact_id_review_candidates": len(linked),
        "unmatched_or_ambiguous_mentions": len(holds),
        "independently_verified_project_links": 0,
        "verified_buyers": 0, "paid_ai_usd": 0,
        "warning": ("An exact ID in an unverified text excerpt is a possible cross-source link, "
                    "not independent project identity or municipal approval. "
                    "Missing inputs are not zero municipal activity."),
        "review_candidates": linked[:MAX_MENTIONS],
        "holds": holds[:MAX_MENTIONS],
    }


def run(results):
    root = Path(results)
    report = build(root)
    out = root / OUTPUT
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(out)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    a = parser.parse_args()
    print(json.dumps({k:v for k,v in run(a.results).items()
                      if k not in ("review_candidates","holds")}, indent=2))
