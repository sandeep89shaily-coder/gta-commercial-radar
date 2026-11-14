"""Offline timestamped council captions (WebVTT) evidence review.

This parses already-supplied captions; it does NOT transcribe audio or access
recordings. All extracted mentions remain provisional and source-uncorroborated.
A local workspace manifest explicitly identifies original council recording URLs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from gta_registered_document_evidence import TERMS

MANIFEST = "GTA_RADAR_MEDIA_INPUTS.json"
OUTPUT = "GTA_RADAR_CAPTION_EVIDENCE_REVIEW.json"
MAX_FILES = 8
MAX_BYTES = 2_000_000
MAX_CUES = 2000
MAX_MATCHES = 30
TIMECODE = re.compile(
    r"(?:(\d{2}):)?(\d{2}):(\d{2})[.](\d{3})"
)
CUE = re.compile(
    r"^((?:\d{2}:)?\d{2}:\d{2}:\d{2}[.]\d{3})\s+-->\s+"
    r"((?:\d{2}:)?\d{2}:\d{2}:\d{2}[.]\d{3})(?:\s+.*)?$"
)
CITIES = {"Toronto", "Brampton", "Mississauga", "Hamilton", "Burlington",
          "Oakville", "Vaughan", "Kitchener", "Markham", "Oshawa", "Milton",
          "Halton Hills", "Caledon", "Cambridge", "Waterloo", "Guelph"}


def _ms(value):
    m = TIMECODE.fullmatch(value)
    if not m:
        raise ValueError("INVALID_CAPTION_TIMESTAMP")
    h, minute, second, milli = m.groups()
    if int(minute) > 59 or int(second) > 59:
        raise ValueError("INVALID_CAPTION_TIME_COMPONENT")
    return ((int(h or 0)*3600 + int(minute)*60 + int(second))*1000 + int(milli))


def parse_vtt(content):
    if not isinstance(content, str) or not content.lstrip("\ufeff").startswith("WEBVTT"):
        raise ValueError("WEBVTT_HEADER_REQUIRED")
    cues = []
    blocks = re.split(r"\r?\n\s*\r?\n", content.lstrip("\ufeff").strip())
    for block in blocks[1:]:
        lines = block.splitlines()
        if not lines or lines[0].startswith(("NOTE", "STYLE", "REGION")):
            continue
        candidate = next((i for i, line in enumerate(lines[:2]) if "-->" in line), None)
        if candidate is None:
            continue
        match = CUE.fullmatch(lines[candidate].strip())
        if match is None:
            raise ValueError("INVALID_CAPTION_CUE")
        start, end = match.groups()
        if _ms(start) >= _ms(end):
            raise ValueError("INVALID_CAPTION_INTERVAL")
        text = " ".join(re.sub(r"<[^>]*>", "", " ".join(lines[candidate+1:])).split())
        cues.append({"start": start, "end": end,
                     "start_ms": _ms(start), "end_ms": _ms(end), "text": text[:1000]})
        if len(cues) > MAX_CUES:
            raise ValueError("CAPTIONS_EXCEED_CUE_LIMIT")
    if any(cues[i]["start_ms"] < cues[i-1]["start_ms"] for i in range(1,len(cues))):
        raise ValueError("NONMONOTONIC_CAPTION_TIMELINE")
    return cues


def _valid_recording(url):
    try:
        p = urlsplit(str(url or ""))
        return bool(p.scheme == "https" and p.hostname
                    and not p.username and not p.password and not p.fragment
                    and p.port in (None,443))
    except ValueError:
        return False


def _file(root, item):
    declared = Path(item["file"])
    raw = declared if declared.is_absolute() else root / declared
    if any(x.is_symlink() for x in (raw, *raw.parents)):
        raise ValueError("SYMLINK_MEDIA_INPUT_HELD")
    path = raw.resolve()
    if not path.is_relative_to(root) or path.suffix.lower() != ".vtt":
        raise ValueError("CAPTIONS_MUST_BE_WORKSPACE_VTT")
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("CAPTION_FILE_MISSING_OR_TOO_LARGE")
    return path


def build(workspace, *, now=None):
    root = Path(workspace).resolve()
    path = root / MANIFEST
    if not path.is_file():
        return {"status": "NO_EXPLICIT_CAPTION_MANIFEST", "files": [],
                "verified_projects": 0, "verified_buyers": 0, "paid_ai_usd": 0}
    if path.stat().st_size > 32_000:
        return {"status": "CAPTION_MANIFEST_TOO_LARGE_HELD", "files": [],
                "verified_projects": 0, "verified_buyers": 0, "paid_ai_usd": 0}
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        docs = manifest["captions"] if manifest.get("version") == 1 else None
        if not isinstance(docs, list) or len(docs) > MAX_FILES:
            raise ValueError("CAPTION_MANIFEST_INVALID")
    except (ValueError, TypeError, KeyError, AttributeError, OSError):
        return {"status": "INVALID_CAPTION_MANIFEST_HELD", "files": [],
                "verified_projects": 0, "verified_buyers": 0, "paid_ai_usd": 0}
    entries = []
    for doc in docs:
        city = doc.get("city") if isinstance(doc, dict) else None
        origin = doc.get("recording_url") if isinstance(doc, dict) else None
        row = {"city": city, "original_recording_url": origin,
               "status": "SOURCE_HELD", "mentions": []}
        if city not in CITIES or not _valid_recording(origin):
            row["reason"] = "INVALID_SOURCE_CITY_OR_URL"
            entries.append(row)
            continue
        try:
            path = _file(root, doc)
            raw = path.read_bytes()
            cues = parse_vtt(raw.decode("utf-8-sig"))
            row.update({"source_sha256": hashlib.sha256(raw).hexdigest(),
                        "captions_cues": len(cues), "status": "CAPTIONS_REVIEW_ONLY",
                        "publication_date_verified": False, "approval_verified": False,
                        "buyer_verified": False})
            for cue in cues:
                for hit in TERMS.finditer(cue["text"]):
                    row["mentions"].append({
                        "start": cue["start"], "end": cue["end"],
                        "start_ms": cue["start_ms"], "end_ms": cue["end_ms"],
                        "keyword": hit.group(0).lower(),
                        "excerpt": cue["text"][:300],
                        "evidence_level": "UNVERIFIED_CAPTION_MENTION",
                    })
                    if len(row["mentions"]) >= MAX_MATCHES:
                        break
                if len(row["mentions"]) >= MAX_MATCHES:
                    row["status"] = "CAPTION_MATCH_LIMIT_REACHED"
                    break
        except (ValueError, OSError, UnicodeError, KeyError, TypeError) as exc:
            row["status"] = "CAPTION_PARSE_HELD"
            row["error_type"] = type(exc).__name__
        entries.append(row)
    return {
        "status": "LOCAL_CAPTION_REVIEW_ONLY",
        "generated_utc": now or dt.datetime.now(dt.timezone.utc).isoformat(),
        "caption_files": len(entries),
        "mentions_for_review": sum(len(x["mentions"]) for x in entries),
        "verified_projects": 0, "verified_buyers": 0, "paid_ai_usd": 0,
        "warning": "Caption mentions are not approval evidence. No audio transcription was performed.",
        "files": entries,
    }


def run(workspace, results):
    report = build(workspace)
    output = Path(results) / OUTPUT
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    print(json.dumps({k:v for k,v in run(args.workspace, args.results).items()
                      if k != "files"}, indent=2))
