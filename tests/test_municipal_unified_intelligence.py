import csv,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from municipal_unified_intelligence import source_chunks,interpret,run
class UnifiedTests(unittest.TestCase):
 def test_audio_transcript_chunks_include_all_segments(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/"transcript.csv"
   with p.open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=["start_seconds","end_seconds","transcript"])
    w.writeheader();w.writerow({"start_seconds":4,"end_seconds":7,"transcript":"A proposed factory"})
    w.writerow({"start_seconds":15,"end_seconds":17,"transcript":"Tax exemption for housing"})
   chunks,meta=source_chunks(transcript=p)
   self.assertEqual(meta["segments_total"],2)
   self.assertEqual([x["marker"] for x in chunks],[4.0,15.0])
 def test_claim_requires_literal_quote_and_correct_timestamp(self):
  def transport(path,payload):
   self.assertEqual(payload["thinking"],{"type":"disabled"})
   return {"choices":[{"finish_reason":"stop","message":{"content":json.dumps(
     {"event_type":"planning","project_mentions":[
       {"address":"18 Main Street","source_marker":4,"exact_quote":"factory"},
       {"address":"Fake","source_marker":4,"exact_quote":"not here"},
       {"address":"Wrong","source_marker":99,"exact_quote":"factory"}]})}}]}
  o=interpret({"kind":"audio","marker":4.0,"text":"Discuss proposed factory"},"x","https://www.toronto.ca/meeting",transport)
  self.assertEqual([v["evidence_check_passed"] for v in o["mentions"]],[True,False,False])
  self.assertEqual(o["commercial_status"],"UNVERIFIED")
 def test_paid_false_does_not_open_shared_ledger(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/"transcript.csv"
   with p.open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=["start_seconds","end_seconds","transcript"])
    w.writeheader();w.writerow({"start_seconds":1,"end_seconds":2,"transcript":"Factory"})
   with patch("municipal_unified_intelligence.v5._ledger") as ledger:
    result=run("https://www.toronto.ca/meeting",t,Path(t)/"out",transcript=p)
    self.assertEqual(result["AI_paid_requests"],0)
    self.assertEqual(result["chunks_unprocessed"],1)
    ledger.assert_not_called()
if __name__=="__main__":unittest.main()
