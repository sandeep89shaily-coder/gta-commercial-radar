"""Regression and safety checks for evidence-backed research dossiers.

The dossier stage is explicitly NOT a confirmed lead or outreach authority.
"""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

import gta_facility_intelligence as graph
import gta_facility_dossiers as dossiers


def event(**changes):
    original = {
        "event_id": "event-industrial-001",
        "source_family": "industrial",
        "source_id": "ero_gta_environmental_instruments",
        "source_record_id": "026-1152|line3",
        "source_url": "https://ero.ontario.ca/notice/026-1152",
        "url_evidence_level": "RECORD_URL_NOT_LIVE_CHECKED",
        "source_date": "2026-11-06",
        "radar_first_seen_at": "2026-11-07",
        "source_age_days": "2",
        "city": "Oakville",
        "site_address": "2714 bristol cir",
        "site_unit": "",
        "site_id": "site-pintys",
        "organization": "Pinty's Delicious Foods Inc.",
        "organization_role": "REGULATORY_PROPONENT_NOT_VERIFIED_BUYER",
        "record_hash": "a"*64,
        "signal_type": "INDUSTRIAL_REPLACEMENT",
        "stage_label": "Proposal",
        "description": "Replace Line 3 dust collector with scrubber.",
        "scope_specificity": "EXPLICIT_EQUIPMENT_CHANGE",
        "supplier_segments_possible": "Dust collection;Scrubber",
        "review_tier": "EQUIPMENT_CHANGE_RESEARCH",
        "verification_required": "BUYER_NOT_VERIFIED;PROCUREMENT_NOT_VERIFIED",
    }
    original.update(changes)
    return original


def link(left, right, relationship, site="site-pintys"):
    return {
        "site_id": site,
        "left_event_id": left,
        "right_event_id": right,
        "relationship": relationship,
        "relationship_verified": "NO",
    }


def write_graph(folder, events, links):
    folder.mkdir(parents=True, exist_ok=True)
    graph.write_csv(folder/graph.OUTPUT_EVENTS, events, graph.EVENT_FIELDS)
    graph.write_csv(folder/graph.OUTPUT_LINKS, links, graph.LINK_FIELDS)


