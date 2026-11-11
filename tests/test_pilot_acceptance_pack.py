"""Acceptance review queues remain source-only and not human validation."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

import gta_pilot_acceptance_pack as a


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as inp:
        return list(csv.DictReader(inp))


class PilotAcceptancePackTests(unittest.TestCase):
    def test_realistic_industrial_three_notices_four_equipment_items(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "INDUSTRIAL_PILOT"
            rows = [
                {"ero_number":"026-1155","official_notice_url":"https://ero.ontario.ca/notice/026-1155",
                 "proponent":"1000792458 Ontario Ltd.","city":"Burlington",
                 "site_address":"890 Harrington Court", "equipment":"Cremation equipment",
                 "action":"INSTALLATION", "source_text_sha256":"one", "notice_stage":"Proposal"},
                {"ero_number":"026-1152","official_notice_url":"https://ero.ontario.ca/notice/026-1152",
                 "proponent":"Pinty's","city":"Oakville","site_address":"2714 Bristol Circle",
                 "equipment":"Dust collection", "action":"REPLACEMENT", "source_text_sha256":"two",
                 "notice_stage":"Proposal"},
                {"ero_number":"026-1021","official_notice_url":"https://ero.ontario.ca/notice/026-1021",
                 "proponent":"Kristofoam","city":"Vaughan","site_address":"160 Planchet Road",
                 "equipment":"Boiler", "action":"INSTALLATION", "source_text_sha256":"three",
                 "notice_stage":"Proposal"},
                {"ero_number":"026-1021","official_notice_url":"https://ero.ontario.ca/notice/026-1021",
                 "proponent":"Kristofoam","city":"Vaughan","site_address":"160 Planchet Road",
                 "equipment":"Cooling tower", "action":"INSTALLATION",
                 "source_text_sha256":"three", "notice_stage":"Proposal"},
            ]
            write_csv(folder/"GTA_RADAR_INDUSTRIAL_EQUIPMENT_REVIEW.csv",rows)
            (folder/"GTA_RADAR_INDUSTRIAL_EQUIPMENT_STATUS.json").write_text(json.dumps({
                "official_fetch_audit":[
                    {"ero_number":"026-1021","status":"DETAIL_RETRIEVED"},
                    {"ero_number":"026-0999","status":"NON_INSTRUMENT_BULLETIN"}]}))
            report = a.build(root, pilot="industrial")
            self.assertEqual(report["industrial"]["equipment_findings"],4)
            self.assertEqual(report["industrial"]["distinct_notices_with_equipment_findings"],3)
            lines = read_csv(root/a.FOLDER/a.INDUSTRIAL)
            self.assertEqual(len(lines),4)  # includes rejected source notice, not a new lead
            self.assertEqual([x for x in lines if x["ero_number"]=="026-1021"][0]
                             ["equipment_changes"],"Boiler:INSTALLATION | Cooling tower:INSTALLATION")
            self.assertEqual({x["supplier_package_available"] for x in lines},{"UNKNOWN"})
            self.assertEqual({x["buyer_verified"] for x in lines},{"NO"})
            self.assertEqual({x["original_notice_rechecked"] for x in lines},{"NOT_YET_RECHECKED"})

    def test_realistic_activation_sample_balances_sources_and_groups_facilities(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);folder=root/"COMMERCIAL_ACTIVATION_PILOT"
            groups=[
                ("toronto_business_licences","Toronto"),
                ("toronto_active_building_permits","Toronto"),
                ("brampton_building_permits","Brampton"),
                ("mississauga_issued_building_permits","Mississauga"),
            ]
            rows=[]
            for source,city in groups:
                for index in range(8):
                    rows.append({
                        "source_id":source,"source_record_key":source+":"+str(index),
                        "source_record_sha256":"sha"+str(index),
                        "source_dataset_url":"https://example.org/data",
                        "source_event_date":"2026-11-%02d"%(10-index),
                        "radar_first_seen_at":"2026-11-10T01:00:00Z",
                        "municipality":city,"business_name":"Unconfirmed",
                        "site_address":str(100+index)+" King Street",
                        "site_unit":"A" if index==0 and source=="toronto_business_licences" else "",
                        "activation_stage":"LICENCE_ISSUED_NOT_OPENING_CONFIRMED",
                        "source_excerpt":"Interior fit out", "same_site_link_status":"NO_CROSS_SOURCE_SITE_LINK",
                    })
            write_csv(folder/"GTA_RADAR_COMMERCIAL_ACTIVATION_REVIEW.csv",rows)
            (folder/"GTA_RADAR_COMMERCIAL_ACTIVATION_STATUS.json").write_text(json.dumps({
                "activation_review_candidates":len(rows),
                "same_site_cross_source_rows":3,
                "excluded_counts":{"RESIDENTIAL_ONLY":15}}))
            report=a.build(root,pilot="activation")
            self.assertEqual(report["activation"]["source_sample_rows"],20)
            self.assertEqual(report["activation"]["distinct_facility_dossiers_queued"],10)
            sample=read_csv(root/a.FOLDER/a.ACTIVATION)
            self.assertEqual(len(sample),20)
            self.assertEqual({s["source_id"] for s in sample},{s for s,_ in groups})
            self.assertEqual(sum(s["source_id"]==groups[0][0] for s in sample),5)
            self.assertTrue(all(s["original_record_rechecked"]=="NOT_YET_RECHECKED"
                                and s["opening_verified"]=="NO" for s in sample))
            dossiers=read_csv(root/a.FOLDER/a.FACILITIES)
            self.assertEqual(len(dossiers),10)
            self.assertGreaterEqual(len({d["municipality"] for d in dossiers}),3)
            self.assertEqual(len({(d["municipality"],d["site_address"],d["site_unit"])
                                   for d in dossiers}),10)
            self.assertEqual({d["business_opening_verified"] for d in dossiers},{"NO"})
            self.assertEqual(report["activation"]["original_rejected_record_samples"],0)

    def test_missing_pilot_files_never_claim_acceptance(self):
        with tempfile.TemporaryDirectory() as td:
            state=a.build(td)
            self.assertEqual(state["industrial"]["equipment_findings"],0)
            self.assertEqual(state["activation"]["existing_pilot_source_candidates"],0)
            self.assertEqual(state["human_verified_openings"],0)
            self.assertEqual(state["open_supplier_packages_verified"],0)
            self.assertTrue((Path(td)/a.FOLDER/a.STATUS).is_file())


if __name__=="__main__":
    unittest.main()
