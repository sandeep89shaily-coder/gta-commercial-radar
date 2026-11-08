"""Commercial qualification must not turn site contacts into permit buyers."""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import gta_commercial_site_qualification as q
import gta_facility_dossiers as dossier

BASE=Path(__file__).resolve().parents[1]


def sample(project="toronto_active_building_permits:26 265861",
           address="568 passmore ave",stage="Not Started",
           status="RESEARCH_SIGNAL_ONLY_NOT_VERIFIED_LEAD"):
    return {
      "source_record_id":project,
      "source_id":"toronto_active_building_permits",
      "site_address":address,
      "dossier_id":"example-dossier",
      "source_stage":stage,
      "commercial_readiness":status,
      "source_url":"https://www.toronto.ca/",
      "source_event_date":"2026-11-05",
      "source_lookup_key":"26 265861 BLD|00",
      "source_url_quality":"DATASET_OR_PORTAL_REFERENCE_NOT_INDIVIDUAL_VERIFICATION"
    }


def output(folder,items):
    p=folder/"dossiers.csv"
    with p.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(items[0]))
        w.writeheader();w.writerows(items)
    return p


class CommercialQualificationTests(unittest.TestCase):
    def test_researched_20_site_file_has_unique_exact_identifiers_and_no_buyer_claims(self):
        evidence=q.load_research(q.DEFAULT_RESEARCH)
        self.assertEqual(len(evidence),20)
        self.assertTrue(all(x["verified_buyer_for_permit"] is False
                            and x["verified_open_work"] is False for x in evidence.values()))
        self.assertTrue(all(x.get("verified_for_project_procurement") is False
                            for x in evidence.values()))
        self.assertTrue(all(x["human_review_status"]=="SOURCE_BACKED_SITE_CONTEXT_ONLY"
                            for x in evidence.values()))

    def test_identifiable_property_contact_is_not_a_specific_buyer(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)
            status=q.run(output(p,[sample()]),out=p/"out")
            self.assertEqual(status["toronto_permit_dossiers"],1)
            self.assertEqual(status["exact_project_and_civic_site_matches"],1)
            with (p/"out"/q.OUTPUT_CSV).open(encoding="utf-8-sig",newline="") as f:
                row=next(csv.DictReader(f))
            self.assertEqual(row["company_or_property_org"],"Beedie")
            self.assertEqual(row["public_business_contact_email"],
                             "newton.leung@colliers.com")
            self.assertEqual(row["contact_is_verified_permit_buyer"],"NO")
            self.assertEqual(row["vendor_work_package_verified"],"NO")
            self.assertEqual(row["procurement_open_verified"],"NO")
            self.assertEqual(row["outreach_authorized"],"NO")

    def test_matching_project_id_with_other_address_never_joins_company(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)
            status=q.run(output(p,[sample(address="568 Fake St")]),out=p/"out")
            self.assertEqual(status["exact_project_and_civic_site_matches"],0)
            self.assertEqual(status["rows_without_exact_site_match"][
                             "EXACT_PROJECT_ID_WITH_DIFFERENT_CIVIC_SITE"],1)
            with (p/"out"/q.OUTPUT_CSV).open(encoding="utf-8-sig",newline="") as f:
                row=next(csv.DictReader(f))
            self.assertEqual(row["company_or_property_org"],"")
            self.assertEqual(row["public_business_contact_email"],"")
            self.assertEqual(row["outreach_authorized"],"NO")

    def test_refusal_notice_ranks_as_hold_not_a_lead(self):
        d=sample(project="toronto_active_building_permits:26 263884",
                 address="29 jutland rd",stage="Refusal Notice")
        priority,action=q.classify(d,q.load_research(q.DEFAULT_RESEARCH)[d["source_record_id"]])
        self.assertEqual(priority,"HOLD_PERMIT_NOT_MARKETABLE")
        self.assertIn("Recheck current City status",action)

    def test_multi_tenant_civic_address_blocks_tenant_inference(self):
        d=sample(project="toronto_active_building_permits:26 245005",
                 address="45 wicksteed ave",stage="Permit Issued")
        research=q.load_research(q.DEFAULT_RESEARCH)[d["source_record_id"]]
        priority,_=q.classify(d,research)
        self.assertEqual(priority,"MULTI_TENANT_SITE_UNIT_UNKNOWN")
        self.assertEqual(research["organization"],"")

    def test_public_procurement_route_not_specific_permit_contract(self):
        d=sample(project="toronto_active_building_permits:26 262684",
                 address="250 front st w",stage="Permit Issued")
        research=q.load_research(q.DEFAULT_RESEARCH)[d["source_record_id"]]
        priority,action=q.classify(d,research)
        self.assertEqual(priority,"GENERAL_PROCUREMENT_ROUTE_NOT_ACTIVE_CONTRACT")
        self.assertIn("official supplier registration",action)
        self.assertEqual(research["contact_email"],"supplym@cbc.ca")

    def test_missing_source_or_unexpected_schema_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)
            with self.assertRaises(FileNotFoundError):
                q.run(p/"not-found.csv",out=p/"out")
            source=p/"wrong.csv"
            source.write_text("address,company\n100 King,example\n")
            with self.assertRaisesRegex(ValueError,"Incompatible source-dossier schema"):
                q.run(source,out=p/"out")

    def test_json_research_cannot_inject_verified_buyers_or_malformed_urls(self):
        base=json.loads(q.DEFAULT_RESEARCH.read_text())
        for field,value in (
            ("verified_buyer_for_permit",True),
            ("verified_open_work",True),
            ("verified_for_project_procurement",True),
            ("source_url","javascript:alert(1)"),
            ("research_as_of","yesterday"),
        ):
            with self.subTest(field=field):
                content=json.loads(json.dumps(base))
                content["rows"][0][field]=value
                with tempfile.TemporaryDirectory() as root:
                    path=Path(root)/"research.json"
                    path.write_text(json.dumps(content),encoding="utf-8")
                    with self.assertRaises(ValueError):
                        q.load_research(path)

    def test_twenty_site_records_cannot_cause_contact_outreach(self):
        research=q.load_research(q.DEFAULT_RESEARCH)
        examples=[]
        for project,r in research.items():
            status="Refusal Notice" if project.endswith("26 263884") else "Permit Issued"
            examples.append(sample(project=project,address=r["site_address"],stage=status))
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)
            src=output(p,examples);old=src.read_bytes()
            s=q.run(src,out=p/"out")
            self.assertEqual(s["toronto_permit_dossiers"],20)
            self.assertEqual(s["exact_project_and_civic_site_matches"],20)
            self.assertEqual(s["verified_open_supplier_contracts"],0)
            self.assertEqual(s["verified_permit_buyers"],0)
            self.assertFalse(s["outreach_authorized"])
            self.assertEqual(src.read_bytes(),old)
            with (p/"out"/q.OUTPUT_CSV).open(encoding="utf-8-sig",newline="") as f:
                data=list(csv.DictReader(f))
            self.assertEqual(len(data),20)
            self.assertEqual({x["outreach_authorized"] for x in data},{"NO"})
            self.assertEqual(sum(x["permit_status_held"]=="YES" for x in data),1)
            self.assertTrue(all(x["contact_is_verified_permit_buyer"]=="NO" for x in data))

if __name__=="__main__":
    unittest.main()
