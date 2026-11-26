"""York and Hamilton alternate open-data collector tests (no HTTP)."""
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import gta_york_hamilton_open_data as regional
from gta_york_hamilton_open_data import (
    YORK,HAMILTON,BRANTFORD,pull,parse_york,parse_hamilton,parse_brantford,run,robots_ok)

def getter(url,**kw):
    if "Hosted_Active_Development_Application" in url:
        return {"features":[{"attributes":{
            "ESRI_OID":1,"REG_FILE_NUM":"D07-2026-004",
            "MUN_NAME":"City of Vaughan","ADDRESS":"44 Westcreek Drive",
            "APPL_DESC":"Industrial warehouse expansion",
            "APPL_NAME":"Example project","OWNERSHIP":"Example Inc",
            "APPL_STATUS":"Under Review","APPL_TYPE":"Official Plan Amendment",
            "DATE_RECVD":1794441600000}},
            {"attributes":{
            "ESRI_OID":2,"REG_FILE_NUM":"D07-2026-005",
            "MUN_NAME":"City of Richmond Hill","ADDRESS":"100 Bayview Avenue",
            "APPL_DESC":"Office and commercial expansion",
            "APPL_STATUS":"Under Review",
            "DATE_RECVD":1794441600000}},
            {"attributes":{
            "ESRI_OID":3,"REG_FILE_NUM":"D07-2026-006",
            "MUN_NAME":"City of Markham","ADDRESS":"2020 Markham Road",
            "APPL_DESC":"Industrial logistics development",
            "APPL_STATUS":"Under Review",
            "DATE_RECVD":1794441600000}},
            {"attributes":{
            "ESRI_OID":4,"REG_FILE_NUM":"D07-2026-007",
            "MUN_NAME":"Town of Newmarket","ADDRESS":"18 Industrial Parkway",
            "APPL_DESC":"Proposed industrial facility"}}]}
    if "Planning_Application_Open_Data_view" in url:
        return {"features":[{"attributes":{
            "OBJECTID":7,"ApplicationNum":"SPA-2026-0004",
            "Address":"15 Copernicus Boulevard",
            "Description":"New industrial factory building",
            "Proposed_use":"Industrial","Applicant":"Example Manufacturing Ltd",
            "Status":"Under Review","Submitted_date":1794441600000}}]}
    return {"features":[{"attributes":{
        "OBJECTID":1,"FILE_NUM":"ZAC-26-098",
        "FILE_TYPE":"Zoning","FILE_YEAR":2026,
        "ADDRESS":"92 John Street","DESCRIP":"Proposed industrial warehouse"}}]}

