"""Integration regression tests: no fabricated acceptance and evidence union."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from gta_integrated_run_gates import evaluate
from gta_document_audit_union import union

class UnifiedEvidenceTests(unittest.TestCase):
    def test_empty_run_must_fail_even_if_scripts_exit_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            report=evaluate(root,root)
            self.assertFalse(report["production_accepted"])
            self.assertIn("OFFICIAL_DOCUMENTS_CAPTURED",report["blockers"])
            self.assertIn("VERIFIED_BUYER_AUTHORITIES",report["blockers"])
            self.assertIn("EARLY_DISCOVERY_PAIR_MEASURED",report["blockers"])

    def test_verified_report_audit_merges_by_url(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            a=root/"a.csv";b=root/"b.csv";dest=root/"combined.csv"
            for file,status in ((a,"FAILED"),(b,"CAPTURED")):
                with file.open("w",newline="",encoding="utf-8") as out:
                    w=csv.DictWriter(out,fieldnames=["attachment_url","status","saved_path","sha256"])
                    w.writeheader()
                    w.writerow({"attachment_url":"https://www.toronto.ca/legdocs/mmis/2026/ph/bgrd/backgroundfile-287454.pdf",
                                "status":status,"saved_path":"test.pdf","sha256":"abc"})
            counts=union([a,b],dest)
            self.assertEqual(counts["distinct_documents"],1)
            self.assertEqual(counts["captured"],1)

    def test_docs_without_buyer_and_commercial_proof_are_not_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            doc=root/"MEETING_DOCUMENTS"/"Toronto"
            doc.mkdir(parents=True)
            (doc/"VERIFIED_REPORT_FETCH_SUMMARY.json").write_text('{"captured":1}')
            with (doc/"VERIFIED_REPORT_FETCH_AUDIT.csv").open("w",newline="") as out:
                w=csv.DictWriter(out,fieldnames=["status"]);w.writeheader();w.writerow({"status":"CAPTURED"})
            result=evaluate(root,root)
            self.assertEqual(result["counts"]["captured_documents"],1)
            self.assertFalse(result["production_accepted"])

if __name__=="__main__":
    unittest.main()
