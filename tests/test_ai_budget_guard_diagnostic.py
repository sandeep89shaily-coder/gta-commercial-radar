"""No-provider-billing-claim tests for the DeepSeek guard ledger audit."""
import datetime as dt
import json
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from gta_ai_budget_guard_diagnostic import build, run, REPORT

DAY = dt.date(2026, 11, 14)


class AIBudgetGuardDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def ledger(self, items):
        path = self.root / "v5_ai_budget.sqlite"
        with closing(sqlite3.connect(path)) as db:
            db.execute("CREATE TABLE spends (day TEXT,candidate TEXT,"
                       "reserved REAL,actual REAL,status TEXT,"
                       "PRIMARY KEY(day,candidate))")
            db.executemany(
                "INSERT INTO spends VALUES (?,?,?,?,?)", items)
            db.commit()
        return path

    def test_missing_ledger_is_unknown_billing_not_zero_invoice(self):
        report = build(self.root, today=DAY)
        self.assertEqual(report["shared_ledger"]["status"], "NO_LEDGER_FILE")
        self.assertIsNone(report["provider_actual_billed_usd"])
        self.assertFalse(report["provider_billing_verified"])
        self.assertEqual(report["paid_calls_invoked_by_this_diagnostic"], 0)

    def test_completed_estimates_separated_from_unbilled_reservations(self):
        self.ledger([
            ("2026-11-14", "model-succeeded", 0.005, 0.0006, "DONE"),
            ("2026-11-14", "attempt-unresolved", 0.99425, None, "RESERVED"),
            ("2026-11-14", "failed-unknown", 0.02, None, "UNKNOWN"),
            ("2026-11-14", "nonbillable", 0.0, 0.0, "NONBILLABLE"),
            ("2026-11-13", "other-day", 0.1, 0.1, "DONE"),
        ])
        report = build(self.root, today=DAY)
        shared = report["shared_ledger"]
        self.assertEqual(shared["rows"], 4)
        self.assertAlmostEqual(shared["completed_estimate_usd"], 0.0006)
        self.assertAlmostEqual(shared["unresolved_reserved_usd"], 1.01425)
        self.assertAlmostEqual(shared["local_guard_usage_usd"], 1.01485)
        self.assertFalse(report["provider_billing_verified"])
        self.assertIsNone(report["provider_actual_billed_usd"])

    def test_zero_current_run_requests_not_equivalent_to_spend(self):
        self.ledger([
            ("2026-11-14", "earlier-reservation", .99425, None, "RESERVED"),
        ])
        (self.root / "GTA_RADAR_V6_RUN.json").write_text(json.dumps({
            "investigation_date": "2026-11-14",
            "selective_ai": {"paid_research_attempts": 0,
                             "native_searches": 0,
                             "status": "DAILY_USD_LIMIT",
                             "actual_daily_ledger_estimate_usd": 0.99425},
        }), encoding="utf-8")
        result = build(self.root, today=DAY)
        self.assertEqual(result["current_saved_run"][
            "selective_ai_attempts_in_saved_daily_run"], 0)
        self.assertEqual(result["shared_ledger"]["completed_estimate_usd"], 0)
        self.assertEqual(result["shared_ledger"]["unresolved_reserved_usd"], .99425)
        self.assertIsNone(result["provider_actual_billed_usd"])

    def test_readonly_audit_does_not_rewrite_ledger(self):
        path = self.ledger([
            ("2026-11-14", "one", 0.25, None, "RESERVED")
        ])
        previous = path.read_bytes()
        result = run(self.root)
        self.assertEqual(result["status"],
                         "LOCAL_BUDGET_GUARD_ACCOUNTING_NOT_PROVIDER_BILLING")
        self.assertEqual(path.read_bytes(), previous)
        self.assertTrue((self.root / REPORT).is_file())

    def test_unreadable_ledger_is_a_hold_not_claimed_zero(self):
        (self.root / "v5_ai_budget.sqlite").write_bytes(b"not a sqlite file")
        result = build(self.root, today=DAY)
        self.assertEqual(result["shared_ledger"]["status"], "LEDGER_UNREADABLE_HOLD")
        self.assertIsNone(result["shared_ledger"]["local_guard_usage_usd"])


if __name__ == "__main__":
    unittest.main()
