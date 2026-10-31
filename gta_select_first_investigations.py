"""Pick the first investigations from the existing operator-associated records.

Reads GTA_RADAR_PROJECT_OPPORTUNITIES.csv (the records already tagged
IDENTIFIED_PROJECT_OPERATOR), ranks them by deterministic commercial
significance, and writes a worklist. NO network, NO AI, NO cost.

Operator and developer names here came from earlier AI/permit research. They are
printed as UNVERIFIED hints and must be corroborated from an independent official
source before anyone relies on them. The worklist never marks anything verified.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
from pathlib import Path

import candidate_scoring as scoring
from reviewed_evidence import looks_like_street_address

DEFAULT_FILE = "GTA_RADAR_PROJECT_OPPORTUNITIES.csv"
DEFAULT_STRENGTH = "IDENTIFIED_PROJECT_OPERATOR"
UNVERIFIED = "UNVERIFIED_UNTIL_CORROBORATED"
CHECKLIST = ("1 Confirm the exact permit/application and address on the official municipal portal; "
             "2 Corroborate the operator or developer on that company's own site or an official registry; "
             "3 Find who controls purchasing (owner/operator statement, procurement page or published role); "
             "4 Record a public business contact route (not a media-only contact); "
             "5 Check supplier status with affirmative evidence (open tender or packages not yet awarded); "
             "6 Record each confirmation in REVIEWED_EVIDENCE.json")


def _clean_name(value):
    value = str(value or "").strip()
    if not value or value.upper() in ("UNKNOWN", "NONE", "N/A", "-") or looks_like_street_address(value):
        return ""
    return value


def load_records(path, strength=DEFAULT_STRENGTH):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [r for r in rows if (not strength) or r.get("opportunity_strength") == strength]


def _work_item(place, row, result, basis):
    return {
        "rank": place,
        "selection_basis": basis,
        "project_id": row.get("project_id", ""),
        "address": row.get("address", ""),
        "city": row.get("city", ""),
        "operator_name": _clean_name(row.get("operator")) or _clean_name(row.get("official_company")),
        "developer_name": _clean_name(row.get("developer")),
        "operator_developer_status": UNVERIFIED,
        "score": result["score"] if result else "",
        "tier": result["tier"] if result else "NOT_SCORED",
        "why_ranked": "; ".join(result["reasons"][:6]) if result else "",
        "current_source_status": row.get("current_source_status", ""),
        "lifecycle_stage": row.get("lifecycle_stage", ""),
        "supplier_contract_status": row.get("supplier_contract_status") or "UNKNOWN",
        "record_source_url": row.get("record_source_url", ""),
        "verification_checklist": CHECKLIST,
    }


def has_source_text(row):
    """Scoring reads only source-record text. AI-written fields do not count."""
    return bool(str(row.get("description") or "").strip() or str(row.get("official_description") or "").strip())


def prioritize(rows, top=10, pinned=()):
    """Return {'top': [...], 'needs_source_refresh': [...]}.

    top: best scorable records, public bodies excluded; owner-pinned projects come first
    and are labelled PINNED_BY_OWNER (a human decision, never a verification).
    needs_source_refresh: records with no source-record text. They cannot be ranked
    honestly, so they are listed (not buried) until the official record is re-pulled.
    """
    pinned = [str(p).strip() for p in pinned if str(p).strip()]
    by_id = {r.get("project_id", ""): r for r in rows}
    work, used = [], set()
    for pid in pinned:
        row = by_id.get(pid)
        if row is not None and pid not in used:
            result = scoring.score(row) if has_source_text(row) else None
            work.append(_work_item(len(work) + 1, row, result, "PINNED_BY_OWNER"))
            used.add(pid)
    scorable = [r for r in rows if has_source_text(r) and r.get("project_id", "") not in used]
    for row, result in scoring.rank(scorable):
        if result["excluded"]:
            continue
        if len(work) >= top:
            break
        work.append(_work_item(len(work) + 1, row, result, "SCORED_FROM_SOURCE_RECORD"))
    refresh = []
    for row in rows:
        pid = row.get("project_id", "")
        if has_source_text(row) or pid in used:
            continue
        if scoring.PUBLIC_BODY.search(" ".join(str(row.get(k) or "") for k in ("operator", "developer", "official_company"))):
            continue
        item = _work_item("", row, None, "SOURCE_RECORD_MISSING")
        item["why_ranked"] = "No source-record description kept; re-pull the official permit/application text before ranking"
        refresh.append(item)
    return {"top": work, "needs_source_refresh": refresh}


def write_worklist(result, out_dir, *, stamp=None):
    """Write CSV + JSON next to the results. Never overwrites an existing file."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = stamp or dt.date.today().strftime("%Y%m%d")
    n, base = 1, f"FIRST_INVESTIGATIONS_{stamp}"
    while (out_dir / f"{base}.csv").exists() or (out_dir / f"{base}.json").exists():
        n += 1
        base = f"FIRST_INVESTIGATIONS_{stamp}_{n}"
    rows = result["top"] + result["needs_source_refresh"]
    fields = list(rows[0].keys()) if rows else ["rank", "project_id"]
    with (out_dir / f"{base}.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / f"{base}.json").write_text(json.dumps({
        "generated_on": dt.date.today().isoformat(),
        "note": "Operator and developer names are UNVERIFIED hints. Nothing here is a verified lead.",
        **result}, indent=2), encoding="utf-8")
    return out_dir / f"{base}.csv"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--results", required=True, help="GTA_RADAR_RESULTS folder")
    p.add_argument("--out", help="Output folder (default: the results folder)")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--strength", default=DEFAULT_STRENGTH, help="Use '' to include every record")
    p.add_argument("--pin", action="append", default=[], help="Project id to investigate first (owner decision); repeatable")
    a = p.parse_args(argv)
    source = Path(a.results) / DEFAULT_FILE
    if not source.is_file():
        print(f"{DEFAULT_FILE} not found in {a.results}")
        return 1
    rows = load_records(source, a.strength)
    result = prioritize(rows, a.top, a.pin)
    path = write_worklist(result, a.out or a.results)
    print(f"{len(rows)} operator-associated records read; worklist written to {path}")
    for item in result["top"]:
        print(f"{item['rank']:>2}. [{str(item['score']):>3}] {item['address']} | operator (unverified): {item['operator_name'] or '-'} | {item['selection_basis']}")
    if result["needs_source_refresh"]:
        print(f"\n{len(result['needs_source_refresh'])} record(s) have no source-record text and cannot be ranked until re-pulled:")
        for item in result["needs_source_refresh"]:
            print(f"    - {item['address']} | operator (unverified): {item['operator_name'] or '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
