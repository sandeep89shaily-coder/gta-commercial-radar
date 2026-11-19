"""Mocked public-source recovery tests; never hit government networks."""
import csv
import json
import ssl
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import gta_stc_oak_official_recovery as recovery

class StCathOakvilleRecovery(unittest.TestCase):
    def fetcher(self,url):
        if url==recovery.STC+"?f=json":
            return json.dumps({"objectIdField":"OBJECTID0",
                 "fields":[{"name":"OBJECTID0"}]})
        if url.startswith(recovery.STC+"/query?"):
            return json.dumps({"features":[{"attributes":{
                "OBJECTID0":1,"FOLDERYEAR":2026,"FOLDERSEQUENCE":42,
                "FOLDERDESC":"COMM","PROPERTYNAME":"12 Factory Street",
                "FOLDERDESCRIPTION":"Industrial manufacturing building",
                "STATUSDESC":"Issued","ISSUEDATE":1794441600000}}]})
        raise AssertionError(url)

    def test_city_open_data_schema_and_composite_permit_id(self):
        rows,health=recovery.permit_records(fetcher=self.fetcher)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["application_id"],"2026-000042-COMM")
        self.assertEqual(rows[0]["record_kind"],"HISTORICAL_OR_ISSUED_PERMIT")
        self.assertEqual(rows[0]["date_basis"],
            "ISSUE_OR_INTAKE_DATE_NOT_PUBLICATION")
        self.assertEqual(rows[0]["buyer_verified"],"False")
        self.assertTrue(health["pagination_complete"])

    def test_official_town_page_links_not_called_meeting_agendas(self):
        body=('''<a href="https://pub-oakville.escribemeetings.com/">Agendas and Meetings</a>
          <a href="/town-hall/news-notices/planning/">Planning notice</a>
          <a href="https://evil.example.net/minutes">Council minutes</a>''')
        links=recovery.oakville_links(body,landing=recovery.OAK_NEWS)
        self.assertEqual(len(links),2)
        self.assertTrue(all(r["meeting_agenda_verified"]=="False" for r in links))
        self.assertTrue(all(r["public_notice_only"]=="True" for r in links))

    def test_run_separates_permits_and_meeting_blocks(self):
        def denied(url):
            if url==recovery.OAK_MEETINGS:
                raise ssl.SSLCertVerificationError("untrusted certificate chain")
            return ('<a href="/town-hall/news-notices/">Planning notices</a>',
                    "SYSTEM_TRUST_STORE",None)
        with tempfile.TemporaryDirectory() as temp:
            report=recovery.run(temp,permit_collector=lambda:
                recovery.permit_records(fetcher=self.fetcher),
                landing_fetch=denied)
            self.assertEqual(report["stc_permit_ids"],1)
            self.assertEqual(report["oakville_actual_agendas_retrieved"],0)
            self.assertEqual(report["sources"]["Oakville_Meeting_Landing"]["status"],
                             "BLOCKED_OR_FAILED")
            self.assertEqual(report["sources"]["St_Catharines_Permits"]["status"],
                             "LIVE_PERMIT_IDS_PARTIAL")
            self.assertEqual(report["verified_buyers"],0)
            self.assertTrue((Path(temp)/recovery.OUTPUT).is_file())

    def test_ssl_remains_strict(self):
        context=recovery.secure_ca_bundle()
        if context is not None:
            self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
            self.assertTrue(context.check_hostname)
        self.assertFalse(recovery.source_url_ok("http://www.oakville.ca/"))
        self.assertFalse(recovery.source_url_ok("https://untrusted.com/"))
        with patch.object(recovery,"robots_ok",return_value=False):
            with self.assertRaises(PermissionError):
                recovery.secure_fetch(recovery.OAK_MEETINGS)

    def test_duplicate_technical_objectid_fails(self):
        def duplicate(url):
            result=json.loads(self.fetcher(url))
            if "/query?" in url:
                result["features"].append(result["features"][0])
            return json.dumps(result)
        with self.assertRaises(ValueError):
            recovery.permit_records(fetcher=duplicate)

if __name__=="__main__":
    unittest.main()
