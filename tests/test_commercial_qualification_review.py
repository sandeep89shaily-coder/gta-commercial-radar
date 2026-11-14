"""Offline regression tests for fresh, grounded commercial qualification."""
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from gta_commercial_qualification_review import build, run, CLIENT, PRIVATE, \
    PENDING, GRAPH, BRIDGE, PREVIOUS, TOP_OUT, REPORT
from gta_ai_research_priority import key as ai_key
from gta_execute_ai_project_research import select_projects


TODAY = dt.date(2026, 11, 14)


class CommercialWorklistTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def csv(self, name, records):
        if not records:
            return
        fields = sorted(set().union(*(row.keys() for row in records)))
        with (self.root/name).open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(records)

    def candidate(self, ident, city, description, date, *,
                  address=None, url=None, previous=False, app=None):
        return {
            "opportunity_id": ident, "city": city, "address": address or ident,
            "application_ids": app or ident,
            "project_name": ident, "nature_of_work": description,
            "stage_gate": "PLANNING_OR_SITE_PLAN_REVIEW",
            "source_event_date": date,
            "source_event_date_basis": (
                "OFFICIAL_APPLICATION_OR_PERMIT_EVENT_DATE_NOT_PUBLICATION"),
            "source_url": url or ("https://gis.toronto.ca/FeatureServer/60/query?where=ID%3D"+ident),
        }

    def test_fresh_industrial_priority_vs_old_residential(self):
        self.csv(CLIENT, [
            self.candidate("FRESH-IND", "Toronto",
                           "New industrial warehouse production expansion 50,000 sqft",
                           "2026-11-13", app="FA26"),
            self.candidate("OLD-RES", "Toronto",
                           "Proposed residential apartment 39 storeys 830 units",
                           "2024-05-01", app="OLD26"),
            self.candidate("FRESH-HOTEL", "Mississauga",
                           "New commercial hotel and restaurant",
                           "2026-11-12", app="HOTEL26"),
        ])
        result = build(self.root, today=TODAY)
        self.assertEqual(result["internal_top_10_count"], 2)
        self.assertEqual(result["top10"][0]["record_id"], "FRESH-IND")
        self.assertEqual(result["top10"][1]["record_id"], "FRESH-HOTEL")
        self.assertEqual(result["verified_buyers"], 0)
        self.assertFalse(result["outreach_authorized"])
        self.assertTrue(all(x["commercial_qualification"] ==
                            "RESEARCH_ONLY_NOT_CLIENT_READY"
                            for x in result["top10"]))

    def test_first_observed_does_not_turn_old_filing_into_recent_publication(self):
        self.csv(PENDING, [{
            "project_id": "toronto_development_applications:OLD001",
            "city": "Toronto", "address": "1 Industrial Avenue",
            "description": "Industrial warehouse manufacturing expansion",
            "source_keys": "OLD001",
            "source_record_date": "2023-01-01",
            "event_date": "2026-11-14T19:00:00Z",
            "date_basis": "SOURCE RECORD UPDATE OBSERVED NOT PUBLICATION",
            "source_group": "MUNICIPAL_CHANGE",
            "record_source_url": "https://gis.toronto.ca/FeatureServer/60/query?where=APPLICATION_NUMBER%3DOLD001",
            "_queued_on": "2026-11-14",
        }])
        result = build(self.root, today=TODAY)
        rec = result["all_candidates"][0]
        self.assertEqual(rec["freshness_band"], "OLDER_SOURCE_RECORD_NOT_NEW_EVENT")
        self.assertNotEqual(rec["source_date"], "2026-11-14")
        self.assertEqual(rec["radar_first_seen_local"], "2026-11-14")
        self.assertFalse(rec["buyer_verified"])

    def test_exact_company_role_joins_only_to_matching_project(self):
        self.csv(PENDING, [
            {"project_id": "toronto_development_applications:APPLICATION1",
             "city": "Toronto", "address": "123 Example Avenue",
             "source_keys": "APPLICATION1",
             "description": "Proposed industrial manufacturing warehouse",
             "source_record_date": "2026-11-11",
             "record_source_url": "https://gis.toronto.ca/FeatureServer/60/query?where=APPLICATION1"},
            {"project_id": "toronto_development_applications:APPLICATION2",
             "city": "Toronto", "address": "123 Example Avenue",
             "source_keys": "APPLICATION2",
             "description": "Other commercial warehouse expansion",
             "source_record_date": "2026-11-12",
             "record_source_url": "https://gis.toronto.ca/FeatureServer/60/query?where=APPLICATION2"},
        ])
        graph={
            "status": "PROJECT_COMPANY_MENTION_GRAPH_REVIEW_ONLY",
            "project_nodes": [{
                "node_id": "project:1", "project_id": "toronto_development_applications:APPLICATION1",
                "city": "Toronto"
            }],
            "organization_nodes": [{
                "node_id": "org:1",
                "organization_name_as_stated": "Example Industrial Holdings Ltd"
            }],
            "edges": [{
                "from_node": "project:1", "to_node": "org:1",
                "role_claimed": "PROPERTY_OWNER",
                "relationship": "PROJECT_ROLE_SOURCE_CLAIM",
                "evidence_origin": "AI_RESEARCH_EXACT_ID_SOURCE_LITERAL_REVIEW_ONLY",
                "source_url": "https://toronto.ca/project"
            }]
        }
        (self.root/GRAPH).write_text(json.dumps(graph), encoding="utf-8")
        bridge={"projects":[{
            "project_id": "toronto_development_applications:APPLICATION1",
            "city": "Toronto", "official_status": "OMB Approved",
            "holds": [{"reason": "AI_LIFECYCLE_CONTRADICTS_OFFICIAL_STATUS"}]
        }]}
        (self.root/BRIDGE).write_text(json.dumps(bridge), encoding="utf-8")
        report=build(self.root, today=TODAY)
        p={x["record_id"]: x for x in report["all_candidates"]}
        self.assertEqual(len(p["toronto_development_applications:APPLICATION1"]["exact_project_roles"]),1)
        self.assertEqual(p["toronto_development_applications:APPLICATION2"]["exact_project_roles"],[])
        self.assertEqual(p["toronto_development_applications:APPLICATION1"]["ai_conflicts"],
                         ["AI_LIFECYCLE_CONTRADICTS_OFFICIAL_STATUS"])
        self.assertEqual(p["toronto_development_applications:APPLICATION1"]["contact_email"], "")
        self.assertEqual(report["verified_buyers"], 0)

    def test_same_address_different_files_not_merged(self):
        self.csv(CLIENT,[
            self.candidate("A","Toronto","Warehouse expansion","2026-11-12",
                           address="same street",app="A1"),
            self.candidate("B","Toronto","Industrial manufacturing plant","2026-11-13",
                           address="same street",app="A2"),
        ])
        report=build(self.root, today=TODAY)
        self.assertEqual(len(report["all_candidates"]),2)

    def test_exact_application_duplicate_display_suppressed_not_rewritten(self):
        self.csv(CLIENT,[
            self.candidate("CLIENT-1","Toronto","New industrial warehouse expansion",
                           "2026-11-13",app="CITY-APP1"),
        ])
        self.csv(PRIVATE,[{
            "opportunity_id":"PRIVATE-1", "city":"Toronto",
            "address":"12 Example Avenue", "application_ids":"CITY-APP1",
            "nature_of_work":"Industrial warehouse construction",
            "source_urls":"https://toronto.ca/current-development-projects/CITY-APP1",
        }])
        report=build(self.root, today=TODAY)
        self.assertEqual(report["presentation_duplicates_suppressed"],1)
        self.assertEqual(report["deduplicated_review_candidates"],1)

    def test_prior_reports_are_penalized_not_called_new(self):
        self.csv(CLIENT, [
            self.candidate("OLD","Toronto","Manufacturing warehouse expansion","2026-11-14"),
            self.candidate("NEW","Brampton","Industrial warehouse expansion","2026-11-14"),
        ])
        self.csv(PREVIOUS,[{"opportunity_id":"OLD", "city":"Toronto"}])
        report=build(self.root,today=TODAY)
        self.assertEqual(report["top10"][0]["record_id"],"NEW")
        old=next(x for x in report["all_candidates"] if x["record_id"]=="OLD")
        self.assertTrue(old["was_previously_reported"])

    def test_outputs_without_paid_model_or_verified_leads(self):
        self.csv(CLIENT,[self.candidate("A","Brampton",
                    "Industrial equipment and cleanroom HVAC","2026-11-14")])
        result=run(self.root)
        self.assertEqual(result["status"],"COMMERCIAL_RESEARCH_QUEUE_NOT_SALES_QUALIFIED")
        self.assertTrue((self.root/TOP_OUT).exists())
        self.assertTrue((self.root/REPORT).exists())
        self.assertEqual(result["paid_ai_calls"],0)
        self.assertEqual(result["verified_open_supplier_contracts"],0)
        with (self.root/TOP_OUT).open(encoding="utf-8-sig",newline="") as f:
            row=list(csv.DictReader(f))[0]
        self.assertEqual(row["procurement_status"],"UNKNOWN_NOT_EVIDENCED")
        self.assertFalse(row["contact_email"])


