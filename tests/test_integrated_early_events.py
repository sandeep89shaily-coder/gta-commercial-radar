import csv
import tempfile
import unittest
from pathlib import Path
from integrated_early_events import harvest,merge
def save(p,rows):
    with p.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
class Tests(unittest.TestCase):
    def test_only_live_successful_nonbaseline_changes(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t)
            save(d/"EARLY_CUES_SOURCE_STATUS.csv",[{"source_id":"ieso_connections","state":"SUCCESS"},{"source_id":"other","state":"FAILED"}])
            save(d/"EARLY_CUES_CHANGES_REVIEW_ONLY.csv",[
                {"source_id":"ieso_connections","record_id":"X","change_type":"NEW","title":"Industrial expansion","source_url":"https://www.ieso.ca/x","observed_at":"2026-10-24T01:00:00Z"},
                {"source_id":"other","record_id":"Y","change_type":"NEW","title":"Factory","source_url":"https://example.org"},
                {"source_id":"ieso_connections","record_id":"Z","change_type":"BASELINE","title":"Factory","source_url":"https://example.org"}])
            rows,_=harvest(d);self.assertEqual(len(rows),1)
            # Old files with SUCCESS labels must not be replayed if the
            # associated collector failed or never ran in this invocation.
            skipped,_=harvest(d,successful_steps=set())
            self.assertEqual(skipped,[])
            current,_=harvest(d,successful_steps={"early_industrial_cues"})
            self.assertEqual(len(current),1)

            self.assertEqual(rows[0]["event_date_basis"],"RADAR_OBSERVATION_NOT_PUBLICATION_DATE")
            save(d/"base.csv",[{"source_id":"a","source_key":"b"}])
            dest,state=merge(d/"base.csv",d,d/"merged.csv")
            self.assertEqual(state["early_pilot_changes_accepted"],1)
            self.assertEqual(len(list(csv.DictReader(dest.open(encoding="utf-8-sig")))),2)
if __name__=="__main__":unittest.main()
