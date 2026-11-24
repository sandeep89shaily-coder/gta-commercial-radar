"""No-network regression for approved, SHA-matched municipal CSV intake."""
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from gta_authorized_application_exports import load, stage_kitchener_export

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

    def test_brampton_mississauga_local_handoffs_require_documented_rights(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            folder=root/"GTA_RADAR_AUTHORIZED_EXPORTS"
            folder.mkdir()
            exports=[]
            for city,source in (
                ("Brampton","https://geohub.brampton.ca/datasets/brampton::pre-consultation-2/about"),
                ("Mississauga","https://data.mississauga.ca/datasets/85536f145719436ebde8d31f36d11d83_0/about"),
            ):
                contents=("FILE,ADDRESS,SCOPE\n"
                          "SP-26-77,10 Test Road,Industrial development application\n")
                local=folder/(city.lower()+".csv")
                local.write_text(contents,encoding="utf-8")
                exports.append({
                    "city":city,"official_source_url":source,
                    "sha256":hashlib.sha256(local.read_bytes()).hexdigest(),
                    "permitted_public_export":True,
                    "dataset_licence":"CC BY 4.0" if city=="Brampton" else "CUSTOM",
                    "licence_or_permission_url":source,
                    "commercial_reuse_permission_confirmed":False,
                    "columns":{"application_id":"FILE","address":"ADDRESS","scope":"SCOPE"},
                })
            manifest=folder/"manifest.json"
            manifest.write_text(json.dumps({"exports":exports}))
            records,report=load(root)
            self.assertEqual(records,[])
            self.assertTrue(all(x["status"]==
                "HELD_DATASET_SPECIFIC_REUSE_NOT_DOCUMENTED" for x in report["sources"]))
            exports[0]["commercial_reuse_permission_confirmed"]=True
            manifest.write_text(json.dumps({"exports":exports}))
            records,report=load(root)
            self.assertEqual([r["city"] for r in records],["Brampton"])
            self.assertTrue(report["no_network_requests"])
            self.assertTrue(report["no_verified_original_publication"])

    def test_kitchener_geohub_export_stages_without_personal_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "download.csv"
            source.write_text(
                "Application Number,Address,Application Summary,Application Type,Status,In Date,Applicant\n"
                "ZBA26/016/K/BB,10 Test Road,,Rezoning,Received,11/2/2026 12:00:00 AM,Personal Name\n",
                encoding="utf-8-sig",
            )
            stage_kitchener_export(source, root)
            rows, status = load(root)
        self.assertTrue(status["no_network_requests"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["application_id"], "ZBA26/016/K/BB")
        self.assertEqual(rows[0]["date"], "2026-11-02")
        self.assertEqual(rows[0]["scope"], "Rezoning")
        self.assertEqual(rows[0]["applicant"], "")

    def test_missing_manifest_never_invents_city_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows,report = load(tmp)
            self.assertEqual(rows, [])
            self.assertEqual(report["rows"], 0)

if __name__ == "__main__":
    unittest.main()
