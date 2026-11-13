"""Twenty-case evidence gate for council agenda → application → permit linkage.

Read-only CSV comparison. Exact normalized application IDs AND civic addresses
required for an application join; permit linkage additionally needs a matching
application ID. Sources and dates are never manufactured. Missing/ambiguous
evidence yields HOLD, not a verified project or a commercial lead.
"""
from __future__ import annotations
import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from gta_facility_intelligence import normalize_address

OUT = "GTA_AGENDA_APPLICATION_PERMIT_20_CASE_REVIEW.csv"
STATUS = "GTA_AGENDA_APPLICATION_PERMIT_20_CASE_STATUS.json"
REQUIRED = {
    "agenda": {"city", "application_id", "address_raw", "source_pdf_url",
               "item_number", "pdf_sha256"},
    "application": {"city", "application_id", "address", "source_url", "project_id"},
    "permit": {"city", "application_id", "address", "source_url", "permit_id"},
}
FIELDS = (
    "city", "agenda_item", "agenda_application_id", "agenda_address",
    "agenda_source_url", "agenda_pdf_sha256",
    "matched_application_project_id", "matched_application_url",
    "matched_permit_id", "matched_permit_url", "status", "hold_reason",
    "match_basis", "official_publication_verified", "early_detection_days",
    "buyer_verified", "procurement_verified"
)
MAX_ROWS = 50000


def _clean(s):
    return " ".join(str(s or "").split()).strip()


def _key(s):
    s = re.sub(r"\s+", "", _clean(s)).upper()
    return s if (4 <= len(s) <= 100 and re.search(r"[0-9]", s)
                 and re.search(r"[/.\-A-Z]", s)) else ""


def _addr(s):
    return normalize_address(_clean(s))


def _url(s):
    p = urlsplit(str(s or ""))
    return p.scheme == "https" and bool(p.hostname) and not p.username and not p.password


def read(path, kind):
    if not path:
        return None
    path = Path(path)
    if not path.is_file():
        return None
    if path.stat().st_size > 22_000_000:
        raise ValueError(kind + "_CSV_OVERSIZED")
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames or not REQUIRED[kind].issubset(reader.fieldnames):
            raise ValueError(kind + "_SCHEMA_MISSING_" +
                             ",".join(sorted(REQUIRED[kind] - set(reader.fieldnames or []))))
        rows = list(reader)
    if len(rows) > MAX_ROWS:
        raise ValueError(kind + "_TOO_MANY_RECORDS")
    return rows


def _index(rows):
    data = defaultdict(list)
    for row in rows or []:
        city = _clean(row.get("city")).casefold()
        aid = _key(row.get("application_id"))
        if city and aid:
            data[(city, aid)].append(row)
    return data


