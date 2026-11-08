"""Acceptance checks: shared facility evidence graph must refuse false business claims."""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import gta_facility_intelligence as graph


def event(family, **kwargs):
    if family == "industrial":
        original = {
            "ero_number":"026-1152", "signal_id":"line3-dust",
            "city":"Oakville", "site_address":"2714 Bristol Circle",
            "proponent":"Pinty's Delicious Foods Inc.",
            "notice_stage":"Proposal", "equipment":"Dust collection",
            "action":"REPLACEMENT", "replacement_equipment":"Scrubber",
            "official_excerpt":"Replace Line 3 dust collector with a scrubber.",
            "official_notice_url":"https://ero.ontario.ca/notice/026-1152",
            "proposal_posted":"2026-11-06",
            "radar_first_seen_at":"2026-11-07T08:30:00-05:00",
        }
    elif family == "planning":
        original = {
            "canonical_id":"OAKVILLE:1403.071/01", "record_kind":"APPLICATION_ID",
            "city":"Oakville", "address":"",
            "description":"Pinty's Delicious Foods, 2714 Bristol Circle - proposed 254.4 m2 addition",
            "source_id":"oakville_early_applications",
            "evidence_urls":"https://www.oakville.ca/business/",
            "date":"2026-05-01",
        }
    elif family == "activation":
        original = {
            "source_id":"toronto_business_licences","source_record_key":"LIC-1",
            "municipality":"Toronto","site_address":"100 Queen St",
            "site_unit":"5","business_name":"New Restaurant Inc",
            "activation_stage":"LICENCE_ISSUED_NOT_OPENING_CONFIRMED",
            "source_event_date":"2026-11-05",
            "source_dataset_url":"https://open.toronto.ca/dataset/municipal-licensing-and-standards-business-licences-and-permits/",
            "source_excerpt":"Eating or drinking establishment",
            "potential_supplier_segments":"Security installation;POS systems",
        }
    elif family == "radar":
        original = {
            "project_id":"TORONTO:PERM:01234","observation":"FIRST_OBSERVED",
            "source_id":"toronto_active_building_permits",
            "city":"Toronto","address":"100 Queen Street, Toronto, ON",
            "description":"Tenant fit-out, commercial retail unit",
            "record_source_url":"https://open.toronto.ca/dataset/building-permits-active-permits/",
            "current_source_status":"Permit Issued",
            "source_record_date":"2026-11-06",
            "first_seen_local":"2026-11-07T09:00:00-05:00",
        }
    else:
        raise ValueError(family)
    original.update(kwargs)
    return graph.adapt(family,original)


