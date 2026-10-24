"""Grounded quality checks and project-level review for GTA early-stage planning.

Read-only report functions; no AI, scraping, private-contact discovery or lead sales.
Dates represent SOURCE application/receipt dates, never presumed public-posting dates.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

QUALITY_VERSION = 2
COMMERCIAL = (
    r"\bindustrial\b", r"\bwarehous\w*\b", r"\bmanufactur\w*\b",
    r"\bcommercial\b", r"\bretail\b", r"\boffice\b", r"\bhotel\b",
    r"\bhospitality\b", r"\bdata\s*(?:centre|center)\b",
    r"\blogistic\w*\b", r"\bfactory\b", r"\bdistribution\s+(?:cent\w*|facilit\w*)\b",
    r"\binstitutional\b", r"\brestaurant\b", r"\blaborator\w*\b",
    r"\bmedical\s+(?:clinic|office)\b", r"\bloading\s+dock\w*\b",
    r"\bcold[ -]?storag\w*\b", r"\brefrigerat\w*\b", r"\bfreezer\w*\b",
    r"\benergy[ -]from[ -]waste\b", r"\bwaste[ -]to[ -]energy\b",
    r"\bpower\s+(?:plant|generation|station)\b", r"\bprocessing\s+plant\b",
    r"\bmanufacturing\s+plant\b", r"\bself[ -]storage\b",
    r"\bcar\s*wash\b", r"\bnew\s+(?:store|business|facility)\b",
    r"\bindustrial\s+(?:unit|condominium)\b",
)
RESIDENTIAL = (
    r"\bsingle[ -]?(?:family|detached)\b", r"\btownhouse\w*\b",
    r"\bcondominium\w*\b", r"\bapartment\w*\b",
    r"(?<!non[ -])\bresidential\b", r"\bdwelling\w*\b",
    r"\bsemi[ -]detached\b", r"\b(?:triplex|duplex)\b",
)
ICI = ("ICI_OFFICE", "ICI_INDUST", "ICI_ICI_FLEX", "ICI_RETAIL",
       "ICI_CC", "ICI_INSTITUT", "ICI_OTHER", "TOTAL_NON_RES_GFA")
COLUMNS = (
    "source_id", "city", "stage", "application_id", "project_group_key",
    "record_identity_confidence", "feature_count", "distinct_location_count",
    "source_application_date", "source_date_basis", "first_observed_at",
    "published_company", "company_role", "status", "commercial_signal",
    "location", "description", "source_url", "review_state"
)
AUDIT_COLUMNS = (
    "source_id", "records", "valid_source_dates", "invalid_or_missing_dates",
    "possible_commercial_records", "mixed_use_records", "project_groups",
    "multi_feature_groups", "feature_identity_groups", "recent_review_projects",
)


def parse_source_date(value, *, today=None):
    """Return ISO date or empty. Handle ArcGIS ms epochs even when numeric strings.

    Do not treat numeric GIS IDs/Excel serials as dates; reject impossible years.
    """
    if value is None or value == "":
        return ""
    today = today or dt.datetime.now(dt.timezone.utc).date()
    try:
        if isinstance(value, (int, float)) or (
                isinstance(value, str) and re.fullmatch(r"\d{10,13}", value.strip())):
            num = float(value)
            if num > 100_000_000_000:
                num /= 1000.0
            elif num < 500_000_000:
                return ""
            date = dt.datetime.fromtimestamp(num, tz=dt.timezone.utc).date()
        else:
            raw = str(value).strip()
            if not raw or re.fullmatch(r"\d+", raw):
                return ""
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", raw):
                date = dt.date.fromisoformat(raw[:10])
            elif re.fullmatch(r"\d{4}/\d{1,2}/\d{1,2}", raw):
                date = dt.datetime.strptime(raw, "%Y/%m/%d").date()
            elif re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", raw):
                date = dt.datetime.strptime(raw, "%m/%d/%Y").date()
            else:
                return ""
    except (OverflowError, ValueError, TypeError, OSError):
        return ""
    return date.isoformat() if dt.date(1980, 1, 1) <= date <= today + dt.timedelta(days=366) else ""


def source_date(row, preferred_fields, *, today=None):
    for field in preferred_fields:
        value = row.get(field.upper())
        if value is None or str(value).strip() == "":
            continue
        converted = parse_source_date(value, today=today)
        if converted:
            return converted, field.upper()
    return "", "MISSING_OR_INVALID_SOURCE_DATE"


def classify(description, source_attributes=None):
    """Conservative triage; mixed-use is not discarded and unknown is not proof residential."""
    source_attributes = source_attributes or {}
    text = str(description or "").casefold()
    evidence = any(re.search(term, text) for term in COMMERCIAL)
    residential = any(re.search(term, text) for term in RESIDENTIAL)
    for field in ICI:
        try:
            evidence = evidence or float(source_attributes.get(field) or 0) > 0
        except (ValueError, TypeError):
            pass
    if evidence and residential:
        return "MIXED_USE_REVIEW"
    if evidence:
        return "POSSIBLE_COMMERCIAL"
    if residential:
        return "RESIDENTIAL_LIKELY"
    return "USE_UNKNOWN"


def app_key(record):
    sid = str(record.get("source_id") or "")
    app = str(record.get("application_id") or "").strip().upper()
    if sid == "york_region_development":
        # APPL_GISID is a GIS identity, NOT a verified municipal application number.
        return sid + "|GIS_FEATURE|" + str(record.get("feature_id") or "")
    if not app or app in {"0", "NONE", "N/A", "UNKNOWN"}:
        return sid + "|FEATURE|" + str(record.get("feature_id") or "")
    return sid + "|APP|" + app


def _clean_location(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _is_recent(date, today, years=3):
    try:
        d = dt.date.fromisoformat(date)
        return dt.date(today.year-years, today.month, min(today.day, 28)) <= d <= today
    except (TypeError, ValueError):
        return False


def _write(path, fields, rows):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def export_project_reports(db, output_dir, *, today=None):
    """Project-level review groups, not claims of unique projects or verified buyers.

    Existing observation-first-seen dates are retained even when enriched later.
    """
    today = today or dt.datetime.now(dt.timezone.utc).date()
    groups = defaultdict(list)
    counts = Counter()
    classifications = defaultdict(Counter)
    date_counts = Counter()
    for sid, first_seen, body in db.execute(
            "SELECT source_id,first_seen,content FROM observations"):
        try:
            item = json.loads(body)
        except (TypeError, ValueError):
            continue
        if not isinstance(item, dict):
            continue
        item["_first_seen"] = first_seen
        if parse_source_date(item.get("source_application_date"), today=today):
            date_counts[sid] += 1
        counts[sid] += 1
        classifications[sid][item.get("commercial_signal") or "USE_UNKNOWN"] += 1
        groups[app_key(item)].append(item)
    output = []
    source_stats = defaultdict(lambda: Counter())
    for key, items in groups.items():
        base = max(items, key=lambda x: (
            bool(x.get("source_application_date")), bool(x.get("description")),
            len(str(x.get("description") or ""))))
        sid = base["source_id"]
        stats = source_stats[sid]
        stats["groups"] += 1
        if len(items) > 1:
            stats["multi"] += 1
        if "|FEATURE|" in key or "|GIS_FEATURE|" in key:
            stats["feature"] += 1
        date_candidates = [x.get("source_application_date") for x in items
                           if parse_source_date(x.get("source_application_date"), today=today)]
        dates = sorted(set(date_candidates))
        when = dates[0] if dates else ""
        labels = {x.get("commercial_signal") for x in items}
        if "MIXED_USE_REVIEW" in labels or (
                "POSSIBLE_COMMERCIAL" in labels and "RESIDENTIAL_LIKELY" in labels):
            signal = "MIXED_USE_REVIEW"
        elif "POSSIBLE_COMMERCIAL" in labels:
            signal = "POSSIBLE_COMMERCIAL"
        elif "RESIDENTIAL_LIKELY" in labels and labels == {"RESIDENTIAL_LIKELY"}:
            signal = "RESIDENTIAL_LIKELY"
        else:
            signal = "USE_UNKNOWN"
        locations = {_clean_location(x.get("location")) for x in items if x.get("location")}
        site_count = len(locations)
        identity = ("FEATURE_NOT_CONFIRMED_PROJECT" if "|FEATURE|" in key or "|GIS_FEATURE|" in key
                    else "MULTIPLE_SITE_FEATURES_REVIEW" if site_count > 1
                    else "SOURCE_APPLICATION_GROUP_REVIEW")
        row = dict(
            source_id=sid, city=base.get("city", ""), stage=base.get("stage", ""),
            application_id=base.get("application_id", ""),
            project_group_key=key, record_identity_confidence=identity,
            feature_count=len(items), distinct_location_count=site_count,
            source_application_date=when,
            source_date_basis=base.get("source_date_basis", "UNVERIFIED_LEGACY_DATE") if when else "MISSING",
            first_observed_at=min(x.get("_first_seen", "") for x in items),
            published_company=base.get("published_company_unverified_role", ""),
            company_role=base.get("company_role", "PUBLISHED_ENTITY_ROLE_UNVERIFIED"),
            status=" | ".join(sorted(set(str(x.get("status") or "") for x in items)))[:180],
            commercial_signal=signal, location=base.get("location", ""),
            description=base.get("description", ""), source_url=base.get("source_url", ""),
            review_state="HISTORICAL_SOURCE_APPLICATION_DATE_NOT_PUBLICATION_DATE"
        )
        if signal not in {"POSSIBLE_COMMERCIAL", "MIXED_USE_REVIEW"}:
            continue
        if not _is_recent(when, today):
            continue
        stats["recent"] += 1
        output.append(row)
    output.sort(key=lambda x: (
        x["source_application_date"], x["stage"] == "PRE_CONSULTATION",
        x["commercial_signal"] == "POSSIBLE_COMMERCIAL"), reverse=True)
    stats_rows = []
    for sid in sorted(counts):
        stats = source_stats[sid]
        stats_rows.append(dict(
            source_id=sid, records=counts[sid], valid_source_dates=date_counts[sid],
            invalid_or_missing_dates=counts[sid]-date_counts[sid],
            possible_commercial_records=classifications[sid]["POSSIBLE_COMMERCIAL"],
            mixed_use_records=classifications[sid]["MIXED_USE_REVIEW"],
            project_groups=stats["groups"], multi_feature_groups=stats["multi"],
            feature_identity_groups=stats["feature"],
            recent_review_projects=stats["recent"]))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write(output_dir/"EARLY_SIGNALS_PROJECTS_REVIEW_ONLY.csv", COLUMNS, output)
    _write(output_dir/"EARLY_SIGNALS_QUALITY_AUDIT.csv", AUDIT_COLUMNS, stats_rows)
    return {"review_candidates":len(output), "source_stats":stats_rows}
