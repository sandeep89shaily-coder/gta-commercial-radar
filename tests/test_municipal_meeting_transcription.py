import tempfile,unittest,csv
from pathlib import Path
from municipal_meeting_transcription import label_segments,transcribe_file
class FakeSeg:
 def __init__(self,s,e,t):self.start=s;self.end=e;self.text=t
class FakeEngine:
 def transcribe(self,*args,**kwargs):
  return iter([FakeSeg(11,15,"Planning application for new warehouse"),FakeSeg(20,22,"Thank you.")]),None
class MeetingTests(unittest.TestCase):
 def test_tags_keep_timestamps_and_do_not_verify(self):
  rows=label_segments([{"start":11,"end":15,"text":"New warehouse construction"},{"start":20,"end":22,"text":"Hello"}])
  self.assertTrue(rows[0]["review_required"]);self.assertFalse(rows[1]["review_required"])
  self.assertEqual(rows[0]["start_seconds"],11)
 def test_local_media_no_api_and_unverified(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/"meeting.wav";p.write_bytes(b"local test media")
   report=transcribe_file(p,"https://www.toronto.ca/meeting",Path(t)/"out",engine=FakeEngine())
   self.assertEqual(report["paid_api_calls"],0)
   self.assertEqual(report["verified_projects"],0)
   self.assertEqual(report["segments"],2)
   with (Path(t)/"out"/"MEETING_TRANSCRIPT.csv").open(encoding="utf-8-sig") as f:
    self.assertEqual(next(csv.DictReader(f))["verification_status"],"UNVERIFIED_SPEECH_TO_TEXT")
 def test_requires_source_and_no_negative_timestamps(self):
  self.assertRaises(ValueError,label_segments,[{"start":-1,"end":1,"text":"hello"}])
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/"meeting.wav";p.write_bytes(b"test")
   self.assertRaises(ValueError,transcribe_file,p,"file:///private",Path(t)/"out",engine=FakeEngine())
if __name__=="__main__":unittest.main()
