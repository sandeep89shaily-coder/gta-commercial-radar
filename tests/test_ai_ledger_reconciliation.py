"""Safety tests for operator-confirmed, reversible DeepSeek local guard repair."""
from contextlib import closing, nullcontext
import datetime as dt
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from gta_reconcile_deepseek_local_holds import reconcile, STATUS, AUDIT


class SafeAIReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.dbpath=self.root/"v5_ai_budget.sqlite"
        self.day=dt.date.today()
        self.yesterday=self.day-dt.timedelta(days=1)
        with closing(sqlite3.connect(self.dbpath)) as db:
            db.execute("CREATE TABLE spends (day TEXT,candidate TEXT,"
                       "reserved REAL,actual REAL,status TEXT,"
                       "PRIMARY KEY(day,candidate))")
            db.executemany("INSERT INTO spends VALUES (?,?,?,?,?)",[
                (self.day.isoformat(),"M8:foo",.008,None,"ERROR"),
                (self.day.isoformat(),"S8:bar:0",.005,None,"ERROR"),
                (self.day.isoformat(),"M8:success",.009,.001,"DONE"),
                (self.day.isoformat(),"M8:unknown",.011,None,"UNKNOWN"),
                (self.day.isoformat(),"F8:pending",.004,None,"RESERVED"),
                (self.yesterday.isoformat(),"M8:old",.010,None,"ERROR"),
            ])
            db.commit()
        self.read_balance=lambda: {
            "status":"RADAR_KEY_BALANCE_READ", "is_available":True}
        self.no_lock=lambda _: nullcontext()

    def _get(self):
        with closing(sqlite3.connect(self.dbpath)) as db:
            return db.execute("SELECT day,candidate,reserved,actual,status "
                              "FROM spends ORDER BY candidate,day").fetchall()

    def test_dry_run_has_zero_side_effects(self):
        before=self.dbpath.read_bytes()
        data=reconcile(self.root,day=self.day)
        self.assertEqual(data["mode"],"DRY_RUN_NO_CHANGES")
        self.assertEqual(data["eligible"]["eligible_error_rows"],2)
        self.assertAlmostEqual(data["eligible"]["eligible_reserved_usd"],.013)
        self.assertEqual(self.dbpath.read_bytes(),before)
        self.assertFalse((self.root/AUDIT).exists())

    def test_apply_requires_explicit_dashboard_confirmation(self):
        with self.assertRaisesRegex(ValueError,"OPERATOR_CONFIRMATION"):
            reconcile(self.root,day=self.day,apply=True,
                      expected_count=2,expected_usd=.013,
                      balance_checker=self.read_balance,
                      lock_factory=self.no_lock)

    def test_mismatched_totals_refuse_before_write(self):
        before=self._get()
        for count, amount in [(388,.99425),(2,.012)]:
            with self.assertRaisesRegex(ValueError,"CHANGED"):
                reconcile(self.root,day=self.day,apply=True,
                          confirmed_zero=True,expected_count=count,
                          expected_usd=amount,balance_checker=self.read_balance,
                          lock_factory=self.no_lock)
            self.assertEqual(self._get(),before)

    def test_saved_key_must_be_currently_available(self):
        with self.assertRaisesRegex(ValueError,"BALANCE_CHECK_FAILED"):
            reconcile(self.root,day=self.day,apply=True,
                      confirmed_zero=True,expected_count=2,expected_usd=.013,
                      balance_checker=lambda:{"status":"BALANCE_ENDPOINT_HTTP_ERROR"},
                      lock_factory=self.no_lock)

    def test_apply_backs_up_and_reclassifies_only_error_null_actual(self):
        before=self._get()
        result=reconcile(self.root,day=self.day,apply=True,
                         confirmed_zero=True,expected_count=2,
                         expected_usd=.013,balance_checker=self.read_balance,
                         lock_factory=self.no_lock)
        self.assertEqual(result["rows_reclassified"],2)
        self.assertAlmostEqual(result["local_guard_holds_released_usd"],.013)
        self.assertTrue(Path(result["backup"]).is_file())
        with closing(sqlite3.connect(result["backup"])) as db:
            backup=db.execute("SELECT day,candidate,reserved,actual,status "
                              "FROM spends ORDER BY candidate,day").fetchall()
        self.assertEqual(before,backup)
        after=dict((r[1],r[2:]) for r in self._get())
        for name in ("M8:foo","S8:bar:0"):
            self.assertEqual(after[name],(0.0,0.0,STATUS))
        self.assertEqual(after["M8:success"],(.009,.001,"DONE"))
        self.assertEqual(after["M8:unknown"],(.011,None,"UNKNOWN"))
        self.assertEqual(after["F8:pending"],(.004,None,"RESERVED"))
        self.assertEqual(after["M8:old"],(.010,None,"ERROR"))
        self.assertEqual(json.loads((self.root/AUDIT).read_text())["mode"],
                         "OPERATOR_CONFIRMED_RECONCILIATION_COMPLETE")
        with self.assertRaisesRegex(ValueError,"CHANGED"):
            reconcile(self.root,day=self.day,apply=True,confirmed_zero=True,
                      expected_count=2,expected_usd=.013,
                      balance_checker=self.read_balance,lock_factory=self.no_lock)

    def test_previous_day_cannot_be_reclassified(self):
        with self.assertRaisesRegex(ValueError,"ONLY_SAME_LOCAL_DAY"):
            reconcile(self.root,day=self.yesterday,apply=True,
                      confirmed_zero=True,expected_count=1,expected_usd=.010,
                      balance_checker=self.read_balance,
                      lock_factory=self.no_lock)


if __name__=="__main__":
    unittest.main()
