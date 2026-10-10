import tempfile,unittest
from pathlib import Path
import source_network as sn
class SourceNetworkTests(unittest.TestCase):
 def test_count_consistency(self):
  r=sn.base_rows();ids=[x["source_id"] for x in r];self.assertEqual(len(ids),len(set(ids))); self.assertGreater(len(r),40)
 def test_no_candidates_enabled(self):
  self.assertFalse(any(x["enabled"]=="true" for x in sn.base_rows() if x["implementation"]=="research_only"))
 def test_persist(self):
  with tempfile.TemporaryDirectory() as t:
   f=Path(t)/"audit.csv";sn.init(f); self.assertEqual(len(sn.load(f)),len(sn.base_rows()))
 def test_ontario_manual(self):
  r={x["source_id"]:x for x in sn.base_rows()}; self.assertEqual(r["ontario_registry"]["enabled"],"false")
 def test_no_unearned_verified(self):
  self.assertEqual(sn.summarize(sn.base_rows())["live_import_verified_in_v09"],0)
if __name__=="__main__":unittest.main()
