import unittest,tempfile,csv
from pathlib import Path
from toronto_open_data_schedule import import_csv,select_resource,write
class OfficialScheduleTest(unittest.TestCase):
 def test_schedule_triage_does_not_invent_agenda_urls(self):
  raw=b"Meeting Date,Meeting Name\n2026-10-29,Planning and Housing Committee\n2026-11-01,City Council\n2026-11-01,City Council\n"
  rows=import_csv(raw)
  self.assertEqual(len(rows),2)
  self.assertEqual(rows[0]["committee_relevance"],"REVIEW_PRIORITY")
  self.assertTrue(all(not r["meeting_url"] for r in rows))
  with tempfile.TemporaryDirectory() as td:
   summary=write(rows,td,{"dataset":"fixture"})
   self.assertEqual(summary["agenda_urls_verified"],0)
   self.assertTrue((Path(td)/"TORONTO_SCHEDULE_MEETINGS_REVIEW.csv").is_file())
 def test_rejects_external_download_host(self):
  data={"success":True,"result":{"resources":[{"name":"meeting-schedule-all-committees-2022-2026","url":"https://other.example.org/data.csv"}]}}
  with self.assertRaises(ValueError):select_resource(data)
if __name__=="__main__":unittest.main()