class FacilityDossierTests(unittest.TestCase):

    def test_industrial_candidate_never_becomes_verified_contract(self):
        primary = event()
        row, detail, tasks = dossiers.build_dossier(primary,{primary["event_id"]:primary},{})
        self.assertEqual(row["research_priority"],"P1_EQUIPMENT_SOURCE_RESEARCH")
        self.assertEqual(row["commercial_readiness"],"RESEARCH_SIGNAL_ONLY_NOT_VERIFIED_LEAD")
        self.assertEqual(row["buyer_verified"],"NO")
        self.assertEqual(row["verified_open_contract"],"NO")
        self.assertEqual(row["outreach_authorized"],"NO")
        self.assertFalse(detail["verified_open_procurement"])
        self.assertFalse(detail["verified_buying_authority"])
        self.assertFalse(detail["outreach_authorized"])
        self.assertIn("PURCHASING_AUTHORITY_NOT_VERIFIED",row["readiness_blockers"])
        self.assertIn("VERIFY_CURRENT_PROCUREMENT_STATUS",[t["task_code"] for t in tasks])

    def test_stale_or_withdrawn_proposal_never_enters_active_research(self):
        for tier in ("HISTORICAL_OR_TERMINAL_REVIEW_ONLY",
                     "HISTORICAL_SOURCE_DATE_REVIEW_ONLY",
                     "HISTORICAL_PLANNING_BASELINE_SITE_CONTEXT_ONLY",
                     "SOURCE_DATE_UNVERIFIED_REVIEW_ONLY"):
            with self.subTest(tier=tier):
                a=event(review_tier=tier)
                row,detail,tasks=dossiers.build_dossier(a,{a["event_id"]:a},{})
                self.assertEqual(row["commercial_readiness"],"HOLD_NOT_COMMERCIALLY_ACTIVE")
                self.assertEqual(row["research_priority"],"HOLD_HISTORY_OR_INCOMPLETE_IDENTITY")
                self.assertEqual([t["task_code"] for t in tasks],
                                 ["RECHECK_HISTORICAL_OR_TERMINAL_STATUS"])
                self.assertEqual(row["verified_open_contract"],"NO")

    def test_identity_repair_holds_buyer_and_outreach(self):
        a=event(site_id="",city="",review_tier="IDENTITY_REPAIR_REQUIRED")
        row,rich,tasks=dossiers.build_dossier(a,{a["event_id"]:a},{})
        self.assertEqual(row["commercial_readiness"],"HOLD_NOT_COMMERCIALLY_ACTIVE")
        self.assertIn("SITE_IDENTITY_UNRESOLVED",row["readiness_blockers"])
        self.assertEqual([x["task_code"] for x in tasks],
                         ["REPAIR_SITE_IDENTITY","VERIFY_INDIVIDUAL_OFFICIAL_RECORD"])

    def test_activation_is_not_an_open_business_or_contract(self):
        a=event(event_id="activation-1",source_family="activation",
                source_id="toronto_business_licences",source_record_id="LIC-123",
                source_url="https://open.toronto.ca/dataset/municipal-licensing-and-standards-business-licences-and-permits/",
                url_evidence_level="SOURCE_REFERENCE_NOT_RECORD_SPECIFIC",
                organization="Example Cafe",organization_role="LICENCE_OPERATING_NAME_NOT_VERIFIED_TENANT",
                signal_type="COMMERCIAL_ACTIVATION_SIGNAL",
                scope_specificity="LICENCE_OR_PERMIT_ACTIVITY",
                review_tier="FACILITY_ACTIVATION_RESEARCH")
        row,detail,tasks=dossiers.build_dossier(a,{a["event_id"]:a},{})
        self.assertEqual(row["research_priority"],"P2_ACTIVATION_SOURCE_RESEARCH")
        self.assertEqual(row["opening_verified"],"NO")
        self.assertEqual(row["buyer_verified"],"NO")
        self.assertEqual(row["source_url_quality"],
                         "DATASET_OR_PORTAL_REFERENCE_NOT_INDIVIDUAL_VERIFICATION")
        self.assertIn("VERIFY_ACTUAL_OPENING",[t["task_code"] for t in tasks])

    def test_portal_url_not_treated_as_individual_evidence(self):
        a=event(url_evidence_level="SOURCE_REFERENCE_NOT_RECORD_SPECIFIC")
        row,_,_=dossiers.build_dossier(a,{a["event_id"]:a},{})
        self.assertEqual(row["source_url_quality"],
                         "DATASET_OR_PORTAL_REFERENCE_NOT_INDIVIDUAL_VERIFICATION")
        self.assertIn("EXACT_INDIVIDUAL_OFFICIAL_RECORD_NOT_RECHECKED",
                      row["readiness_blockers"])

    def test_untrusted_url_never_receives_clickable_source_quality(self):
        for source in ("http://ero.ontario.ca/notice/1",
                       "javascript:alert(1)",
                       "https://attacker@ero.ontario.ca/notice/1",
                       "https://localhost/"):
            with self.subTest(url=source):
                a=event(source_url=source)
                row,_,_=dossiers.build_dossier(a,{a["event_id"]:a},{})
                self.assertEqual(row["source_url"],"")
                self.assertEqual(row["source_url_quality"],"NO_STABLE_SOURCE_URL")

    def test_matching_civic_address_only_provides_context_not_project_proof(self):
        industrial=event()
        planning=event(event_id="planning-1",source_family="planning",
                       source_id="oakville_planning",source_record_id="1403.071/01",
                       scope_specificity="PLANNING_DESCRIPTION_ADDRESS_UNVERIFIED",
                       organization="",organization_role="UNKNOWN",
                       review_tier="HISTORICAL_PLANNING_BASELINE_SITE_CONTEXT_ONLY")
        event_map={x["event_id"]:x for x in (industrial,planning)}
        links={"site-pintys":[link(industrial["event_id"],planning["event_id"],
                                 "DESCRIPTION_ADDRESS_SAME_SITE_CANDIDATE_ONLY")]}
        row,detail,_=dossiers.build_dossier(industrial,event_map,links)
        self.assertEqual(row["cross_source_context_events"],1)
        self.assertEqual(row["cross_source_context_status"],"UNVERIFIED_CIVIC_SITE_LINK_ONLY")
        self.assertEqual(len(detail["site_context_not_project_corroboration"]),1)
        context=detail["site_context_not_project_corroboration"][0]
        self.assertEqual(context["same_project_verified"],"NO")
        self.assertEqual(context["same_company_verified"],"NO")
        self.assertEqual(context["scope_corroborated"],"NO")
        self.assertIn("CROSS_SOURCE_SAME_PROJECT_NOT_VERIFIED",row["readiness_blockers"])

    def test_conflicting_units_are_blocked_from_context(self):
        a=event()
        b=event(event_id="activation-1",source_family="activation",
                source_id="toronto_business_licences",site_id="site-pintys",
                source_record_id="licence-2")
        events={x["event_id"]:x for x in (a,b)}
        edges={"site-pintys":[link(a["event_id"],b["event_id"],
                                  "DIFFERENT_UNITS_NOT_SAME_TENANT")]}
        row,rich,_=dossiers.build_dossier(a,events,edges)
        self.assertEqual(row["cross_source_context_events"],0)
        self.assertEqual(row["cross_source_context_status"],"UNIT_CONFLICTS_EXCLUDED")
        self.assertEqual(rich["unit_conflicts_excluded"],1)

    def test_malicious_or_corrupt_link_never_crosses_site_ids(self):
        a=event()
        b=event(event_id="other",source_family="radar",site_id="site-other")
        edge=link(a["event_id"],b["event_id"],"SAME_CIVIC_SITE_PROJECT_UNVERIFIED")
        row,rich,_=dossiers.build_dossier(a,
            {a["event_id"]:a,b["event_id"]:b},{"site-pintys":[edge]})
        self.assertEqual(row["cross_source_context_events"],0)
        self.assertEqual(rich["site_context_not_project_corroboration"],[])

    def test_same_source_record_through_different_paths_is_not_corroboration(self):
        a=event()
        b=event(event_id="copy",source_family="radar")
        row,rich,_=dossiers.build_dossier(a,
            {a["event_id"]:a,b["event_id"]:b},
            {"site-pintys":[link(a["event_id"],b["event_id"],
                                "SAME_CIVIC_SITE_PROJECT_UNVERIFIED")]})
        self.assertEqual(row["cross_source_context_events"],0)
        self.assertEqual(rich["site_context_not_project_corroboration"],[])

    def test_stable_dossier_id_per_original_record(self):
        a=event()
        d1,_,_=dossiers.build_dossier(a,{a["event_id"]:a},{})
        b=dict(a,description="Updated proposal details",record_hash="b"*64)
        d2,_,_=dossiers.build_dossier(b,{b["event_id"]:b},{})
        self.assertEqual(d1["dossier_id"],d2["dossier_id"])
        self.assertNotEqual(d1["source_description"],d2["source_description"])

    def test_missing_graph_input_is_error_not_zero_success(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)
            with self.assertRaises(FileNotFoundError):
                dossiers.run(p/"missing",p/"output")
            self.assertFalse((p/"output").exists())

    def test_wrong_schema_fails_without_writing_report(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)
            g=p/"graph";g.mkdir()
            (g/graph.OUTPUT_EVENTS).write_text("some,other,columns\n1,2,3\n")
            (g/graph.OUTPUT_LINKS).write_text("site_id,left_event_id,right_event_id,relationship\n")
            with self.assertRaisesRegex(ValueError,"Unexpected graph schema"):
                dossiers.run(g,p/"out")
            self.assertFalse((p/"out").exists())

    def test_empty_valid_graph_generates_empty_honest_summary(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);g=p/"graph"
            write_graph(g,[],[])
            status=dossiers.run(g,p/"out")
            self.assertEqual(status["candidate_dossiers"],0)
            self.assertEqual(status["verified_open_supplier_contracts"],0)
            self.assertEqual(status["manual_verification_tasks"],0)

    def test_end_to_end_dossiers_are_research_only_and_source_unchanged(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);g=p/"graph";out=p/"dossier"
            one=event()
            two=event(event_id="planning-1",source_family="planning",
                      source_id="oakville_planning",source_record_id="1403.071/01",
                      review_tier="HISTORICAL_PLANNING_BASELINE_SITE_CONTEXT_ONLY",
                      source_date="2026-05-01",source_age_days="191")
            three=event(event_id="activation-1",source_family="activation",
                        source_id="toronto_business_licences",source_record_id="LIC-23",
                        city="Toronto",site_address="101 Queen St",site_id="site-toronto",
                        url_evidence_level="SOURCE_REFERENCE_NOT_RECORD_SPECIFIC",
                        review_tier="FACILITY_ACTIVATION_RESEARCH",
                        source_age_days="3")
            source_links=[link(one["event_id"],two["event_id"],
                               "DESCRIPTION_ADDRESS_SAME_SITE_CANDIDATE_ONLY")]
            write_graph(g,[one,two,three],source_links)
            before={(g/name).name:(g/name).read_bytes() for name in
                    (graph.OUTPUT_EVENTS,graph.OUTPUT_LINKS)}
            summary=dossiers.run(g,out)
            self.assertEqual(summary["candidate_dossiers"],3)
            self.assertEqual(summary["dossiers_with_unverified_cross_source_context"],2)
            self.assertEqual(summary["verified_buyers"],0)
            self.assertEqual(summary["outreach_authorized"],0)
            for name in (dossiers.DOSSIERS_CSV,dossiers.DOSSIERS_JSONL,
                         dossiers.TASKS_CSV,dossiers.REPORT_HTML,dossiers.REPORT_STATUS):
                self.assertTrue((out/name).is_file(),name)
            with (out/dossiers.DOSSIERS_CSV).open(encoding="utf-8-sig",newline="") as f:
                rows=list(csv.DictReader(f))
            self.assertEqual([r["research_priority"] for r in rows],
                 ["P1_EQUIPMENT_SOURCE_RESEARCH",
                  "P2_ACTIVATION_SOURCE_RESEARCH",
                  "HOLD_HISTORY_OR_INCOMPLETE_IDENTITY"])
            self.assertEqual({r["verified_open_contract"] for r in rows},{"NO"})
            self.assertEqual({r["outreach_authorized"] for r in rows},{"NO"})
            rich=[json.loads(x) for x in (out/dossiers.DOSSIERS_JSONL).read_text().splitlines()]
            self.assertEqual(len(rich),3)
            self.assertEqual(before,{(g/name).name:(g/name).read_bytes() for name in
                    (graph.OUTPUT_EVENTS,graph.OUTPUT_LINKS)})

    def test_csv_formula_injection_stays_neutralized_across_exports(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);g=p/"graph";out=p/"dossier"
            a=event(description="=HYPERLINK(\"https://bad.example\",\"CLICK\")",
                    organization="+CMD|' /C calc'!A0",site_address="@SUM(1,1)")
            write_graph(g,[a],[])
            dossiers.run(g,out)
            with (out/dossiers.DOSSIERS_CSV).open(encoding="utf-8-sig",newline="") as f:
                row=next(csv.DictReader(f))
            self.assertTrue(row["source_description"].startswith("'="))
            self.assertTrue(row["organization_mention"].startswith("'+"))
            self.assertTrue(row["site_address"].startswith("'@"))
            facts=json.loads((out/dossiers.DOSSIERS_JSONL).read_text().splitlines()[0])
            # Graph CSV already neutralizes this untrusted value on write.
            self.assertTrue(facts["primary_source_event"]["source_record_description"].startswith("'="))
            page=(out/dossiers.REPORT_HTML).read_text()
            self.assertNotIn("<script>",page)
            self.assertNotIn("href=\"javascript:",page)

    def test_missing_or_corrupted_source_still_reports_research_not_sale_ready(self):
        a=event(source_url="",organization="",source_date="",
                review_tier="SOURCE_DATE_UNVERIFIED_REVIEW_ONLY")
        row,detail,tasks=dossiers.build_dossier(a,{a["event_id"]:a},{})
        self.assertEqual(row["research_priority"],"HOLD_HISTORY_OR_INCOMPLETE_IDENTITY")
        self.assertEqual(row["verified_business_contact"],"")
        self.assertEqual(row["procurement_verified"],"NO")
        self.assertEqual(row["opening_verified"],"NOT_APPLICABLE")
        self.assertEqual(row["source_url_quality"],"NO_STABLE_SOURCE_URL")
        self.assertIn("COMPANY_OR_OPERATOR_UNKNOWN",row["readiness_blockers"])


if __name__=="__main__":
    unittest.main()
