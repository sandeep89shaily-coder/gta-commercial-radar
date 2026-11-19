"""York and Hamilton alternate open-data collector tests (no HTTP)."""
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
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
            "DATE_RECVD":1794441600000}}]}
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
    def test_real_regional_file_id_and_three_cities(self):
        features,diag=pull(YORK,getter=getter,check_robots=False)
        rows=parse_york(features)
        self.assertEqual({r["city"] for r in rows},
                         {"Vaughan","Markham","Richmond Hill"})
        self.assertTrue(all(r["application_id"].startswith("D07-") for r in rows))
        self.assertEqual(rows[0]["date_basis"],"REGIONAL_RECEIPT_NOT_PUBLICATION")
        self.assertEqual(rows[0]["buyer_verified"],"False")
        self.assertTrue(diag["pagination_complete"])
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
            self.assertEqual(result["total_valid_application_files"],5)
            self.assertEqual(result["records_by_city"],{
                "Vaughan":1,"Markham":1,"Richmond Hill":1,"Hamilton":1,"Brantford":1})
            self.assertFalse(result["complete_citywide_application_inventory_verified"])
            self.assertEqual(result["verified_buyers"],0)
            with (Path(tmp)/"GTA_RADAR_ADDITIONAL_OFFICIAL_OPEN_DATA.csv").open(
                    encoding="utf-8-sig") as fp:
                self.assertEqual(len(list(csv.DictReader(fp))),5)
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
