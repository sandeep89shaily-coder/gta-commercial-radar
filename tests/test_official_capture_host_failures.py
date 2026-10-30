import csv
import tempfile
import unittest
from pathlib import Path
from v8_official_document_capture import scan

class HostFailureCacheTest(unittest.TestCase):
    def test_blocked_host_is_skipped_and_other_city_checked(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            with (root/"CANDIDATES_V4_ALL_REVIEW_ONLY.csv").open("w",newline="") as h:
                w=csv.DictWriter(h,fieldnames=["project_id","city","record_source_url"])
                w.writeheader()
                for i in range(6):
                    w.writerow(dict(project_id="b"+str(i),city="Brampton",
                                    record_source_url="https://maps1.brampton.ca/item/"+str(i)))
                w.writerow(dict(project_id="t",city="Toronto",
                                record_source_url="https://www.toronto.ca/item"))
            attempted=[]
            def fake(url):
                attempted.append(url)
                if "brampton.ca" in url:
                    return "", "robots policy unavailable"
                return "Council rezoning for warehouse", ""
            summary=scan(root,limit=6,fetch=True,fetcher=fake)
            self.assertEqual(summary["captured"],1)
            self.assertEqual(sum("brampton.ca" in u for u in attempted),1)
            self.assertEqual(sum("toronto.ca" in u for u in attempted),1)
            with (root/"DOCUMENT_REVIEW"/"OFFICIAL_DOCUMENT_FETCH_AUDIT.csv").open(encoding="utf-8-sig") as h:
                audit=list(csv.DictReader(h))
            self.assertTrue(any("Host previously blocked" in a["reason"] for a in audit))
if __name__=="__main__":
    unittest.main()
