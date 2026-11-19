"""No-network regression for approved, SHA-matched municipal CSV intake."""
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from gta_authorized_application_exports import load

class AuthorizedExportTests(unittest.TestCase):
    def test_source_identity_and_permission_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "GTA_RADAR_AUTHORIZED_EXPORTS"
            folder.mkdir()
            raw = ("APPLICATION_NO,STREET,SCOPE,INDATE\n"
                   "A-26-123,10 Official Rd,Industrial plant,2026-11-10\n")
            path = folder / "kitchener.csv"
            path.write_text(raw, encoding="utf-8")
            item = {
                "city": "Kitchener", "permitted_public_export": True,
                "official_source_url":
                    "https://www.kitchener.ca/planning-applications/",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "columns": {"application_id": "APPLICATION_NO",
                            "address": "STREET", "scope": "SCOPE",
                            "application_date": "INDATE"},
            }
            manifest = folder / "manifest.json"
            manifest.write_text(json.dumps({"exports": [item]}))
            records, report = load(root)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["application_id"], "A-26-123")
            self.assertIn("NOT_FIRST_PUBLICATION", records[0]["source_date_basis"])
            self.assertTrue(report["no_verified_citywide_current_coverage"])
            self.assertTrue(report["no_network_requests"])
            item["sha256"] = "0" * 64
            manifest.write_text(json.dumps({"exports": [item]}))
            self.assertEqual(load(root)[0], [])
            item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            item["permitted_public_export"] = False
            manifest.write_text(json.dumps({"exports": [item]}))
            self.assertEqual(load(root)[0], [])
            item["permitted_public_export"] = True
            item["official_source_url"] = "https://unrelated.example.org/source"
            manifest.write_text(json.dumps({"exports": [item]}))
            self.assertEqual(load(root)[0], [])

    def test_missing_manifest_never_invents_city_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows,report = load(tmp)
            self.assertEqual(rows, [])
            self.assertEqual(report["rows"], 0)

if __name__ == "__main__":
    unittest.main()
