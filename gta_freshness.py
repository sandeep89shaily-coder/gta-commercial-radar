"""Conservative, zero-cost source-date freshness classification for GTA Radar.

A first Radar observation is not a new announcement. A source-record date may
be a filing/status date, not its first *public* release. Never use an undated
municipal-change detection timestamp as evidence of a new construction event.
Classifications guide research priority only; they do not verify bid availability.
"""
from __future__ import annotations

import datetime as dt

# A source-dated project can enter paid investigation for <=90 days after the
# documented source event. Scope edits to old projects remain investigable, but
# only when Radar has stored before/after description snapshots.
FRESH_MAX_DAYS = 90


def _date(value):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    value = str(value or "").strip()
    try:
        return dt.date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return None


def _source_date(row, today):
    # Distinguish publicly *reported* publication from ordinary permit filing,
    # status-update and detection dates. Neither is independently verified here.
    for field, basis in (
        ("source_publication_at", "REPORTED_PUBLICATION_DATE_UNVERIFIED"),
        ("first_public_at", "REPORTED_PUBLICATION_DATE_UNVERIFIED"),
        ("source_record_date", "SOURCE_RECORD_DATE_NOT_PUBLICATION_PROOF"),
    ):
        raw = str(row.get(field) or "").strip()
        d = _date(raw)
        if d is not None and d <= today:
            return d, basis

    # Event dates from municipal change streams are detection dates. They
    # MUST NOT rescue an old or undated source record into the fresh bucket.
    group = str(row.get("source_group") or "").upper()
    basis = str(row.get("date_basis") or row.get("event_date_basis") or "").upper()
    if (group in ("MUNICIPAL_CHANGE", "PEEL_PROJECT", "REGIONAL_ARCHIVED_SOURCE")
            or "UPDATE" in basis or "CHANGE" in basis or "OBSERV" in basis
            or "ARCHIV" in basis):
        return None, "DETECTION_TIMESTAMP_IS_NOT_PUBLICATION"
    d = _date(row.get("event_date"))
    if d is not None and d <= today:
        return d, "SOURCE_EVENT_DATE_NOT_PUBLICATION_PROOF"
    return None, "NO_TRUSTWORTHY_SOURCE_DATE"


def assess(row, today=None):
    """Return fixed categories for review, paid AI gating and daily ordering.

    Change reviews are deliberately not called new announcements. Only changes
    to an actually remembered *description* can justify paid investigation of
    an older project; address-only, company-name or status-only updates cannot.
    """
    today = _date(today) or dt.date.today()
    date, basis = _source_date(row, today)
    age = (today-date).days if date else None
    observation = str(row.get("observation") or "").upper()
    changed = {s.strip() for s in str(row.get("changed_fields") or "").split("|") if s.strip()}
    scope_change = observation == "RECORD_CHANGED" and "description" in changed

    if age is not None and age <= 7:
        band, bucket = "SOURCE_DATED_0_7_DAYS", 0
    elif age is not None and age <= 30:
        band, bucket = "SOURCE_DATED_8_30_DAYS", 1
    elif age is not None and age <= FRESH_MAX_DAYS:
        band, bucket = "SOURCE_DATED_31_90_DAYS", 2
    elif scope_change:
        band, bucket = "OLDER_PROJECT_SCOPE_CHANGED_REVIEW", 3
    elif age is not None:
        band, bucket = "HISTORICAL_SOURCE_DATE", 4
    else:
        band, bucket = "SOURCE_DATE_UNKNOWN", 5

    if observation in ("INITIAL_BASELINE", "ARCHIVE_CONTEXT", "UNCHANGED"):
        paid = False
    else:
        paid = bucket <= 2 or scope_change

    return {
        "freshness_band": band,
        "freshness_sort_bucket": bucket,
        "freshness_date": date.isoformat() if date else "",
        "freshness_date_basis": basis,
        "source_age_days": age if age is not None else "",
        "paid_freshness_eligible": paid,
        "freshness_warning": (
            "Source-date and change-review classifications are not proof of "
            "first publication, an unawarded contract, or first market discovery."
        ),
    }


def rank(row, today):
    """Stable ranking: freshness first, then lifecycle and commercial score."""
    detail = assess(row, today)
    stage = str(row.get("stage_from_local_status") or row.get("current_source_status") or "").upper()
    # Callers with a V4 source status should supply already-classified stage.
    lifecycle = {
        "PRE_APPROVAL": 0, "PRE_ISSUANCE": 1, "APPROVED_NOT_ISSUED": 2,
        "PERMIT_ISSUED": 3, "UNKNOWN": 4, "INSPECTION_STAGE": 7,
        "BLOCKED_OR_INACTIVE": 9, "COMPLETED": 9,
    }.get(stage, 4)
    try:
        priority = -int(row.get("review_priority") or 0)
    except (ValueError, TypeError):
        priority = 0
    return (detail["freshness_sort_bucket"], lifecycle, priority,
            str(row.get("project_id") or ""))
