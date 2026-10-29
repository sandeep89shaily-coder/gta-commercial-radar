import unittest
from gta_ai_work_allocator import plan
class AIPlannerTests(unittest.TestCase):
 def test_no_buying_authority_generates_research_task_not_lead(self):
  r=plan({"project_id":"site1","sources":[{"type":"pdf","analyzed":False}],
          "supplier_selection_verified":False})
  self.assertEqual(r["ai_calls_executed"],0)
  self.assertEqual(r["verified_leads_created"],0)
  self.assertIn("BUYER_RELATIONSHIP",[x["stage"] for x in r["tasks"]])
  self.assertIn("SOURCE_EXTRACTION",[x["stage"] for x in r["tasks"]])
  self.assertTrue(all(x["approval_required"] for x in r["tasks"]))
 def test_evidenced_record_does_not_create_unnecessary_calls(self):
  r=plan({"project_identity_confirmed":True,"buying_authority_verified":True,
          "supplier_selection_verified":True,"sources":[{"type":"pdf","analyzed":True}]})
  self.assertEqual(r["tasks"],[])
if __name__=="__main__":unittest.main()
