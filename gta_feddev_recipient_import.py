"""Evidence-only import of the Nov 21 audited FedDev recipient research.

Do not treat a funding announcement as a new 72-hour lead, a confirmed
equipment purchase, an open tender or a verified procurement contact.
This module imports *all* audited recipients and emits a separate durable
watchlist for selective independent procurement checks. No network or AI.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlsplit

SOURCE = Path(__file__).parent / "research" / "feddev_78_recipient_procurement_triage_2026-11-21.csv"
OUT = "GTA_RADAR_FEDDEV_RECIPIENT_EQUIPMENT_WATCHLIST.csv"
STATUS = "GTA_RADAR_FEDDEV_RECIPIENT_IMPORT_STATUS.json"
COLS = ("company", "city", "scope", "equipment_relevance", "source_date",
        "source_date_basis", "official_backgrounder_url", "company_website",
        "public_contact_route", "procurement_stage", "stage_evidence",
        "stage_evidence_url", "specific_order_status", "buyer_verified",
        "open_equipment_order_verified", "freshness", "next_action",
        "research_provenance")

def _https(url):
    try:
        p = urlsplit(url)
        return p.scheme == "https" and bool(p.hostname) and not p.username and not p.password
    except ValueError:
        return False

def run(results, *, today=None, source=SOURCE):
    root = Path(results)
    if not root.is_dir():
        raise FileNotFoundError("EXISTING_RESULTS_REQUIRED")
    day = today or dt.date.today()
    source = Path(source)
    if not source.is_file() or source.is_symlink() or source.stat().st_size > 250_000:
        raise ValueError("AUDITED_RECIPIENT_SOURCE_MISSING_OR_UNSAFE")
    with source.open(encoding="utf-8-sig", newline="") as stream:
        data = list(csv.DictReader(stream))
    if len(data) != 78:
        raise ValueError("AUDITED_RECIPIENT_COUNT_MISMATCH")
    rows, seen = [], set()
    for record in data:
        name = (record.get("Recipient / company") or "").strip()
        city = (record.get("City") or "").strip()
        evidence = (record.get("Official backgrounder URL") or "").strip()
        date = (record.get("Publication date") or "").strip()
        if not name or not city or not _https(evidence):
            raise ValueError("INVALID_RECIPIENT_SOURCE_IDENTITY")
        key = (name.casefold(), city.casefold(), evidence)
        if key in seen:
            raise ValueError("DUPLICATE_RECIPIENT_SOURCE_ROW")
        seen.add(key)
        try:
            published = dt.date.fromisoformat(date)
        except ValueError as exc:
            raise ValueError("INVALID_SOURCE_PUBLICATION_DATE") from exc
        if published > day:
            raise ValueError("FUTURE_DATED_SOURCE_REQUIRES_REVIEW")
        site = (record.get("Company website (linked by FedDev)") or "").strip()
        contact = (record.get("Verified general business route") or "").strip()
        if site and not _https(site):
            site = ""
        independent_url = (record.get("Independent evidence URL") or "").strip()
        if independent_url and not _https(independent_url):
            independent_url = ""
        rows.append({
            "company": name, "city": city,
            "scope": record.get("Official project scope (condensed)", ""),
            "equipment_relevance": record.get("Equipment relevance", ""),
            "source_date": published.isoformat(),
            "source_date_basis": "FEDDEV_BACKGROUND_PUBLICATION_NOT_EQUIPMENT_ORDER",
            "official_backgrounder_url": evidence,
            "company_website": site,
            "public_contact_route": contact,
            "procurement_stage": record.get("Nov 21 procurement-stage assessment", "")
                                   or "NOT_INDEPENDENTLY_VERIFIED",
            "stage_evidence": record.get("Independent follow-up evidence", ""),
            "stage_evidence_url": independent_url,
            "specific_order_status": record.get("Specific order status", "") or "NOT_VERIFIED",
            "buyer_verified": "False", "open_equipment_order_verified": "False",
            "freshness": "HISTORICAL_FEDDEV_RECIPIENT_WATCHLIST_NOT_NEW_ANNOUNCEMENT",
            "next_action": record.get("Next action", "") or "PROCUREMENT_STAGE_CHECK",
            "research_provenance": "AUDITED_2026-11-21_NOT_LIVE_RECHECK",
        })
    destination = root / OUT
    with destination.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("'" + str(row.get(k, "")) if str(row.get(k, "")).lstrip().startswith(
                ("=", "+", "-", "@")) else row.get(k, "")) for k in COLS})
    summary = {
        "status": "FEDDEV_78_HISTORICAL_RECIPIENTS_IMPORTED_RESEARCH_ONLY",
        "as_of": day.isoformat(), "rows": len(rows),
        "explicit_machinery": sum(r["equipment_relevance"] == "Explicit machinery" for r in rows),
        "production_or_technology_expansion": sum(
            r["equipment_relevance"] == "Production/technology expansion" for r in rows),
        "open_orders_verified": 0, "purchasing_contacts_verified": 0,
        "live_procurement_rechecks_performed": 0,
        "source": str(source.relative_to(Path(__file__).parent)),
        "output": OUT,
        "warning": "Source analysis is historical; never count these rows as today's new equipment leads.",
    }
    (root / STATUS).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--results", required=True)
    args = p.parse_args()
    print(json.dumps(run(args.results), indent=2))
