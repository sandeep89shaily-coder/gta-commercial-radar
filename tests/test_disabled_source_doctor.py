"""Doctor gating logic, no live requests."""
import subprocess
import unittest
from types import SimpleNamespace
from disabled_source_doctor import evaluate
class DisabledDoctorTests(unittest.TestCase):
    def source(self,**kwargs):
        return dict(id="york_region_active_development_applications",
                    family="planning_application",mode="daily",
                    date_fields=["MOD_DATE"],**kwargs)
    def mocked(self,code,text):
        def run(*args,**kwargs):
            self.assertIn("--source",args[0])
            return SimpleNamespace(returncode=code,stdout=text,stderr="")
        return run
    def test_good_probe_needs_baseline_before_activation(self):
        row=evaluate(self.source(),run=self.mocked(0,
            "Checking york ... OK (dataset; full filtered count=140; recent-window count=5)"))
        self.assertEqual(row["decision"],"READY_FOR_ISOLATED_BASELINE_TEST")
        self.assertEqual(row["full_count"],"140")
    def test_broken_incremental_query_blocks_source(self):
        row=evaluate(self.source(),run=self.mocked(0,
            "Checking york ... OK (dataset; full filtered count=100; incremental filter FAILED)"))
        self.assertEqual(row["decision"],"BLOCKED_INCREMENTAL_QUERY")
    def test_http_fail_does_not_claim_ready(self):
        row=evaluate(self.source(),run=self.mocked(1,"Checking york ... FAIL: 403"))
        self.assertEqual(row["decision"],"BLOCKED_DOCTOR")
    def test_timeout_is_unverified_not_zero(self):
        def timed(*args,**kwargs):raise subprocess.TimeoutExpired("cmd",90)
        row=evaluate(self.source(),run=timed)
        self.assertEqual(row["decision"],"UNVERIFIED_TIMEOUT")
    def test_without_dates_needs_review(self):
        src=self.source();src["date_fields"]=[]
        row=evaluate(src,run=self.mocked(0,"Checking york ... OK (dataset; full filtered count=99)"))
        self.assertEqual(row["decision"],"REVIEW_DATE_SEMANTICS")
    def test_legacy_permits_backfill_only(self):
        src=self.source();src.update(mode="backfill",family="permit_history")
        row=evaluate(src,run=self.mocked(0,"Checking york ... OK (dataset)"))
        self.assertEqual(row["decision"],"HISTORICAL_ONLY")
if __name__=="__main__":unittest.main()
