"""Conservative council/committee document-link delta pilot.

Tracks exact official agenda/document links exposed by existing meeting
discovery, not "new projects", municipal posting dates, or confirmed approvals.
No recording downloads, AI calls, database resets, or scheduled runs.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from municipal_meeting_capture import discover, OFFICIAL

LEDGER = "COUNCIL_DOCUMENT_LINK_LEDGER.json"
EVENTS = "COUNCIL_DOCUMENT_LINK_EVENTS.csv"
STATUS = "COUNCIL_DOCUMENT_LINK_STATUS.json"
FIELDS = ("city", "document_id", "document_url", "document_title",
          "discovery_source", "first_observed_utc", "last_observed_utc",
          "event", "evidence_level", "publication_date", "source_content_checked")


def canonical_url(raw):
    """Remove fragments only. Never collapse distinct PDF/query item identities."""
    s = urlsplit(str(raw or "").strip())
    if s.scheme != "https" or not s.hostname or s.username or s.password:
        raise ValueError("HTTPS_SOURCE_REQUIRED")
    return urlunsplit((s.scheme, s.netloc.lower(), s.path, s.query, ""))


def _identity(city, url):
    return hashlib.sha256((city.casefold() + "|" + url).encode("utf-8")).hexdigest()[:24]


def _read(path):
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("version") != 1 or not isinstance(payload.get("items"), dict):
        raise ValueError("UNRECOGNIZED_LEDGER_SCHEMA")
    return payload["items"]


def _write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            out = {k: row.get(k, "") for k in FIELDS}
            for key, value in out.items():
                if str(value).lstrip().startswith(("=", "+", "-", "@")):
                    out[key] = "'" + str(value)
            writer.writerow(out)


def run(city, results, *, fetch=None, now=None):
    if city not in OFFICIAL:
        raise ValueError("UNSUPPORTED_MUNICIPALITY")
    folder = Path(results)
    folder.mkdir(parents=True, exist_ok=True)
    current_time = now or dt.datetime.now(dt.timezone.utc)
    if current_time.tzinfo is None:
        raise ValueError("TIMEZONE_AWARE_TIMESTAMP_REQUIRED")
    at = current_time.astimezone(dt.timezone.utc).isoformat()
    ledger_path = folder / LEDGER
    before = _read(ledger_path)
    # Keep previously accepted evidence intact if the official portal blocks
    # collection or a parser/source failure occurs.
    try:
        snapshot = discover(city, fetch=fetch, now=current_time)
        source_state = snapshot.get("official_index_status", "UNKNOWN")
        if source_state != "INDEX_FETCHED_LINK_ONLY":
            return _status_only(folder, city, source_state, at,
                                "INDEX_NOT_FETCHED_NO_LEDGER_MUTATION")
        candidates = snapshot.get("agenda_candidates", [])
        if not isinstance(candidates, list):
            raise ValueError("INVALID_DISCOVERY_SCHEMA")
        newest = {}
        for row in candidates:
            url = canonical_url(row["url"])
            # Discovery has already restricted links to official hosts.
            # Treat the linked file as unverified: no document fetched.
            if row.get("city") != city or row.get("discovery_source") != OFFICIAL[city]:
                raise ValueError("UNEXPECTED_DOCUMENT_ORIGIN")
            docid = _identity(city, url)
            title = " ".join(str(row.get("title") or "").split())[:180]
            if docid in newest and newest[docid]["title"] != title:
                raise ValueError("CONFLICTING_DOCUMENT_LINK_LABELS")
            newest[docid] = {"city": city, "url": url, "title": title,
                             "discovery_source": OFFICIAL[city]}
    except Exception as exc:
        # A parser/schema error must not be misreported as zero agenda items.
        return _status_only(folder, city, "DISCOVERY_FAILED", at,
                            type(exc).__name__ + ": " + str(exc)[:160])
    # Each municipality must have its own baseline even when the shared ledger\n    # already contains another city. A second city is not a new publication.\n    previous_city = {key: item for key, item in before.items()\n                     if item.get("city") == city}\n    baseline = not previous_city\n    retained = dict(before)
    changed = []
    newly_observed = 0
    renamed = 0
    for docid, row in sorted(newest.items()):
        old = before.get(docid)
        if old and (old.get("url") != row["url"] or old.get("city") != city):
            raise ValueError("CONFLICTING_STORED_DOCUMENT_IDENTITY")
        event = ("BASELINE_EXISTING_LINK_NOT_NEW_PUBLICATION" if baseline
                 else "FIRST_OBSERVED_LINK_NOT_NEW_PUBLICATION" if old is None
                 else "INDEX_LINK_TITLE_CHANGED_NOT_PROJECT_UPDATE" if old.get("title") != row["title"]
                 else "UNCHANGED_LINK")
        if event.startswith("FIRST_OBSERVED"):
            newly_observed += 1
        if event.startswith("INDEX_LINK_TITLE_CHANGED"):
            renamed += 1
        first = old.get("first_observed_utc", at) if old else at
        retained[docid] = {
            **row, "first_observed_utc": first, "last_observed_utc": at,
            "evidence_level": "OFFICIAL_INDEX_LINK_ONLY_UNREAD_DOCUMENT",
            "publication_date": None, "source_content_checked": False}
        if event != "UNCHANGED_LINK":
            changed.append({
                "city": city, "document_id": docid,
                "document_url": row["url"], "document_title": row["title"],
                "discovery_source": row["discovery_source"],
                "first_observed_utc": first, "last_observed_utc": at,
                "event": event,
                "evidence_level": "OFFICIAL_INDEX_LINK_ONLY_UNREAD_DOCUMENT",
                "publication_date": "", "source_content_checked": "false"})
    # Never infer removals from a partial/dynamic index or link absence.
    ledger = {"version": 1, "updated_utc": at, "items": retained}
    temp = ledger_path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    temp.replace(ledger_path)
    _write_csv(folder / EVENTS, changed)\n    # Per-city snapshots avoid one city overwriting another during sequential runs.\n    # Retain existing filenames for compatibility with single-city consumers.\n    _write_csv(folder / (city.upper() + "_" + EVENTS), changed)
    summary = {
        "city": city, "checked_utc": at,
        "status": "INDEX_LINK_BASELINE_ONLY" if baseline else "INDEX_LINK_DELTA_REVIEW_ONLY",
        "official_index_status": source_state,
        "links_visible_this_check": len(newest),
        "first_observed_links": newly_observed,
        "changed_link_titles": renamed,
        "historical_links_retained": len(retained),
        "links_missing_from_current_index_not_removed": len(set(previous_city) - set(newest)),
        "new_publications_verified": 0, "actual_document_contents_retrieved": 0,
        "verified_projects": 0, "buyer_or_procurement_verified": 0,
        "warning": "First observed is not first published. Index links and title edits are not project approvals. Read exact linked agenda/staff report separately, subject to source permissions."
    }
    (folder / STATUS).write_text(json.dumps(summary, indent=2), encoding="utf-8")\n    (folder / (city.upper() + "_" + STATUS)).write_text(\n        json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _status_only(folder, city, source_state, at, explanation):
    result = {
        "city": city, "checked_utc": at, "status": "SOURCE_HELD_NO_LEDGER_MUTATION",
        "official_index_status": source_state, "reason": explanation,
        "new_publications_verified": 0, "verified_projects": 0,
        "warning": "No assertion of empty/no-new municipal agenda documents."
    }
    (folder / STATUS).write_text(json.dumps(result, indent=2), encoding="utf-8")\n    (folder / (city.upper() + "_" + STATUS)).write_text(\n        json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", choices=sorted(OFFICIAL), required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.city, args.out), indent=2))
