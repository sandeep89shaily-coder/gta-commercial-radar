"""Kitchener disabled-source baseline and change-gating regression tests."""
import json
import tempfile
import unittest
from pathlib import Path
from radar import Snapshot,open_db,register_sources,process_snapshot,latest_changes

ROOT=Path(__file__).resolve().parents[1]
SOURCE_ID="kitchener_active_planning_applications"

class KitchenerChangeGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        sources=json.loads((ROOT/"config/sources.json").read_text(encoding="utf-8"))
        self.source=next(s for s in sources if s["id"]==SOURCE_ID)
        self.assertFalse(self.source["enabled"])
        self.db=open_db(self.root/"isolated.sqlite")
        register_sources(self.db,[self.source])
    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()
    def snap(self,rows):
        return Snapshot(source=self.source,rows=rows,raw_bytes=b"[]",
            resource_url=self.source["url"],metadata={},is_complete=True)
    def changes(self):
        return list(self.db.execute("SELECT change_type,record_key FROM changes WHERE source_id=?",
                                    (SOURCE_ID,)))
    def test_initial_history_never_becomes_new_lead(self):
        self.snap_run([{"OBJECTID":1,"INDATE":1704067200000},
                       {"OBJECTID":2,"INDATE":1704067200000}])
        self.assertEqual(self.changes(),[])
    def snap_run(self,rows):
        return process_snapshot(self.db,self.snap(rows),self.root/"raw")
    def test_identical_repeat_does_not_create_change(self):
        rows=[{"OBJECTID":1,"INDATE":1704067200000}]
        self.snap_run(rows)
        self.snap_run(rows)
        self.assertEqual(self.changes(),[])
    def test_new_id_after_baseline_is_observation_not_publication(self):
        self.snap_run([{"OBJECTID":1,"INDATE":1704067200000}])
        self.snap_run([{"OBJECTID":1,"INDATE":1704067200000},
                       {"OBJECTID":2,"INDATE":1704067200000}])
        self.assertEqual([(r["change_type"],r["record_key"]) for r in self.changes()],[("NEW","2")])
        # A newly observed historical record must keep its old source date.
        record=self.db.execute("SELECT source_date FROM records_current WHERE source_id=? AND record_key='2'",(SOURCE_ID,)).fetchone()
        self.assertEqual(record["source_date"],"")
    def test_residential_not_automatically_sale_ready(self):
        from radar import normalized_summary,normalize_row
        row=normalized_summary(normalize_row({"OBJECTID":1}),self.source)
        self.assertNotEqual(row["commercial_relevance"],"HIGH")

if __name__=="__main__":unittest.main()
