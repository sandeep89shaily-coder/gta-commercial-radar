"""Acceptance regression tests: original City record proof != commercial lead."""
from __future__ import annotations
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode

import gta_toronto_permit_evidence as permits
import gta_toronto_permit_acceptance as gate

AS_OF=dt.datetime(2026,11,8,15,0,tzinfo=dt.timezone.utc)


def row(n, *, project=None, status="Permit Issued",
        address="220 yonge st", quality="OFFICIAL_CKAN_EXACT_KEY_LIVE_RECHECKED",
        query=None):
    folder=f"26 {200000+n:06d}"
    permit=folder+" BLD"
    project=project or permits.SOURCE+":"+folder
    filters=json.dumps({"PERMIT_NUM":permit,"REVISION_NUM":"00"},
                       separators=(",",":"))
    query=query or permits.API+"datastore_search?"+urlencode({
        "resource_id":permits.RESOURCE_HINT,"filters":filters,"limit":3
    })
    return {
        "project_id":project,"source_key":permit+"|00",
        "permit_num":permit,"revision_num":"00",
        "individual_record_retrieved_live":"YES",
        "remote_status":"LIVE_EXACT_KEY_MATCH_OFFICIAL_DATASET",
        "remote_query_url":query,
        "final_evidence_level":quality,
        "remote_record_status":status,
        "remote_record_address":address,
        "remote_address_comparison":"ADDRESS_COMPATIBLE_WITH_AVAILABLE_SNAPSHOTS",
        "buyer_verified":"NO",
        "record_is_a_verified_open_supplier_contract":"NO",
    }


def batch(folder,rows,*,suffix="A",stamp=None,resource=None):
    folder.mkdir(parents=True,exist_ok=True)
    payload={
        "mode":"BOUNDED_EXPLICIT_PUBLIC_TORONTO_CKAN_QUERIES",
        "retrieved_at_utc":(stamp or AS_OF).isoformat(),
        "resource_id":resource or permits.RESOURCE_HINT,
        "source_dataset":permits.OFFICIAL_DATASET,
        "offset":0,"requested_limit":10,
        "attempted_records":len(rows),
        "records_with_exact_live_key":sum(
            x.get("individual_record_retrieved_live")=="YES" for x in rows),
        "commercial_buyer_verified":False,
        "open_supplier_contracts_verified":0,
        "audit_records":rows
    }
    path=folder/("TORONTO_CKAN_EXACT_CHECK_"+suffix+"_OFFSET_0.json")
    path.write_text(json.dumps(payload,indent=2),encoding="utf-8")
    return path


