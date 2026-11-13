"""Conservative Mississauga exact file-ID reconciliation tests."""
import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path

from gta_mississauga_official_gis_records import run as collect, CSV, STATUS
from gta_mississauga_gis_reconciliation import run, _key, OUT

AT = dt.datetime(2026, 11, 13, tzinfo=dt.timezone.utc)


def city_fetch(url, params):
    from gta_mississauga_official_gis_source_audit import LAYERS, NAMES, REQUIRED
    base = url.removesuffix("/query")
    layer = next(key for key, value in LAYERS.items() if value == base)
    if not url.endswith("/query"):
        return {"name": NAMES[layer], "objectIdField": "OBJECTID",
                "fields": [{"name": key} for key in REQUIRED]}
    if params.get("returnIdsOnly"):
        return {"objectIds": [1]}
    return {"features": [{"attributes": {
        "OBJECTID": 1, "APP_FILE_NO": "OZ/OPA 25-3 W11" if layer == "REZONING" else "SP 26-1",
        "SITE_ADDRESS": "123 Example Road", "DESCRIPTION": "Industrial warehouse",
        "APPLICATION_DATE": 1790000000000, "APPROVAL_DATE": None,
        "APPLICANT": "Industrial Example Inc", "SIMPLE_STATUS": "In process",
        "TOTAL_NON_RES_GFA": 100, "ICI_INDUST": 50,
        "ICI_OFFICE": 0, "ICI_RETAIL": 0,
    }}]}


class MississaugaReconciliationTests(unittest.TestCase):
    def test_exact_id_not_near_id(self):
        self.assertEqual(_key("OZ/OPA 25-3 W11"), _key("OZ OPA-25 3 W11"))
        self.assertNotEqual(_key("OZ/OPA 25-3 W11"), _key("OZ/OPA 25-30 W11"))

    def test_matching_saved_city_only_and_no_buyer_promotion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            collected = root / "source"
            collect(collected, fetch=True, fetcher=city_fetch, now=AT)
            results = root / "results"
            results.mkdir()
            (results / "GTA_RADAR_PRIVATE_TOP_10.csv").write_text(
                "city,address,application_id\n"
                "Mississauga,123 Example Road,OZ/OPA 25-3 W11\n"
                "Toronto,Another Road,SP 26-1\n", encoding="utf-8")
            report = run(collected, results, root / "audit")
            self.assertEqual(report["status"], "EXACT_FILE_ID_REVIEW_READY")
            self.assertEqual(report["exact_ids_in_saved_radar"], 1)
            with (root / "audit" / OUT).open(encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 2)
            matched = next(r for r in rows if r["application_id"] == "OZ/OPA 25-3 W11")
            self.assertEqual(matched["previously_in_private_top_ten"], "True")
            self.assertEqual(matched["buyer_verified"], "False")

    def test_refuse_stale_source_after_failed_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            collected = root / "source"
            collect(collected, fetch=True, fetcher=city_fetch, now=AT)
            collect(collected, fetch=True, fetcher=lambda *a: (_ for _ in ()).throw(
                PermissionError("403")), now=AT + dt.timedelta(days=1))
            status = run(collected, root, root / "audit")
            self.assertEqual(status["status"], "NO_CURRENT_SUCCESSFUL_GIS_SOURCE")


if __name__ == "__main__":
    unittest.main()
