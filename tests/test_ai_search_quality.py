import unittest
from v8_deepseek_native import queries
class SearchQualityRegression(unittest.TestCase):
 def test_prefers_project_id_over_ambiguous_address(self):
  row={"project_id":"toronto_development_applications:26175566S4514TLAB",
       "source_keys":"26175566S4514TLAB","address":"45 BASEBALL PL","city":"Toronto"}
  q=queries(row)
  self.assertIn("26175566S4514TLAB",q[0])
  self.assertTrue(any("developer" in x for x in q))
  self.assertFalse(any("industrial project" in x for x in q))
 def test_old_application_is_searched_by_id(self):
  row={"source_keys":"1612220700017MV","address":"1233 ST CLAIR AVE W","city":"Toronto"}
  self.assertIn("1612220700017MV",queries(row)[0])
if __name__=="__main__":unittest.main()
