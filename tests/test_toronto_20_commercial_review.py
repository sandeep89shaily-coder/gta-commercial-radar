"""Commercial review must never convert a source permit into a sales-ready buyer."""
import tempfile
import unittest
from pathlib import Path

import gta_toronto_20_commercial_review as module


def record(i, status="Application Acceptable", cost=500000):
    return {
        "project_id":f"toronto_active_building_permits:26 {260000+i:06}",
        "permit_key":f"26 {260000+i:06} BLD|00",
        "civic_site":f"{100+i} yonge st",
        "source_status":status,
        "city_scope":"Commercial interior alterations to office",
        "city_estimated_cost_cad":cost,
        "source_url":"https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search",
        "exact_ckan_identity_verified":True,
        "archived_civic_address_compatible":True,
    }


class CommercialDossierResearchTests(unittest.TestCase):
    def setUp(self):
        self.scopes=[record(i) for i in range(20)]

    def test_twenty_verified_source_records_zero_buyers_or_contracts(self):
        results,contacts,excluded=module.build(self.scopes,[])
        self.assertEqual(len(results),20)
        self.assertEqual(len(contacts),0)
        self.assertTrue(all(x["project_buyer_verified"]=="NO" for x in results))
        self.assertTrue(all(x["available_supplier_contract_verified"]=="NO" for x in results))
        self.assertTrue(all(x["outreach_authorized"]=="NO" for x in results))
        self.assertTrue(all("PROCUREMENT_STATUS_NOT_VERIFIED" in
                            x["qualification_blockers"] for x in results))

    def test_refusal_status_is_held_even_with_large_budget_and_manager(self):
        self.scopes[0]["source_status"]="Refusal Notice"
        self.scopes[0]["city_estimated_cost_cad"]=60000000
        results,_,_=module.build(self.scopes,[])
        blocked=next(x for x in results if x["project_id"]==self.scopes[0]["project_id"])
        self.assertEqual(blocked["qualification_category"],"HOLD_SOURCE_STATUS")
        self.assertEqual(blocked["research_priority"],4)
        self.assertIn("BLOCKED_MUNICIPAL_PERMIT_STAGE",blocked["qualification_blockers"])

    def test_issued_stage_cannot_prove_open_bid(self):
        self.scopes[0]["source_status"]="Permit Issued"
        result,_,_=module.build(self.scopes,[])
        issued=next(x for x in result if x["project_id"]==self.scopes[0]["project_id"])
        self.assertEqual(issued["qualification_category"],"ISSUED_AWARD_RISK")
        self.assertEqual(issued["available_supplier_contract_verified"],"NO")
        self.assertIn("POSSIBLE_ALREADY_AWARDED",issued["qualification_blockers"])

    def test_placeholder_construction_value_not_treated_as_amount(self):
        self.scopes[0]["city_estimated_cost_cad"]="DO NOT UPDATE OR DELETE THIS INFO FIELD"
        records,_,_=module.build(self.scopes,[])
        row=next(x for x in records if x["project_id"]==self.scopes[0]["project_id"])
        self.assertIsNone(row["estimated_construction_cost_cad"])
        self.assertIn("NO_VALID_NUMERIC_CITY_COST",row["qualification_blockers"])

    def test_site_similar_but_different_project_does_not_get_contacts(self):
        c={"project_id":"toronto_active_building_permits:OTHER",
           "site_address":"100 yonge st","organization":"Example",
           "primary_evidence_url":"https://example.com"}
        rows,routes,excluded=module.build(self.scopes,[c])
        self.assertEqual(len(routes),0)
        self.assertEqual(excluded["NO_EXACT_PROJECT_ID"],1)
        self.assertTrue(all(x["organization_association"]=="" for x in rows))

    def test_exact_id_but_wrong_address_is_rejected(self):
        c={"project_id":self.scopes[0]["project_id"],
           "site_address":"999 different street","organization":"Example",
           "primary_evidence_url":"https://example.com"}
        rows,routes,excluded=module.build(self.scopes,[c])
        self.assertEqual(len(routes),0)
        self.assertEqual(excluded["ADDRESS_MISMATCH"],1)

    def test_only_https_first_party_claim_remains_unverified_even_when_exact_site(self):
        c={"project_id":self.scopes[0]["project_id"],
           "site_address":"100 yonge st","organization":"Example Property Management",
           "public_contact_name":"Example Office",
           "public_business_email":"info@example.com",
           "primary_evidence_url":"https://example.com/buildings/100yonge",
           "contact_role_type":"PROPERTY_MANAGEMENT_CONTACT",
           "project_specific_purchasing_authority_verified":True,
           "open_supplier_package_verified":True,
           "outreach_authorized":True}
        rows,routes,excluded=module.build(self.scopes,[c])
        self.assertEqual(len(routes),1)
        self.assertFalse(routes[0]["project_specific_purchasing_authority_verified"])
        self.assertFalse(routes[0]["open_supplier_package_verified"])
        self.assertFalse(routes[0]["outreach_authorized"])
        linked=next(x for x in rows if x["project_id"]==self.scopes[0]["project_id"])
        self.assertEqual(linked["project_buyer_verified"],"NO")
        self.assertEqual(linked["available_supplier_contract_verified"],"NO")
        self.assertEqual(linked["outreach_authorized"],"NO")

    def test_invalid_url_rejected_even_with_matching_site_and_id(self):
        c={"project_id":self.scopes[0]["project_id"],
           "site_address":"100 yonge st","organization":"Example",
           "primary_evidence_url":"javascript:alert(1)"}
        _,contacts,excluded=module.build(self.scopes,[c])
        self.assertEqual(contacts,[])
        self.assertEqual(excluded["INVALID_OR_UNTRUSTED_CONTACT_URL"],1)

    def test_duplicate_or_missing_city_scope_identity_is_refused(self):
        invalid=list(self.scopes)
        invalid[0]=dict(invalid[1])
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            module.build(invalid,[])
        invalid=list(self.scopes)
        invalid[0]=dict(invalid[0],archived_civic_address_compatible=False)
        with self.assertRaisesRegex(ValueError,"Unverified"):
            module.build(invalid,[])

    def test_real_commit_data_produces_noncommercial_research_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            status=module.run(out=p)
            self.assertEqual(status["original_city_source_checked_permit_count"],20)
            self.assertEqual(status["numeric_city_construction_estimates"],14)
            self.assertEqual(status["public_business_routes_with_site_match"],9)
            self.assertEqual(status["projects_with_public_business_routes"],8)
            self.assertEqual(status["project_buyers_verified"],0)
            self.assertEqual(status["open_supplier_packages_verified"],0)
            self.assertFalse(status["outreach_authorized"])
            self.assertTrue((p/module.OUTPUT).is_file())
            self.assertTrue((p/module.CONTACT_OUTPUT).is_file())
            self.assertTrue((p/module.STATUS_OUTPUT).is_file())


if __name__=="__main__":
    unittest.main()
