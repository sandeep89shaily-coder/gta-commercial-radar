"""GROUND/Datum comparison pack from GTA Radar's OWN records, with manual verification.

No scraping or network access to competitor systems; no project coverage is
inferred from an absent Google result. Human-entered review fields are retained.
Only actually evidenced, same-project precise detection timestamps can be
compared. The file is a research worklist, not a sales-ready claim.
"""
from __future__ import annotations

import csv
from contextlib import closing
import datetime as dt
import html
import json
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

COMPETITORS = (
    ("GROUND", "https://groundintel.ca/places"),
    ("Datum", "https://datumai.ca/"),
)
PERMANENT = "GTA_RADAR_COMPETITOR_MANUAL_REVIEWS.csv"
PREFIX = "GTA_RADAR_GROUND_DATUM_COMPARISON_"
LEVELS = {"NOT_CHECKED", "ADDRESS_ONLY", "SAME_PROJECT", "EXACT_PERMIT",
          "NO_PUBLIC_MATCH_OBSERVED", "INCONCLUSIVE"}
PROVEN = {"SAME_PROJECT", "EXACT_PERMIT"}
MANUAL_FIELDS = (
    "match_level", "competitor_record_url", "match_evidence_url",
    "competitor_first_detected_at", "competitor_detection_proof_url",
    "reviewed_on", "researcher_notes",
)
FIELDS = (
    "project_id", "address", "city", "radar_source_description",
    "radar_freshness_band", "radar_source_date", "radar_source_date_basis",
    "radar_first_seen_local_date", "radar_first_seen_precise_utc",
    "radar_source_url", "competitor", "competitor_start_page",
    *MANUAL_FIELDS, "first_seen_comparison_status",
    "radar_lead_days_if_verified", "evidence_warning",
)


def _valid_http(url):
    try:
        p = urlparse(str(url or "").strip())
        return p.scheme in ("http", "https") and bool(p.hostname) and not p.username and not p.password
    except ValueError:
        return False


def _read(path):
    if not Path(path).is_file():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_atomic(path, rows):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


def _precise(stamp):
    raw = str(stamp or "").strip()
    # Calendar date alone is NOT a valid precise first-detection timestamp.
    if "T" not in raw:
        return None
    try:
        value = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value.astimezone(dt.timezone.utc) if value.tzinfo else None


def _radar_first_seen(root):
    """Read Radar's append-only first-seen SQLite in read-only mode."""
    file = Path(root) / "RADAR_DISCOVERY_LEDGER.sqlite"
    if not file.is_file():
        return {}
    try:
        with closing(sqlite3.connect(f"{file.resolve().as_uri()}?mode=ro", uri=True)) as db:
            return {pid:stamp for pid,stamp in
                    db.execute("SELECT project_id, first_seen_at FROM discovery")
                    if pid and _precise(stamp)}
    except sqlite3.DatabaseError:
        return {}


def _compare(row):
    level = str(row.get("match_level") or "").strip()
    if level not in LEVELS:
        return "INVALID_MANUAL_MATCH_LEVEL", ""
    if level not in PROVEN:
        return "NOT_COMPARABLE_NOT_SAME_PROJECT_CONFIRMED", ""
    if not (_valid_http(row.get("match_evidence_url"))
            and _valid_http(row.get("competitor_record_url"))):
        return "NOT_COMPARABLE_MATCH_EVIDENCE_MISSING", ""
    radar = _precise(row.get("radar_first_seen_precise_utc"))
    theirs = _precise(row.get("competitor_first_detected_at"))
    if not (radar and theirs and _valid_http(row.get("competitor_detection_proof_url"))):
        return "NOT_COMPARABLE_DETECTION_TIMESTAMP_UNPROVEN", ""
    days = (theirs - radar).total_seconds() / 86400
    # Positive: Radar observed earlier; negative: competitor earlier. These
    # are observed detection timestamps, NOT earliest public disclosure dates.
    return "COMPARABLE_REVIEW_ONLY", f"{days:.2f}"


