"""Read-only, privacy-preserving Toronto business-licence funnel audit.

Reports counts and field names only: no source rows, licence IDs, client names,
addresses, emails or phone numbers leave the existing local SQLite database.
"""
from __future__ import annotations
import argparse
from collections import Counter
from contextlib import closing
import datetime as dt
import json
import sqlite3
from pathlib import Path

from gta_commercial_activation_pilot import (
    SOURCES, LICENCE_TYPES, TERMINAL, RENEWAL,
    get, event_date, physical_site, classify,
)
import re
from v6_daily_pipeline import find_workspace, choose_database

SOURCE = "toronto_business_licences"


def analyze(db, *, limit=40000, as_of=None, window_days=120):
    as_of = as_of or dt.datetime.now(dt.timezone.utc).date()
    if not isinstance(as_of, dt.date):
        raise ValueError("as_of must be a date")
    limit = int(limit)
    if not 1 <= limit <= 100000:
        raise ValueError("limit must be between 1 and 100000")
    db = Path(db)
    counts = Counter()
    fields = Counter()
    years = Counter()
    exclusions = Counter()
    count_total = 0
    with closing(sqlite3.connect(db.resolve().as_uri() + "?mode=ro",
                                uri=True, timeout=20)) as con:
        count_total = con.execute(
            "SELECT count(*) FROM records_current WHERE source_id=? AND active=1",
            (SOURCE,)).fetchone()[0]
        cursor = con.execute(
            """SELECT c.record_key,c.first_seen_at,c.source_date,v.payload_json
                 FROM records_current c JOIN record_versions v
                   ON v.source_id=c.source_id AND v.record_key=c.record_key
                   AND v.version_id=(SELECT MAX(x.version_id) FROM record_versions x
                     WHERE x.source_id=c.source_id AND x.record_key=c.record_key)
                 WHERE c.source_id=? AND c.active=1
                 ORDER BY c.source_date DESC,c.record_key DESC LIMIT ?""",
            (SOURCE,limit))
        for key, seen, source_date, payload in cursor:
            counts["rows_scanned"] += 1
            try:
                raw = json.loads(payload)
                if not isinstance(raw,dict):
                    counts["invalid_payload"] += 1
                    continue
            except (TypeError,ValueError):
                counts["invalid_payload"] += 1
                continue
            fields.update(str(k) for k in raw)
            addr, unit = physical_site(raw,SOURCE)
            if addr:
                counts["valid_physical_address"] += 1
            else:
                counts["invalid_or_missing_physical_address"] += 1
            category = get(raw,"CATEGORY","LICENCE_CATEGORY")
            target = any(re.search(pat,category,re.I) for pat,_ in LICENCE_TYPES)
            if target: counts["target_category"] += 1
            else: counts["non_target_or_missing_category"] += 1
            cancelled = get(raw,"CANCEL DATE","CANCEL_DATE","CANCELDATE")
            status = get(raw,"STATUS","LICENCE_STATUS","STATUSDESC")
            inactive = bool(cancelled or TERMINAL.search(status) or
                            RENEWAL.search(status+" "+get(raw,"TRANSACTION_TYPE","LICENCE_TYPE")))
            if inactive: counts["cancelled_terminal_or_renewed"] += 1
            else: counts["not_known_cancelled_or_terminal"] += 1
            issued = get(raw,"LICENCE_ISSUED_DATE","ISSUED_DATE","DATE_ISSUED","ISSUED")
            date = event_date(issued)
            if date:
                counts["parseable_issue_date"] += 1
                years[str(date.year)] += 1
                if -1 <= (as_of-date).days <= window_days:
                    counts["issue_date_within_window"] += 1
                    if target and not inactive:
                        counts["recent_active_target_even_without_site"] += 1
                        if addr:
                            counts["recent_active_target_with_site"] += 1
            else:
                counts["missing_or_unparseable_issue_date"] += 1
            row, reason = classify({
                "source":SOURCE,"key":str(key or ""),
                "raw":raw,"first_seen":str(seen or ""),"sha":""},
                as_of,window_days)
            exclusions[reason if reason else "ACCEPTED"] += 1
        # Windows keeps the SQLite file locked while a SELECT cursor lives,
        # even if the connection has left its context manager.
        cursor.close()

    return {
        "source":SOURCE,
        "mode":"READ_ONLY_AGGREGATE_AUDIT_NO_PERSONAL_RECORD_EXPORT",
        "active_records_in_ledger":count_total,
        "rows_scanned_limit":limit,
        "rows_scanned":counts["rows_scanned"],
        "selection":"source_date DESC, record_key DESC (not issue-date order)",
        "as_of":as_of.isoformat(),
        "issue_window_days":window_days,
        "metric_counts":dict(sorted(counts.items())),
        "original_field_presence_counts":dict(sorted(fields.items())),
        "issue_year_counts":dict(sorted(years.items())),
        "sequential_classification_counts":dict(sorted(exclusions.items())),
        "note":"No individual records or field values exported; zero accepted may reflect source cap, address parsing, category selection, cancellations or issue dates.",
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace")
    parser.add_argument("--limit",type=int,default=40000)
    args=parser.parse_args()
    workspace=find_workspace(args.workspace)
    db=choose_database(workspace)
    result=analyze(db,limit=args.limit)
    out=Path(workspace)/"GTA_RADAR_RESULTS"/"COMMERCIAL_ACTIVATION_PILOT"
    out.mkdir(parents=True,exist_ok=True)
    path=out/"TORONTO_LICENCE_FIELD_AUDIT.json"
    path.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({"audit_file":str(path),
        "active_records_in_ledger":result["active_records_in_ledger"],
        "rows_scanned":result["rows_scanned"],
        "metric_counts":result["metric_counts"],
        "sequential_classification_counts":result["sequential_classification_counts"]},indent=2))
    print("Audit file includes original field NAMES and aggregate frequencies, no personal records.")


if __name__=="__main__":
    main()