def compare(agenda, applications=None, permits=None, limit=20):
    if not 1 <= limit <= 100:
        raise ValueError("REVIEW_LIMIT_OUT_OF_BOUNDS")
    appindex = _index(applications)
    permitindex = _index(permits)
    cases = []
    for item in agenda[:limit]:
        city = _clean(item.get("city"))
        aid = _key(item.get("application_id"))
        address = _addr(item.get("address_raw"))
        base = {
            "city": city, "agenda_item": _clean(item.get("item_number")),
            "agenda_application_id": aid,
            "agenda_address": _clean(item.get("address_raw")),
            "agenda_source_url": _clean(item.get("source_pdf_url")),
            "agenda_pdf_sha256": _clean(item.get("pdf_sha256")),
            "matched_application_project_id": "", "matched_application_url": "",
            "matched_permit_id": "", "matched_permit_url": "",
            "official_publication_verified": False, "early_detection_days": "",
            "buyer_verified": False, "procurement_verified": False,
            "match_basis": "", "status": "HOLD", "hold_reason": ""
        }
        if not city or not aid or not address[0] or not _url(base["agenda_source_url"]):
            base["hold_reason"] = "AGENDA_ID_ADDRESS_OR_ORIGIN_MISSING"
        elif not re.fullmatch(r"[0-9a-fA-F]{64}", base["agenda_pdf_sha256"]):
            base["hold_reason"] = "ACTUAL_AGENDA_PDF_SHA256_NOT_CAPTURED"
        elif applications is None:
            base["hold_reason"] = "APPLICATION_EXPORT_UNAVAILABLE"
        else:
            matches = [r for r in appindex[(city.casefold(), aid)]
                       if _addr(r.get("address")) == address and _url(r.get("source_url"))]
            if len(matches) != 1:
                base["hold_reason"] = ("NO_EXACT_APPLICATION_ID_AND_SITE"
                                       if not matches else "AMBIGUOUS_APPLICATION_MATCH")
            else:
                app = matches[0]
                base["matched_application_project_id"] = _clean(app["project_id"])
                base["matched_application_url"] = _clean(app["source_url"])
                base["match_basis"] = "SAME_CITY_APPLICATION_ID_AND_NORMALIZED_SITE_REVIEW_ONLY"
                if permits is None:
                    base["hold_reason"] = "PERMIT_EXPORT_UNAVAILABLE"
                else:
                    pmatches = [r for r in permitindex[(city.casefold(), aid)]
                                if _addr(r.get("address")) == address and
                                _url(r.get("source_url")) and _clean(r.get("permit_id"))]
                    if len(pmatches) != 1:
                        base["hold_reason"] = ("NO_EXACT_PERMIT_APPLICATION_ID_AND_SITE"
                                               if not pmatches else "AMBIGUOUS_PERMIT_MATCH")
                    else:
                        permit = pmatches[0]
                        base["matched_permit_id"] = _clean(permit["permit_id"])
                        base["matched_permit_url"] = _clean(permit["source_url"])
                        base["status"] = "THREE_SOURCE_IDENTITY_REVIEW_NOT_INDEPENDENTLY_VERIFIED"
                        base["hold_reason"] = "ORIGINAL_RECORDS_AND_PUBLICATION_DATES_NEED_REVIEW"
        cases.append(base)
    return cases


def run(agenda_csv, application_csv, permit_csv, out, limit=20):
    agenda = read(agenda_csv, "agenda")
    if agenda is None:
        raise ValueError("ACTUAL_AGENDA_CSV_REQUIRED")
    apps = read(application_csv, "application")
    permits = read(permit_csv, "permit")
    cases = compare(agenda, apps, permits, limit)
    target = Path(out)
    target.mkdir(parents=True, exist_ok=True)
    with (target / OUT).open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for case in cases:
            writer.writerow({key: ("'" + str(value) if str(value).lstrip().startswith(
                ("=", "+", "-", "@")) else value)
                for key, value in case.items() if key in FIELDS})
    summary = {
        "cases_requested": limit, "cases_available_from_agenda": len(agenda),
        "cases_reviewed": len(cases),
        "three_source_identity_review_candidates": sum(
            case["status"].startswith("THREE_SOURCE") for case in cases),
        "source_verified_same_project_matches": 0,
        "publication_lead_times_proven": 0,
        "early_detection_advantage_proven": False,
        "actual_application_export_present": apps is not None,
        "actual_permit_export_present": permits is not None,
        "missing_case_count": max(0, limit - len(cases)),
        "hold_count": sum(case["status"] == "HOLD" for case in cases),
        "warning": "Identity comparisons are only review candidates. Genuine lead-time proof needs original publisher dates, original permit records, persistent Radar first-seen time and independent same-project review."
    }
    (target / STATUS).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--agenda-csv", required=True)
    cli.add_argument("--applications-csv")
    cli.add_argument("--permits-csv")
    cli.add_argument("--out", required=True)
    cli.add_argument("--limit", type=int, default=20)
    args = cli.parse_args()
    print(json.dumps(run(args.agenda_csv, args.applications_csv,
                         args.permits_csv, args.out, args.limit), indent=2))
