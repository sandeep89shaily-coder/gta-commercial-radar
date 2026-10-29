import datetime as dt,json,tempfile,unittest
from pathlib import Path
from toronto_current_open_ckan import collect
class CKANTests(unittest.TestCase):
 def test_paginates_and_only_counts_future_closing_candidates(self):
  calls=[]
  def fake(url):
   calls.append(url)
   if "package_show" in url:
    return {"success":True,"result":{"resources":[{"id":"abc","datastore_active":True}]}}
   from urllib.parse import urlparse,parse_qs
   p=parse_qs(urlparse(url).query)
   offset=int(p["offset"][0]);limit=int(p["limit"][0])
   sample=[{"Document Number":str(1234567890+i),
     "Submission Deadline":"2010-01-01" if i<2 else "2026-11-07",
     "Buyer Name":"Toronto Buyer"} for i in range(3)]
   return {"success":True,"result":{"records":sample[offset:offset+limit],"total":3}}
  with tempfile.TemporaryDirectory() as t:
   result=collect(Path(t)/"current.json",fetch=fake,limit=5,today=dt.date(2026,10,29))
   self.assertTrue(result["complete"])
   self.assertEqual(len(result["records"]),3)
   self.assertEqual(result["candidate_future_closing"],1)
   self.assertEqual(len(calls),3)
 def test_empty_or_unavailable_fails_closed(self):
  def fail(url):raise RuntimeError("Unavailable")
  with tempfile.TemporaryDirectory() as t:
   result=collect(Path(t)/"out.json",fetch=fail)
   self.assertEqual(result["status"],"UNAVAILABLE")
   self.assertEqual(result["candidate_future_closing"],0)
if __name__=="__main__":unittest.main()
