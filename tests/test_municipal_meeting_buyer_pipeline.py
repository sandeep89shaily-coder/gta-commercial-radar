import tempfile,unittest,json
from pathlib import Path
from municipal_meeting_capture import discover,normalize_video,capture
from municipal_buyer_procurement import dossier
from municipal_captions_to_transcript import convert
from municipal_official_buyer_research import shortlist
class PipelineTests(unittest.TestCase):
 def test_official_meeting_links_and_agenda_uncertainty(self):
  markup='<a href="https://www.youtube.com/watch?v=abcdefghijk">Planning</a><iframe src="https://www.youtube.com/embed/abcdefghijk"></iframe>'
  r=discover("Toronto",fetch=lambda url:markup)
  self.assertEqual(r["discovered"],1)
  self.assertEqual(r["meetings"][0]["agenda_match"],"UNRESOLVED_NEEDS_OFFICIAL_MEETING_ID")
  self.assertIsNone(normalize_video("https://www.youtube.com/channel/xyz"))
 def test_capture_requires_authorization(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(PermissionError):capture("https://youtu.be/abcdefghijk",t)
 def test_captions_timestamps(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);src=root/"m.vtt"
   src.write_text("WEBVTT\n\n00:00:03.000 --> 00:00:06.000\nNew warehouse\n\n00:00:07.000 --> 00:00:08.000\nFuture equipment\n")
   r=convert(src,root/"m.csv","https://www.toronto.ca/meetings")
   self.assertEqual(r["caption_segments"],2)
 def test_buyer_fail_closed(self):
  obs=[{"source_url":"https://www.toronto.ca/contracts","quote":"A contract was awarded",
    "page":3,"source_kind":"document","role":"operator","organization":"Example",
    "procurement_status":"OPEN"}]
  d=dossier("id","Example Street",obs)
  self.assertEqual(d["procurement_checks"][0]["status"],"UNKNOWN")
  self.assertEqual(d["verified_purchasing_contacts"],0)
  self.assertFalse(d["sale_ready"])
 def test_official_scout_does_not_invent_buyer(self):
  r=shortlist("175 Oak Street",["https://www.toronto.ca/notice"],fetch=lambda _: "Proposed 175 Oak Street facility.")
  self.assertEqual(r["verified_unawarded_contracts"],0)
  self.assertEqual(r["observations"][0]["classification"],"ADDRESS_MENTION_UNVERIFIED")
if __name__=="__main__":unittest.main()
