import unittest,tempfile,json
from pathlib import Path
from RUN_MEETING_BUYER_PIPELINE import pipeline
class EndToEndTests(unittest.TestCase):
 def test_official_index_meeting_buyer_and_evidence_graph(self):
  with tempfile.TemporaryDirectory() as td:
   html='<iframe src="https://www.youtube.com/embed/abcdefghijk"></iframe>'
   result=pipeline("Toronto",Path(td),fetch=lambda url:html,
      address="175 Oak Street",
      research_fetch=lambda url:"Report for 175 Oak Street prospective facility.")
   self.assertEqual(result["official_videos_discovered"],1)
   self.assertEqual(result["buyer_evidence_status"],"SOURCE_CHECKED_NOT_VERIFIED")
   graph=json.loads((Path(td)/"PROJECT_EVIDENCE_GRAPH.json").read_text())
   self.assertEqual(graph["sale_ready_opportunities"],0)
   self.assertEqual(len(graph["nodes"]),1)
 def test_unmatched_recording_no_download(self):
  with tempfile.TemporaryDirectory() as td:
   result=pipeline("Brampton",Path(td),fetch=lambda url:"<html/>",
       recording_url="https://www.youtube.com/watch?v=abcdefghijk",
       capture_authorized=True)
   self.assertEqual(result["caption_status"],"RECORDING_NOT_MATCHED_TO_OFFICIAL_INDEX")
if __name__=="__main__":unittest.main()
