import json,sqlite3,unittest
from gta_adaptive_deepseek_planner import plan
import v8_deepseek_native as native
class AdaptivePlannerTests(unittest.TestCase):
 def test_model_only_reorders_approved_queries(self):
  db=sqlite3.connect(":memory:")
  db.execute("CREATE TABLE spends(day TEXT,candidate TEXT,reserved REAL,actual REAL,status TEXT,PRIMARY KEY(day,candidate))")
  row={"project_id":"p1","source_keys":"P1","address":"123 Main St","description":"Commercial renovation"}
  allowed=native.queries(row)[:3]
  self.assertTrue(allowed)
  def transport(path,payload):
   return {"choices":[{"message":{"content":json.dumps({"topic":"buyer_organization","query_indices":[2,0,999,-1,"bad"]})}}],
           "usage":{"prompt_tokens":200,"completion_tokens":25}}
  result=plan(row,"fake",db,"2026-10-29",0,transport)
  self.assertEqual(result["status"],"AI_PLANNED")
  self.assertEqual(result["topic"],"buyer_organization")
  self.assertEqual(set(result["queries"]),set(allowed))
  self.assertEqual(result["queries"][0],allowed[2])
 def test_no_budget_does_not_call_model(self):
  db=sqlite3.connect(":memory:")
  db.execute("CREATE TABLE spends(day TEXT,candidate TEXT,reserved REAL,actual REAL,status TEXT,PRIMARY KEY(day,candidate))")
  row={"project_id":"p2","source_keys":"P2","address":"123 Main St"}
  result=plan(row,"fake",db,"2026-10-29",.49,lambda *args: self.fail("must not spend"))
  self.assertEqual(result["status"],"PLANNER_BUDGET_OR_PRIOR_REQUEST")
if __name__=="__main__":unittest.main()
