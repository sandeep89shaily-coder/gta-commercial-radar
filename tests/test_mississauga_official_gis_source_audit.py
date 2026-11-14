"""Offline acceptance tests for City of Mississauga GIS sources."""
import tempfile
import unittest
from pathlib import Path

from gta_mississauga_official_gis_source_audit import audit, LAYERS, NAMES, REQUIRED, OUT


class MississaugaGisAuditTests(unittest.TestCase):
    def test_no_network_by_default(self):
        with tempfile.TemporaryDirectory() as folder:
            result = audit(folder)
            self.assertEqual(result["status"], "EXPLICIT_MANUAL_FETCH_NOT_REQUESTED")
            self.assertEqual(result["paid_ai_calls"], 0)
            self.assertTrue((Path(folder) / OUT).exists())

    def test_complete_both_layers(self):
        called = []
        def fixture(url, params):
            called.append(url)
            base = url.removesuffix("/query")
            layer = next(k for k, v in LAYERS.items() if v == base)
            if url.endswith("/query"):
                return {"objectIds": [3, 1, 2]}
            return {"name": NAMES[layer], "objectIdField": "OBJECTID",
                    "fields": [{"name": x} for x in REQUIRED]}
        with tempfile.TemporaryDirectory() as folder:
            result = audit(folder, fetch=True, fetcher=fixture)
            self.assertEqual(result["status"], "BOTH_SOURCE_SCHEMAS_AND_ID_INVENTORIES_READY")
            self.assertEqual(result["schema_valid_layers"], 2)
            self.assertEqual(result["id_inventory_complete_layers"], 2)
            self.assertEqual(len(called), 4)
            self.assertEqual(result["publisher_first_publications_verified"], 0)
            self.assertEqual(result["buyer_verified"], 0)

    def test_schema_drift_is_not_success(self):
        def fixture(url, params):
            if url.endswith("/query"):
                return {"objectIds": [1]}
            return {"name": "unexpected", "objectIdField": "OBJECTID",
                    "fields": [{"name": f} for f in REQUIRED]}
        with tempfile.TemporaryDirectory() as folder:
            result = audit(folder, fetch=True, fetcher=fixture)
            self.assertEqual(result["status"], "PARTIAL_OR_BLOCKED_OFFICIAL_GIS_SOURCE")
            self.assertEqual(result["schema_valid_layers"], 0)

    def test_duplicate_id_inventory_held(self):
        def fixture(url, params):
            base = url.removesuffix("/query")
            layer = next(k for k, v in LAYERS.items() if v == base)
            if url.endswith("/query"):
                return {"objectIds": [1, 1]}
            return {"name": NAMES[layer], "objectIdField": "OBJECTID",
                    "fields": [{"name": f} for f in REQUIRED]}
        with tempfile.TemporaryDirectory() as folder:
            result = audit(folder, fetch=True, fetcher=fixture)
            self.assertEqual(result["id_inventory_complete_layers"], 0)
            self.assertEqual(result["status"], "PARTIAL_OR_BLOCKED_OFFICIAL_GIS_SOURCE")


if __name__ == "__main__":
    unittest.main()
