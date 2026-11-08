"""Exact-ID company role hints can NEVER become verified buyers by inference."""
from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import gta_facility_intelligence as graph
import gta_facility_role_review as role


def ev(project="toronto_active_building_permits:26 246271",
       event_id="evt-1", source_family="radar"):
    return {"event_id":event_id,"source_family":source_family,
            "project_id":project,"source_id":"toronto_active_building_permits",
            "source_record_id":project}


def opp(project="toronto_active_building_permits:26 246271",
        organization="Scrivener Square Nominee Inc",
        confidence="EXACT_LOCAL_COLLECTOR"):
    return {
        "project_id":project,
        "operator":organization,
        "project_identity_confidence":confidence,
        "official_record_url":"https://open.toronto.ca/dataset/building-permits-active-permits/",
        "official_verification_level":"COLLECTOR_SOURCE_MATCH",
        "contact":"unverified@test.example", # MUST NOT be exported or authorized
        "contact_source_url":"https://other.example",
    }


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        w.writeheader();w.writerows(rows)


class ExactProjectRoleReviewTests(unittest.TestCase):
    def test_exact_project_role_name_stays_unverified(self):
        rows,status=role.exact_role_hints([ev()],[opp()])
        self.assertEqual(len(rows),1)
        self.assertEqual(status["exact_project_ids_with_research_row"],1)
        r=rows[0]
        self.assertEqual(r["organization_name_claimed"],"Scrivener Square Nominee Inc")
        self.assertEqual(r["record_identity_match"],"EXACT_LOCAL_PROJECT_ID_ONLY")
        self.assertEqual(r["role_type_claimed"],"OPERATOR_RESEARCH_HINT")
        self.assertEqual(r["buyer_verified"],"NO")
        self.assertEqual(r["company_role_verified"],"NO")
        self.assertEqual(r["procurement_verified"],"NO")
        self.assertEqual(r["public_contact_verified"],"NO")
        self.assertNotIn("unverified@test.example",str(r))
        self.assertNotIn("other.example",str(r))

    def test_address_similarity_without_exact_project_id_never_joins(self):
        rows,counts=role.exact_role_hints([ev()],[opp(project="other:12345")])
        self.assertEqual(rows,[])
        self.assertEqual(counts["research_rows_without_exact_project_match"],1)

    def test_weak_record_identity_is_excluded_despite_matching_project_id(self):
        for confidence in ("ADDRESS_CONTEXT_ONLY","ADDRESS_MATCH_ONLY",
                           "UNVERIFIED_IDENTITY"):
            with self.subTest(confidence=confidence):
                rows,counts=role.exact_role_hints([ev()],[opp(confidence=confidence)])
                self.assertEqual(rows,[])
                self.assertEqual(counts["research_rows_with_weak_identity_excluded"],1)

    def test_ambiguous_names_and_null_placeholders_do_not_create_roles(self):
        for name in ("", "N/A", "unknown", "None", "99999", "x"*220):
            with self.subTest(name=name):
                rows,counts=role.exact_role_hints([ev()],[opp(organization=name)])
                self.assertEqual(rows,[])
                self.assertEqual(counts["project_ids_with_role_claims"],0)

    def test_no_role_claims_from_pilot_site_only_context(self):
        rows,counts=role.exact_role_hints([
            ev(source_family="industrial",event_id="ind-1")],[opp()])
        self.assertEqual(rows,[])
        self.assertEqual(counts["exact_project_ids_in_graph"],0)

    def test_evidence_link_does_not_alone_verify_company_role(self):
        row=opp()
        row.update({"company_owner":"Example Holdings Inc",
                    "company_tenant":"Example Clinic",
                    "official_verification_level":"OFFICIAL_ID_AND_STATUS_MATCH"})
        rows,_=role.exact_role_hints([ev()],[row])
        self.assertEqual(len(rows),3)
        self.assertTrue(all(x["company_role_verified"]=="NO" for x in rows))
        self.assertTrue(all(x["role_document_quote_present"]=="NO" for x in rows))
        self.assertTrue(all(x["official_record_url_reference"].startswith("https://")
                            for x in rows))

    def test_duplicate_role_claims_from_same_project_are_suppressed(self):
        rows,_=role.exact_role_hints([ev()],[opp(),opp()])
        self.assertEqual(len(rows),1)

    def test_malformed_untrusted_url_is_suppressed(self):
        row=opp()
        row["official_record_url"]="https://admin:secret@open.toronto.ca/records"
        rows,_=role.exact_role_hints([ev()],[row])
        self.assertEqual(rows[0]["official_record_url_reference"],"")
        self.assertEqual(rows[0]["buyer_verified"],"NO")

    def test_missing_optional_role_research_file_reports_gap(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);g=root/"graph";out=root/"role"
            write_csv(g/graph.OUTPUT_EVENTS,[ev()],graph.EVENT_FIELDS)
            s=role.run(g,root/"NOT_PRESENT.csv",out)
            self.assertEqual(s["role_hints"],0)
            self.assertEqual(s["research_export_status"],
                             "RESEARCH_EXPORT_MISSING_NO_ROLE_CLAIMS")
            self.assertEqual(s["verified_purchasing_authorities"],0)
            self.assertTrue((out/role.OUT_CSV).is_file())

    def test_end_to_end_role_ledger_preserves_source_export(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);g=root/"graph";out=root/"role"
            opp_file=root/"GTA_RADAR_PROJECT_OPPORTUNITIES.csv"
            write_csv(g/graph.OUTPUT_EVENTS,[ev()],graph.EVENT_FIELDS)
            write_csv(opp_file,[opp(),opp(project="unrelated:123")],
                      ("project_id","operator","project_identity_confidence",
                       "official_record_url","official_verification_level",
                       "contact","contact_source_url"))
            before=opp_file.read_bytes()
            status=role.run(g,opp_file,out)
            self.assertEqual(status["research_rows_read"],2)
            self.assertEqual(status["role_hints"],1)
            self.assertEqual(status["research_rows_without_exact_project_match"],1)
            self.assertEqual(status["verified_company_roles"],0)
            self.assertEqual(before,opp_file.read_bytes())
            with (out/role.OUT_CSV).open(encoding="utf-8-sig",newline="") as f:
                record=next(csv.DictReader(f))
            self.assertEqual(record["organization_name_claimed"],"Scrivener Square Nominee Inc")
            self.assertEqual(record["buyer_verified"],"NO")

    def test_corrupted_research_schema_fails_instead_of_guessing_roles(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);g=root/"graph";out=root/"role"
            write_csv(g/graph.OUTPUT_EVENTS,[ev()],graph.EVENT_FIELDS)
            file=root/"opportunities.csv";file.write_text("address,operator\n100 Queen,Example\n")
            with self.assertRaisesRegex(ValueError,"Unexpected project-opportunities schema"):
                role.run(g,file,out)
            self.assertFalse(out.exists())


if __name__=="__main__":
    unittest.main()
