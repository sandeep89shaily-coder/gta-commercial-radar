"""Toronto official AIC metadata + document-link enrichment, mock-only tests."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
from unittest.mock import patch

import gta_toronto_aic_enrichment as aic
import gta_24_city_combined as combined

AIC_PAGE="https://www.toronto.ca/city-government/planning-development/application-information-centre/?action=init&folderRsn=VALID"
DOCUMENT="https://www.toronto.ca/wp-content/uploads/2026/10/project-site-plan.pdf"

def source_row():
    return {"canonical_id":"TORONTO:FILE:25123456STE15OZ",
        "city":"Toronto","cohort":"CORE_16","record_kind":"APPLICATION",
        "application_id":"25 123456 STE 15 OZ","address":"44 King Street West",
        "scope":"Commercial office redevelopment"}

def fake_query(application_id):
    if application_id!="25 123456 STE 15 OZ":
        raise AssertionError(application_id)
    return {"APPLICATION_NUMBER":"25123456STE15OZ",
        "FULL_ADDRESS":"44 King Street West","FOLDERDESCRIPTION":"Industrial and retail floors",
        "STATUS_DESC":"Under Review","LATEST_MILESTONE":"Community consultation",
        "LATEST_MILESTONE_DATE":1794441600000,"SUBMIT_DATE":1794355200000,
        "AIC_URL":AIC_PAGE,"ASSIGNEDPLANNER":"City Planner",
        "PLANNEREMAIL":"planning@toronto.ca"},"EXACT_AIC_MATCH"

class TorontoAIC(unittest.TestCase):
    def prepare(self,root):
        with (root/aic.CKAN_MASTER).open("w",encoding="utf-8-sig",newline="") as fp:
            w=csv.DictWriter(fp,fieldnames=combined.COLS)
            w.writeheader()
            w.writerow(source_row())

    def test_exact_arcgis_number_strips_ckan_spaces(self):
        captured=[]
        def fetch(url):
            captured.append(url)
            return json.dumps({"features":[{"attributes":{
                "APPLICATION_NUMBER":"25123456STE15OZ","FULL_ADDRESS":"44 King Street West",
                "AIC_URL":AIC_PAGE}}]})
        details,state=aic.query_exact("25 123456 STE 15 OZ",fetcher=fetch)
        self.assertEqual(state,"EXACT_AIC_MATCH")
        self.assertEqual(details["APPLICATION_NUMBER"],"25123456STE15OZ")
        query=parse_qs(urlsplit(captured[0]).query)
        self.assertIn("25123456STE15OZ",query["where"][0])
        self.assertNotIn("LIKE",query["where"][0])
        self.assertTrue(captured[0].startswith(aic.LAYER+"/query?"))

    def test_no_loose_or_ambiguous_file_matches(self):
        def other(url):
            return json.dumps({"features":[{"attributes":{
                "APPLICATION_NUMBER":"25123457STE15OZ"}}]})
        obj,status=aic.query_exact("25 123456 STE 15 OZ",fetcher=other)
        self.assertIsNone(obj)
        self.assertEqual(status,"NO_EXACT_AIC_MATCH")

    def test_document_links_only_explicit_official_urls(self):
        html=('<a href="'+DOCUMENT+'">Proposed site plan</a>'
              '<a href="https://evil.example.net/steal.pdf">External drawing</a>'
              '<a href="/wp-content/uploads/2026/10/project-site-plan.pdf">Duplicate</a>'
              '<a href="/other">Other navigation</a>')
        docs=aic.document_links(html,page_url=AIC_PAGE)
        self.assertEqual(len(docs),1)
        self.assertEqual(docs[0]["official_document_url"],DOCUMENT)

    def test_run_produces_source_backed_metadata_and_document_index(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            self.prepare(root)
            report=aic.run(root,queryer=fake_query,
                page_fetcher=lambda url:'<a href="'+DOCUMENT+'">Site Plan</a>')
            self.assertEqual(report["candidate_application_ids"],1)
            self.assertEqual(report["exact_aic_matches"],1)
            self.assertEqual(report["official_document_links_indexed_not_downloaded"],1)
            self.assertEqual(report["buyer_contacts_verified"],0)
            with (root/aic.ENRICH).open(encoding="utf-8-sig") as f:
                row=list(csv.DictReader(f))[0]
            self.assertEqual(row["aic_description"],"Industrial and retail floors")
            self.assertEqual(row["published_planner_name_not_buyer"],"City Planner")
            self.assertEqual(row["verified_buying_contact"],"False")
            with (root/aic.DOCUMENTS).open(encoding="utf-8-sig") as f:
                self.assertEqual(len(list(csv.DictReader(f))),1)

    def test_blocked_document_page_keeps_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            self.prepare(root)
            def blocked(url):
                raise PermissionError("AIC website refused")
            report=aic.run(root,queryer=fake_query,page_fetcher=blocked)
            self.assertEqual(report["exact_aic_matches"],1)
            self.assertEqual(report["records_with_aic_page_blocked"],1)
            self.assertEqual(report["official_document_links_indexed_not_downloaded"],0)
            self.assertTrue((root/aic.ENRICH).is_file())

    def test_nonstandard_aic_deeplink_never_auto_fetched(self):
        self.assertEqual(aic.approved_url("https://evil.org/?x=1",kind="aic"),"")
        self.assertEqual(aic.approved_url("https://www.toronto.ca/other",kind="aic"),"")
        self.assertFalse(aic.approved_url("http://www.toronto.ca/a.pdf",kind="document"))
        with patch.object(aic,"robots_allowed",return_value=False):
            with self.assertRaises(PermissionError):
                aic.fetch(AIC_PAGE)

if __name__=="__main__":
    unittest.main()