class AdaptiveAIPriorityTests(unittest.TestCase):
    def test_priority_fresh_industrial_over_old_high_score_tower(self):
        old={"description":"New commercial residential condominium apartments 40 storeys",
             "source_record_date":"2023-01-01",
             "source_group":"MUNICIPAL_CHANGE","event_date":"2026-11-14",
             "source_id":"toronto_development_applications",
             "current_source_status":"Final Approval Completed","project_id":"A"}
        industrial={"description":"Industrial manufacturing warehouse expansion",
                    "source_record_date":"2026-11-12",
                    "source_id":"toronto_development_applications",
                    "current_source_status":"Under Review","project_id":"B"}
        self.assertLess(ai_key(industrial,{"score":40},TODAY),
                        ai_key(old,{"score":100},TODAY))

    def test_select_projects_uses_budget_independent_priority(self):
        rows=[
            {"project_id":"old", "address":"1 Old Road", "description":
             "New 30-storey residential rental condominium development and retail",
             "record_source_url":"https://toronto.ca/old",
             "source_id":"toronto_development_applications",
             "source_record_date":"2022-01-01",
             "current_source_status":"Final Approval Completed"},
            {"project_id":"fresh", "address":"2 New Road", "description":
             "New industrial manufacturing warehouse expansion 20000 sq ft",
             "record_source_url":"https://toronto.ca/fresh",
             "source_id":"toronto_development_applications",
             "source_record_date":"2026-11-13",
             "current_source_status":"Under Review"},
        ]
        eligible, result=select_projects(rows,today=TODAY)
        self.assertEqual(eligible[0][0]["project_id"],"fresh")
        self.assertGreaterEqual(result["eligible_for_paid_ai"],1)


if __name__=="__main__":
    unittest.main()
