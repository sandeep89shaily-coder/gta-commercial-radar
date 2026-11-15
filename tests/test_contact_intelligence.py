"""Offline regression of the full public-contact investigator.

Synthetic organizations only. No real DeepSeek/network spending. Test direct
source quotes, named people, public corporate channels, absent/private details,
provider failures, legacy budget and canonical worklist preservation.
"""
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

from gta_contact_intelligence import (
    _public_channels, _verified_people, _queries, _source_page,
    investigate, _rank_hits,
)

DAY = dt.date(2026, 11, 15)
ANNOUNCEMENT = (
    "Harbourlight Developments announced acquisition of Northfield Works "
    "in Brampton, Ontario, in partnership with Atlas Capital. "
    "The project is planned for a 90,000 square foot industrial condo site "
    "on Willow Drive. Construction anticipated to begin Q3 2027."
)
MODEL = {"projects": [{
    "project_name": "Northfield Works", "city": "Brampton",
    "location_text": "Willow Drive", "construction_timing": "Q3 2027",
    "claims": [
        {"kind": "developer", "subject": "Harbourlight Developments",
         "source_index": 0,
         "quote": "Harbourlight Developments announced acquisition of Northfield Works"},
        {"kind": "partner", "subject": "Atlas Capital",
         "source_index": 0,
         "quote": "in partnership with Atlas Capital"},
    ],
}]}
COMPANY_PAGE = (
    "Harbourlight Developments | Contact our team. "
    "General enquiries: office@harbourlight.example or call 416-555-0198. "
    "Director of Development: Morgan Reid. "
    "Morgan Reid, Director of Development, Harbourlight Developments, "
    "office@harbourlight.example. No appointment to a specific project stated."
)
OTHER_PAGE = (
    "Atlas Capital business office contact: info@atlascapital.example. "
    "Telephone 905-555-0154. Investor relations."
)
BAD_PAGE = (
    "Harbourlight Developments: do not send inquiries to the private address "
    "privateperson@gmail.com."
)


class ContactInvestigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        folder = self.root / "GTA_RADAR_INVESTMENT_DISCOVERY"
        folder.mkdir()
        report = {
            "city": "Brampton",
            "model_status": "OK",
            "source_pages": [{
                "url": "https://example.org/announcement",
                "content": ANNOUNCEMENT,
                "fetched_on_not_publication": DAY.isoformat(),
            }],
            "model_output_excerpt": json.dumps(MODEL),
            "discovered_projects": [{
                "project_name": "Northfield Works", "city": "Brampton",
                "location_text": "Willow Drive",
                "companies": [{"kind": "developer",
                               "subject": "Harbourlight Developments"}],
            }],
        }
        (folder / "INVESTMENT_original_RECONCILED.json").write_text(
            json.dumps(report), encoding="utf-8")
        self.early = self.root / "GTA_RADAR_EARLY_INVESTMENT_LEADS.csv"
        with self.early.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=[
                "project_name", "city", "developer", "verified_buyer",
                "verified_open_contract", "outreach_authorized"])
            writer.writeheader()
            writer.writerow({"project_name": "Northfield Works",
                             "city": "Brampton",
                             "developer": "Harbourlight Developments",
                             "verified_buyer": "false",
                             "verified_open_contract": "false",
                             "outreach_authorized": "false"})
            writer.writerow({"project_name": "Other Project",
                             "city": "Mississauga",
                             "developer": "Different Inc",
                             "verified_buyer": "false",
                             "verified_open_contract": "false",
                             "outreach_authorized": "false"})

    def test_preflight_does_not_invoke_deepseek(self):
        result = investigate(self.root, project_name="Northfield Works",
                             day=DAY)
        self.assertEqual(result["status"], "FREE_PREFLIGHT_NO_SPEND")
        self.assertEqual(result["search_calls"], 0)
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(len(result["company_coverage"]), 2)
        self.assertFalse((self.root / "v5_ai_budget.sqlite").exists())
        queries = _queries(result["project"])
        self.assertTrue(any("contact" in q for q in queries))
        self.assertTrue(any("procurement" in q for q in queries))
        self.assertTrue(any("Northfield Works" in q for q in queries))

    def test_all_contacts_fetched_and_cited_and_exported(self):
        calls = []
        def provider(endpoint, payload):
            calls.append(endpoint)
            if endpoint == "/v1/tools/search":
                return {"results": [
                    {"url": "https://harbourlight.example/contact",
                     "title": "Harbourlight Developments contact",
                     "snippet": "Harbourlight Developments team contact"},
                    {"url": "https://atlas.example/contact",
                     "title": "Atlas Capital official contact",
                     "snippet": "Atlas Capital investor relations"},
                ]}
            if endpoint == "/v1/tools/fetch":
                return {"content": (COMPANY_PAGE if
                    payload["url"] == "https://harbourlight.example/contact"
                    else OTHER_PAGE)}
            if endpoint == "/chat/completions":
                packet = json.loads(payload["messages"][1]["content"])
                self.assertEqual(len(packet["sources"]), 3)
                return {
                    "choices": [{"finish_reason": "stop", "message": {
                        "content": json.dumps({"contacts": [{
                            "company": "Harbourlight Developments",
                            "person": "Morgan Reid",
                            "job_title": "Director of Development",
                            "project_relationship": "",
                            "source_index": 1,
                            "quote": "Morgan Reid, Director of Development, Harbourlight Developments, office@harbourlight.example.",
                            "email": "office@harbourlight.example",
                            "phone": "",
                            "purchasing_authority": "UNKNOWN",
                        }]})}}],
                    "usage": {"prompt_tokens": 560, "completion_tokens": 125}}
            self.fail(endpoint)
        result = investigate(self.root, project_name="Northfield Works",
                             day=DAY, paid=True, token="fake", transport=provider)
        self.assertEqual(result["status"],
                         "NAMED_CONTACTS_AND_BUSINESS_CHANNELS_REVIEW")
        self.assertEqual(result["search_calls"], 8)
        self.assertEqual(result["fetch_calls"], 2)
        self.assertEqual(result["model_calls"], 1)
        self.assertEqual(result["people"][0]["person"], "Morgan Reid")
        self.assertEqual(result["people"][0]["job_title"],
                         "Director of Development")
        self.assertEqual(result["people"][0]["email"],
                         "office@harbourlight.example")
        self.assertEqual(result["people"][0]["purchasing_authority"], "UNKNOWN")
        # Generic office@ is a legitimate published company route, not
        # Morgan Reid's personally assigned direct email.
        self.assertFalse(result["people"][0]["direct_business_contact_verified"])
        self.assertTrue(result["people"][0]["public_channel_mentioned_with_person"])
        self.assertTrue(any(c["type"] == "PUBLIC_PHONE"
                            for c in result["public_channels"]))
        self.assertFalse(result["outreach_authorized"])
        with self.early.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        selected = [x for x in rows if x["project_name"] == "Northfield Works"][0]
        self.assertEqual(selected["contact_person"], "Morgan Reid")
        self.assertEqual(selected["contact_public_business_email"],
                         "office@harbourlight.example")
        self.assertEqual(selected["verified_buyer"], "false")
        self.assertEqual(selected["outreach_authorized"], "false")
        self.assertEqual(len(rows), 2)
        old = [x for x in rows if x["project_name"] == "Other Project"][0]
        self.assertEqual(old["developer"], "Different Inc")
        again = investigate(self.root, project_name="Northfield Works",
                            day=DAY, paid=True, token="fake",
                            transport=lambda *_: self.fail("Never pay twice"))
        self.assertTrue(again["checkpoint_reused"])

    def test_http_error_fetch_is_preserved_and_other_pages_continue(self):
        def provider(endpoint, payload):
            if endpoint == "/v1/tools/search":
                return {"results": [
                    {"url": "https://harbourlight.example/broken",
                     "title": "Harbourlight Developments contacts",
                     "snippet": "Harbourlight Developments contact"},
                    {"url": "https://atlas.example/contact",
                     "title": "Atlas Capital contact",
                     "snippet": "Atlas Capital investor relations"},
                ]}
            if endpoint == "/v1/tools/fetch":
                if payload["url"].endswith("broken"):
                    raise HTTPError(payload["url"], 403, "Forbidden", None, None)
                return {"content": OTHER_PAGE}
            if endpoint == "/chat/completions":
                return {"choices": [{"finish_reason": "stop", "message": {
                    "content": json.dumps({"contacts": []})}}],
                    "usage": {"prompt_tokens": 400, "completion_tokens": 60}}
            self.fail(endpoint)
        result = investigate(self.root, project_name="Northfield Works",
                             day=DAY, paid=True, token="fake", transport=provider)
        self.assertEqual(len(result["fetch_failures"]), 1)
        self.assertEqual(result["fetch_failures"][0]["status"],
                         "UNCERTAIN_HTTPError")
        self.assertEqual(result["model_calls"], 1)
        self.assertEqual(len(result["public_channels"]), 2)
        self.assertFalse(result["outreach_authorized"])

    def test_gmail_and_invented_person_contact_are_rejected(self):
        src = _source_page("https://harbourlight.example/contact", BAD_PAGE,
                           ["Harbourlight Developments"], "Northfield Works", DAY)
        self.assertEqual(_public_channels([src], [
            "Harbourlight Developments"]), [])
        validated = _verified_people({
            "contacts": [
                {"company": "Harbourlight Developments",
                 "person": "Invented Name", "job_title": "Project Director",
                 "source_index": 0,
                 "quote": "Harbourlight Developments: do not send inquiries",
                 "email": "invented@harbourlight.example"},
            ]}, [src], ["Harbourlight Developments"])
        self.assertEqual(validated, [])

    def test_official_corporate_domain_contact_page_with_brand_only(self):
        companies = ["Harbourlight Developments"]
        hits = _rank_hits({"results": [{
            "url": "https://www.harbourlightdevelopments.ca/contact",
            "title": "Contact us", "snippet": "Get in touch with our team"}]},
            companies, "Northfield Works")
        self.assertEqual(hits, [
            "https://www.harbourlightdevelopments.ca/contact"])
        page = _source_page(
            hits[0], "Harbourlight contact. Office enquiries: "
            "info@harbourlightdevelopments.ca or 416-555-0145.",
            companies, "Northfield Works", DAY)
        self.assertIsNotNone(page)
        self.assertEqual(page["companies_mentioned"], companies)
        channels = _public_channels([page], companies)
        self.assertEqual(len(channels), 2)
        self.assertTrue(all(not x["project_purchasing_role_verified"]
                            for x in channels))

    def test_public_phone_not_treated_as_personal_procurement_direct_line(self):
        src = _source_page(
            "https://harbourlight.example/contact", COMPANY_PAGE,
            ["Harbourlight Developments"], "Northfield Works", DAY)
        channels = _public_channels([src], ["Harbourlight Developments"])
        self.assertTrue(any(x["value"] == "416-555-0198" for x in channels))
        self.assertTrue(all(not x["assigned_to_named_person"] and
                            not x["project_purchasing_role_verified"]
                            for x in channels))

    def test_masked_sales_vendor_emails_and_sample_formats_are_rejected(self):
        source = _source_page(
            "https://www.signalhire.com/companies/fiera-real-estate",
            "Fiera Real Estate: Contact employees. "
            "h*****************c@uqtr.ca k*********k@fierarealestate.com "
            "m******i@brampton.ca.",
            ["Fiera Real Estate"], "Ace Brampton", DAY)
        channels = _public_channels([source], ["Fiera Real Estate"])
        self.assertEqual(channels, [])
        sample = _source_page(
            "https://www.neverbounce.com/company/fiera-real-estate",
            "Fiera Real Estate Contact email pattern (ex. "
            "John.Smith@fierarealestate.com) and JSmith@fierarealestate.com. "
            "First.Last@fierarealestate.com",
            ["Fiera Real Estate"], "Ace Brampton", DAY)
        self.assertEqual(_public_channels([sample], ["Fiera Real Estate"]), [])

    def test_crunchbase_joined_contact_email_is_normalized(self):
        page = _source_page(
            "https://www.crunchbase.com/organization/fiera-real-estate",
            "Fiera Real Estate Contact Emailinfo@fierarealestate.com "
            "Phone Number844-431-7684",
            ["Fiera Real Estate"], "Ace Brampton", DAY)
        channels = _public_channels([page], ["Fiera Real Estate"])
        self.assertEqual({x["value"] for x in channels},
                         {"info@fierarealestate.com", "844-431-7684"})
        self.assertTrue(all(x["needs_live_business_verification"] for x in channels))

    def test_reconcile_saved_contact_report_without_api_calls(self):
        from gta_contact_intelligence import reconcile_saved, _save
        old = investigate(self.root, project_name="Northfield Works", day=DAY)
        old["status"] = "NAMED_CONTACTS_AND_BUSINESS_CHANNELS_REVIEW"
        old["evidence"].append(_source_page(
            "https://www.crunchbase.com/organization/harbourlight",
            "Harbourlight Developments Contact Emailinfo@harbourlightdevelopments.ca "
            "Phone Number416-555-0149",
            ["Harbourlight Developments"], "Northfield Works", DAY))
        old["public_channels"] = [{
            "company": "Harbourlight Developments",
            "type": "PUBLIC_EMAIL", "value": "Emailinfo@harbourlightdevelopments.ca",
            "source_url": "https://www.crunchbase.com/organization/harbourlight",
            "literal_quote": "Contact Emailinfo@harbourlightdevelopments.ca"}]
        _save(Path(old["report_path"]), old)
        result = reconcile_saved(
            self.root, project_name="Northfield Works", city="Brampton")
        self.assertEqual(result["paid_calls_during_reconciliation"], 0)
        self.assertIn("info@harbourlightdevelopments.ca",
                      [x["value"] for x in result["public_channels"]])
        self.assertNotIn("Emailinfo@harbourlightdevelopments.ca",
                         [x["value"] for x in result["public_channels"]])
        original = json.loads(Path(old["report_path"]).read_text())
        self.assertEqual(original["public_channels"][0]["value"],
                         "Emailinfo@harbourlightdevelopments.ca")
        self.assertFalse((self.root / "v5_ai_budget.sqlite").exists())

    def test_unknown_project_does_not_query_paid_provider(self):
        with self.assertRaisesRegex(ValueError,
                                    "EXACT_CITED_DISCOVERY_NOT_FOUND"):
            investigate(self.root, project_name="Someone Else",
                        day=DAY, paid=True, token="fake",
                        transport=lambda *_: self.fail("No paid calls"))


if __name__ == "__main__":
    unittest.main()
