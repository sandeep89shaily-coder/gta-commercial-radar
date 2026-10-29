import json,tempfile,unittest
from pathlib import Path
from municipal_cross_source_synthesis import observations,synthesize
class CrossSourceTests(unittest.TestCase):
 def fixture(self,root,suffix,kind,marker):
  path=root/(suffix+".json")
  path.write_text(json.dumps({"source_sha256":suffix,"source_url":"https://www.toronto.ca/"+suffix,
    "completed_chunks":[1],"mentions":[{"source_kind":kind,
    "source_marker_expected":marker,"address":"175 Oak Street","exact_quote":"175 Oak Street",
    "quote_present":True,"marker_correct":True,"evidence_check_passed":True}]}))
  return path
 def test_sources_are_separate_and_citation_ids_rechecked(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);a=self.fixture(root,"report","pdf",2);b=self.fixture(root,"meeting","audio",150.0)
   found=observations([a,b])
   self.assertEqual(len(found["evidence"]),2)
   self.assertEqual([x["id"] for x in found["evidence"]],["E1","E2"])
   def fake(path,payload):
    self.assertEqual(payload["thinking"],{"type":"disabled"})
    return {"choices":[{"finish_reason":"stop","message":{"content":json.dumps({
      "project_candidates":[
       {"name":"Possible shared site","source_evidence_ids":["E1","E2"]},
       {"name":"Invented","source_evidence_ids":["BAD"]}]})}}]}
   r=synthesize([a,b],root,root/"review.json",paid=True,key="fake",transport=fake)
   self.assertEqual(r["status"],"SYNTHESIS_REVIEW_ONLY")
   self.assertEqual(r["candidate_project_groups"],1)
   self.assertEqual(r["invalid_citations_rejected"],1)
   self.assertEqual(r["sale_ready_leads"],0)
 def test_preflight_does_not_call_ai(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);a=self.fixture(root,"report","pdf",2)
   r=synthesize([a],root,root/"review.json")
   self.assertEqual(r["paid_model_calls"],0)
if __name__=="__main__":unittest.main()