def write(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as file:
        writer=csv.DictWriter(file,fieldnames=tuple(rows[0]))
        writer.writeheader();writer.writerows(rows)


class FacilityIntelligenceTests(unittest.TestCase):
    def test_industrial_proposal_is_not_available_purchase(self):
        record,why=event("industrial")
        self.assertIsNone(why)
        self.assertEqual(record["organization_role"],
                         "REGULATORY_PROPONENT_NOT_VERIFIED_BUYER")
        self.assertEqual(record["review_tier"],"EQUIPMENT_CHANGE_RESEARCH")
        self.assertEqual(record["procurement_status"],"UNKNOWN")
        self.assertEqual(record["buyer_verified"],"NO")
        self.assertIn("BUYER_NOT_VERIFIED",record["verification_required"])
        self.assertEqual(record["source_date"],"2026-11-06")

    def test_different_source_same_pintys_civic_location_only_unverified(self):
        industrial,_=event("industrial")
        planning,_=event("planning")
        self.assertEqual(industrial["site_id"],planning["site_id"])
        self.assertEqual(planning["site_identity_status"],
                         "DESCRIPTION_ONLY_UNVERIFIED_ADDRESS")
        links=graph.relationships([industrial,planning])
        self.assertEqual(len(links),1)
        self.assertEqual(links[0]["relationship"],
                         "DESCRIPTION_ADDRESS_SAME_SITE_CANDIDATE_ONLY")
        self.assertEqual(links[0]["relationship_verified"],"NO")
        profile=graph.facility_profiles([industrial,planning],links)[0]
        self.assertEqual(profile["cross_source_civic_matches"],1)
        self.assertEqual(profile["distinct_source_records"],2)
        self.assertIn("NOT_VERIFIED",profile["status"])

    def test_address_variants_match_but_street_number_must_match(self):
        self.assertEqual(graph.normalize_address("2714 Bristol Circle")[0],
                         graph.normalize_address("2714 Bristol Cir, Oakville, ON")[0])
        self.assertNotEqual(graph.normalize_address("2714 Bristol Circle")[0],
                            graph.normalize_address("12714 Bristol Cir")[0])

    def test_unknown_or_region_only_city_cannot_join(self):
        p,why=event("radar",city="Peel",source_id="unrecognized_regional_feed")
        self.assertIsNone(why)
        self.assertEqual(p["site_id"],"")
        self.assertEqual(p["review_tier"],"IDENTITY_REPAIR_REQUIRED")
        self.assertIn("SITE_ADDRESS_OR_CITY_UNVERIFIED",p["verification_required"])

    def test_configured_source_can_recover_brampton_city_not_tenant_identity(self):
        row,reason=event("radar",source_id="brampton_building_permits",
                         city="Peel",address="7535 Financial Dr, Brampton, ON,")
        self.assertIsNone(reason)
        self.assertEqual(row["city"],"Brampton")
        self.assertEqual(row["site_address"],"7535 financial dr")
        self.assertEqual(row["site_identity_status"],
                         "SOURCE_JURISDICTION_CITY_NOT_INDEPENDENTLY_CHECKED")
        self.assertIn("CITY_DERIVED_FROM_CONFIGURED_SOURCE_JURISDICTION",
                      row["verification_required"])

    def test_conflicting_city_and_source_jurisdiction_prevents_join(self):
        row,_=event("radar",source_id="brampton_building_permits",
                    city="Toronto",address="7535 Financial Dr")
        self.assertEqual(row["site_id"],"")
        self.assertIn("SOURCE_CITY_CONFLICT",row["verification_required"])

    def test_toronto_permit_partial_postal_does_not_poison_site_key(self):
        row,_=event("radar",address="220 YONGE ST M5B")
        self.assertEqual(row["site_address"],"220 yonge st")

    def test_aggregated_planning_descriptions_do_not_create_false_site_matches(self):
        row,_=event("planning",description=(
            "Featured Application: City File: OZS-1. Location 100 Queen St. "
            "Featured Application: City File: OZS-2. Location 200 King St."))
        self.assertEqual(row["site_id"],"")
        self.assertEqual(row["review_tier"],"IDENTITY_REPAIR_REQUIRED")

    def test_zero_address_is_a_placeholder_not_a_site(self):
        row,_=event("planning",description="Location 0 Edvac Drive: no municipal address")
        self.assertEqual(row["site_id"],"")

    def test_different_unit_cannot_verify_same_tenant(self):
        a,_=event("activation")
        b,_=event("radar",address="100 Queen St Unit 9")
        links=graph.relationships([a,b])
        self.assertEqual(len(links),1)
        self.assertEqual(links[0]["relationship"],"DIFFERENT_UNITS_NOT_SAME_TENANT")
        self.assertEqual(links[0]["relationship_verified"],"NO")

    def test_unit_unknown_cannot_verify_tenant(self):
        a,_=event("activation")
        b,_=event("radar")
        links=graph.relationships([a,b])
        self.assertEqual(links[0]["relationship"],"SAME_BUILDING_UNIT_UNKNOWN")

    def test_licence_issue_never_confirms_business_opening(self):
        row,why=event("activation")
        self.assertIsNone(why)
        self.assertEqual(row["opening_confirmed"],"NO")
        self.assertEqual(row["procurement_status"],"UNKNOWN")
        self.assertEqual(row["organization_role"],"LICENCE_OPERATING_NAME_NOT_VERIFIED_TENANT")
        self.assertEqual(row["review_tier"],"FACILITY_ACTIVATION_RESEARCH")

    def test_terminal_works_blocked_even_if_equipment_specific(self):
        a,why=event("industrial",notice_stage="Withdrawn")
        self.assertIsNone(why)
        self.assertEqual(a["review_tier"],"HISTORICAL_OR_TERMINAL_REVIEW_ONLY")
        self.assertEqual(a["procurement_status"],"NOT_OPEN_OR_TERMINAL_STATUS")
        self.assertIn("HISTORICAL_OR_TERMINAL_STATUS",a["verification_required"])

    def test_untrustworthy_urls_are_never_copied_into_reports(self):
        for url in ("http://example.com/a", "https://username@ero.ontario.ca/a",
                    "https://localhost/a"):
            row,_=event("industrial",official_notice_url=url)
            self.assertEqual(row["source_url"],"")
            self.assertIn("NO_SOURCE_URL",row["verification_required"])

    def test_old_source_date_not_rewritten_as_recent_from_observation(self):
        row,_=event("radar",source_record_date="2019-07-02",
                    first_seen_local="2026-11-08T09:00:00-05:00")
        self.assertEqual(row["source_date"],"2019-07-02")
        self.assertEqual(row["radar_first_seen_at"],"2026-11-08T09:00:00-05:00")
        self.assertEqual(row["procurement_status"],"UNKNOWN")

    def test_historical_source_date_cannot_be_relabelled_fresh(self):
        row,why=graph.adapt("radar",{
            "project_id":"T:OLD","observation":"FIRST_OBSERVED",
            "source_id":"toronto_active_building_permits","city":"Toronto",
            "address":"100 Queen Street","source_record_date":"2019-07-02",
            "first_seen_local":"2026-11-08T08:30:00-05:00",
            "description":"Historical tenant fit-out",
        },as_of=__import__("datetime").date(2026,11,8))
        self.assertIsNone(why)
        self.assertEqual(row["review_tier"],"HISTORICAL_SOURCE_DATE_REVIEW_ONLY")
        self.assertIn("SOURCE_DATE_OLDER_THAN_RESEARCH_WINDOW",
                      row["verification_required"])
        self.assertGreater(int(row["source_age_days"]),180)
        self.assertEqual(row["procurement_status"],"UNKNOWN")

    def test_source_date_missing_does_not_become_new_publication(self):
        row,_=graph.adapt("industrial",{
            "ero_number":"026-1152","signal_id":"a",
            "city":"Oakville","site_address":"2714 Bristol Circle",
            "notice_stage":"Proposal","radar_first_seen_at":"2026-11-08T09:00:00Z",
        },as_of=__import__("datetime").date(2026,11,8))
        self.assertEqual(row["review_tier"],"SOURCE_DATE_UNVERIFIED_REVIEW_ONLY")
        self.assertIn("SOURCE_DATE_NOT_VERIFIED",row["verification_required"])
        self.assertEqual(row["source_date"],"")
        self.assertEqual(row["opening_confirmed"],"UNKNOWN")

    def test_normalizing_pob_and_missing_city_remains_in_audit(self):
        a,_=event("radar",address="PO Box 110")
        self.assertEqual(a["site_id"],"")
        b,_=event("industrial",city="Queens")
        self.assertEqual(b["site_id"],"")

    def test_no_fake_cross_source_links_for_same_family(self):
        a,_=event("industrial")
        b,_=event("industrial",ero_number="026-1145",signal_id="another")
        self.assertEqual(graph.relationships([a,b]),[])

    def test_end_to_end_csv_outputs_and_status_without_source_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            results=Path(temp)/"GTA_RADAR_RESULTS"
            results.mkdir()
            def input_row(family):
                # Extract a complete record only to obtain the original source fields.
                if family=="industrial":
                    return {"ero_number":"026-1152","signal_id":"line3-dust",
                        "city":"Oakville","site_address":"2714 Bristol Circle",
                        "proponent":"Pinty's Delicious Foods",
                        "notice_stage":"Proposal","action":"REPLACEMENT",
                        "equipment":"Dust collection",
                        "official_excerpt":"Replace dust collector with scrubber",
                        "official_notice_url":"https://ero.ontario.ca/notice/026-1152",
                        "proposal_posted":"2026-11-06"}
                return {"canonical_id":"OAKVILLE:1403.071/01",
                    "record_kind":"APPLICATION_ID","city":"Oakville",
                    "address":"","source_id":"oakville_early_applications",
                    "description":"Pinty's 2714 Bristol Circle 254 m2 expansion",
                    "evidence_urls":"https://www.oakville.ca/business/"}
            planning=results/"GTA_RADAR_COLLECTION_MASTER.csv"
            industrial=results/"INDUSTRIAL_PILOT"/"GTA_RADAR_INDUSTRIAL_EQUIPMENT_REVIEW.csv"
            write(planning,[input_row("planning")])
            write(industrial,[input_row("industrial")])
            unchanged=planning.read_bytes(),industrial.read_bytes()
            out=results/"FACILITY_INTELLIGENCE_PILOT"
            s=graph.run(results,out)
            self.assertEqual(s["source_event_count"],2)
            self.assertEqual(s["sites_with_civic_identity"],1)
            self.assertEqual(s["cross_source_candidate_links"],1)
            self.assertEqual(s["verified_open_supplier_contracts"],0)
            self.assertEqual(s["verified_buyers"],0)
            self.assertEqual(unchanged,(planning.read_bytes(),industrial.read_bytes()))
            for name in (graph.OUTPUT_EVENTS,graph.OUTPUT_FACILITIES,
                         graph.OUTPUT_LINKS,graph.OUTPUT_REVIEW,
                         graph.OUTPUT_HTML,graph.OUTPUT_STATUS):
                self.assertTrue((out/name).is_file(),name)
            with (out/graph.OUTPUT_LINKS).open(encoding="utf-8-sig",newline="") as f:
                links=list(csv.DictReader(f))
            self.assertEqual(links[0]["relationship_verified"],"NO")

    def test_incomplete_and_duplicate_rows_not_false_projects(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)
            write(path/"GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv",[
                {"source_id":"toronto_active_building_permits",
                 "project_id":"T:123","observation":"FIRST_OBSERVED",
                 "city":"Toronto","address":"100 Queen St",
                 "description":"Tenant fit-out"},
                {"source_id":"toronto_active_building_permits",
                 "project_id":"T:123","observation":"FIRST_OBSERVED",
                 "city":"Toronto","address":"100 Queen St",
                 "description":"Duplicate row"},
                {"source_id":"toronto_active_building_permits",
                 "project_id":"T:999","observation":"UNCHANGED",
                 "city":"Toronto","address":"100 Queen St",
                 "description":"Old history"}
            ])
            summary=graph.run(path)
            self.assertEqual(summary["source_event_count"],1)
            self.assertEqual(summary["exclusions"]["DUPLICATE_EVENT_ID"],1)
            self.assertEqual(summary["exclusions"]["radar:NOT_NEW_OR_CHANGED"],1)


if __name__=="__main__":
    unittest.main()
