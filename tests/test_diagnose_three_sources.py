"""Three-source retry must expose error details, not fabricate zero leads."""
import csv
import tempfile
import unittest
from pathlib import Path
import diagnose_three_sources as d

class Tests(unittest.TestCase):
    def test_missing_status_not_success(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(d.run(folder),1)
            self.assertTrue(all(x[1]=="NOT_RUN" for x in d.parse_source_status(folder)))

    def test_official_success_and_calendar_partial(self):
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)
            data=[
              ("EARLY_CUES_SOURCE_STATUS.csv",
               [{"source_id":"ieso_connections","state":"SUCCESS","fetched":"2085","error":""}]),
              ("EARLY_DISCOVERY_SOURCE_STATUS.csv",
               [{"source_id":"brampton_planning_agendas","status":"PARTIAL_CALENDAR_ONLY",
                 "fetched":"1","warning":"AGENDA_ITEMS_UNAVAILABLE"}]),
              ("EARLY_AJAX_SOURCE_STATUS.csv",
               [{"source_id":"ajax_planning_properties","status":"FAILED",
                 "parsed":"0","error":"HTTP 403 Forbidden"}])
            ]
            for filename,rows in data:
                with (f/filename).open("w",newline="",encoding="utf8") as stream:
                    w=csv.DictWriter(stream,fieldnames=list(rows[0]))
                    w.writeheader();w.writerows(rows)
            parsed=d.parse_source_status(folder)
            self.assertEqual(parsed[0][1],"SUCCESS")
            self.assertEqual(parsed[0][2],"2085")
            self.assertEqual(parsed[1][1],"PARTIAL_CALENDAR_ONLY")
            self.assertIn("403",parsed[2][3])
            self.assertEqual(d.run(folder),1)

if __name__=="__main__":unittest.main()
