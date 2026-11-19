"""Official Brampton and Mississauga planning recovery regression tests (offline)."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch
import gta_brampton_mississauga_open_data as peel

def fake(lane):
    if lane not in peel.SOURCES:raise AssertionError(lane)
    return lane

def response(url):
    lane=next((k for k,v in peel.SOURCES.items() if url.startswith(v)),None)
    if lane is None:raise AssertionError(url)
    if "?f=json" in url:
        return {"objectIdField":"OBJECTID","fields":[{"name":"OBJECTID"}]}
    if "/query?" not in url:raise AssertionError(url)
    if lane.startswith("Brampton"):
        return {"features":[{"attributes":{
            "OBJECTID":1,"FILE_NUMBER":"SPA-2026-003",
            "LOCATION":"9 Steeles Avenue West",
            "PROPOSAL_DESCRIPTION":"Industrial factory expansion with equipment",
            "APPLICATION_TITLE":"New warehouse","STATUS":"Under Review",
            "AGENT_COMPANY":"Design Architects",
            "APPLICANT_COMPANY":"Factory Inc",
            "DATE_RECEIVED":1794528000000}}]}
    return {"features":[{"attributes":{
        "OBJECTID":1,"APP_FILE_NO":"SP-26-0101",
        "SITE_ADDRESS":"1100 Dixie Road",
        "DESCRIPTION":"Industrial and office expansion",
        "APPROVAL_DATE":None,"APPLICATION_DATE":1794441600000,
        "APPLICANT":"Industrial Developers Inc",
        "TOTAL_NON_RES_GFA":12500.0,"ICI_INDUST":9000,
        "ICI_OFFICE":2500.0,"ICI_RETAIL":1000.0,
        "SIMPLE_STATUS":"Under Review"}}]}

class OfficialPeel(unittest.TestCase):
    def test_brampton_layers_separate_and_correct_organization(self):
        for lane in list(peel.SOURCES)[:3]:
            data,info=peel.query_lane(lane,getter=response)
            self.assertEqual(info["valid_files"],1)
            self.assertEqual(data[0]["application_id"],"SPA-2026-003")
            self.assertEqual(data[0]["applicant"],"Factory Inc")
            self.assertEqual(data[0]["agent"],"Design Architects")
            self.assertEqual(data[0]["source_date_basis"],
                             "APPLICATION_RECEIVED_NOT_FIRST_PUBLICATION")
    def test_mississauga_non_residential_gfa_preserved_not_buyer(self):
        data,info=peel.query_lane("Mississauga_Site_Plan",getter=response)
        self.assertEqual(data[0]["non_res_gfa"],"12500.0")
        self.assertEqual(data[0]["industrial_gfa"],"9000")
        self.assertEqual(data[0]["office_gfa"],"2500.0")
        self.assertEqual(data[0]["retail_gfa"],"1000.0")
        self.assertEqual(data[0]["licence_status"],"CUSTOM_LICENSE_NOT_VERIFIED")
        self.assertEqual(data[0]["buyer_verified"],"False")
    def test_four_lanes_become_two_deduped_municipal_files(self):
        with tempfile.TemporaryDirectory() as d:
            result=peel.run(d,getter=response)
            self.assertEqual(result["unique_application_files"],2)
            self.assertEqual(result["by_city"],{"Brampton":1,"Mississauga":1})
            self.assertEqual(len(result["source_status"]),4)
            self.assertFalse(result["mississauga_custom_licence_reuse_authorized"])
            with (Path(d)/peel.OUTPUT).open(encoding="utf-8-sig") as f:
                self.assertEqual(len(list(csv.DictReader(f))),2)
    def test_blocked_city_keeps_independent_other_source(self):
        def restricted(url):
            if "services3.arcgis.com" in url:raise PermissionError("robots blocked")
            return response(url)
        with tempfile.TemporaryDirectory() as d:
            result=peel.run(d,getter=restricted)
            self.assertEqual(result["by_city"]["Mississauga"],1)
            self.assertEqual(result["by_city"]["Brampton"],0)
            self.assertTrue(all(result["source_status"][k]["status"]=="BLOCKED_OR_FAILED"
                for k in list(peel.SOURCES)[:3]))
    def test_reject_duplicate_ids_and_cross_host_redirect(self):
        def duplicate(url):
            x=response(url)
            if "/query?" in url:
                return {"features":x["features"]*2}
            return x
        with self.assertRaises(ValueError):
            peel.query_lane("Mississauga_Site_Plan",getter=duplicate)
        self.assertFalse(peel.robots_permit("http://not-official.com"))
        with patch.object(peel,"robots_permit",return_value=False):
            with self.assertRaises(PermissionError):
                peel.request_json(peel.MISSISSAUGA+"?f=json")

if __name__=="__main__":
    unittest.main()
