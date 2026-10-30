import tempfile,unittest
from pathlib import Path
from gta_early_signal_feed_monitor import collect,FEEDS
class FeedMonitorTests(unittest.TestCase):
 def test_dedup_and_first_seen(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   def html(_):return '<a href="/en/planning/industrial-project.aspx">Industrial Planning Project</a>'
   first=collect(root,transport=html)
   second=collect(root,transport=html)
   self.assertEqual(len(first["candidate_links"]),len(FEEDS))
   self.assertEqual(len(second["candidate_links"]),len(FEEDS))
   self.assertTrue(all(not x["publication_date_verified"] for x in second["candidate_links"]))
   self.assertEqual(second["verified_open_work_packages"],0)
 def test_no_nonofficial_links(self):
  with tempfile.TemporaryDirectory() as d:
   obj=collect(d,transport=lambda _:'<a href="https://evil.example/planning">Industrial planning</a>')
   self.assertEqual(len(obj["candidate_links"]),0)
if __name__=="__main__":unittest.main()
