"""Operator-confirmed, exact-day reconciliation of blocked DeepSeek software holds.

This does not claim a provider charge was or was not made. The operator must
independently confirm zero billable usage for all API keys for this *same day*
in the provider dashboard, after reporting latency has elapsed. Default is
READ-ONLY PREVIEW. Apply requires explicit confirmation, an exact matching
row-count and total, a funded saved-key balance check, and an immutable SQLite
backup. Never deletes rows or changes successful/unknown/pending entries.
"""
from __future__ import annotations

import argparse
import datetime as dt
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import uuid

from gta_deepseek_check_saved_key_balance import check as check_saved_key
from radar_run_lock import once_lock

STATUS = "RECONCILED_OPERATOR_CONFIRMED_ZERO_USAGE"
BACKUP_DIR = "AI_LEDGER_RECONCILIATION_BACKUPS"
AUDIT = "AI_LEDGER_RECONCILIATION_AUDIT.json"

ELIGIBLE = ("day=? AND status='ERROR' AND actual IS NULL "
            "AND reserved IS NOT NULL AND reserved>0")


def _inspect(db, day):
    total = db.execute(
        "SELECT COUNT(*), COALESCE(SUM(reserved),0) FROM spends WHERE "+ELIGIBLE,
        (day,)).fetchone()
    statuses = db.execute(
        "SELECT status,COUNT(*) FROM spends WHERE day=? GROUP BY status",
        (day,)).fetchall()
    return {
        "eligible_error_rows": int(total[0]),
        "eligible_reserved_usd": round(float(total[1]), 6),
        "all_status_counts": {str(status): int(count) for status,count in statuses},
    }


def reconcile(results, *, day=None, apply=False, confirmed_zero=False,
              expected_count=None, expected_usd=None,
              balance_checker=check_saved_key, lock_factory=once_lock):
    root=Path(results).resolve()
    dbpath=root/"v5_ai_budget.sqlite"
    date=(day or dt.date.today()).isoformat() if isinstance(day, dt.date) else (day or dt.date.today().isoformat())
    if not dbpath.is_file() or dbpath.is_symlink():
        raise ValueError("EXISTING_SHARED_LEDGER_REQUIRED")
    try:
        dt.date.fromisoformat(date)
    except ValueError as exc:
        raise ValueError("INVALID_DATE") from exc

    with closing(sqlite3.connect(dbpath.as_uri()+"?mode=ro",uri=True,timeout=5)) as db:
        summary=_inspect(db,date)
    report={
        "date": date,
        "mode": "DRY_RUN_NO_CHANGES" if not apply else "APPLY_REQUESTED",
        "provider_billed_amount_verified": False,
        "source": "EXISTING_LOCAL_LEDGER_NOT_PROVIDER_INVOICE",
        "eligible": summary,
        "affects_status_only": "ERROR with NULL actual and positive reservation",
        "preserves": "all DONE, RESERVED, UNKNOWN, NONBILLABLE and other-date records",
        "old_reservation_bytes_deleted": False,
        "existing_ledger_rewritten": False,
        "model_calls": 0,
    }
    if not apply:
        return report

    if date != dt.date.today().isoformat():
        raise ValueError("ONLY_SAME_LOCAL_DAY_RECONCILIATION_ALLOWED")
    if not confirmed_zero:
        raise ValueError("OPERATOR_CONFIRMATION_OF_PROVIDER_ZERO_USAGE_REQUIRED")
    if expected_count is None or expected_usd is None:
        raise ValueError("EXACT_EXPECTED_COUNT_AND_USD_REQUIRED")
    if summary["eligible_error_rows"] != expected_count:
        raise ValueError("ERROR_COUNT_CHANGED_REFUSING_RECONCILIATION")
    if abs(summary["eligible_reserved_usd"] - round(float(expected_usd),6)) > 0.000001:
        raise ValueError("ERROR_RESERVATION_TOTAL_CHANGED_REFUSING_RECONCILIATION")
    if summary["eligible_error_rows"] == 0:
        raise ValueError("NO_ELIGIBLE_ERROR_HOLDS_TO_RECONCILE")

    # A balance check cannot prove historic billing, but must confirm Radar's
    # saved key is still authenticated to a currently available account.
    balance=balance_checker()
    if balance.get("status")!="RADAR_KEY_BALANCE_READ" or not balance.get("is_available"):
        raise ValueError("RADAR_SAVED_KEY_BALANCE_CHECK_FAILED")

    with lock_factory(root):
        with closing(sqlite3.connect(dbpath,timeout=10)) as source:
            source.execute("PRAGMA busy_timeout=10000")
            # Check the exact same-day rows again under a write transaction
            # before changing any data. Backup is taken while collector lock
            # is held, before BEGIN IMMEDIATE.
            folder=root/BACKUP_DIR
            folder.mkdir(exist_ok=True)
            suffix=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup=folder/("v5_ai_budget_"+date+"_"+suffix+"_"+uuid.uuid4().hex[:8]+".sqlite")
            with closing(sqlite3.connect(backup)) as saved:
                source.backup(saved)
            source.execute("BEGIN IMMEDIATE")
            try:
                current=_inspect(source,date)
                if current["eligible_error_rows"] != expected_count or abs(
                        current["eligible_reserved_usd"]-round(float(expected_usd),6)
                        )>0.000001:
                    raise ValueError("LEDGER_CHANGED_DURING_BACKUP_NO_ROWS_MODIFIED")
                source.execute(
                    "UPDATE spends SET status=?, reserved=0, actual=0 WHERE "+ELIGIBLE,
                    (STATUS,date))
                changed=source.execute("SELECT changes()").fetchone()[0]
                if changed!=expected_count:
                    raise RuntimeError("RECONCILIATION_ROW_COUNT_MISMATCH")
                source.commit()
            except Exception:
                source.rollback()
                raise
            updated=_inspect(source,date)

    report.update({
        "mode": "OPERATOR_CONFIRMED_RECONCILIATION_COMPLETE",
        "existing_ledger_rewritten": True,
        "backup": str(backup),
        "rows_reclassified": expected_count,
        "local_guard_holds_released_usd": summary["eligible_reserved_usd"],
        "after": updated,
        "reconciliation_reason": (
            "Operator explicitly confirmed provider dashboard showed zero "
            "usage for the same date, across all keys, after the reporting delay."
        ),
        "provider_billed_amount_verified": False,
        "preserved_original_rows_in_backup": True,
        "reclassified_rows_remain_in_live_ledger": True,
    })
    audit=root/AUDIT
    tmp=audit.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report,indent=2),encoding="utf-8")
    tmp.replace(audit)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results",required=True)
    parser.add_argument("--date",help="Local calendar date YYYY-MM-DD; default today")
    parser.add_argument("--apply",action="store_true",help="Modify only eligible ERROR holds")
    parser.add_argument("--confirm-provider-zero-usage",action="store_true",
                        help="I checked all API keys in provider dashboard for this date")
    parser.add_argument("--expected-errors",type=int)
    parser.add_argument("--expected-usd",type=float)
    args=parser.parse_args()
    try:
        output=reconcile(
            args.results,day=args.date,apply=args.apply,
            confirmed_zero=args.confirm_provider_zero_usage,
            expected_count=args.expected_errors,
            expected_usd=args.expected_usd)
    except (OSError,sqlite3.Error,ValueError,RuntimeError) as exc:
        print(json.dumps({"status":"REFUSED_NO_UNVERIFIED_RECONCILIATION",
                          "error":str(exc)},indent=2))
        return 2
    print(json.dumps(output,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
