import csv
import tempfile
import unittest
from pathlib import Path
from integrated_early_events import harvest,merge
def save(p,rows):
    with p.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
class Tests(unittest.TestCase):
    def test_oakville_new_change_can_reach_one_selection_input(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t)
            save(d/"EARLY_OAKVILLE_SOURCE_STATUS.csv",[
                {"source_id":"oakville_development","status":"SUCCESS"}])
            save(d/"EARLY_OAKVILLE_CHANGES_REVIEW_ONLY.csv",[
                {"source_id":"oakville_development","record_id":"P1",
                 "change_type":"NEW","title":"Industrial site plan",
                 "source_url":"https://www.oakville.ca/planning/p1",
                 "commercial_fit":"POSSIBLE_COMMERCIAL","observed_at":"2026-10-24T08:00:00Z"},
                {"source_id":"oakville_development","record_id":"P2",
                 "change_type":"NEW","title":"Residential houses",
                 "source_url":"https://www.oakville.ca/planning/p2",
                 "commercial_fit":"RESIDENTIAL_LIKELY","observed_at":"2026-10-24T08:00:00Z"}])
            rows,_=harvest(d,successful_steps={"early_oakville"})
            self.assertEqual([r["source_key"] for r in rows],["P1"])
            self.assertEqual(harvest(d,successful_steps=set())[0],[])

    def test_stale_successful_output_not_replayed_into_next_run(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            save(folder/"EARLY_AJAX_SOURCE_STATUS.csv",[{"source_id":"ajax_planning_properties","status":"SUCCESS"}])
            save(folder/"EARLY_AJAX_CHANGES_REVIEW_ONLY.csv",[{
                "source_id":"ajax_planning_properties","record_id":"A1",
                "change_type":"NEW","title":"Industrial facility",
                "commercial_fit":"COMMERCIAL","source_url":"https://ajax.ca/a1",
                "observed_at":"2026-10-24T09:00:00Z"}])
            self.assertEqual(harvest(folder,successful_steps={"early_ajax"},
                                     run_started="2026-10-24T10:00:00Z")[0],[])
            self.assertEqual(len(harvest(folder,successful_steps={"early_ajax"},
                                     run_started="2026-10-24T08:00:00Z")[0]),1)
            save(folder/"EARLY_AJAX_CHANGES_REVIEW_ONLY.csv",[{
                "source_id":"ajax_planning_properties","record_id":"A2",
                "change_type":"NEW","title":"Residential planning",
                "commercial_fit":"USE_UNKNOWN","source_url":"https://ajax.ca/a2",
                "observed_at":"2026-10-24T11:00:00Z"}])
            self.assertEqual(harvest(folder,successful_steps={"early_ajax"},
                                     run_started="2026-10-24T10:00:00Z")[0],[])

    def test_tenders_never_promoted_as_private_commercial_project(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t)
            save(d/"EARLY_INVESTMENT_TENDERS_STATUS.csv",[
                {"source_id":"federal_open_tenders","status":"SUCCESS"}])
            save(d/"EARLY_INVESTMENT_TENDERS_CHANGES.csv",[
                {"source_id":"federal_open_tenders","record_id":"T1",
                 "change_type":"NEW","title":"Federal government contract",
                 "source_url":"https://canadabuys.canada.ca/open-tender",
                 "observed_at":"2026-10-24T11:00:00Z"}])
            rows,audit=harvest(d,successful_steps={"early_investment_tenders"},
                               run_started="2026-10-24T10:00:00Z")
            self.assertEqual(rows,[])
            self.assertTrue(any(s["source_file"]=="EARLY_INVESTMENT_TENDERS_STATUS.csv"
                                for s in audit))

    def test_markham_report_index_not_misrepresented_as_project(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t)
            save(d/"EARLY_MARKHAM_REPORT_SOURCE_STATUS.csv",[
                {"source_id":"markham_circulated_application_reports",
                 "status":"SUCCESS_REPORT_INDEX"}])
            save(d/"EARLY_MARKHAM_NEW_REPORTS_REVIEW_ONLY.csv",[
                {"source_id":"markham_circulated_application_reports",
                 "record_id":"PDF-1","change_type":"NEW",
                 "title":"Circulated planning applications",
                 "source_url":"https://www.markham.ca/report.pdf",
                 "observed_at":"2026-10-24T11:00:00Z"}])
            rows,audit=harvest(d,successful_steps={"early_markham"},
                               run_started="2026-10-24T10:00:00Z")
            self.assertEqual(rows,[])
            self.assertTrue(any(s["source_file"]=="EARLY_MARKHAM_REPORT_SOURCE_STATUS.csv"
                                for s in audit))

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