class Recovery(unittest.TestCase):
    def test_real_regional_file_ids(self):
        features,diag=pull(YORK,getter=getter,check_robots=False)
        rows=parse_york(features)
        self.assertEqual({r["city"] for r in rows},
                         {"Vaughan","Markham","Richmond Hill","Newmarket"})
        self.assertTrue(all(r["application_id"].startswith("D07-") for r in rows))
        self.assertEqual(rows[0]["date_basis"],"REGIONAL_RECEIPT_NOT_PUBLICATION")
        self.assertEqual(rows[0]["buyer_verified"],"False")
        self.assertTrue(diag["pagination_complete"])
    def test_default_york_uses_the_regional_catalogue_csv(self):
        rows = [{"MUN_NAME": "Vaughan", "REG_FILE_NUM": "SP.18.V.0111",
                 "ADDRESS": "9580 Jane Street", "APPL_TYPE": "Site Plan",
                 "APPL_NAME": "Proposed development", "OWNERSHIP": "Personal Name",
                 "DATE_RECVD": "2018/04/22 04:00:00+00"}]
        with tempfile.TemporaryDirectory() as root:
            with patch.object(regional, "download_rows", return_value=rows), \
                    patch.object(regional, "fetch_json", side_effect=getter):
                result = regional.run(root)
            self.assertEqual(result["records_by_city"]["Vaughan"], 1)
            self.assertEqual(result["source_status"]["York Region"]["transport"], "ARCGIS_HUB_CSV")
            with (Path(root) / regional.OUTPUT).open(encoding="utf-8-sig", newline="") as f:
                row = next(csv.DictReader(f))
        self.assertEqual(row["date"], "2018-04-22")
        self.assertEqual(row["source_url"], regional.YORK_CATALOGUE)
        self.assertEqual(row["applicant"], "")
        self.assertEqual(row["publication_verified"], "False")

    def test_default_hamilton_uses_licensed_catalogue_csv(self):
        sample = {"FILE_NUM": "ZAC-26-098", "FILE_TYPE": "Zoning", "FILE_YEAR": "2026",
                  "ADDRESS": "92 John Street", "DESCRIP": "Proposed industrial warehouse"}
        def download(item, required):
            if item == regional.HAMILTON_ITEM:
                return [sample]
            raise PermissionError("Unavailable source")

        with tempfile.TemporaryDirectory() as root:
            with patch.object(regional, "download_rows", side_effect=download), \
                    patch.object(regional, "fetch_json", side_effect=PermissionError("Unavailable source")):
                result = regional.run(root)
            self.assertEqual(result["records_by_city"]["Hamilton"], 1)
            self.assertEqual(result["source_status"]["Hamilton"]["transport"], "ARCGIS_HUB_CSV")
            with (Path(root) / regional.OUTPUT).open(encoding="utf-8-sig", newline="") as fp:
                row = next(csv.DictReader(fp))
        self.assertEqual(row["source_url"], regional.HAMILTON_CATALOGUE)
        self.assertEqual(row["date"], "")
        self.assertEqual(row["publication_verified"], "False")

    def test_default_brantford_imports_public_fields_without_applicant(self):
        sample = {"ApplicationNum": "SPA-2026-0004", "Address": "15 Copernicus Boulevard",
                  "Description": "New industrial factory building", "Applicant": "Personal Name",
                  "Status": "Under Review", "Submitted_date": "11/20/2026"}
        def download(item, required):
            if item == regional.BRANTFORD_ITEM:
                return [sample]
            raise PermissionError("Unavailable source")

        with tempfile.TemporaryDirectory() as root:
            with patch.object(regional, "download_rows", side_effect=download):
                result = regional.run(root)
            self.assertEqual(result["records_by_city"]["Brantford"], 1)
            self.assertEqual(result["source_status"]["Brantford"]["transport"], "ARCGIS_HUB_CSV")
            with (Path(root) / regional.OUTPUT).open(encoding="utf-8-sig", newline="") as fp:
                row = next(csv.DictReader(fp))
        self.assertEqual(row["source_url"], regional.BRANTFORD_CATALOGUE)
        self.assertEqual(row["date"], "2026-11-20")
        self.assertEqual(row["applicant"], "")
        self.assertEqual(row["publication_verified"], "False")

    def test_hamilton_file_year_not_publication(self):
        rows=parse_hamilton(pull(HAMILTON,getter=getter,check_robots=False)[0])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["application_id"],"ZAC-26-098")
        self.assertEqual(rows[0]["date"],"")
        self.assertEqual(rows[0]["date_basis"],"FILE_YEAR_ONLY_NOT_PUBLICATION")
    def test_brantford_exact_file_number(self):
        rows=parse_brantford(pull(BRANTFORD,getter=getter,check_robots=False)[0])
        self.assertEqual(rows[0]["application_id"],"SPA-2026-0004")
        self.assertEqual(rows[0]["address"],"15 Copernicus Boulevard")
        self.assertEqual(rows[0]["buyer_verified"],"False")

    def test_all_four_recover_independently(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=run(tmp,getter=getter)
            self.assertEqual(result["total_valid_application_files"],6)
            self.assertEqual(result["records_by_city"],{
                "Vaughan":1,"Markham":1,"Richmond Hill":1,"Newmarket":1,"Hamilton":1,"Brantford":1})
            self.assertFalse(result["complete_citywide_application_inventory_verified"])
            self.assertEqual(result["verified_buyers"],0)
            with (Path(tmp)/"GTA_RADAR_ADDITIONAL_OFFICIAL_OPEN_DATA.csv").open(
                    encoding="utf-8-sig") as fp:
                self.assertEqual(len(list(csv.DictReader(fp))),6)
    def test_failed_york_keeps_hamilton(self):
        def partial(url,**kw):
            if "Hosted_" in url:raise PermissionError("Denied")
            return getter(url,**kw)
        with tempfile.TemporaryDirectory() as tmp:
            result=run(tmp,getter=partial)
            self.assertEqual(result["total_valid_application_files"],2)
            self.assertEqual(result["records_by_city"]["Hamilton"],1)
            self.assertEqual(result["source_status"]["York Region"]["status"],"BLOCKED_OR_FAILED")
    def test_robots_invalid_origin(self):
        self.assertFalse(robots_ok("http://services1.arcgis.com/"))
        self.assertFalse(robots_ok("https://user:pass@services1.arcgis.com/"))
    def test_reject_duplicate_oid(self):
        def duplicates(url,**kw):
            return {"features":[{"attributes":{"ESRI_OID":1}} for _ in range(2)]}
        with self.assertRaises(ValueError):
            pull(YORK,getter=duplicates,check_robots=False)
if __name__=="__main__":
    unittest.main()


class YorkDailyIntegrationTest(unittest.TestCase):
    def test_regional_snapshot_feeds_daily_reconciliation(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            import datetime as dt
            import csv
            from unittest.mock import patch
            from gta_york_hamilton_open_data import YORK_ITEM, run
            from gta_unified_municipal_daily import OUTPUT, run as reconcile
            from gta_24_city_source_readiness import _sources

            baseline = {"MUN_NAME": "City of Richmond Hill", "REG_FILE_NUM": "SP-26-101",
                        "ADDRESS": "1 Industrial Road", "APPL_DESC": "Proposed industrial manufacturing building.",
                        "DATE_RECVD": "11/20/2026"}
            changed = dict(baseline, APPL_DESC="Revised industrial manufacturing building with warehouse.")
            added = dict(baseline, MUN_NAME="Vaughan", REG_FILE_NUM="SP-26-102")

            def collect(rows, today):
                def download(item, fields):
                    if item != YORK_ITEM:
                        raise PermissionError("Unavailable source")
                    return rows
                with patch("gta_york_hamilton_open_data.download_rows", download), patch(
                        "gta_york_hamilton_open_data.pull", side_effect=PermissionError("ROBOTS_DENIED")):
                    return run(tmp_path, today=today)

            first = dt.date(2026, 11, 25)
            day = dt.date(2026, 11, 26)
            assert collect([baseline, added], first)["observations"] == {"INITIAL_BASELINE": 2}
            assert reconcile(tmp_path, today=first)["unified_change_rows"] == 0
            assert collect([], day)["observations"] == {}
            assert collect([changed, added, dict(added, REG_FILE_NUM="SP-26-103")], day)["observations"] == {
                "RECORD_CHANGED": 1, "UNCHANGED": 1, "FIRST_OBSERVED": 1}
            assert reconcile(tmp_path, today=day)["unified_change_rows"] == 2
            with (tmp_path / OUTPUT).open(encoding="utf-8-sig", newline="") as fp:
                records = {row["city"]: row for row in csv.DictReader(fp)}
            assert records["Richmond Hill"]["observation"] == "RECORD_CHANGED"
            assert records["Vaughan"]["observation"] == "FIRST_OBSERVED"
            assert all(not r["record_source_url"] for r in records.values())
            assert all(r["paid_freshness_eligible"] == "False" for r in records.values())
            assert _sources(tmp_path, not_before=0)["Vaughan"][0]["application_id_rows"] == 2
            assert not _sources(tmp_path, not_before=float("inf")).get("Vaughan")
