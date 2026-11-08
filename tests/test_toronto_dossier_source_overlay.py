"""Gated source-evidence overlay must NEVER promote verified permits to buyers."""
from __future__ import annotations
import csv
import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode

import gta_facility_intelligence as graph
import gta_facility_dossiers as dossiers
import gta_toronto_permit_acceptance as acceptance
import gta_toronto_permit_evidence as permits
import gta_toronto_dossier_source_overlay as overlay

NOW=dt.datetime(2026,11,8,16,0,tzinfo=dt.timezone.utc)


def dossier(project="26 265617",keys=None,site="220 yonge st",
            stage="Pending Parent Folder Review",city="Toronto",id="dossier-one"):
    keys=keys or "26 265617 HVA|00 | 26 265617 BLD|00 | 26 265617 PLB|00"
    return {
        "dossier_id":id,"event_id":"event-"+id,
        "source_family":"radar","source_id":permits.SOURCE,
        "source_record_id":permits.SOURCE+":"+project,
        "source_lookup_key":keys,
        "city":city,"site_address":site,"source_stage":stage,
        "buyer_verified":"NO","verified_open_contract":"NO",
        "outreach_authorized":"NO",
    }


def accepted(project="26 265617",key="26 265617 BLD|00",site="220 yonge st",
             status="Permit Issued",date=NOW):
    permit,rev=key.split("|")
    query=permits.API+"datastore_search?"+urlencode({
        "resource_id":permits.RESOURCE_HINT,
        "filters":json.dumps({"PERMIT_NUM":permit,"REVISION_NUM":rev},
                             separators=(",",":")),
        "limit":3})
    return {
        "project_id":permits.SOURCE+":"+project,
        "source_key":key,
        "permit_num":permit,"revision_num":rev,
        "source_address":site,
        "source_status":status,
        "source_query_url":query,
        "record_validation":overlay.SOURCE_EVIDENCE,
        "live_checked_at_utc":date.isoformat(),
        "buyer_verified":"NO",
        "open_supplier_contract_verified":"NO",
    }


def write_inputs(base,source_rows=None,verified_rows=None,gate=True):
    dossier_dir=base/"FACILITY_DOSSIER_PILOT";dossier_dir.mkdir()
    permit_dir=base/"TORONTO_PERMIT_EVIDENCE_PILOT";permit_dir.mkdir()
    source_rows=source_rows if source_rows is not None else [dossier()]
    graph.write_csv(dossier_dir/dossiers.DOSSIERS_CSV,
                    source_rows,dossiers.DOSSIER_FIELDS)
    if verified_rows is None:
        verified_rows=[accepted()]
    graph.write_csv(permit_dir/acceptance.OUTPUT_CSV,
                    verified_rows,acceptance.FIELDNAMES)
    manifest={
        "official_source_sample_gate_passed":gate,
        "commercial_production_accepted":False,
        "buyer_and_open_procurement_verified":False,
        "integrity_or_source_mismatch_rejection_count":0,
        "accepted_active_csv_sha256":hashlib.sha256(
            (permit_dir/acceptance.OUTPUT_CSV).read_bytes()).hexdigest(),
    }
    (permit_dir/acceptance.OUTPUT_JSON).write_text(
        json.dumps(manifest),encoding="utf-8")
    return dossier_dir,permit_dir


