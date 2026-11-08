"""Exact Toronto active-permit record audit: archive-based and mocked live CKAN.

No actual network needed for CI. All tests prevent false current-stage and buyer
claims. Production SQLite is never written, and no collect/scheduler is invoked.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import gta_toronto_permit_evidence as permits


def daily(project="toronto_active_building_permits:26 265617",
          keys="26 265617 HVA|00 | 26 265617 BLD|00 | 26 265617 PLB|00",
          address="220 YONGE ST M5B",status="Pending Parent Folder Review"):
    return {
        "project_id":project,"source_id":permits.SOURCE,"source_keys":keys,
        "address":address,"city":"Toronto","current_source_status":status,
        "observation":"FIRST_OBSERVED","source_record_date":"2026-11-06",
        "record_source_url":"","official_source_portal_url":"https://open.toronto.ca/"
    }


def write_daily(root, rows):
    target=root/permits.DAILY_CSV
    with target.open("w",encoding="utf-8-sig",newline="") as f:
        names=list(daily())
        writer=csv.DictWriter(f,fieldnames=names,extrasaction="ignore")
        writer.writeheader();writer.writerows(rows)
    return target


def payload(permit="26 265617 BLD",rev="00",
            status="Pending Parent Folder Review",street="YONGE"):
    return {"PERMIT_NUM":permit,"REVISION_NUM":rev,
            "STREET_NUM":"220","STREET_NAME":street,
            "STREET_TYPE":"ST","STREET_DIRECTION":"",
            "POSTAL":"M5B","STATUS":status,
            "WORK":"Interior Alterations",
            "DESCRIPTION":"Retail tenant fit-out",
            "APPLICATION_DATE":"2026-10-28"}


def create_db(file, items):
    con=sqlite3.connect(file)
    con.executescript("""
        CREATE TABLE records_current(
            source_id TEXT, record_key TEXT,first_seen_at TEXT,
            source_date TEXT,active INTEGER
        );
        CREATE TABLE record_versions(
            version_id INTEGER PRIMARY KEY, source_id TEXT,
            record_key TEXT,payload_json TEXT
        );
    """)
    for i,(k,raw,active) in enumerate(items,1):
        con.execute("INSERT INTO records_current VALUES (?,?,?,?,?)",
            (permits.SOURCE,k,"2026-11-07T13:00:00Z","2026-11-06",active))
        con.execute("INSERT INTO record_versions VALUES (?,?,?,?)",
            (i,permits.SOURCE,k,json.dumps(raw)))
    con.commit();con.close()


def fake_ckan(url):
    p=urlsplit(url)
    q=parse_qs(p.query)
    if p.path.endswith("package_show"):
        assert q["id"] == [permits.PACKAGE]
        return {"success":True,"result":{
            "name":permits.PACKAGE,
            "resources":[{"id":permits.RESOURCE_HINT,
                          "datastore_active":True,"last_modified":"2026-11-06T10:22:00Z"}]}}
    if p.path.endswith("datastore_search"):
        assert q["resource_id"] == [permits.RESOURCE_HINT]
        filters=json.loads(q["filters"][0])
        assert filters["REVISION_NUM"]=="00"
        rec=payload(permit=filters["PERMIT_NUM"],
                    rev=filters["REVISION_NUM"],status="Permit Issued")
        return {"success":True,"result":{"records":[rec],"total":1}}
    raise AssertionError("Unexpected CKAN operation: "+url)


class TorontoPermitRecordAuditTests(unittest.TestCase):
    def test_actual_three_key_bundle(self):
        keys,reason=permits.split_source_keys(daily())
        self.assertFalse(reason)
        self.assertEqual(len(keys),3)
        self.assertEqual(keys[0],("26 265617 HVA|00","26 265617 HVA","00"))
        self.assertEqual(keys[1],("26 265617 BLD|00","26 265617 BLD","00"))

    def test_case_from_real_archive_single_key_revised(self):
        keys,reason=permits.split_source_keys(daily(
            project="toronto_active_building_permits:26 230833",
            keys="26 230833 HVA|01"))
        self.assertEqual(reason,"")
        self.assertEqual(keys,[("26 230833 HVA|01","26 230833 HVA","01")])

    def test_invalid_or_mixed_source_identifiers_rejected_before_lookup(self):
        examples=[
            ("toronto_active_building_permits:26 265617","26 265617 BLD|00 | 26 265618 HVA|00"),
            ("toronto_active_building_permits:26 265617","26 265617 BLD|00 | 26 265617 BLD|00"),
            ("toronto_active_building_permits:26 265617","26 265617 BLD|0;"),
            ("toronto_active_building_permits:26 265617","26 265617 BLD|00 | 27 265617 HVA|00"),
            ("toronto_active_building_permits:26 265617","26 265617 BLD|00 | https://evil.example"),
        ]
        for project,keys in examples:
            with self.subTest(keys=keys):
                parsed,reason=permits.split_source_keys(daily(project=project,keys=keys))
                self.assertEqual(parsed,[])
                self.assertTrue(reason)

    def test_too_many_constituent_keys_cannot_expand_into_unbounded_requests(self):
        rows=" | ".join(f"26 265617 BLD|{i:02d}" for i in range(13))
        parsed,reason=permits.split_source_keys(daily(keys=rows))
        self.assertEqual(parsed,[])
        self.assertEqual(reason,"TOO_MANY_KEYS_REQUIRE_MANUAL_REVIEW")

    def test_exact_local_sqlite_payload_reconciliation_is_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);db=root/"radar.sqlite"
            create_db(db,[
                ("26 265617 HVA|00",payload(permit="26 265617 HVA"),1),
                ("26 265617 BLD|00",payload(permit="26 265617 BLD"),1),
                ("26 265617 PLB|00",payload(permit="26 265617 PLB"),1),
            ])
            original=db.read_bytes()
            write_daily(root,[daily()])
            before=(root/permits.DAILY_CSV).read_bytes()
            status=permits.run(root,db=db)
            self.assertEqual(status["distinct_original_constituent_keys"],3)
            self.assertEqual(status["local_record_payloads_matched"],3)
            self.assertEqual(status["live_record_queries_attempted"],0)
            self.assertEqual(status["verified_open_contracts"],0)
            self.assertEqual(db.read_bytes(),original)
            self.assertEqual((root/permits.DAILY_CSV).read_bytes(),before)
            with (root/"TORONTO_PERMIT_EVIDENCE_PILOT"/permits.PROJECT_CSV).open(
                    encoding="utf-8-sig",newline="") as f:
                group=next(csv.DictReader(f))
            self.assertEqual(group["local_records_matched"],"3")
            self.assertEqual(group["project_review_status"],
                             "LOCAL_SNAPSHOT_EXACT_KEY_MATCH_UNRECHECKED")
            self.assertEqual(group["verified_open_contract"],"NO")

    def test_local_source_payload_key_conflict_is_not_a_match(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);db=root/"radar.sqlite"
            create_db(db,[("26 265617 BLD|00",payload(permit="26 265617 BLD",rev="01"),1)])
            write_daily(root,[daily(keys="26 265617 BLD|00")])
            status=permits.run(root,db=db)
            self.assertEqual(status["local_record_payloads_matched"],0)
            with (root/"TORONTO_PERMIT_EVIDENCE_PILOT"/permits.AUDIT_CSV).open(
                    encoding="utf-8-sig",newline="") as f:
                row=next(csv.DictReader(f))
            self.assertEqual(row["local_snapshot_status"],"LOCAL_KEY_PAYLOAD_MISMATCH")
            self.assertEqual(row["final_evidence_level"],"UNVERIFIED_SOURCE_RECORD_ID")

    def test_source_address_conflict_blocks_exact_snapshot_match(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);db=root/"radar.sqlite"
            create_db(db,[("26 265617 BLD|00",payload(street="BAY"),1)])
            write_daily(root,[daily(keys="26 265617 BLD|00")])
            status=permits.run(root,db=db)
            self.assertEqual(status["local_record_payloads_matched"],0)
            with (root/"TORONTO_PERMIT_EVIDENCE_PILOT"/permits.AUDIT_CSV).open(
                    encoding="utf-8-sig",newline="") as f:
                row=next(csv.DictReader(f))
            self.assertEqual(row["local_snapshot_status"],"LOCAL_RECORD_ADDRESS_CONFLICT")
            self.assertEqual(row["local_address_comparison"],"SOURCE_ADDRESS_CONFLICT")

    def test_multiple_constituent_statuses_do_not_promote_one_group_stage(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);db=root/"radar.sqlite"
            create_db(db,[
                ("26 265617 HVA|00",payload(permit="26 265617 HVA",status="Under Review"),1),
                ("26 265617 BLD|00",payload(permit="26 265617 BLD",status="Refusal Notice"),1),
            ])
            write_daily(root,[daily(keys="26 265617 HVA|00 | 26 265617 BLD|00")])
            status=permits.run(root,db=db)
            with (root/"TORONTO_PERMIT_EVIDENCE_PILOT"/permits.PROJECT_CSV).open(
                    encoding="utf-8-sig",newline="") as f:
                row=next(csv.DictReader(f))
            self.assertEqual(row["local_record_stage_count"],"2")
            self.assertEqual(row["project_review_status"],
                             "LOCAL_SNAPSHOT_MULTIPLE_DISTINCT_PERMIT_STAGES")
            self.assertIn("Refusal Notice",row["local_statuses"])
            self.assertEqual(status["verified_open_contracts"],0)

    def test_inactive_local_record_must_not_look_active(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);db=root/"radar.sqlite"
            create_db(db,[("26 265617 BLD|00",payload(),0)])
            write_daily(root,[daily(keys="26 265617 BLD|00")])
            permits.run(root,db=db)
            with (root/"TORONTO_PERMIT_EVIDENCE_PILOT"/permits.AUDIT_CSV).open(
                    encoding="utf-8-sig",newline="") as f:
                row=next(csv.DictReader(f))
            self.assertEqual(row["local_snapshot_status"],"LOCAL_RECORD_INACTIVE_HISTORY")

    def test_no_local_sqlite_is_explicit_missing_evidence_not_bad_database(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);write_daily(root,[daily()])
            def no_network(_):raise AssertionError("Unexpected live network call")
            result=permits.run(root,fetch=no_network)
            self.assertEqual(result["local_snapshot_state"],"NO_LOCAL_SQLITE_PROVIDED")
            self.assertEqual(result["local_record_payloads_matched"],0)
            self.assertEqual(result["live_record_queries_attempted"],0)
            self.assertEqual(result["verified_buyers"],0)

    def test_network_opt_in_filters_exact_permit_num_and_revision(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);write_daily(root,[daily(keys="26 265617 BLD|00")])
            calls=[]
            def fetch(url):
                calls.append(url)
                return fake_ckan(url)
            status=permits.run(root,live=True,live_limit=1,fetch=fetch,
                               as_of=__import__("datetime").datetime(2026,11,8))
            self.assertEqual(len(calls),2)
            self.assertEqual(status["live_exact_record_payloads_received"],1)
            self.assertEqual(status["metadata_resource_id"],permits.RESOURCE_HINT)
            self.assertEqual(status["verified_open_contracts"],0)
            with (root/"TORONTO_PERMIT_EVIDENCE_PILOT"/permits.AUDIT_CSV).open(
                    encoding="utf-8-sig",newline="") as f:
                row=next(csv.DictReader(f))
            self.assertEqual(row["individual_record_retrieved_live"],"YES")
            self.assertEqual(row["remote_record_status"],"Permit Issued")
            self.assertEqual(row["remote_status"],"LIVE_EXACT_KEY_MATCH_OFFICIAL_DATASET")
            self.assertIn("CKAN_ROW_DOES_NOT_PROVE_BUYER_OR_OPEN_CONTRACT",
                          row["review_blockers"])
            self.assertEqual(row["buyer_verified"],"NO")

    def test_unexpected_resource_id_fails_without_falling_back_to_wrong_dataset(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);write_daily(root,[daily(keys="26 265617 BLD|00")])
            def wrong(url):
                if "/package_show?" in url:
                    return {"success":True,"result":{
                        "name":permits.PACKAGE,
                        "resources":[{"id":"other-resource-id","datastore_active":True}]}}
                raise AssertionError("Should not query another dataset")
            result=permits.run(root,live=True,live_limit=1,fetch=wrong)
            self.assertIn("RESOURCE_LOOKUP_UNAVAILABLE",result["live_status"])
            self.assertEqual(result["live_exact_record_payloads_received"],0)
            self.assertEqual(result["verified_open_contracts"],0)

    def test_not_present_active_dataset_does_not_mean_closed_or_cancelled(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);write_daily(root,[daily(keys="26 265617 BLD|00")])
            def no_record(url):
                if "/package_show?" in url:
                    return fake_ckan(url)
                return {"success":True,"result":{"records":[],"total":0}}
            result=permits.run(root,live=True,live_limit=1,fetch=no_record)
            with (root/"TORONTO_PERMIT_EVIDENCE_PILOT"/permits.AUDIT_CSV).open(
                    encoding="utf-8-sig",newline="") as f:
                row=next(csv.DictReader(f))
            self.assertEqual(row["remote_status"],
                             "NOT_PRESENT_IN_ACTIVE_DATASTORE_NOT_PROOF_OF_CLOSURE")
            self.assertEqual(row["final_evidence_level"],
                             "LIVE_RECORD_MISSING_OR_AMBIGUOUS_MANUAL_REVIEW")
            self.assertEqual(result["verified_open_contracts"],0)

    def test_live_limit_cannot_exceed_bounded_ten(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);write_daily(root,[daily()])
            with self.assertRaisesRegex(ValueError,"0..10"):
                permits.run(root,live=True,live_limit=100)

    def test_bad_sqlite_does_not_count_as_verified_local_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);write_daily(root,[daily()])
            db=root/"invalid.sqlite";db.write_bytes(b"not sqlite")
            result=permits.run(root,db=db)
            self.assertTrue(result["local_snapshot_state"].startswith("LOCAL_SQLITE_UNAVAILABLE"))
            self.assertEqual(result["local_record_payloads_matched"],0)

    def test_local_source_missing_address_cannot_prove_same_project_site(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);db=root/"radar.sqlite"
            missing=payload()
            missing["STREET_NUM"]=""
            missing["STREET_NAME"]=""
            create_db(db,[("26 265617 BLD|00",missing,1)])
            write_daily(root,[daily(keys="26 265617 BLD|00")])
            summary=permits.run(root,db=db)
            self.assertEqual(summary["local_record_payloads_matched"],0)
            with (root/"TORONTO_PERMIT_EVIDENCE_PILOT"/permits.AUDIT_CSV).open(
                    encoding="utf-8-sig",newline="") as f:
                row=next(csv.DictReader(f))
            self.assertEqual(row["local_snapshot_status"],
                             "LOCAL_RECORD_ADDRESS_MISSING_REVIEW")

    def test_live_city_record_address_conflict_is_flagged(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);write_daily(root,[daily(keys="26 265617 BLD|00")])
            def fetched(url):
                data=fake_ckan(url)
                if "datastore_search" in url:
                    data["result"]["records"][0]["STREET_NAME"]="BAY"
                return data
            out=permits.run(root,live=True,live_limit=1,fetch=fetched)
            self.assertEqual(out["live_record_queries_attempted"],1)
            with (root/"TORONTO_PERMIT_EVIDENCE_PILOT"/permits.AUDIT_CSV).open(
                    encoding="utf-8-sig",newline="") as f:
                row=next(csv.DictReader(f))
            self.assertEqual(row["final_evidence_level"],"REVIEW_SOURCE_ADDRESS_CONFLICT")
            self.assertEqual(row["remote_address_comparison"],
                             "LIVE_ADDRESS_CONTRADICTS_ARCHIVED_SOURCE")
            self.assertEqual(row["buyer_verified"],"NO")

    def test_failed_live_circuit_counts_attempt_and_no_verified_result(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);write_daily(root,[daily(keys="26 265617 BLD|00")])
            def flaky(url):
                if "datastore_search" in url:
                    raise TimeoutError("Source unavailable")
                return fake_ckan(url)
            out=permits.run(root,live=True,live_limit=1,fetch=flaky)
            self.assertEqual(out["live_record_queries_attempted"],1)
            self.assertEqual(out["live_queries_failed"],1)
            self.assertEqual(out["live_exact_record_payloads_received"],0)
            self.assertEqual(out["verified_open_contracts"],0)

    def test_missing_daily_file_is_error_not_zero_opportunities(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                permits.run(Path(folder))

    def test_real_bundle_count_cannot_be_confused_with_three_projects(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);write_daily(root,[daily(),daily(
                project="toronto_active_building_permits:26 265928",
                keys="26 265928 BLD|00",
                address="673 YONGE ST M4Y",status="Application Acceptable")])
            out=permits.run(root)
            self.assertEqual(out["toronto_project_groups"],2)
            self.assertEqual(out["distinct_original_constituent_keys"],4)
            self.assertEqual(out["valid_toronto_permit_groups"],2)
            self.assertEqual(out["verified_buyers"],0)

if __name__=="__main__":
    unittest.main()
