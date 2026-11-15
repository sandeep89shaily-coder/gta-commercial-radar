"""Offline tests for fresh official, same-address and superseded-scope checks."""
import datetime as dt
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from urllib.error import HTTPError

import v5_investigator as v5
from gta_top10_live_source_recheck import (
    _identity, _identity_pattern, check_one,
)
from gta_ai_top10_reranker import _validate, run as run_reranker
from gta_commercial_qualification_review import (
    build, CLIENT,
)
import csv

TODAY = dt.date(2026,11,14)


def row(app="25249692ESC21CD", *, source_url=None):
    return {
        "record_id":"client:"+app,
        "origin":"CLIENT","city":"Toronto",
        "address":"1430 Birchmount Road, Toronto, ON",
        "application_id":app, "project_description":"Industrial condo units",
        "source_date":"2026-11-12", "date_basis":"OFFICIAL_APPLICATION_DATE",
        "radar_first_seen_local":"2026-11-14",
        "source_stage":"Under Review","sector":"INDUSTRIAL_EQUIPMENT_WAREHOUSE",
        "source_url": source_url or "https://www.toronto.ca/planning/current-development/",
        "was_previously_reported":False,
        "exact_project_roles":[],"ai_conflicts":[],
    }


class LiveTopTenProjectCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.db=v5._ledger(self.root/"v5_ai_budget.sqlite")
        self.addCleanup(self.db.close)

    def test_whitespace_variation_in_exact_application_key(self):
        self.assertIsNotNone(_identity_pattern("25249692ESC21CD").search(
            "Application 25 249692 ESC21CD was received."))
        identity,quote=_identity(
            "Application 25 249692 ESC21CD was received.", row())
        self.assertEqual(identity,"EXACT_APPLICATION_ID_IN_FETCHED_TEXT")
        self.assertIn("25 249692",quote)

    def test_different_application_same_address_is_context_not_original_file(self):
        identity,excerpt=_identity(
            "At 1430 Birchmount Road the new unrelated 26 999999 application "
            "describes a different 2026 construction project.", row())
        self.assertEqual(identity,"SAME_ADDRESS_PROJECT_CONTEXT_NOT_LINKED")
        self.assertIn("1430 birchmount",excerpt)

    def test_live_search_fetch_exact_id_with_source_checkpoint_reuse(self):
        calls=[]
        def api(path,payload):
            calls.append(path)
            if path=="/v1/tools/search":
                return {"results":[{
                    "url":"https://www.toronto.ca/council/approved-planning-record",
                    "snippet":"The 25 249692 ESC21CD planning application status "
                              "has been updated by the City.",
                }]}
            if path=="/v1/tools/fetch":
                return {"content":
                    "Toronto official planning summary: 25 249692 ESC21CD "
                    "Application under review. Site plan currently approved "
                    "subject to conditions. This does not confirm construction."}
            self.fail("Unexpected API route")
        result,reused=check_one(
            self.root,row(),"testkey",self.db,TODAY,0,transport=api)
        self.assertFalse(reused)
        self.assertTrue(result["complete"])
        self.assertEqual(len(result["sources"]),1)
        self.assertEqual(result["sources"][0]["identity"],
                         "EXACT_APPLICATION_ID_IN_FETCHED_TEXT")
        self.assertEqual(result["sources"][0]["retrieved_on"],"2026-11-14")
        self.assertTrue(result["sources"][0]["date_is_fetch_day_not_publication"])
        self.assertGreater(len(calls),1)
        again,cached=check_one(
            self.root,row(),"testkey",self.db,TODAY,0,
            transport=lambda *_:self.fail("Repeated input cannot incur a call"))
        self.assertTrue(cached)
        self.assertEqual(result,again)

    def test_same_address_newer_scheme_flagged_not_merged_as_original(self):
        def api(path,payload):
            if path=="/v1/tools/search":
                return {"results":[{"url":"https://developer.example/new-project",
                                    "snippet":"New development at 1430 Birchmount Road "
                                              "describes a mixed-use 2026 tower"}]}
            if path=="/v1/tools/fetch":
                return {"content":"At 1430 Birchmount Road a different mixed-use "
                                  "development proposal received a new application "
                                  "in 2026. The old industrial file isn't mentioned."}
            self.fail(path)
        result,_=check_one(self.root,row(),"testkey",self.db,TODAY,0,transport=api)
        self.assertTrue(result["has_unlinked_address_context"])
        self.assertFalse(result["has_exact_current_application"])
        self.assertEqual(result["sources"][0]["authority"],
                         "NONOFFICIAL_PROJECT_CONTEXT")
        self.assertFalse(result["buyer_verified"])

    def test_arcgis_exact_current_status_differs_from_saved_without_auto_merging(self):
        url=("https://gis.toronto.ca/arcgis/rest/services/Planning/"
             "FeatureServer/0/query?where=APPLICATION_NUMBER%3D"
             "%2725249692ESC21CD%27&f=json")
        record=row(source_url=url)
        def arcgis_reply(_url):
            return {"features":[{"attributes":{
                "APPLICATION_NUMBER":"25249692ESC21CD",
                "STATUS_DESC":"Approved",
                "FULL_ADDRESS":"1430 Birchmount Road",
                "LATEST_MILESTONE":"Zoning approval",
            }}]}
        def provider(path,payload):
            if path=="/v1/tools/search":
                return {"results":[]}
            self.fail("DeepSeek fetch should not be required for exact GIS")
        result,_=check_one(self.root,record,"testkey",self.db,TODAY,0,
                           transport=provider,arcgis_transport=arcgis_reply)
        self.assertEqual(result["official_current_status_literal"],"Approved")
        self.assertEqual(result["official_status_change_review"]["saved_stage"],"Under Review")
        self.assertTrue(result["has_exact_current_application"])
        self.assertEqual(result["sources"][0]["authority"],
                         "OFFICIAL_ARCGIS_EXACT_ID")
        self.assertFalse(result["procurement_available_verified"])

    def test_bad_model_citation_to_unrelated_page_is_rejected(self):
        item=row()
        checks={("toronto",item["record_id"]):{
            "sources":[{"url":"https://city.toronto.ca/page",
                        "identity":"EXACT_APPLICATION_ID_IN_FETCHED_TEXT",
                        "excerpt":"25249692ESC21CD remains under review",
                        "retrieved_on":"2026-11-14"}]}}
        output={"choices":[{"finish_reason":"stop",
                            "message":{"content":json.dumps({"reviews":[{
                                "i":0,"decision":"DEPRIORITIZE",
                                "reason":"Complete construction announced",
                                "investigate":"Check city record",
                                "evidence_j":0,
                                "evidence_quote":"building completed in 2026"
                            }]})}}]}
        with self.assertRaisesRegex(ValueError,"LIVE_CITATION_NOT_IN"):
            _validate(output,1,[item],checks)

    def test_http_402_releases_reservation_and_stops_recheck(self):
        def reject(path,payload):
            raise HTTPError("https://api.deepseek.com/v1/tools/search",
                            402,"Payment Required",None,None)
        with self.assertRaises(Exception) as result:
            check_one(self.root,row(),"testkey",self.db,TODAY,0,transport=reject)
        self.assertEqual(type(result.exception).__name__,"DeepSeekAccountBalanceError")
        with closing(sqlite3.connect(self.root/"v5_ai_budget.sqlite")) as db:
            statuses=db.execute(
                "SELECT status,reserved,actual FROM spends").fetchall()
        self.assertEqual(statuses,[("NONBILLABLE",0.0,0.0)])

    def test_failed_or_missing_search_is_not_promotion_to_current(self):
        def api(path,payload):
            return {"results":[]} if path=="/v1/tools/search" else {"content":""}
        result,_=check_one(self.root,row(),"testkey",self.db,TODAY,0,transport=api)
        self.assertTrue(result["complete"])
        self.assertEqual(result["sources"],[])
        self.assertFalse(result["has_exact_current_application"])


if __name__=="__main__":
    unittest.main()