class TorontoSourceAcceptanceTests(unittest.TestCase):
    def test_no_batches_is_not_success(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);s=gate.run(p/"unmade",p/"report",as_of=AS_OF)
            self.assertEqual(s["batch_files_seen"],0)
            self.assertFalse(s["official_source_sample_gate_passed"])
            self.assertFalse(s["commercial_production_accepted"])
            self.assertFalse(s["user_outreach_authorized"])
            self.assertEqual(s["recent_unique_exact_ckan_source_records"],0)

    def test_two_manual_batches_reach_source_sample_only_not_customer_acceptance(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);b=p/"batches"
            batch(b,[row(i,status="Permit Issued") for i in range(10)],suffix="A")
            batch(b,[row(i,status="Inspection") for i in range(10,20)],suffix="B")
            s=gate.run(b,p/"report",as_of=AS_OF)
            self.assertEqual(s["recent_unique_exact_ckan_source_records"],20)
            self.assertEqual(s["distinct_project_folders_rechecked"],20)
            self.assertTrue(s["official_source_sample_gate_passed"])
            self.assertEqual(s["source_stage_buckets_covered"],["INSPECTION","ISSUED"])
            self.assertFalse(s["commercial_production_accepted"])
            self.assertFalse(s["buyer_and_open_procurement_verified"])
            self.assertFalse(s["field_human_reviewer_approved"])
            with (p/"report"/gate.OUTPUT_CSV).open(
                    encoding="utf-8-sig",newline="") as f:
                records=list(csv.DictReader(f))
            self.assertEqual(len(records),20)
            self.assertTrue(all(r["buyer_verified"]=="NO" for r in records))
            self.assertTrue(all(r["open_supplier_contract_verified"]=="NO"
                                for r in records))

    def test_duplicate_live_sample_does_not_count_twice(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);b=p/"batches"
            first=[row(i) for i in range(10)]
            batch(b,first,suffix="A")
            batch(b,first,suffix="B")
            s=gate.run(b,p/"out",as_of=AS_OF)
            self.assertEqual(s["recent_unique_exact_ckan_source_records"],10)
            self.assertFalse(s["official_source_sample_gate_passed"])

    def test_twenty_records_from_same_site_or_project_do_not_pass_independence(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);b=p/"batches"
            # Same project ID is invalid unless each key is genuinely in the
            # source ID's folder; tampered labels are therefore rejected.
            rows=[row(i,project=permits.SOURCE+":26 200000") for i in range(10)]
            batch(b,rows,suffix="A")
            s=gate.run(b,p/"out",as_of=AS_OF)
            self.assertLess(s["recent_unique_exact_ckan_source_records"],10)
            self.assertIn("SOURCE_PROJECT_FOLDER_CONFLICT",
                          s["rejected_or_unproven_counts"])

    def test_all_one_stage_does_not_pass_source_diversity(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);b=p/"batches"
            batch(b,[row(i) for i in range(10)],suffix="A")
            batch(b,[row(i) for i in range(10,20)],suffix="B")
            s=gate.run(b,p/"out",as_of=AS_OF)
            self.assertEqual(s["recent_unique_exact_ckan_source_records"],20)
            self.assertFalse(s["official_source_sample_gate_passed"])

    def test_malicious_query_host_or_mismatched_id_rejected(self):
        valid=row(1)
        self.assertEqual(gate._classify(valid),
                         "EXACT_OFFICIAL_SOURCE_ROW_WITH_ARCHIVED_ADDRESS_COMPATIBLE")
        for url in ("http://ckan0.cf.opendata.inter.prod-toronto.ca/query",
                    "https://evil.example/api/3/action/datastore_search",
                    "https://admin@ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search",
                    permits.API+"datastore_search?resource_id=other&filters={}",
                    permits.API+"datastore_search?resource_id=other&filters="+
                        urlencode({"bad":"wrong"})):
            with self.subTest(url=url):
                altered=dict(valid,remote_query_url=url)
                self.assertEqual(gate._classify(altered),
                                 "REMOTE_QUERY_PROVENANCE_INVALID")

    def test_missing_remote_status_address_or_conflict_rejected(self):
        for data,reason in [
            ({"remote_record_status":""},"REMOTE_STATUS_OR_ADDRESS_MISSING"),
            ({"remote_record_address":""},"REMOTE_STATUS_OR_ADDRESS_MISSING"),
            ({"final_evidence_level":"REVIEW_SOURCE_ADDRESS_CONFLICT"},
             "LIVE_RECORD_STAGE_OR_ADDRESS_NOT_VERIFIED"),
            ({"remote_address_comparison":"LIVE_ADDRESS_CONTRADICTS_ARCHIVED_SOURCE"},
             "ADDRESS_NOT_COMPATIBLE_WITH_ARCHIVE"),
            ({"individual_record_retrieved_live":"NO"},"NOT_ACTUALLY_RETRIEVED"),
        ]:
            with self.subTest(data=data):
                self.assertEqual(gate._classify(dict(row(1),**data)),reason)

    def test_buying_authority_inferred_from_permit_is_rejected(self):
        self.assertEqual(gate._classify(dict(row(1),buyer_verified="YES")),
                         "UNEXPECTED_BUYER_VERIFICATION_CLAIM")
        self.assertEqual(gate._classify(dict(row(1),
            record_is_a_verified_open_supplier_contract="YES")),
            "UNEXPECTED_OPEN_CONTRACT_CLAIM")

    def test_stale_evidence_batch_not_counted_as_recent(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);b=p/"batches"
            batch(b,[row(i) for i in range(10)],suffix="A",
                  stamp=AS_OF-dt.timedelta(days=30))
            status=gate.run(b,p/"report",as_of=AS_OF)
            self.assertEqual(status["recent_unique_exact_ckan_source_records"],0)
            self.assertIn("OUTSIDE_RECENT_VERIFICATION_WINDOW",
                          status["rejected_or_unproven_counts"])

    def test_unauthorized_resource_or_corrupt_batch_not_promoted(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);b=p/"batches"
            batch(b,[row(i) for i in range(10)],suffix="A",resource="wrong")
            (b/"TORONTO_CKAN_EXACT_CHECK_X_OFFSET_0.json").write_text("{bad json",
                                                                    encoding="utf-8")
            status=gate.run(b,p/"report",as_of=AS_OF)
            self.assertEqual(status["recent_unique_exact_ckan_source_records"],0)
            self.assertEqual(status["batch_files_rejected_or_unreadable"],2)
            self.assertFalse(status["official_source_sample_gate_passed"])

    def test_unbounded_batch_payload_not_accepted(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);b=p/"batches"
            batch(b,[row(i) for i in range(11)],suffix="A")
            s=gate.run(b,p/"report",as_of=AS_OF)
            self.assertEqual(s["batch_files_rejected_or_unreadable"],1)
            self.assertFalse(s["commercial_production_accepted"])

    def test_naive_as_of_rejected_no_ambiguous_freshness(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError,"timezone"):
                gate.run(Path(root)/"batches",Path(root)/"report",
                         as_of="2026-11-08T10:00:00")

if __name__=="__main__":
    unittest.main()
