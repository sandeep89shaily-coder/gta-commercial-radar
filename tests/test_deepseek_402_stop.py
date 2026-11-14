"""HTTP 402 must stop an entire DeepSeek research cycle, not create 388 holds."""
import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

import gta_adaptive_deepseek_planner as planner
import v8_deepseek_native as native
import v5_investigator as v5


ROW = {
    "project_id": "project-one",
    "address": "1430 Birchmount Road, Toronto, ON",
    "city": "Toronto",
    "source_id": "toronto_permit",
    "source_keys": "24 101010",
    "company_name": "",
    "description": "New industrial units development",
    "lane": "PERMIT_REVIEW",
    "review_priority": "75",
    "current_source_status": "Under review",
}


def reject_402(path, payload):
    raise HTTPError("https://api.deepseek.com" + path, 402,
                    "Payment Required", None, None)


class DeepSeek402Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = v5._ledger(self.root / "v5_ai_budget.sqlite")
        self.addCleanup(self.db.close)
        self.day = "2026-11-14"

    def entries(self):
        return self.db.execute(
            "SELECT candidate,status,reserved,actual FROM spends "
            "WHERE day=?", (self.day,)).fetchall()

    def test_search_402_stops_and_releases_search_reservation(self):
        calls = []
        def api(path, payload):
            calls.append(path)
            return reject_402(path,payload)
        with self.assertRaises(native.DeepSeekAccountBalanceError):
            native.fetch_native(ROW, "mock-key", self.db, self.day, 0, api)
        self.assertEqual(len(calls), 1)
        entries = self.entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][1], "NONBILLABLE")
        self.assertEqual(entries[0][2], 0)
        self.assertEqual(native.effective_spend(self.db,self.day)[0], 0)

    def test_direct_fetch_402_stops_before_search(self):
        row = {**ROW,"record_source_url":"https://example.com/project"}
        calls=[]
        def api(path,payload):
            calls.append(path)
            return reject_402(path,payload)
        with self.assertRaises(native.DeepSeekAccountBalanceError):
            native.fetch_native(row,"mock-key",self.db,self.day,0,api)
        self.assertEqual(calls,["/v1/tools/fetch"])
        self.assertEqual(self.entries()[0][1],"NONBILLABLE")

    def test_planner_402_does_not_create_unknown_charge_hold(self):
        with self.assertRaises(native.DeepSeekAccountBalanceError):
            planner.plan(ROW,"mock-key",self.db,self.day,0,reject_402,
                         daily_limit=1.0)
        entries=self.entries()
        self.assertEqual(len(entries),1)
        self.assertEqual(entries[0][1],"NONBILLABLE")
        self.assertEqual(native.effective_spend(self.db,self.day)[0],0)

    def test_daily_pipeline_402_only_one_attempt_not_hundreds(self):
        root = self.root / "output"
        root.mkdir()
        project_file = self.root / "candidates.csv"
        rows = [ROW, {**ROW,"project_id":"project-two",
                      "address":"322 Horner Avenue, Toronto, ON"}]
        with project_file.open("w",encoding="utf-8",newline="") as f:
            writer=csv.DictWriter(f, fieldnames=ROW.keys())
            writer.writeheader()
            writer.writerows(rows)
        calls=[]
        def api(path,payload):
            calls.append(path)
            return reject_402(path,payload)
        response=native.run(project_file,root,key="mock-key",transport=api,
                            max_projects=10,today=dt.date(2026,11,14))
        self.assertEqual(response["queue_stop_reason"],
                         "DEEPSEEK_HTTP_402_ACCOUNT_BALANCE")
        self.assertEqual(len(calls),1)
        self.assertEqual(response["ai_calls_attempted"],0)
        self.assertEqual(response["unresolved_reservations_usd"],0)
        self.assertEqual(response["charged_estimate_usd"],0)
        self.assertEqual(len(native.read_csv(root/"GTA_RADAR_V6_LATEST_INVESTIGATIONS.csv")),0)


if __name__ == "__main__":
    unittest.main()
