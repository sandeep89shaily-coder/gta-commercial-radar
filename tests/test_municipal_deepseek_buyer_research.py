import unittest,tempfile,json
from pathlib import Path
from municipal_deepseek_buyer_research import propose
class BuyerAITests(unittest.TestCase):
 def test_exact_evidence_and_no_buyer_verification(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   rows=[{"source_url":"https://www.toronto.ca/notice",
          "quote":"Owner Example Development Inc. Project on 175 Oak Street."}]
   def fake(path,payload):
    self.assertEqual(payload["thinking"],{"type":"disabled"})
    return {"choices":[{"finish_reason":"stop","message":{"content":json.dumps({
      "relationships":[
       {"organization":"Example Development Inc.","role":"owner","source_index":1,
        "exact_quote":"Owner Example Development Inc."},
       {"organization":"Fake buyer","role":"purchasing_organization","source_index":1,
        "exact_quote":"not actually on the page"}]})}}]}
   state=propose(rows,root,root/"buyer.json",paid=True,key="mock",transport=fake)
   self.assertEqual(state["candidate_relationships"],1)
   self.assertEqual(state["invalid_evidence"],1)
   obj=json.loads((root/"buyer.json").read_text())
   self.assertFalse(obj["observations"][0]["purchasing_responsibility_verified"])
   self.assertEqual(obj["verified_unawarded_contracts"],0)
if __name__=="__main__":unittest.main()
