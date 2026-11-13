"""Toronto's official TMMIS-derived meeting schedule, as a separate evidence tier.

Toronto Open Data publishes 2022-26 meeting SCHEDULE rows (date, committee,
meeting number). The schedule is not an agenda, nor an agenda URL source.
Read only official CKAN resource metadata and one pinned CSV resource. Fail
closed on access/format/robots errors. This is review-only, manual only.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import re
import socket
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import requests

import robots_policy
from toronto_pdf_download import public_dns

RESOURCE_ID = "08c8aedb-afba-41f5-830e-bbfb305ebbc7"
METADATA_HOST = "ckan0.cf.opendata.inter.prod-toronto.ca"
METADATA_URL = (
    "https://" + METADATA_HOST + "/api/3/action/resource_show?id=" + RESOURCE_ID
)
ALLOWED_HOSTS = {
    METADATA_HOST, "open.toronto.ca"
}
CATALOGUE = "https://open.toronto.ca/dataset/3bfab808-105b-45ab-8d92-cf1916594653/"
AGENT = "GTARadarResearch/1.0 (City Clerk Open Data meeting schedule)"
TIMEOUT = (7, 20)
MAX_META = 200_000
MAX_CSV = 2_000_000
MAX_ROWS = 5000
RESULTS_CSV = "TORONTO_OFFICIAL_SCHEDULE_RECENT_MEETINGS.csv"
STATUS = "TORONTO_OFFICIAL_SCHEDULE_STATUS.json"
FIELDS = ("meeting_date", "committee", "meeting_number", "start_time",
          "location", "term", "schedule_evidence", "agenda_url",
          "agenda_retrieved", "publication_date_verified",
          "project_verified")
REQUIRED = {"Term", "Committee", "MTG #", "Date", "Start Time"}
PLANNING = re.compile(
    r"planning|housing|community\s+council|city\s+council|economic|"
    r"executive\s+committee|infrastructure|government\s+management",
    re.I
)


def _official_csv_url(value):
    if not isinstance(value, str):
        raise ValueError("RESOURCE_URL_REQUIRED")
    p = urlsplit(value)
    if (p.scheme != "https" or p.hostname not in ALLOWED_HOSTS or
            p.username or p.password or p.port not in (None, 443) or
            p.fragment or not p.path.lower().endswith(".csv")):
        raise ValueError("SOURCE_CSV_OUTSIDE_OFFICIAL_ALLOWLIST")
    return value


def _get(session, url, maximum, accepted, *,
         resolver=socket.getaddrinfo, policy_reader=None):
    host = urlsplit(url).hostname
    if host not in ALLOWED_HOSTS or not public_dns(host, resolver):
        raise ValueError("OFFICIAL_HOST_DNS_UNAVAILABLE")
    allowed, reason = robots_policy.evaluate(
        session, url, AGENT, timeout=TIMEOUT, policy_reader=policy_reader)
    if not allowed:
        raise PermissionError("OFFICIAL_ROBOTS_" + str(reason))
    with session.get(url, timeout=TIMEOUT, allow_redirects=False,
                     stream=True) as response:
        if response.status_code != 200 or response.url != url:
            raise ValueError("OFFICIAL_SOURCE_HTTP_OR_REDIRECT_" +
                             str(response.status_code))
        mime = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if mime not in accepted:
            raise ValueError("OFFICIAL_RESOURCE_UNEXPECTED_MIME_" + mime[:50])
        buf = bytearray()
        for piece in response.iter_content(chunk_size=65536):
            if piece:
                buf.extend(piece)
                if len(buf) > maximum:
                    raise ValueError("OFFICIAL_RESOURCE_OVER_LIMIT")
        if not buf:
            raise ValueError("OFFICIAL_SOURCE_EMPTY")
        return bytes(buf)


def fetch_csv(*, session=None, resolver=socket.getaddrinfo,
              policy_reader=None):
    session = session or requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": AGENT, "Accept": "application/json,text/csv"})
    metadata = _get(
        session, METADATA_URL, MAX_META,
        {"application/json", "text/json"},
        resolver=resolver, policy_reader=policy_reader)
    meta = json.loads(metadata.decode("utf-8"))
    resource = meta.get("result") if meta.get("success") is True else None
    if (not isinstance(resource, dict) or
            resource.get("id", "").lower() != RESOURCE_ID or
            str(resource.get("format", "")).upper() != "CSV"):
        raise ValueError("NOT_PINNED_TORONTO_CSV_RESOURCE")
    url = _official_csv_url(resource.get("url"))
    raw = _get(
        session, url, MAX_CSV,
        {"text/csv", "application/csv", "text/plain",
         "application/octet-stream"},
        resolver=resolver, policy_reader=policy_reader)
    return raw.decode("utf-8-sig"), url


def parse(text, *, now=None, window_days=28):
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_CSV:
        raise ValueError("SCHEDULE_CSV_OVERSIZED")
    today = (now or dt.datetime.now(dt.timezone.utc)).date()
    if not 0 <= window_days <= 60:
        raise ValueError("INVALID_DATE_WINDOW")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or not REQUIRED.issubset(set(reader.fieldnames)):
        raise ValueError("UNKNOWN_OFFICIAL_SCHEDULE_CSV_SCHEMA")
    selected = []
    total = 0
    seen = set()
    for row in reader:
        total += 1
        if total > MAX_ROWS:
            raise ValueError("SCHEDULE_ROW_LIMIT_EXCEEDED")
        day_text = (row.get("Date") or "").strip()
        try:
            day = dt.date.fromisoformat(day_text[:10])
        except ValueError:
            raise ValueError("INVALID_OFFICIAL_MEETING_DATE")
        if abs((day - today).days) > window_days:
            continue
        committee = " ".join((row.get("Committee") or "").split())[:180]
        number = " ".join((row.get("MTG #") or "").split())[:40]
        if not committee or not number:
            continue
        identity = (day_text[:10], committee.casefold(), number)
        if identity in seen:
            continue
        seen.add(identity)
        selected.append({
            "meeting_date": day_text[:10], "committee": committee,
            "meeting_number": number,
            "start_time": " ".join((row.get("Start Time") or "").split())[:45],
            "location": " ".join((row.get("Location") or "").split())[:200],
            "term": " ".join((row.get("Term") or "").split())[:35],
            "schedule_evidence": "CITY_CLERK_PUBLISHED_SCHEDULE_ONLY",
            "agenda_url": "",
            "agenda_retrieved": False,
            "publication_date_verified": False, "project_verified": False
        })
    selected.sort(key=lambda row: (
        0 if PLANNING.search(row["committee"]) else 1,
        row["meeting_date"], row["committee"], row["meeting_number"]))
    return selected, total


def run(folder, *, fetch=False, csv_text=None, csv_url=None, now=None,
        downloader=None):
    out = Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    result = {
        "status": "HOLD", "city": "Toronto",
        "dataset_url": CATALOGUE, "resource_id": RESOURCE_ID,
        "schedule_rows_read": 0, "recent_scheduled_meetings": 0,
        "high_priority_committee_meetings": 0,
        "agenda_urls_discovered": 0, "agendas_fetched": 0,
        "publisher_first_publications_verified": 0,
        "verified_projects": 0, "paid_ai_calls": 0,
        "warning": "Official schedule rows alone provide no TMMIS agenda URL, "
                   "published agenda, project, buyer or procurement verification."
    }
    try:
        if csv_text is None:
            if not fetch:
                result["status"] = "NO_FETCH_HISTORICAL_REVIEW"
                return result
            csv_text, csv_url = (downloader or fetch_csv)()
        if csv_url is not None:
            _official_csv_url(csv_url)
        rows, total = parse(csv_text, now=now)
        # Never overwrite prior validated output with a false empty result:
        # a city schedule with no near-term rows can be legitimate, but it
        # must remain an explicit zero-yield review state.
        result["source_sha256"] = hashlib.sha256(
            csv_text.encode("utf-8")).hexdigest()
        result["schedule_rows_read"] = total
        result["recent_scheduled_meetings"] = len(rows)
        result["high_priority_committee_meetings"] = sum(
            bool(PLANNING.search(row["committee"])) for row in rows)
        result["source_csv_url"] = csv_url or ""
        result["status"] = ("RECENT_SCHEDULE_REVIEW_ONLY" if rows
                            else "OFFICIAL_SCHEDULE_NO_NEAR_TERM_MEETINGS")
        with (out / RESULTS_CSV).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            for row in rows:
                cleaned = {k: ("'" + v if isinstance(v, str) and
                             v.lstrip().startswith(("=", "+", "-", "@")) else v)
                           for k, v in row.items()}
                writer.writerow(cleaned)
    except Exception as exc:
        result["status"] = "OFFICIAL_SCHEDULE_BLOCKED_OR_SCHEMA_HELD"
        result["error_type"] = type(exc).__name__
        result["error_reason"] = str(exc)[:180]
    finally:
        (out / STATUS).write_text(json.dumps(result, indent=2),
                                  encoding="utf-8")
    return result