def build(results, projects, *, today=None):
    root = Path(results)
    root.mkdir(parents=True, exist_ok=True)
    day = today or dt.date.today()
    saved = _read(root / PERMANENT)
    by_key = {(r.get("project_id",""),r.get("competitor","")):r
              for r in saved if r.get("project_id") and r.get("competitor")}
    seen = _radar_first_seen(root)
    daily = []
    for p in projects:
        pid = str(p.get("project_id") or "").strip()
        if not pid:
            continue
        for competitor, start_page in COMPETITORS:
            old = by_key.get((pid, competitor), {})
            fresh = {
                "project_id":pid,
                "address":p.get("address",""),
                "city":p.get("city",""),
                "radar_source_description":p.get("source_description") or p.get("description") or "",
                "radar_freshness_band":p.get("freshness_band",""),
                "radar_source_date":p.get("source_record_date",""),
                "radar_source_date_basis":p.get("freshness_date_basis") or p.get("date_basis") or "",
                "radar_first_seen_local_date":p.get("radar_first_seen") or p.get("first_seen_local") or "",
                "radar_first_seen_precise_utc":seen.get(pid,""),
                "radar_source_url":p.get("source_url") or p.get("record_source_url") or "",
                "competitor":competitor,
                "competitor_start_page":start_page,
                **{k:old.get(k,"") for k in MANUAL_FIELDS},
                "evidence_warning":("UNVERIFIED_RESEARCH_WORKLIST: exact project match, "
                    "competitor detection and publication dates must be checked manually."),
            }
            if not fresh["match_level"]:
                fresh["match_level"] = "NOT_CHECKED"
            status, lead = _compare(fresh)
            fresh["first_seen_comparison_status"] = status
            fresh["radar_lead_days_if_verified"] = lead
            by_key[(pid, competitor)] = fresh
            daily.append(fresh)
    # Persist all previously reviewed projects, not just today's selected
    # projects. Manual fields are reused on each future run.
    _write_atomic(root / PERMANENT,
                  [by_key[key] for key in sorted(by_key)])
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    csv_name = PREFIX + stamp + ".csv"
    html_name = PREFIX + stamp + ".html"
    _write_atomic(root / csv_name, daily)
    escape = lambda value: html.escape(str(value or ""), quote=True)
    page = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<title>GTA Radar — GROUND / Datum comparison</title>",
        "<style>body{font:14px Segoe UI,Arial,sans-serif;max-width:1150px;margin:30px auto;padding:0 16px;color:#172d3b}table{border-collapse:collapse;width:100%}th,td{padding:11px 9px;border-bottom:1px solid #dbe2e7;text-align:left;vertical-align:top}th{background:#eef4f6}small{color:#566b79}a{color:#086487}</style>",
        "<h1>GTA Radar — GROUND / Datum competitive match review</h1>",
        "<p>Each row is a HUMAN REVIEW assignment, not proof the competitor does or does not cover the project. "
        "Use public, permitted browser access only. Do not scrape competitor-derived data. "
        "Only same-project/exact-permit matching plus independently evidenced, timezone-aware timestamps "
        "permit observed-detection comparisons. A project source date is not an announcement date.</p>",
        "<p><a href='" + csv_name + "'>Export today's comparison (CSV)</a> · "
        "Persistent editable research file: " + PERMANENT + "</p>",
        "<table><tr><th>Radar project</th><th>Source freshness</th><th>Competitor</th><th>Match review</th><th>Detection comparison</th></tr>",
    ]
    for r in daily:
        url = r["competitor_record_url"] if _valid_http(r["competitor_record_url"]) else r["competitor_start_page"]
        page.append("<tr><td><b>"+escape(r["address"] or r["project_id"])+"</b><br><small>"+
                    escape(r["project_id"])+"</small></td><td>"+
                    escape(r["radar_freshness_band"] or "UNKNOWN")+"</td><td><a href='"+
                    escape(url)+"'>"+escape(r["competitor"])+"</a></td><td>"+
                    escape(r["match_level"])+"</td><td>"+
                    escape(r["first_seen_comparison_status"])+
                    (" · "+escape(r["radar_lead_days_if_verified"])+" days" if
                     r["radar_lead_days_if_verified"] else "")+"</td></tr>")
    page.append("</table></body></html>")
    (root / html_name).write_text("".join(page), encoding="utf-8")
    summary = {
        "generated_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "projects_checked_in_worklist":len({r["project_id"] for r in daily}),
        "competitor_review_rows":len(daily),
        "confirmed_same_project_or_exact_permit":sum(
            r["match_level"] in PROVEN and _valid_http(r["match_evidence_url"])
            for r in daily),
        "comparable_first_detection_pairs":sum(
            r["first_seen_comparison_status"]=="COMPARABLE_REVIEW_ONLY" for r in daily),
        "public_competitor_data_scraped":False,
        "competitor_coverage_unchecked_is_unknown":True,
        "comparison_csv":str(root / csv_name),
        "comparison_html":str(root / html_name),
        "persistent_manual_reviews_csv":str(root / PERMANENT),
        "limitations":"No competitor coverage or first-detection advantage inferred from search absence; source dates do not prove earliest publication.",
    }
    return summary


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--results", required=True, help="GTA_RADAR_RESULTS folder")
    p.add_argument("--projects-csv", required=True, help="Existing GTA_RADAR_PROJECTS_TO_VERIFY_*.csv")
    a = p.parse_args()
    print(json.dumps(build(a.results, _read(a.projects_csv)), indent=2))
