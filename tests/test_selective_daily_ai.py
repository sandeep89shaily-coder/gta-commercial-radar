"""Regression tests: paid AI only for recent source events, max USD 0.25."""
from __future__ import annotations
import csv
import datetime as dt
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import selective_daily_ai as selected
import v8_deepseek_native as ai
import v5_investigator as v5
import v6_daily_pipeline as v6
from free_daily_report import build as free_build, CSV_NAME

NOW=dt.date(2026,10,21)
BASE=dict(project_id="brampton_building_permits:26-123456",
          source_id="brampton_building_permits",
          source_keys="26-123456",city="Brampton",
          lane="PERMIT_REVIEW",review_priority="85",
          address="10 Industrial Parkway",
          description="New industrial warehouse expansion with refrigerated loading dock",
          current_source_status="Applied",
          source_group="MUNICIPAL_CHANGE",event_date="2026-10-21",
          source_record_date="2026-10-20",
          record_source_url="https://public.example/26-123456")

def row(**fields):return dict(BASE,**fields)

def save(path,records):
    keys=list(dict.fromkeys(k for r in records for k in r)) if records else ["project_id"]
    with open(path,"w",encoding="utf-8-sig",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=keys);w.writeheader();w.writerows(records)

class SelectiveDailyTests(unittest.TestCase):
    def test_gate_no_irrelevant_or_historic_spend(self):
        self.assertTrue(selected.permitted(row()))
        self.assertTrue(selected.permitted(row(lane="PLANNING_WATCH",review_priority="35",
                                               description="New industrial facility site plan application")))
        for x in [
            row(description="New single detached house addition"),
            row(description="Office building historic heritage listing"),
            row(description="New retail shop sign installation only"),
            row(source_id="peel_health_food",description="Restaurant health inspection"),
            row(lane="ENRICHMENT_ONLY"),
            row(current_source_status="Complete"),
            row(current_source_status="Cancelled"),
        ]:
            with self.subTest(x=x["description"]):
                self.assertFalse(selected.permitted(x))

    def test_first_baseline_always_zero_ai(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);inp=root/"candidates.csv"
            save(inp,[row()]);free_build(inp,root,today=NOW)
            with patch.object(ai,"run",side_effect=AssertionError("paid AI should not run")):
                result=selected.run(inp,root/CSV_NAME,root,root,today=NOW)
            self.assertEqual(result["paid_research_attempts"],0)
            self.assertEqual(result["status"],"NO_ELIGIBLE_NEW_PROJECTS")
            self.assertFalse((root/"v5_ai_budget.sqlite").exists())

    def test_new_or_changed_eligible_only_and_persisted(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=root/"candidates.csv"
            save(p,[row()]);free_build(p,root,today=NOW)
            second=row(project_id="brampton_building_permits:26-789012",
                       source_keys="26-789012")
            old=row(project_id="toronto_active_building_permits:historic",
                    source_keys="26-000000",current_source_status="Complete")
            save(p,[row(),second,old])
            free_build(p,root,today=NOW+dt.timedelta(days=1))
            pending,new=selected.enqueue(p,root/CSV_NAME,root)
            self.assertEqual(new,[second["project_id"]])
            self.assertEqual(len(pending),1)
            save(p,[row(),old]) # new project ages out of 48h
            free_build(p,root,today=NOW+dt.timedelta(days=2))
            pending,new=selected.enqueue(p,root/CSV_NAME,root)
            self.assertEqual(new,[])
            self.assertEqual(len(pending),1) # still kept for the next AI allowance

    def test_one_paid_attempt_per_exact_project_fingerprint(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=root/"candidates.csv"
            save(p,[row()])
            selected.enqueue(p,root/"absent_observations.csv",root)
            queue_path=root/selected.PENDING
            save(queue_path,[row()])
            signature=selected.queue.fingerprint(row())
            save(root/selected.HISTORY,[dict(project_id=row()["project_id"],
                        input_fingerprint=signature,api_attempted="YES",
                        status="AI_SOURCE_RECORD_REVIEW")])
            self.assertEqual(selected.prune(root),0)
            self.assertEqual(selected.read(queue_path),[])

    def test_selective_runner_forwards_strict_scope_and_cap(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=root/"candidates.csv"
            save(p,[row()]);free_build(p,root,today=NOW)
            new=row(project_id="brampton_building_permits:26-789012",
                    source_keys="26-789012")
            save(p,[row(),new]);free_build(p,root,today=NOW+dt.timedelta(days=1))
            def stub(*args,**kwargs):
                self.assertEqual(kwargs["budget_cap_usd"],0.25)
                self.assertEqual(kwargs["eligible_project_ids"],{new["project_id"]})
                self.assertLessEqual(kwargs["max_runtime_seconds"],600)
                return dict(queue_stop_reason="QUEUE_DRAINED",ai_calls_attempted=0,
                            native_searches=0,processed=0,reserved_usd=0.0)
            with patch.object(ai,"run",side_effect=stub) as fake:
                result=selected.run(p,root/CSV_NAME,root,root,today=NOW+dt.timedelta(days=1))
            fake.assert_called_once()
            self.assertEqual(result["new_eligible"],1)

    def test_hard_ceiling_on_every_ledger_claim(self):
        with tempfile.TemporaryDirectory() as td:
            conn=v5._ledger(Path(td)/"v5_ai_budget.sqlite")
            try:
                today=NOW.isoformat()
                self.assertTrue(ai.ledger_claim(conn,today,"first",.239,0,daily_limit=.25))
                self.assertFalse(ai.ledger_claim(conn,today,"over",.012,0,daily_limit=.25))
                self.assertTrue(ai.ledger_claim(conn,today,"under",.010,0,daily_limit=.25))
                self.assertFalse(ai.ledger_claim(conn,today,"over-again",.002,0,daily_limit=.25))
                self.assertFalse(ai.ledger_claim(conn,today,"legacy-hold",.001,.02,daily_limit=.25))
                self.assertFalse(ai.ledger_claim(conn,today,"lowered-global",.80,0,daily_limit=1.00))
            finally:conn.close()

    def test_schedule_uses_selective_flag_and_enables_previously_disabled_task(self):
        runner=Path("RUN_GTA_RADAR_V6.bat")
        workspace=Path(".")
        ok=SimpleNamespace(returncode=0,stderr="",stdout="")
        with patch.object(v6,"os",SimpleNamespace(name="nt")),patch.object(v6.subprocess,"run",return_value=ok) as mock_run:
            result=v6.schedule_daily(runner,workspace,selective_ai=True)
        self.assertTrue(result.startswith("SUCCESS"))
        calls=[x.args[0] for x in mock_run.call_args_list]
        task=next(x for x in calls if "/Create" in x)
        self.assertIn("--unattended --selective-ai",task[task.index("/TR")+1])
        self.assertNotIn("--no-ai",task[task.index("/TR")+1])
        self.assertTrue(any("/ENABLE" in x and "/Change" in x for x in calls))

    def test_pipeline_selective_mode_keeps_free_first_and_rebuilds_reports(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);workspace=root/"new data";workspace.mkdir()
            data=workspace/"COLLECTOR"/"data";data.mkdir(parents=True)
            db=data/"radar.sqlite";db.write_bytes(b"existing unchanged DB")
            dest=workspace/"GTA_RADAR_RESULTS"
            calls=[]
            def collector(name,args,log_dir,**kwargs):
                calls.append(name)
                if name=="fresh_48h_opportunities":
                    save(data/"opportunities_ALL_REVIEW_ONLY.csv",
                         [dict(source_id=BASE["source_id"],source_key=BASE["source_keys"],
                               address=BASE["address"],description=BASE["description"])])
                return dict(step=name,status="SUCCESS",exit_code=0)
            def selector(src,out,database):
                calls.append("selector")
                save(Path(out)/"CANDIDATES_V4_ALL_REVIEW_ONLY.csv",[row()])
            with patch("selective_daily_ai.run",return_value={"status":"NO_ELIGIBLE_NEW_PROJECTS",
                       "paid_research_attempts":0,"daily_ceiling_usd":.25}) as fake_ai:
                with patch("commercial_lead_reports.build",return_value={"qualified_investigation_candidates":0}):
                    state=v6.pipeline(workspace,db,collector=collector,selector=selector,
                                      run_research=False,selective_ai=True,today=NOW)
            self.assertEqual(state["status"],"SUCCESS")
            self.assertEqual(state["ai_mode"],"SELECTIVE_USD_0_25")
            self.assertEqual(state["free_daily_watch"]["initial_baseline"],1)
            self.assertIn("selector",calls)
            fake_ai.assert_called_once()
            self.assertTrue((dest/"GTA_RADAR_DAILY_NEW_DEVELOPMENTS.html").exists())
            dash=(dest/"GTA_RADAR_V6_DASHBOARD.html").read_text(encoding="utf-8")
            self.assertIn("Selective DeepSeek (US$0.25/day maximum)",dash)
            self.assertIn("Newly observed and changed",dash)

if __name__=="__main__":
    unittest.main()
