"""Optional OFFLINE transcription of a specifically supplied, authorized meeting audio file.

Requires ffprobe/ffmpeg installed and an already downloaded faster-whisper
model directory. Local files only; no web/media fetch, no model downloads,
no paid AI, no DB changes. Real source/publication/approval/buyer unverified.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from gta_local_caption_evidence import CITIES, parse_vtt
from gta_registered_document_evidence import TERMS

MAX_AUDIO_BYTES = 100_000_000
MAX_AUDIO_SECONDS = 15 * 60
MAX_SEGMENTS = 300
MAX_MATCHES = 30
MAX_VTT_BYTES = 1_000_000
AUDIO_FORMATS = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}
OUTPUT = "GTA_RADAR_LOCAL_TRANSCRIPTION_REVIEW.json"


def _local_file(root, name, *, suffixes=None, directory=False):
    root = Path(root).resolve()
    requested = Path(name)
    candidate = requested if requested.is_absolute() else root / requested
    if any(p.is_symlink() for p in (candidate, *candidate.parents)):
        raise ValueError("SYMLINK_LOCAL_INPUT_HELD")
    path = candidate.resolve()
    if not path.is_relative_to(root):
        raise ValueError("LOCAL_INPUT_OUTSIDE_WORKSPACE")
    if directory:
        if not path.is_dir():
            raise ValueError("LOCAL_MODEL_DIRECTORY_REQUIRED")
    elif (not path.is_file() or path.suffix.lower() not in suffixes
          or not 100 <= path.stat().st_size <= MAX_AUDIO_BYTES):
        raise ValueError("INVALID_OR_UNBOUNDED_LOCAL_AUDIO")
    return path


def _recording_url(url):
    try:
        p = urlsplit(str(url or ""))
        if (p.scheme != "https" or not p.hostname or p.username or p.password
                or p.fragment or p.port not in (None, 443)):
            raise ValueError
        return url
    except (ValueError, TypeError):
        raise ValueError("OFFICIAL_RECORDING_URL_REQUIRED") from None


def probe_duration(path, *, probe=None):
    if probe is not None:
        seconds = probe(path)
    else:
        if shutil.which("ffprobe") is None:
            raise RuntimeError("FFPROBE_NOT_INSTALLED")
        proc = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "json", str(path)
        ], capture_output=True, check=True, timeout=20)
        payload = json.loads(proc.stdout.decode("utf-8", "replace"))
        seconds = payload["format"]["duration"]
    try:
        value = float(seconds)
    except (ValueError, TypeError):
        raise ValueError("INVALID_AUDIO_DURATION") from None
    if not math.isfinite(value) or not 0 < value <= MAX_AUDIO_SECONDS:
        raise ValueError("AUDIO_DURATION_OUTSIDE_PILOT_LIMIT")
    return value


def _stamp(seconds):
    millis = max(0, round(float(seconds) * 1000))
    h, rem = divmod(millis, 3_600_000)
    m, rem = divmod(rem, 60_000)
    sec, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d}.{ms:03d}"


def _load_local_model(model_dir, *, backend=None):
    if backend is not None:
        return backend
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError("FASTER_WHISPER_NOT_INSTALLED") from None
    # Crucial: the model path is an existing local directory and model
    # initialization is explicitly forbidden from downloading any model.
    return WhisperModel(str(model_dir), device="cpu", compute_type="int8",
                        local_files_only=True)


def transcribe(workspace, audio, *, model, city, recording_url,
               authorized=False, backend=None, probe=None):
    """Return VTT and review evidence; no model or network without opt-in."""
    if not authorized:
        raise PermissionError("EXPLICIT_AUDIO_PROCESSING_AUTHORIZATION_REQUIRED")
    if city not in CITIES:
        raise ValueError("UNREGISTERED_CITY")
    original = _recording_url(recording_url)
    audio_path = _local_file(workspace, audio, suffixes=AUDIO_FORMATS)
    model_dir = _local_file(workspace, model, directory=True)
    duration = probe_duration(audio_path, probe=probe)
    loaded = _load_local_model(model_dir, backend=backend)
    segments, info = loaded.transcribe(
        str(audio_path), beam_size=3, vad_filter=True,
        language="en", condition_on_previous_text=False)
    rows, vtt = [], ["WEBVTT", ""]
    last_start = -1
    for segment in segments:
        if len(rows) >= MAX_SEGMENTS:
            raise ValueError("TRANSCRIPTION_SEGMENT_LIMIT_HELD")
        start = float(segment.start)
        end = float(segment.end)
        if (not math.isfinite(start) or not math.isfinite(end) or
                start < 0 or start < last_start or start >= end or
                end > duration + 2):
            raise ValueError("INVALID_TRANSCRIPTION_SEGMENT_TIMING")
        phrase = " ".join(str(segment.text).split())
        if not phrase:
            continue
        if len(phrase) > 900:
            raise ValueError("TRANSCRIPTION_SEGMENT_TEXT_TOO_LONG")
        last_start = start
        start_t, end_t = _stamp(start), _stamp(end)
        rows.append({"start": start_t, "end": end_t,
                     "start_ms": round(start * 1000),
                     "end_ms": round(end * 1000), "text": phrase})
        vtt.extend([f"{start_t} --> {end_t}", phrase, ""])
    content = "\n".join(vtt) + "\n"
    if len(content.encode("utf-8")) > MAX_VTT_BYTES:
        raise ValueError("TRANSCRIPT_OUTPUT_TOO_LARGE")
    # The output must be accepted by the same existing caption parsing engine.
    verified = parse_vtt(content)
    if len(verified) != len(rows):
        raise ValueError("TRANSCRIPT_CAPTION_ROUNDTRIP_MISMATCH")
    mentions = []
    for row in verified:
        for hit in TERMS.finditer(row["text"]):
            mentions.append({
                "start": row["start"], "end": row["end"],
                "start_ms": row["start_ms"], "end_ms": row["end_ms"],
                "keyword": hit.group(0).lower(),
                "excerpt": row["text"][:300],
                "evidence_level": "UNVERIFIED_ASR_TRANSCRIPT_MENTION",
            })
            if len(mentions) >= MAX_MATCHES:
                break
        if len(mentions) >= MAX_MATCHES:
            break
    report = {
        "status": "LOCAL_SPEECH_TRANSCRIPTION_REVIEW_ONLY",
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "city": city,
        "original_recording_url": original,
        "source_audio_sha256": hashlib.sha256(audio_path.read_bytes()).hexdigest(),
        "model_source": "OPERATOR_SUPPLIED_LOCAL_DIRECTORY",
        "audio_duration_seconds": duration,
        "transcript_segments": len(rows),
        "mentions_for_review": len(mentions),
        "mentions": mentions,
        "first_publication_verified": False,
        "decision_verified": False,
        "project_verified": False,
        "buyer_verified": False,
        "paid_ai_usd": 0,
        "warning": ("ASR text may contain recognition errors; no official "
                    "minutes or planning file reconciliation has occurred."),
    }
    return content, report


def run(workspace, results, audio, *, model, city, recording_url, authorized=False,
        backend=None, probe=None):
    """Atomic output after successful transcription, preserving previous results."""
    root = Path(results)
    root.mkdir(parents=True, exist_ok=True)
    content, report = transcribe(
        workspace, audio, model=model, city=city,
        recording_url=recording_url, authorized=authorized,
        backend=backend, probe=probe)
    digest = report["source_audio_sha256"]
    out_dir = root / "LOCAL_TRANSCRIPTS"
    out_dir.mkdir(parents=True, exist_ok=True)
    vtt = out_dir / (digest + ".vtt")
    if not vtt.exists():
        tmp = vtt.with_suffix(".vtt.tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(vtt)
    report["saved_vtt"] = str(vtt)
    destination = root / OUTPUT
    temp = destination.with_suffix(".json.tmp")
    temp.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    temp.replace(destination)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--audio", required=True)
    parser.add_argument("--local-model-dir", required=True)
    parser.add_argument("--city", choices=sorted(CITIES), required=True)
    parser.add_argument("--recording-url", required=True)
    parser.add_argument("--authorized-local-transcription", action="store_true")
    args = parser.parse_args()
    try:
        report = run(
            args.workspace, args.results, args.audio,
            model=args.local_model_dir, city=args.city,
            recording_url=args.recording_url,
            authorized=args.authorized_local_transcription)
    except (ValueError, PermissionError, RuntimeError, OSError,
            subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "LOCAL_TRANSCRIPTION_HELD",
                          "error_type": type(exc).__name__,
                          "reason": str(exc)[:180],
                          "project_verified": False, "paid_ai_usd": 0}))
        raise SystemExit(2)
    print(json.dumps({k: v for k,v in report.items()
                      if k != "mentions"}, indent=2))
