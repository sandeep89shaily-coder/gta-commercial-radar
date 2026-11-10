"""Read-only municipal expansion tests, no network and no false coverage."""
from __future__ import annotations

import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

import gta_four_city_expansion_gate as gate
import gta_ggh_early_planning as ggh


class FourCityExpansionGateTests(unittest.TestCase):
    def test_only_existing_three_are_configured_and_ajax_is_held(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            original={
                "source_status":[
                    {"city":"Pickering","state":"NO_APPLICATION_ID_ROWS","application_id_rows":0},
                    {"city":"Niagara Falls","state":"COLLECTED","application_id_rows":57,
                     "new_or_changed":2,"commercial_text_matches":12},
                    {"city":"Barrie","state":"BASELINE_COMPLETE","application_id_rows":24},
                ]
            }
            status=root/gate.GGH_STATUS
            status.write_text(json.dumps(original),encoding="utf-8")
            before=status.read_bytes()
            report=gate.build(root,today=dt.date(2026,11,10))
            self.assertEqual(report["cities_requested"],4)
            self.assertEqual(report["cities_already_configured_in_experimental_ggh_source_list"],3)
            self.assertEqual(report["new_live_collectors_enabled"],0)
            self.assertEqual(report["verified_fresh_commercial_leads"],0)
            self.assertEqual(report["cities_verified_citywide_complete"],0)
            self.assertEqual(status.read_bytes(),before)
            by={x["city"]:x for x in report["municipalities"]}
            self.assertEqual(by["Niagara Falls"]["file_id_candidate_rows_not_unique_leads"],57)
            self.assertEqual(by["Barrie"]["pilot_acceptance"],
                             "APPLICATION_IDS_EXTRACTED_MANUAL_REVIEW_REQUIRED")
            self.assertEqual(by["Pickering"]["pilot_acceptance"],
                             "NO_VERIFIED_APPLICATION_ID_COVERAGE")
            self.assertEqual(by["Ajax"]["pilot_acceptance"],
                             "SOURCE_RESEARCH_ONLY_NOT_ENABLED")
            self.assertEqual(by["Ajax"]["registered_in_existing_ggh_pilot"],"NO")
            self.assertEqual(by["Ajax"]["automated_source_recovered"],"NO")
            with (root/gate.OUTPUT).open(encoding="utf-8-sig",newline="") as fp:
                records=list(csv.DictReader(fp))
            self.assertEqual(len(records),4)
            self.assertTrue(all(x["verified_citywide_coverage"]=="NO" for x in records))

    def test_absent_or_invalid_status_never_promotes_any_city(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for contents in (None, "{", json.dumps({"source_status":{"bad":1}}),
                             json.dumps({"source_status":[{"city":"Barrie"},
                                  {"city":"Barrie","application_id_rows":100}]})):
                with self.subTest(contents=contents):
                    p=root/gate.GGH_STATUS
                    if contents is None:p.unlink(missing_ok=True)
                    else:p.write_text(contents,encoding="utf-8")
                    report=gate.build(root)
                    self.assertEqual(report["new_live_collectors_enabled"],0)
                    self.assertNotEqual(report["source_status_basis"],
                                        "PREVIOUSLY_EXPORTED_UNVERIFIED_SOURCE_STATUS")
                    self.assertEqual(report["verified_fresh_commercial_leads"],0)

    def test_blocked_arcgis_not_counted_from_impossible_row_count(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/gate.GGH_STATUS).write_text(json.dumps({"source_status":[
                {"city":"Barrie","state":"FAILED","application_id_rows":900,
                 "error":"ROBOTS_DENIED:policy"}
            ]}),encoding="utf-8")
            report=gate.build(root)
            barrie=next(x for x in report["municipalities"] if x["city"]=="Barrie")
            self.assertEqual(barrie["pilot_acceptance"],"SOURCE_BLOCKED_OR_FAILED")
            self.assertEqual(report["verified_fresh_commercial_leads"],0)

    def test_barrie_mock_gis_pagination_no_network_and_first_run_baseline(self):
        source=ggh.SOURCES["Barrie"]
        attrs={
            "OBJECTID":11,"FILENO":"SP-2026-011","LOCATION":"300 Test Road",
            "STATUS":"Under Review", "DESCRIPT":"New industrial warehouse",
            "NAME":"Warehouse Project", "TYPE":"Site Plan", "APPLICANT":"Example Ltd",
            "OWNER":"Owner Ltd",
        }
        seen=[]
        def json_fetch(url,params):
            seen.append((url,dict(params)))
            if url==source:
                return {"fields":[{"name":x} for x in attrs],
                        "objectIdField":"OBJECTID"}
            if url==source+"/query":
                self.assertEqual(params["where"],"1=1")
                self.assertEqual(params["orderByFields"],"OBJECTID ASC")
                return {"features":[{"attributes":attrs}]}
            raise AssertionError("Unexpected network call")
        def no_html(url):
            raise AssertionError("Barrie GIS must not fetch HTML")
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            first=ggh.run(root,today=dt.date(2026,11,10),
                sources={"Barrie":source},fetcher=no_html,gis_fetcher=json_fetch)
            self.assertEqual(first["application_id_rows"],1)
            self.assertEqual(first["new_or_changed"],0)
            self.assertEqual(first["citywide_coverage_verified"],0)
            self.assertEqual(first["verified_fresh_commercial_leads"],0)
            second=ggh.run(root,today=dt.date(2026,11,11),
                sources={"Barrie":source},fetcher=no_html,gis_fetcher=json_fetch)
            self.assertEqual(second["new_or_changed"],0)
            with (root/ggh.ALL).open(encoding="utf-8-sig",newline="") as fp:
                row=next(csv.DictReader(fp))
            self.assertEqual(row["application_id"],"SP-2026-011")
            self.assertEqual(row["observation"],"UNCHANGED")
            self.assertEqual(row["source_date"],"")
            self.assertGreater(len(seen),2)

    def test_barrie_policy_failure_does_not_fake_first_observed(self):
        source=ggh.SOURCES["Barrie"]
        def blocked(url,params):
            raise PermissionError("ROBOTS_ACCESS_DENIED")
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            result=ggh.run(root,today=dt.date(2026,11,10),
                sources={"Barrie":source},gis_fetcher=blocked)
            self.assertEqual(result["application_id_rows"],0)
            self.assertEqual(result["new_or_changed"],0)
            self.assertEqual(result["source_status"][0]["state"],"FAILED")
            self.assertIn("ROBOTS_ACCESS_DENIED",result["source_status"][0]["error"])
            self.assertEqual(result["citywide_coverage_verified"],0)


if __name__=="__main__":
    unittest.main()
