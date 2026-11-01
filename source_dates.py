"""Deterministic dates for GTA Radar. The AI model never converts or invents dates.

Municipal ArcGIS records store dates as epoch milliseconds (UTC). Every date the
Radar reports is computed here from the raw value and kept with that raw value,
so a reader can check it. Any calendar date that a model writes which is not
backed by a raw source value is replaced by a visible marker.
"""
from __future__ import annotations
import datetime as dt
import re

UNVERIFIED = "[date unverified]"
_EPOCH = re.compile(r'"?([A-Za-z_][A-Za-z0-9_ ]{1,40})"?\s*[:=]\s*"?(\d{13})"?')
_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_LONG = re.compile(
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|"
    r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b",
    re.I)
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_LOW, _HIGH = 946684800000, 4102444800000  # 2000-01-01 .. 2100-01-01 (ms)


def epoch_ms_to_date(value):
    """Epoch milliseconds -> 'YYYY-MM-DD' in UTC, or None if implausible."""
    try:
        ms = int(value)
    except (TypeError, ValueError):
        return None
    if not _LOW <= ms <= _HIGH:
        return None
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date().isoformat()


def extract_dated_fields(text):
    """Find epoch-millisecond fields in JSON-like source text.

    Returns [{'field','raw','date'}] in order of first appearance, de-duplicated.
    """
    found, seen = [], set()
    for name, raw in _EPOCH.findall(text or ""):
        day = epoch_ms_to_date(raw)
        key = (name.strip().upper(), raw)
        if day and key not in seen:
            seen.add(key)
            found.append({"field": name.strip().upper(), "raw": raw, "date": day})
    return found


def _normalise_iso(text):
    out = set()
    for y, m, d in _ISO.findall(text or ""):
        try:
            out.add(dt.date(int(y), int(m), int(d)).isoformat())
        except ValueError:
            pass
    return out


def verified_dates(row, evidence=()):
    """All dated facts the Radar can prove: raw epoch fields plus ISO dates
    present in the source row or fetched page text. Returns a list of dicts."""
    items, seen = [], set()
    blobs = [("source_record", " ".join(str(v) for v in (row or {}).values() if v))]
    blobs += [(e.get("url", "page"), e.get("text", "")) for e in evidence or ()]
    for origin, text in blobs:
        for item in extract_dated_fields(text):
            key = (item["field"], item["date"])
            if key not in seen:
                seen.add(key)
                items.append({**item, "origin": origin})
        for day in sorted(_normalise_iso(text)):
            key = ("ISO_DATE_IN_SOURCE", day)
            if key not in seen:
                seen.add(key)
                items.append({"field": "ISO_DATE_IN_SOURCE", "raw": day, "date": day, "origin": origin})
    return items


def allowed_date_set(row, evidence=()):
    return {item["date"] for item in verified_dates(row, evidence)}


def _long_to_iso(match):
    month = _MONTHS.get(match.group(1)[:3].lower())
    try:
        return dt.date(int(match.group(3)), month, int(match.group(2))).isoformat()
    except (TypeError, ValueError):
        return None


def sanitize_model_text(text, allowed):
    """Replace any calendar date not backed by a raw source value.

    Returns (clean_text, removed_count)."""
    removed = 0

    def iso_sub(m):
        nonlocal removed
        try:
            day = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            removed += 1
            return UNVERIFIED
        if day in allowed:
            return m.group(0)
        removed += 1
        return UNVERIFIED

    def long_sub(m):
        nonlocal removed
        day = _long_to_iso(m)
        if day and day in allowed:
            return m.group(0)
        removed += 1
        return UNVERIFIED

    text = _ISO.sub(iso_sub, text or "")
    text = _LONG.sub(long_sub, text)
    return text, removed
