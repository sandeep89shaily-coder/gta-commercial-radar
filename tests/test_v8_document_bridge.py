import csv
import tempfile
import unittest
from pathlib import Path
from v8_document_bridge import bridge


class TestV8DocumentBridge(unittest.TestCase):
    def test_existing_v8_outputs_remain_unchanged(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            original=b"project_id,address,city\na,10 Main Street,Brampton\n"
            (p/"CANDIDATES_V4_ALL_REVIEW_ONLY.csv").write_bytes(original)
            (p/"GTA_RADAR_V8_INVESTIGATIONS.csv").write_text(
                "project_id,status\na,AI_EVIDENCE_REVIEW\n",encoding="utf-8")
            result=bridge(p)
            self.assertEqual(result["current_candidates"],1)
            self.assertEqual(result["investigations_matched"],1)
            self.assertEqual(result["documents"],0)
            self.assertEqual(result["sale_ready"],0)
            self.assertEqual(result["ai_calls"],0)
            self.assertEqual((p/"CANDIDATES_V4_ALL_REVIEW_ONLY.csv").read_bytes(),original)
            self.assertTrue((p/"GTA_RADAR_DOCUMENT_OPERATIONS.html").is_file())
            self.assertTrue((p/"DOCUMENT_SOURCE_MANIFEST.csv").is_file())
            second=bridge(p)
            self.assertEqual(second["current_candidates"],1)

if __name__=="__main__":
    unittest.main()
