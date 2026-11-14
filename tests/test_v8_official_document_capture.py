import csv
import tempfile
import unittest
from pathlib import Path
from v8_official_document_capture import scan
from v8_document_bridge import bridge


class CaptureTest(unittest.TestCase):
    def test_dry_run_is_network_free_and_fetch_populates_review(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            source=p/"CANDIDATES_V4_ALL_REVIEW_ONLY.csv"
            with source.open("w",newline="",encoding="utf-8") as f:
                w=csv.DictWriter(f,fieldnames=["project_id","source_id","record_source_url","city","address"])
                w.writeheader()
                w.writerow(dict(project_id="x",source_id="toronto",record_source_url="https://www.toronto.ca/example",
                                city="Toronto",address="100 Main Street"))
            calls=[]
            def fake(url):
                calls.append(url)
                return "Council discusses rezoning and a warehouse for future construction.", ""
            summary=scan(p,fetch=False,fetcher=fake)
            self.assertEqual(calls,[])
            self.assertEqual(summary["captured"],0)
            self.assertFalse((p/"DOCUMENT_SOURCE_MANIFEST.csv").exists())
            summary=scan(p,fetch=True,fetcher=fake)
            self.assertEqual(summary["captured"],1)
            self.assertEqual(len(calls),1)
            output=bridge(p)
            self.assertEqual(output["documents"],1)
            self.assertGreater(output["mentions"],0)
            self.assertEqual(output["sale_ready"],0)
            self.assertEqual(scan(p,fetch=True,fetcher=fake)["captured"],0)
            self.assertEqual(len(calls),1)
            self.assertEqual(source.read_text().count("100 Main Street"),1)

    def test_unapproved_websites_not_fetched(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/"CANDIDATES_V4_ALL_REVIEW_ONLY.csv").write_text(
                "project_id,record_source_url\nx,https://evil.example.org/project\n",encoding="utf-8")
            def fail(url):
                raise AssertionError("Unapproved host fetched")
            self.assertEqual(scan(p,fetch=True,fetcher=fail)["eligible_checked"],0)

if __name__=="__main__":
    unittest.main()
