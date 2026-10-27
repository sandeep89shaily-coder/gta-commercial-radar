import csv
import tempfile
import unittest
from pathlib import Path
from municipal_document_registry import validate, report, ROOT

class RegistryTest(unittest.TestCase):
    def test_all_official_entrypoints_registered_without_false_operational_claims(self):
        records=validate(ROOT/"config"/"municipal_document_sources.csv")
        self.assertEqual({r["city"] for r in records},
                         {"Toronto","Brampton","Mississauga","Hamilton"})
        with tempfile.TemporaryDirectory() as t:
            result=report(ROOT/"config"/"municipal_document_sources.csv",t)
            self.assertEqual(result["registered_sources"],4)
            self.assertEqual(result["documents_retrieved"],0)
            self.assertEqual(result["automated_source_fetch_approved"],0)
            self.assertEqual(result["commercial_reuse_permissions_confirmed"],0)

    def test_reject_duplicate_and_unverified_claims(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"sources.csv"
            original=(ROOT/"config"/"municipal_document_sources.csv").read_text()
            p.write_text(original.replace("OFFICIAL_INDEX_CONFIRMED_DOCUMENT_FETCH_UNTESTED",
                                           "PRODUCTION_READY"),encoding="utf-8")
            with self.assertRaises(ValueError):
                validate(p)

if __name__=="__main__":
    unittest.main()
