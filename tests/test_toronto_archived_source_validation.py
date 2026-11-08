"""CI regression tests for twenty ACTUAL Nov 7 Toronto archived source IDs.

Fixture comes from previous Radar CSV and contains only public site and permit
identity, date and stage. Live City calls are mocked here; an isolated PR-only
workflow separately performs real City API queries.
"""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import gta_facility_intelligence as graph
import gta_toronto_permit_evidence as permit
import gta_toronto_archived_source_validation as historical


class ArchivedTorontoSourceValidationTests(unittest.TestCase):
    def test_source_fixture_has_20_distinct_original_permit_sites(self):
        records=historical.validate_fixture(historical.FIXTURE)
        self.assertEqual(len(records),20)
        self.assertEqual(len({r["project_id"] for r in records}),20)
        self.assertEqual(len({graph.normalize_address(r["address"])[0]
                              for r in records}),20)
        self.assertIn("Refusal Notice",{r["current_source_status"] for r in records})
        self.assertIn("Permit Issued",{r["current_source_status"] for r in records})
        self.assertTrue(all(len(permit.split_source_keys(r)[0])==1 for r in records))

    @staticmethod
    def mocked_official_api(*,missing_active=None, cleared=True, contradict=None):
        rows=historical.validate_fixture(historical.FIXTURE)
        exact={}
        for item in rows:
            key,number,revision=permit.split_source_keys(item)[0][0]
            street=graph.normalize_address(item["address"])[0]
            pieces=street.split()
            # Official sample row projection. Even synthetic addresses and
            # quoted statuses go through the exact source comparison.
            record={
                "PERMIT_NUM":number,"REVISION_NUM":revision,
                "STREET_NUM":pieces[0],
                "STREET_NAME":" ".join(pieces[1:-1]).upper(),
                "STREET_TYPE":pieces[-1].upper(),
                "STREET_DIRECTION":"",
                "STATUS":item["current_source_status"],
                "APPLICATION_DATE":item["source_record_date"],
            }
            exact[key]=record
        calls=[]
        def fetch(url):
            calls.append(url)
            p=urlsplit(url);args=parse_qs(p.query)
            if p.path.endswith("package_show"):
                slug=args["id"][0]
                if slug==permit.PACKAGE:
                    resource=permit.RESOURCE_HINT
                elif slug==permit.CLEARED_PACKAGE:
                    resource=permit.CLEARED_RESOURCE_HINT
                else:
                    raise AssertionError("Unexpected official source package")
                return {"success":True,"result":{"name":slug,
                    "resources":[{"id":resource,"datastore_active":True}]}}
            if not p.path.endswith("datastore_search"):
                raise AssertionError("Unexpected live request")
            resource=args["resource_id"][0]
            filters=json.loads(args["filters"][0])
            key=filters["PERMIT_NUM"]+"|"+filters["REVISION_NUM"]
            rec=exact.get(key)
            if not rec:
                return {"success":True,"result":{"records":[],"total":0}}
            if resource==permit.RESOURCE_HINT and key==missing_active:
                return {"success":True,"result":{"records":[],"total":0}}
            if resource==permit.CLEARED_RESOURCE_HINT:
                if key!=missing_active or not cleared:
                    return {"success":True,"result":{"records":[],"total":0}}
                rec=dict(rec,STATUS="Closed",COMPLETED_DATE="2026-11-07")
            elif resource!=permit.RESOURCE_HINT:
                raise AssertionError("Wrong resource")
            if contradict==key:
                rec=dict(rec,STREET_NUM="9999")
            return {"success":True,"result":{"records":[rec],"total":1}}
        return fetch,calls

    def test_full_twenty_record_two_batch_acceptance_with_mocked_city(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            fetch,calls=self.mocked_official_api()
            result=historical.run(root,fetch=fetch,check_cleared=True)
            self.assertTrue(result["api_evidence_sample_passed"],result)
            self.assertEqual(len(result["batch_results"]),2)
            self.assertEqual([r["offset"] for r in result["batch_results"]],[0,10])
            self.assertEqual(sum(r["active_exact_query_attempts"] for r in
                                 result["batch_results"]),20)
            self.assertEqual(len(calls),22) # 2 metadata + 20 exact records
            acceptance=result["source_acceptance"]
            self.assertEqual(acceptance["recent_unique_exact_active_source_records"],20)
            self.assertEqual(acceptance["distinct_project_folders"],20)
            self.assertEqual(acceptance["distinct_physical_sites"],20)
            self.assertGreaterEqual(len(acceptance["source_stage_categories"]),2)
            self.assertEqual(acceptance["exact_cleared_historical_records"],0)
            self.assertTrue(acceptance["source_sample_gate_passed"])
            self.assertFalse(result["commercial_production_accepted"])
            self.assertEqual(result["active_open_supplier_contracts_verified"],0)
            self.assertFalse(result["actual_current_buyer_verified"])
            self.assertTrue((root/historical.REPORT_NAME).is_file())
            self.assertEqual(len(list((root/"TORONTO_PERMIT_EVIDENCE_PILOT"/
                    permit.LIVE_BATCH_DIR).glob("*.json"))),2)

    def test_one_missing_active_source_is_historical_not_sale_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            fetch,_=self.mocked_official_api(missing_active="26 263884 BLD|00")
            result=historical.run(root,fetch=fetch,check_cleared=True)
            acceptance=result["source_acceptance"]
            self.assertEqual(acceptance["recent_unique_exact_active_source_records"],19)
            self.assertEqual(acceptance["exact_cleared_historical_records"],1)
            self.assertFalse(result["api_evidence_sample_passed"])
            self.assertEqual(result["active_open_supplier_contracts_verified"],0)

    def test_one_city_address_mismatch_blocks_source_sample_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            fetch,_=self.mocked_official_api(contradict="26 265617 BLD|00")
            result=historical.run(root,fetch=fetch,check_cleared=True)
            acceptance=result["source_acceptance"]
            self.assertLess(acceptance["recent_unique_exact_active_source_records"],20)
            self.assertFalse(result["api_evidence_sample_passed"])
            self.assertEqual(result["active_open_supplier_contracts_verified"],0)

    def test_no_source_network_refuses_fake_success_but_writes_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            def unavailable(_): raise TimeoutError("no source connection")
            result=historical.run(root,fetch=unavailable)
            self.assertFalse(result["api_evidence_sample_passed"])
            self.assertEqual(result["source_acceptance"][
                "recent_unique_exact_active_source_records"],0)
            self.assertTrue((root/historical.REPORT_NAME).is_file())


if __name__=="__main__":
    unittest.main()