class TorontoDossierSourceOverlayTests(unittest.TestCase):
    def test_real_shape_multiple_permit_folder_never_proves_full_project_stage(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);d,p=write_inputs(root)
            before=(d/dossiers.DOSSIERS_CSV).read_bytes()
            result=overlay.run(d,p,as_of=NOW)
            self.assertEqual(result["toronto_dossiers_with_exact_checked_permit_source"],1)
            self.assertEqual(result["exact_permit_records_linked"],1)
            self.assertEqual(result["verified_constituents_in_multi_permit_project_folders"],1)
            self.assertEqual(result["source_stage_difference_to_archived_project_summary"],1)
            self.assertEqual(result["verified_buyers"],0)
            self.assertFalse(result["outreach_authorized"])
            self.assertEqual(before,(d/dossiers.DOSSIERS_CSV).read_bytes())
            with (d/overlay.OUTPUT_CSV).open(encoding="utf-8-sig",newline="") as f:
                row=next(csv.DictReader(f))
            self.assertEqual(row["original_project_permit_key_count"],"3")
            self.assertEqual(row["exact_permit_source_stage"],"Permit Issued")
            self.assertEqual(row["source_stage_comparison"],
                "PROJECT_AGGREGATE_DIFFERS_NOT_PROOF_OF_INDIVIDUAL_STAGE_CHANGE")
            self.assertEqual(row["original_project_full_status_verified"],"NO")
            self.assertEqual(row["procurement_verified"],"NO")
            self.assertEqual(row["outreach_authorized"],"NO")

    def test_single_constituent_refusal_notice_stays_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            d,p=write_inputs(root,
                [dossier(project="26 263884",keys="26 263884 BLD|00",
                         site="29 jutland rd",stage="Refusal Notice")],
                [accepted(project="26 263884",key="26 263884 BLD|00",
                          site="29 jutland rd",status="Refusal Notice")])
            result=overlay.run(d,p,as_of=NOW)
            self.assertEqual(result["blocked_source_status_records_not_sales_ready"],1)
            with (d/overlay.OUTPUT_CSV).open(encoding="utf-8-sig",newline="") as f:
                row=next(csv.DictReader(f))
            self.assertEqual(row["commercial_research_status"],"BLOCKED_PERMIT_REVIEW_ONLY")
            self.assertEqual(row["buyer_verified"],"NO")

    def test_no_source_gate_means_no_verified_link_even_when_csv_has_names(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            d,p=write_inputs(root,gate=False)
            out=overlay.run(d,p,as_of=NOW)
            self.assertFalse(out["sample_source_gate_enabled"])
            self.assertEqual(out["toronto_dossiers_with_exact_checked_permit_source"],0)
            self.assertEqual(out["exact_permit_records_linked"],0)
            self.assertFalse(out["production_promotion_allowed"])

    def test_missing_source_manifest_reports_no_city_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            d,p=write_inputs(root)
            (p/acceptance.OUTPUT_JSON).unlink()
            result=overlay.run(d,p,as_of=NOW)
            self.assertEqual(result["source_gate_reason"],"NO_ACCEPTED_CITY_SOURCE_EVIDENCE")
            self.assertEqual(result["exact_permit_records_linked"],0)
            self.assertEqual(result["verified_open_supplier_contracts"],0)

    def test_modified_accepted_csv_fails_closed_without_source_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            d,p=write_inputs(root)
            f=p/acceptance.OUTPUT_CSV
            f.write_bytes(f.read_bytes()+b"\n")
            with self.assertRaisesRegex(ValueError,"differs from source gate manifest"):
                overlay.run(d,p,as_of=NOW)
            self.assertFalse((d/overlay.OUTPUT_CSV).exists())

    def test_wrong_revision_from_same_project_cannot_join_dossier(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            d,p=write_inputs(root,verified_rows=[accepted(
                key="26 265617 BLD|99")])
            result=overlay.run(d,p,as_of=NOW)
            self.assertEqual(result["toronto_dossiers_with_exact_checked_permit_source"],0)
            self.assertEqual(result["exact_permit_records_linked"],0)
            self.assertEqual(result["unresolved_matching_reasons"].get(
                "CITY_SOURCE_KEY_NOT_IN_ORIGINAL_PROJECT"),1)

    def test_same_project_wrong_civic_address_cannot_join(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            d,p=write_inputs(root,verified_rows=[accepted(site="333 bay st")])
            result=overlay.run(d,p,as_of=NOW)
            self.assertEqual(result["exact_permit_records_linked"],0)
            self.assertEqual(result["unresolved_matching_reasons"].get(
                "EXACT_PERMIT_SITE_OR_CITY_CONFLICT"),1)

    def test_expired_source_record_must_be_rechecked(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            d,p=write_inputs(root,verified_rows=[accepted(
                date=NOW-dt.timedelta(days=10))])
            result=overlay.run(d,p,as_of=NOW)
            self.assertEqual(result["exact_permit_records_linked"],0)
            self.assertEqual(result["unresolved_matching_reasons"].get(
                "ACCEPTED_CITY_SOURCE_PROOF_EXPIRED"),1)

    def test_fake_purchasing_authority_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            row=accepted();row["buyer_verified"]="YES"
            d,p=write_inputs(root,verified_rows=[row])
            result=overlay.run(d,p,as_of=NOW)
            self.assertEqual(result["exact_permit_records_linked"],0)
            self.assertEqual(result["verified_buyers"],0)
            self.assertFalse(result["outreach_authorized"])

    def test_company_and_other_municipal_dossiers_are_not_toronto_matches(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            not_toronto=dossier();not_toronto["source_id"]="brampton_building_permits"
            not_toronto["dossier_id"]="brampton-dossier"
            d,p=write_inputs(root,source_rows=[not_toronto])
            result=overlay.run(d,p,as_of=NOW)
            self.assertEqual(result["toronto_dossiers_in_research"],0)
            self.assertEqual(result["exact_permit_records_linked"],0)


if __name__=="__main__":
    unittest.main()
