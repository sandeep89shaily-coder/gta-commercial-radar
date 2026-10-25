"""Early-only runs never invoke V8 collection, AI or scheduling."""
import csv
import tempfile
import unittest
from pathlib import Path
from early_only_mode import RUNNERS, REPORT, SOURCES_CSV, run
from unified_collector_inventory import PILOT_GROUPS


class EarlyOnlyTests(unittest.TestCase):
    def test_only_the_nine_early_runners_execute_and_produce_one_report(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            calls=[]
            def collector(name,args,log_dir,timeout):
                calls.append((name,args))
                return dict(step=name,status="SUCCESS")
            state=run(home/"data",home/"GTA_RADAR_RESULTS",collector=collector)
            self.assertEqual(set(name for name,_ in calls),set(PILOT_GROUPS))
            self.assertEqual(len(calls),9)
            self.assertTrue(all("--data-dir" in args and "--output-dir" in args
                                for _,args in calls))
            self.assertTrue(all("main.py" not in args
                                and "business_discovery.py" not in args
                                for _,args in calls))
            self.assertEqual(state["deepseek_calls"],0)
            self.assertEqual(state["early_pilot_changes_accepted"],0)
            self.assertEqual(state["pilot_unique_outside_v8"],17)
            self.assertEqual(state["status"],"PARTIAL") # no source health files
            out=home/"GTA_RADAR_RESULTS"
            self.assertTrue((out/REPORT).exists())
            with (out/SOURCES_CSV).open(encoding="utf-8-sig",newline="") as f:
                self.assertEqual(len(list(csv.DictReader(f))),21)
            self.assertTrue((out/"GTA_RADAR_EARLY_CUES_REVIEW.csv").exists())
            self.assertTrue((out/"GTA_RADAR_EARLY_QUALIFIED_CANDIDATES.csv").exists())

    def test_failed_runner_never_promotes_stale_early_signal(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            out=home/"results"
            out.mkdir()
            status=out/"EARLY_CUES_SOURCE_STATUS.csv"
            status.write_text("source_id,state\nieso_connections,SUCCESS\n",encoding="utf-8")
            events=out/"EARLY_CUES_CHANGES_REVIEW_ONLY.csv"
            events.write_text("observed_at,source_id,record_id,change_type,title,source_url\n"
                "2026-10-25T12:00:00Z,ieso_connections,STALE,NEW,"
                "New industrial project,https://www.ieso.ca/a\n",encoding="utf-8")
            def collector(name,args,log_dir,timeout):
                return dict(step=name,status="FAILED")
            state=run(home/"data",out,collector=collector)
            self.assertEqual(state["early_pilot_changes_accepted"],0)
            self.assertEqual(state["early_cues_reviewed"],0)
            self.assertEqual(state["status"],"PARTIAL")


if __name__=="__main__":
    unittest.main()
