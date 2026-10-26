"""Offline production orchestration, scheduling and overlap tests."""
import tempfile
import unittest
from pathlib import Path
import radar_workspace as rw
import radar_v8_migration as v8
import radar_production as production
from test_radar_v8_migration import make_v8


class RunnerTests(unittest.TestCase):
    def prepared(self,root):
        home=Path(root)/"home"
        previous=Path(root)/"previous"/"radar.sqlite"
        make_v8(previous)
        rw.setup(home)
        v8.adopt_database(home,previous,rw._has_fields)
        return home

    def test_no_automatic_empty_database_creation(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                production.run(Path(td))
            self.assertFalse((Path(td)/"Data"/"radar.sqlite").exists())

    def test_consolidated_collects_both_without_ai_and_writes_report(self):
        with tempfile.TemporaryDirectory() as td:
            home=self.prepared(td)
            seen=[]
            def core(root):
                seen.append(("v8",root/"Data"/"radar.sqlite"))
                return 0
            def early(root):
                seen.append(("early",root/"Data"))
                return {"status":"SUCCESS","source_issues":0}
            result=production.run(home,core=core,early=early)
            self.assertEqual(result["status"],"SUCCESS")
            self.assertEqual(result["deepseek_calls"],0)
            self.assertEqual(seen[0][1].resolve(),(home/"Data"/"radar.sqlite").resolve())
            self.assertEqual(seen[1][1].resolve(),(home/"Data").resolve())
            self.assertGreater(rw.status(home)["records"],0)
            self.assertTrue((home/"Results"/"GTA_RADAR_OPERATIONS.html").is_file())
            self.assertFalse((home/"Data"/"production.lock").exists())

    def test_partial_feeds_not_marked_successful(self):
        with tempfile.TemporaryDirectory() as td:
            home=self.prepared(td)
            result=production.run(home,core=lambda _:1,
                                  early=lambda _:{"status":"PARTIAL"})
            self.assertEqual(result["status"],"PARTIAL")
            self.assertEqual(result["v8_status"],"PARTIAL_OR_FAILED")
            self.assertIn("PARTIAL",(home/"Results"/"GTA_RADAR_OPERATIONS.html").read_text())

    def test_existing_lock_blocks_overlapping_collection(self):
        with tempfile.TemporaryDirectory() as td:
            home=self.prepared(td)
            lock=home/"Data"/"production.lock"
            lock.write_text("in use")
            with self.assertRaises(RuntimeError):
                production.run(home,core=lambda _:0)
            self.assertEqual(lock.read_text(),"in use")

    def test_scheduler_never_runs_automatically_from_setup(self):
        with tempfile.TemporaryDirectory() as td:
            home=self.prepared(td)
            calls=[]
            class Result:
                returncode=0
                stderr=""
            def fake(args,**kwargs):
                calls.append(args)
                return Result()
            outcome=production.install_schedule(home,operating_system="nt",execute=fake)
            self.assertEqual(len(calls),2)
            self.assertIn("/Create",calls[0])
            self.assertIn("08:30",calls[0])
            self.assertEqual(outcome["status"],"INSTALLED_NOT_EXECUTED")
            self.assertTrue(Path(outcome["launcher"]).exists())
            self.assertFalse((home/"Results"/production.RUNFILE).exists())

    def test_scheduler_rejects_missing_database(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                production.install_schedule(Path(td),operating_system="nt")


if __name__=="__main__":
    unittest.main()
