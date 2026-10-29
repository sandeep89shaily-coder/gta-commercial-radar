import csv,json,tempfile,unittest
from pathlib import Path
from municipal_unified_intelligence import run
class ResumeTests(unittest.TestCase):
 def test_two_paid_passes_resume_and_keep_first_evidence(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);data=root/"long.csv";out=root/"out"
   with data.open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=["start_seconds","end_seconds","transcript"]);w.writeheader()
    w.writerow({"start_seconds":"1","end_seconds":"10","transcript":"Factory A at 25 Eden Place. "*90})
    w.writerow({"start_seconds":"12","end_seconds":"23","transcript":"Industrial B at 175 Oak Street. "*90})
   calls=[]
   def fake(path,payload):
    calls.append(1)
    source=json.loads(payload["messages"][1]["content"])["source"]
    return {"choices":[{"finish_reason":"stop","message":{"content":json.dumps(
      {"project_mentions":[{"source_marker":source["marker"],
                            "exact_quote":"Factory" if "Factory" in source["text"] else "Industrial",
                            "address":"25 Eden Place"}]})}}]}
   url="https://www.toronto.ca/meeting"
   first=run(url,root,out,transcript=data,paid=True,max_chunks=1,key="fake",transport=fake)
   self.assertEqual(first["chunks_completed"],1)
   second=run(url,root,out,transcript=data,paid=True,max_chunks=1,key="fake",transport=fake)
   self.assertEqual(second["chunks_completed"],2)
   self.assertEqual(len(calls),2)
   completed=json.loads((out/"UNIFIED_EVIDENCE.json").read_text())["completed_chunks"]
   self.assertEqual(completed,[1,2])
   preflight=run(url,root,out,transcript=data,paid=False)
   self.assertEqual(preflight["chunks_completed"],2)
   self.assertEqual(len(calls),2)
if __name__=="__main__":unittest.main()
