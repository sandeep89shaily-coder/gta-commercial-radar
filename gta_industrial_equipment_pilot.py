"""Isolated, zero-AI industrial equipment-change pilot for GTA Radar.

Reads Radar's existing ERO ledger read-only. Search cards rarely contain detailed
equipment proposals, so a separately verified official-notice excerpt CSV is
required for change extraction. Never turn a source mention into an open bid.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

# Exact site-city gate. The upstream ERO collector can match a company name
# containing "York" even when its actual facility is outside the target area.
TARGET_CITIES = frozenset({
    "toronto", "brampton", "mississauga", "caledon", "oakville", "burlington",
    "milton", "halton hills", "vaughan", "richmond hill", "markham",
    "newmarket", "aurora", "east gwillimbury", "king", "whitchurch-stouffville",
    "pickering", "ajax", "whitby", "oshawa", "clarington", "hamilton",
    "cambridge", "kitchener", "waterloo", "guelph", "st. catharines",
    "st catharines", "niagara falls", "welland", "grimsby", "lincoln",
    "barrie", "innisfil", "new tecumseth",
})

ERO_SOURCE = "ero_gta_environmental_instruments"
OUTPUT = "GTA_RADAR_INDUSTRIAL_EQUIPMENT_REVIEW.csv"
STATUS = "GTA_RADAR_INDUSTRIAL_EQUIPMENT_STATUS.json"
HTML = "GTA_RADAR_INDUSTRIAL_EQUIPMENT_REVIEW.html"
PROJECT_FILES = (
    "GTA_RADAR_COLLECTION_MASTER.csv",
    "GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv",
    "GTA_RADAR_INTEGRATED_INTELLIGENCE.csv",
    "GTA_RADAR_V8_PROJECTS.csv",
    "GTA_RADAR_PROJECT_OPPORTUNITIES.csv",
)
EQUIPMENT = {
    "Dust collection": r"\b(?:dust collector|baghouse|cartridge filter)\b",
    "Scrubber": r"\b(?:wet scrubber|dry scrubber|scrubber)\b",
    "Industrial ventilation": r"\b(?:industrial ventilation|exhaust fan|fume hood)\b",
    "Boiler": r"\b(?:boilers?|steam generator)\b",
    "Cooling tower": r"\b(?:cooling towers?)\b",
    "Industrial refrigeration": r"\b(?:industrial refrigeration|ammonia refrigeration|chiller)\b",
    "Process line": r"\b(?:bottling line|production line|processing line)\b",
    "Wastewater treatment": r"\b(?:wastewater treatment system|effluent treatment system)\b",
    "Transformer": r"\b(?:transformers?|switchgear)\b",
    "Furnace": r"\b(?:industrial furnace|kiln)\b",
}
ACTIONS = {
    "REPLACEMENT": r"\b(?:replac(?:e|es|ed|ing|ement)|substitut(?:e|ion))\b",
    "INSTALLATION": r"\b(?:install(?:ation|ed|ing)?|add(?:ed|ition|ing)?|new)\b",
    "UPGRADE": r"\b(?:upgrad(?:e|ed|ing)|retrofit|moderniz(?:e|ation)|refurbish)\b",
    "EXPANSION": r"\b(?:expand(?:ed|ing)?|expansion|extend(?:ed|ing)?|extension)\b",
    "REMOVAL": r"\b(?:remov(?:e|al|ed|ing)|decommission(?:ed|ing)?)\b",
}
REGEX_EQUIPMENT = {k: re.compile(v, re.I) for k, v in EQUIPMENT.items()}
REGEX_ACTIONS = {k: re.compile(v, re.I) for k, v in ACTIONS.items()}
NEGATED = re.compile(
    r"\b(?:no|not|without)\s+(?:(?:currently|planned|proposed|any|further)\s+){0,3}"
    r"(?:replacement|installation|upgrade|expansion|removal|change|changes|new equipment)\b",
    re.I,
)
INVENTORY = re.compile(
    r"\b(?:existing (?:sources|equipment)|sources at (?:the|this) facility include|"
    r"facility currently includes|emission sources include)\b",
    re.I,
)
COLUMNS = (
    "signal_id", "ero_number", "official_notice_url", "notice_stage",
    "proponent", "site_address", "city", "proposal_posted",
    "radar_first_seen_at", "radar_record_present", "equipment", "action",
    "official_excerpt", "evidence_basis", "project_match_status",
    "related_project_id", "related_project_source_url", "procurement_status",
    "buyer_verified", "review_status",
)

def _str(value):
    return " ".join(str(value or "").split()).strip()

def _official_notice(url, number):
    p = urlsplit(_str(url))
    return (
        p.scheme == "https" and p.hostname == "ero.ontario.ca"
        and p.username is None and p.password is None and p.port in (None, 443)
        and p.path.rstrip("/") == "/notice/" + number
    )

def _number(value):
    s = _str(value)
    return s if re.fullmatch(r"\d{3}-\d{4}", s) else ""

def _norm_address(value):
    s = re.sub(r"[^a-z0-9 ]", " ", _str(value).lower())
    s = re.sub(r"\b(?:street|st)\b", "st", s)
    s = re.sub(r"\b(?:drive|dr)\b", "dr", s)
    s = re.sub(r"\b(?:road|rd)\b", "rd", s)
    s = re.sub(r"\b(?:avenue|ave)\b", "ave", s)
    return " ".join(s.split())

def _read_csv(path):
    if not path or not Path(path).is_file():
        return []
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def read_radar_ero(db):
    """Read latest full raw ERO cards, never update the production SQLite file."""
    if db is None:
        return {}
    p = Path(db)
    if not p.is_file():
        raise FileNotFoundError("Radar database not found: " + str(p))
    uri = p.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=6) as conn:
        values = conn.execute(
            """SELECT c.record_key,c.first_seen_at,c.source_date,v.payload_json
               FROM records_current c JOIN record_versions v
               ON v.source_id=c.source_id AND v.record_key=c.record_key
               AND v.version_id=(
                 SELECT MAX(t.version_id) FROM record_versions t
                 WHERE t.source_id=c.source_id AND t.record_key=c.record_key
               )
               WHERE c.source_id=? AND c.active=1""", (ERO_SOURCE,)
        ).fetchall()
    out = {}
    for key, first_seen, source_date, raw in values:
        try:
            card = json.loads(raw)
        except (TypeError, ValueError):
            continue
        no = _number(card.get("ERO_NUMBER", key))
        if not no:
            continue
        url = _str(card.get("NOTICE_URL"))
        if not _official_notice(url, no):
            continue
        out[no] = {
            "ero_number": no, "official_notice_url": url,
            "notice_stage": _str(card.get("NOTICE_STAGE")),
            "proponent": _str(card.get("ENTITY_NAME")),
            "proposal_posted": _str(card.get("PROPOSAL_POSTED")),
            "radar_first_seen_at": _str(first_seen),
            "source_date": _str(source_date),
        }
    return out

def _notices(path):
    """Only human-sourced exact ERO notice excerpts; no guessed full text."""
    accepted = {}
    rejected = []
    for line, item in enumerate(_read_csv(path), start=2):
        number = _number(item.get("ero_number"))
        url = _str(item.get("official_notice_url") or item.get("notice_url"))
        excerpt = _str(item.get("proposal_details") or item.get("official_excerpt"))
        if not number or not _official_notice(url, number) or not excerpt:
            rejected.append({"row": line, "reason": "INVALID_ID_URL_OR_MISSING_EXCERPT"})
            continue
        if number in accepted:
            rejected.append({"row": line, "reason": "DUPLICATE_ERO_NOTICE"})
            continue
        accepted[number] = {
            "ero_number": number, "official_notice_url": url,
            "notice_stage": _str(item.get("notice_stage")),
            "proponent": _str(item.get("proponent")),
            "site_address": _str(item.get("site_address")),
            "city": _str(item.get("city")),
            "proposal_posted": _str(item.get("proposal_posted")),
            "proposal_details": excerpt[:25000],
        }
    return accepted, rejected

def equipment_changes(text):
    """Conservative proposed physical changes, not an existing equipment list."""
    found = []
    seen = set()
    for clause in re.split(r"[;\n]+|(?<=[.!?])\s+", _str(text)):
        if len(clause) > 1000:
            continue
        if NEGATED.search(clause) or INVENTORY.search(clause):
            continue
        for equipment, pattern in REGEX_EQUIPMENT.items():
            equipment_match = pattern.search(clause)
            if not equipment_match:
                continue
            choices = []
            for action, action_pattern in REGEX_ACTIONS.items():
                for match in action_pattern.finditer(clause):
                    distance = min(abs(match.end() - equipment_match.start()),
                                   abs(equipment_match.end() - match.start()))
                    if distance <= 100:
                        choices.append((distance, action))
            if not choices:
                continue
            action = min(choices)[1]
            marker = (equipment, action)
            if marker not in seen:
                seen.add(marker)
                found.append({"equipment": equipment, "action": action,
                              "official_excerpt": clause[:500]})
    return found

def _projects(results):
    index = {}
    if results is None:
        return index
    for name in PROJECT_FILES:
        for row in _read_csv(Path(results) / name):
            address = _norm_address(row.get("address"))
            city = _str(row.get("city") or row.get("municipality")).casefold()
            pid = _str(row.get("project_id") or row.get("canonical_id"))
            if not address or not city or not pid:
                continue
            index.setdefault((address, city), []).append({
                "project_id": pid,
                "source_url": _str(row.get("source_url") or row.get("record_source_url")),
            })
    return index

def run(out, *, db=None, notice_csv=None, results=None):
    if db is None and notice_csv is None:
        raise ValueError("Provide --db and/or --notice-csv; no auto-fetch is performed")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    cards = read_radar_ero(db)
    notices, rejected = _notices(notice_csv)
    projects = _projects(results)
    signals = []
    site_exclusions = []
    for number, notice in sorted(notices.items()):
        # Never infer facility location from the proponent mailing address/name.
        if _str(notice.get("city")).casefold() not in TARGET_CITIES:
            site_exclusions.append({"ero_number": number, "reason": "MISSING_OR_OUT_OF_SCOPE_SITE_CITY"})
            continue
        card = cards.get(number, {})
        # When the card exists, its stored first observation is the ONLY source
        # of Radar first-seen truth. Notice posted dates stay separate.
        base = {
            **card, **{k: v for k, v in notice.items() if k != "proposal_details" and v},
            "radar_first_seen_at": card.get("radar_first_seen_at", ""),
            "radar_record_present": "YES" if card else "NO",
        }
        address = _norm_address(notice.get("site_address"))
        city = _str(notice.get("city")).casefold()
        matched = projects.get((address, city), []) if address and city else []
        for finding in equipment_changes(notice["proposal_details"]):
            sid = hashlib.sha256(
                (number + "|" + finding["equipment"] + "|" + finding["action"]).encode()
            ).hexdigest()[:20]
            # More than one project at an address is ambiguous by definition.
            relation = ("UNVERIFIED_SINGLE_SITE_CANDIDATE" if len(matched) == 1 else
                        "UNVERIFIED_MULTIPLE_SITE_CANDIDATES" if matched else
                        "NO_PROJECT_MATCH")
            signals.append({
                **base, **finding, "signal_id": sid,
                "evidence_basis": "USER_SUPPLIED_OFFICIAL_NOTICE_EXCERPT_NOT_LIVE_RECHECKED",
                "project_match_status": relation,
                "related_project_id": matched[0]["project_id"] if len(matched) == 1 else "",
                "related_project_source_url": matched[0]["source_url"] if len(matched) == 1 else "",
                "procurement_status": "UNKNOWN", "buyer_verified": "NO",
                "review_status": "MANUAL_REVIEW_REQUIRED",
            })
    with (out / OUTPUT).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(signals)
    rows = "".join(
        "<tr>" + "".join("<td>" + html.escape(str(s.get(key, ""))) + "</td>"
                            for key in ("ero_number", "proponent", "city", "equipment",
                                        "action", "official_excerpt", "project_match_status")) +
        "</tr>" for s in signals
    )
    (out / HTML).write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>Industrial Equipment Pilot</title>"
        "<style>body{font:14px Arial,sans-serif;margin:24px}table{border-collapse:collapse}"
        "th,td{border:1px solid #ddd;padding:8px;text-align:left;vertical-align:top}"
        "th{background:#f2f2f2}</style></head><body><h1>Industrial equipment review only</h1>"
        "<p>These are source-text change candidates, not verified orders, open bids, "
        "or proven company/project matches. Each finding needs official notice recheck.</p>"
        "<table><tr><th>ERO</th><th>Proponent</th><th>City</th><th>Equipment</th>"
        "<th>Action</th><th>Source excerpt</th><th>Project link</th></tr>" + rows +
        "</table></body></html>", encoding="utf-8"
    )
    summary = {
        "mode": "OFFLINE_REVIEW_ONLY_NO_LIVE_FETCH_NO_PAID_AI",
        "ero_cards_in_existing_ledger": len(cards),
        "official_notice_excerpts_loaded": len(notices),
        "rejected_notice_rows": rejected,
        "excluded_out_of_scope_sites": site_exclusions,
        "equipment_change_candidates": len(signals),
        "same_site_candidate_links": sum(s["project_match_status"] ==
            "UNVERIFIED_SINGLE_SITE_CANDIDATE" for s in signals),
        "verified_buyers": 0, "verified_open_procurement": 0,
        "limitations": [
            "ERO search cards do not establish full proposal equipment scope",
            "Notice CSV excerpts need manual verification against original ERO pages",
            "Matching address and city never proves same project or purchasing authority",
            "No live source retrieval, enrichment of missing notice details, or outreach",
        ],
        "csv": str(out / OUTPUT), "html": str(out / HTML),
    }
    (out / STATUS).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, help="Existing data/radar.sqlite, read-only")
    parser.add_argument("--notice-csv", type=Path, help="Official ERO notice excerpts entered for review")
    parser.add_argument("--results", type=Path, help="Existing GTA_RADAR_RESULTS directory, read-only")
    parser.add_argument("--out", type=Path, required=True, help="Separate pilot output directory")
    args = parser.parse_args()
    print(json.dumps(run(args.out, db=args.db, notice_csv=args.notice_csv,
                         results=args.results), indent=2))

if __name__ == "__main__":
    main()
