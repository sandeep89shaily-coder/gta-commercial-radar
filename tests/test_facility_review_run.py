"""Integration tests: one manual graph + dossier run, no collector or schedule."""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import gta_facility_review_run as runner
import gta_facility_intelligence as graph
import gta_facility_dossiers as dossier


def daily_csv(path, rows):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        fields=("project_id","observation","source_id","source_keys","city","address",
                "description","source_record_date","first_seen_local",
                "record_source_url","current_source_status")
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader();w.writerows(rows)


class ManualReviewRunnerTests(unittest.TestCase):
    def test_no_source_export_refuses_zero_leads_report(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)
            with self.assertRaisesRegex(FileNotFoundError,"No existing Radar or pilot"):
                runner.execute(results=p)
            self.assertFalse((p/"FACILITY_DOSSIER_PILOT").exists())

    def test_nonexistent_results_path_refuses_to_create_empty_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"absent"
            with self.assertRaisesRegex(FileNotFoundError,"Existing Radar results folder missing"):
                runner.execute(results=p)
            self.assertFalse(p.exists())

    def test_offline_end_to_end_writes_separate_outputs_and_keeps_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);results=root/"GTA_RADAR_RESULTS";results.mkdir()
            csv_path=results/"GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv"
            daily_csv(csv_path,[{
                "project_id":"brampton_building_permits:26-183257-000-00",
                "observation":"FIRST_OBSERVED",
                "source_id":"brampton_building_permits","city":"Peel",
                "address":"7535 Financial Dr, Brampton, ON,",
                "description":"Alteration (Renovation) F2: Industrial",
                "source_record_date":"2026-11-06",
                "first_seen_local":"2026-11-07",
                "record_source_url":"https://maps1.brampton.ca/arcgis/rest/services/BuildingPermit/Building_Permits/FeatureServer/0/query?where=PERMITNUMBER",
                "current_source_status":"Permit Issued",
            }])
            role_file=results/"GTA_RADAR_PROJECT_OPPORTUNITIES.csv"
            with role_file.open("w",encoding="utf-8-sig",newline="") as f:
                fields=("project_id","operator","project_identity_confidence",
                        "official_record_url","official_verification_level")
                w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
                w.writerow({"project_id":"brampton_building_permits:26-183257-000-00",
                            "operator":"Hypothetical Facility Inc.",
                            "project_identity_confidence":"EXACT_LOCAL_COLLECTOR",
                            "official_record_url":"https://maps1.brampton.ca/",
                            "official_verification_level":"COLLECTOR_SOURCE_MATCH"})
            before=csv_path.read_bytes()
            role_before=role_file.read_bytes()
            output=runner.execute(results=results,as_of="2026-11-08")
            self.assertEqual(output["source_rows_read"]["radar"],1)
            self.assertEqual(output["graph_site_identities"],1)
            self.assertEqual(output["research_dossiers"],1)
            self.assertGreater(output["manual_evidence_tasks"],0)
            self.assertFalse(output["new_records_published_claimed"])
            self.assertFalse(output["outreach_authorized"])
            self.assertEqual(output["verified_open_supplier_contracts"],0)
            self.assertEqual(output["toronto_constituent_permit_keys_found"],0)
            self.assertEqual(output["toronto_exact_local_permit_payloads_matched"],0)
            self.assertEqual(output["toronto_permit_audit_status"],
                             "NO_TORONTO_PERMITS_IN_EXISTING_EXPORT")
            self.assertEqual(output["toronto_saved_live_source_records"],0)
            self.assertFalse(output["toronto_source_sample_gate_passed"])
            self.assertFalse(output["toronto_commercial_production_accepted"])
            self.assertEqual(output["toronto_dossiers_with_exact_city_permit_evidence"],0)
            self.assertEqual(output["toronto_permit_stage_disagreements_requiring_review"],0)
            self.assertTrue((results/"FACILITY_DOSSIER_PILOT"/
                             "GTA_RADAR_TORONTO_DOSSIER_SOURCE_EVIDENCE.csv").is_file())
            self.assertTrue((results/"TORONTO_PERMIT_EVIDENCE_PILOT"/
                             "GTA_RADAR_TORONTO_PERMIT_EVIDENCE_STATUS.json").is_file())
            self.assertEqual(output["unverified_company_role_hints"],1)
            self.assertEqual(output["role_hints_verified"],0)
            self.assertEqual(output["authorized_application_identity_overlay"],
                             "ASSISTED_OFFICIAL_EXPORT_MISSING")
            self.assertEqual(output["authorized_application_roles_verified"],0)
            self.assertEqual(csv_path.read_bytes(),before)
            self.assertEqual(role_file.read_bytes(),role_before)
            self.assertTrue((results/"FACILITY_INTELLIGENCE_PILOT"/graph.OUTPUT_EVENTS).is_file())
            report=(results/"FACILITY_DOSSIER_PILOT"/dossier.REPORT_STATUS)
            self.assertTrue(report.is_file())
            self.assertEqual(json.loads(report.read_text())["verified_buyers"],0)
            with (results/"FACILITY_DOSSIER_PILOT"/dossier.DOSSIERS_CSV).open(
                    encoding="utf-8-sig",newline="") as f:
                row=next(csv.DictReader(f))
            self.assertEqual(row["city"],"Brampton")
            self.assertEqual(row["source_event_date"],"2026-11-06")
            self.assertEqual(row["outreach_authorized"],"NO")

    def test_authorized_roles_overlay_reconciles_only_exact_id_and_site(self):
        with tempfile.TemporaryDirectory() as temp:
            results=Path(temp)
            daily_csv(results/"GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv", [{
                "project_id":"sample:site","observation":"FIRST_OBSERVED",
                "source_id":"brampton_building_permits","city":"Brampton",
                "address":"7535 Financial Drive",
                "description":"Review-only unrelated site",
                "source_record_date":"2026-11-03","first_seen_local":"2026-11-04",
                "current_source_status":"Permit Issued",
            }])
            imported=results/"GTA_RADAR_OFFICIAL_CSV_IMPORT_APPLICATIONS.csv"
            official=results/"GTA_RADAR_ADDITIONAL_CITY_GIS_APPLICATIONS.csv"
            with imported.open("w",encoding="utf-8-sig",newline="") as fp:
                row={
                    "city":"Kitchener","application_id":"ZBA-26-018",
                    "address":"100 King Street","project_id":"OFFICIAL_EXPORT:KITCHENER:ZBA-26-018",
                    "source_url":"https://www.arcgis.com/home/item.html?id=one",
                    "provenance":"USER_SUPPLIED_OFFICIAL_EXPORT_NOT_INDEPENDENTLY_AUTHENTICATED",
                    "applicant_name_unverified":"Factory Example Ltd",
                }
                writer=csv.DictWriter(fp,fieldnames=list(row))
                writer.writeheader();writer.writerow(row)
            with official.open("w",encoding="utf-8-sig",newline="") as fp:
                row={
                    "city":"Kitchener","application_id":"ZBA-26-018",
                    "address":"100 King St","project_id":"GIS:KITCHENER:ZBA-26-018",
                }
                writer=csv.DictWriter(fp,fieldnames=list(row))
                writer.writeheader();writer.writerow(row)
            originals=(imported.read_bytes(),official.read_bytes())
            report=runner.execute(results=results,as_of="2026-11-10")
            self.assertEqual(report["authorized_application_role_candidates_review_only"],1)
            self.assertEqual(report["authorized_application_role_holds"],0)
            self.assertEqual(report["authorized_application_roles_verified"],0)
            self.assertTrue(Path(report["authorized_application_role_review_csv"]).is_file())
            self.assertEqual((imported.read_bytes(),official.read_bytes()),originals)
            self.assertEqual(report["buyers_verified"],0)
            self.assertFalse(report["outreach_authorized"])

    def test_invalid_reference_date_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            daily_csv(root/"GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv",[])
            with self.assertRaises(ValueError):
                runner.execute(results=root,as_of="2026-11-99")
            self.assertFalse((root/"FACILITY_DOSSIER_PILOT").exists())

if __name__ == "__main__":
    unittest.main()
