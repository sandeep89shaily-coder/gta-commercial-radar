"""Offline regression tests for actual zipped Radar results reconciliation."""
import csv
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import gta_pilot_archive_reconciliation as a


def make_csv(rows):
    output = io.StringIO()
    if rows:
        writer=csv.DictWriter(output,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return output.getvalue()

def make_zip(path,activation,industrial,*,burl_status="SOURCE_ACCESS_OR_PARSE_BLOCKED"):
    with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED) as out:
        out.writestr(a.ROOT+a.ACTIVATION,make_csv(activation))
        out.writestr(a.ROOT+a.INDUSTRIAL,make_csv(industrial))
        out.writestr(a.ROOT+a.BURLINGTON,json.dumps({"source_status":[
            {"city":"Burlington","status":burl_status,
             "application_id_rows_this_stage":11 if burl_status=="OFFICIAL_PAGE_COLLECTION" else 0}]}))
        out.writestr(a.ROOT+a.LEDGER,json.dumps({"schema":1,"seen":{
            "OFFICIAL_PAGE:BURLINGTON:505-11/26":{
                "digest":"sha","first_seen_local":"2026-11-06"}}}))

def candidate(source,key,hash,*,stage="LICENCE_ISSUED_NOT_OPENING_CONFIRMED"):
    return {"source_id":source,"source_record_key":key,"source_record_sha256":hash,
        "municipality":"Toronto" if source.startswith("toronto") else "Brampton",
        "site_address":"100 King Street","site_unit":"101",
        "source_event_date":"2026-11-10","activation_stage":stage,
        "source_dataset_url":"https://open.toronto.ca/dataset/example/"}

def equipment(no,signal,kind):
    return {"ero_number":no,"signal_id":signal,"equipment":kind,"action":"INSTALLATION",
        "notice_stage":"Proposal","source_text_sha256":"sourcehash",
        "official_notice_url":"https://ero.ontario.ca/notice/"+no}

class ArchiveReconciliationTests(unittest.TestCase):
    def test_same_records_stable_later_licences_are_not_publication_proof(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td);old=t/"old.zip";new=t/"new.zip"
            records=[
                candidate("toronto_active_building_permits","p1","hash1",
                          stage="FITOUT_PERMIT_ISSUED_NOT_OPENING_CONFIRMED"),
                candidate("brampton_building_permits","b1","hash2"),
            ]
            new_rows=records+[candidate("toronto_business_licences","l1","hash3")]
            make_zip(old,records,[equipment("026-1152","s1","Dust collection")])
            make_zip(new,new_rows,[
                equipment("026-1152","s1","Dust collection"),
                equipment("026-1021","s2","Boiler"),
                equipment("026-1021","s3","Cooling tower")])
            report=a.compare(old,new,t/"out")
            self.assertEqual(report["common_exact_source_keys"],2)
            self.assertEqual(report["stable_saved_source_hash_and_stage_rows"],2)
            self.assertEqual(report["added_records_in_later_archive_not_new_publications"],1)
            self.assertEqual(report["modified_saved_source_hash_or_stage_rows"],0)
            self.assertEqual(report["industrial_distinct_ero_notice_count"],2)
            self.assertEqual(report["burlington_stored_ledger_ids_in_both"],1)
            self.assertFalse(report["burlington_prior_live_collected"])
            self.assertFalse(report["burlington_current_live_collected"])
            self.assertEqual(report["actual_openings_verified"],0)
            with (t/"out"/a.SAMPLE).open(encoding="utf-8-sig",newline="") as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),3)
            added=next(x for x in rows if x["source_record_key"]=="l1")
            self.assertEqual(added["archive_comparison"],
                             "FIRST_PRESENT_IN_LATER_ARCHIVE_NOT_NEW_PUBLICATION")
            self.assertEqual(added["actual_business_opening_verified"],"NO")
            self.assertEqual(added["publisher_original_rechecked"],"NO")

    def test_changed_hash_and_site_mismatch_demand_review(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td);old=t/"old.zip";new=t/"new.zip"
            base=candidate("brampton_building_permits","A1","hash")
            modified={**base,"source_record_sha256":"newhash"}
            stage_changed={**base,"source_record_key":"A2","activation_stage":"OTHER"}
            prior_stage={**base,"source_record_key":"A2"}
            make_zip(old,[base,prior_stage],[])
            make_zip(new,[modified,stage_changed],[])
            report=a.compare(old,new,t/"out")
            self.assertEqual(report["modified_saved_source_hash_or_stage_rows"],2)
            self.assertEqual(report["stable_saved_source_hash_and_stage_rows"],0)
            self.assertEqual(report["source_change_categories"][
                "SOURCE_HASH_CHANGED_IN_SAVED_OUTPUT_RECHECK_REQUIRED"],1)
            self.assertEqual(report["source_change_categories"][
                "CLASSIFICATION_OR_SITE_CHANGED_RECHECK_REQUIRED"],1)

    def test_duplicate_exact_key_is_held_and_does_not_override(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td);old=t/"old.zip";new=t/"new.zip"
            base=candidate("brampton_building_permits","A1","hash")
            make_zip(old,[base],[])
            make_zip(new,[base,{**base,"source_record_sha256":"conflict"}],[])
            report=a.compare(old,new,t/"out")
            self.assertGreaterEqual(report["duplicate_or_missing_source_keys_held"],1)
            self.assertEqual(report["common_exact_source_keys"],0)
            self.assertEqual(report["publisher_original_source_records_rechecked"],0)

    def test_cannot_self_compare_one_archive(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"run.zip";make_zip(p,[],[])
            with self.assertRaisesRegex(ValueError,"TWO_INDEPENDENT_ARCHIVES_REQUIRED"):
                a.compare(p,p,Path(td)/"output")

if __name__=="__main__":
    unittest.main()
