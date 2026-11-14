"""Read-only DeepSeek budget guard diagnostic, NEVER a provider billing report.

Separates recorded completed usage estimates from unresolved reservations,
which can block requests without being charges. Never resets or reconciles
ledger entries automatically. No paid calls, network, secrets or database edits.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path

from radar_config import DEEPSEEK_DAILY_LIMIT_USD

REPORT = "GTA_RADAR_AI_BUDGET_GUARD_DIAGNOSTIC.json"


def _table(path, day, date_column):
    path = Path(path)
    if not path.is_file():
        return {"status": "NO_LEDGER_FILE", "rows": 0,
                "completed_estimate_usd": 0.0, "unresolved_reserved_usd": 0.0,
                "local_guard_usage_usd": 0.0}
    if path.is_symlink():
        raise ValueError("SYMLINKED_BUDGET_LEDGER_REFUSED")
    try:
        # Important: read-only URI; sqlite3.connect(path) would create a missing DB.
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro",
                             uri=True, timeout=3) as db:
            if date_column == "day":
                sql = """SELECT status, COUNT(*), COALESCE(SUM(reserved),0),
                  COALESCE(SUM(CASE WHEN status='DONE'
                  AND actual IS NOT NULL AND actual >= 0 THEN actual ELSE 0 END),0),
                  COALESCE(SUM(CASE WHEN status='DONE'
                  AND actual IS NOT NULL AND actual >= 0 THEN 0 ELSE reserved END),0)
                  FROM spends WHERE day=? GROUP BY status"""
            else:
                sql = """SELECT 'LEGACY_RESERVATION', COUNT(*),
                  COALESCE(SUM(reserved),0), 0, COALESCE(SUM(reserved),0)
                  FROM spends WHERE date=?"""
            rows = db.execute(sql, (day,)).fetchall()
    except sqlite3.Error as exc:
        return {"status": "LEDGER_UNREADABLE_HOLD",
                "error_type": type(exc).__name__, "rows": None,
                "completed_estimate_usd": None, "unresolved_reserved_usd": None,
                "local_guard_usage_usd": None}
    completed = sum(float(row[3] or 0) for row in rows)
    unresolved = sum(float(row[4] or 0) for row in rows)
    return {
        "status": "READ_ONLY_ACCOUNTING",
        "rows": sum(int(row[1]) for row in rows),
        "by_status": {str(row[0]): int(row[1]) for row in rows},
        "completed_estimate_usd": round(completed, 6),
        "unresolved_reserved_usd": round(unresolved, 6),
        "local_guard_usage_usd": round(completed + unresolved, 6),
        "nominal_reservations_usd": round(sum(float(row[2] or 0) for row in rows), 6),
    }


def build(results, *, today=None):
    results = Path(results)
    day = (today or dt.date.today()).isoformat()
    shared = _table(results / "v5_ai_budget.sqlite", day, "day")
    legacy = _table(results / "deepseek_budget.sqlite", day, "date")
    v6 = {}
    path = results / "GTA_RADAR_V6_RUN.json"
    try:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("investigation_date") == day:
                selective = data.get("selective_ai") or {}
                v6 = {
                    "selective_ai_attempts_in_saved_daily_run": selective.get("paid_research_attempts"),
                    "selective_ai_native_searches_in_saved_daily_run": selective.get("native_searches"),
                    "selective_ai_status_in_saved_daily_run": selective.get("status"),
                    "saved_run_guard_estimate_usd_not_provider_billing": selective.get(
                        "actual_daily_ledger_estimate_usd"),
                }
    except (OSError, ValueError, TypeError):
        v6 = {"status": "SAVED_RUN_REPORT_UNREADABLE"}
    report = {
        "status": "LOCAL_BUDGET_GUARD_ACCOUNTING_NOT_PROVIDER_BILLING",
        "date": day,
        "configured_daily_software_guard_usd": DEEPSEEK_DAILY_LIMIT_USD,
        "shared_ledger": shared,
        "legacy_ledger": legacy,
        "current_saved_run": v6,
        "provider_actual_billed_usd": None,
        "provider_billing_verified": False,
        "no_spend_claim": ("The software ledger contains estimates and request holds, "
                           "not a verified provider invoice. Only the provider billing "
                           "records can establish actual billed dollars."),
        "manual_reconciliation_required": (
            "If the software guard blocks requests despite zero provider billing, "
            "inspect source ledger statuses and provider usage; never reset "
            "reservations automatically or relabel them paid calls."),
        "read_only": True,
        "paid_calls_invoked_by_this_diagnostic": 0,
    }
    return report


def run(results):
    root = Path(results)
    report = build(root)
    path = root / REPORT
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.results), indent=2))
