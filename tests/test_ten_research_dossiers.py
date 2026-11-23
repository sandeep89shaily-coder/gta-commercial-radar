"""No new AI or collector calls are needed for the first ten dossier view."""
import csv
import tempfile
import unittest
from pathlib import Path
from ten_research_dossiers import build, CSV, OUTPUT, INPUT


class DossierTests(unittest.TestCase):
    def test_unknowns_and_no_fake_dossier(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with (root / INPUT).open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["project_id", "address",
                    "source_urls", "contact", "operator", "supplier_contract_status"])
                writer.writeheader()
                writer.writerow({"project_id":"test-1", "address":"100 Example Street",
                    "source_urls":"https://example.org/project", "contact":"unverified@example.org",
                    "operator":"", "supplier_contract_status":"UNKNOWN"})
                writer.writerow({"project_id":"test-1", "address":"duplicate"})
            result = build(root)
            self.assertEqual(result["dossiers"], 1)
            with (root / CSV).open(encoding="utf-8-sig", newline="") as handle:
                dossier = list(csv.DictReader(handle))[0]
            self.assertEqual(dossier["public_contact"], "UNKNOWN")
            self.assertEqual(dossier["buyer_status"], "PURCHASING_AUTHORITY_NOT_VERIFIED")
            self.assertEqual(dossier["dossier_status"], "RESEARCH_ONLY_NOT_SALE_READY")
            self.assertIn("SUPPLIER_SELECTION_UNKNOWN", dossier["missing_evidence"])
            self.assertTrue((root / OUTPUT).exists())

    def test_no_rows_produces_no_claims(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / INPUT).write_text("project_id,address\n", encoding="utf-8")
            self.assertEqual(build(root)["dossiers"], 0)


if __name__ == "__main__":
    unittest.main()
