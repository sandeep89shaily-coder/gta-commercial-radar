"""Published St Catharines / Oakville planning notice tests (offline)."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import gta_stc_oak_planning_notices as n

STC_NOTICE=("""<h1>Notice of Complete Applications and Open House - 8 Gale Crescent</h1>
<p>The Planning and Building Services Department received applications
to Amend the Official Plan and Zoning By-law for lands located at 8 Gale Crescent.</p>
<h2>PROPOSAL</h2><p>The Applicant is seeking amendments to facilitate a mixed use
development including commercial space.</p>
<p>This notice is issued on November 10, 2026.</p>
<p>Refer to File No: 26 112777 OP &amp; 26 112778 ZA</p>
<a href="/planning-and-development/development-applications/">Development application</a>""")
OAK_NOTICE=("""<h1>Notice of complete application at 118-132 Cross Avenue</h1>
<p>Site location: 118-132 Cross Avenue. Located in Midtown.</p>
<p>Applicant: Example Development Inc</p>
<p>File number: OPA1614.84, Z.1614.84</p>
<h2>What is proposed?</h2>
<p>New 38 storey mixed-use building including commercial retail.</p>
<h2>How to participate</h2>
<p>This notice is issued on October 29, 2026.</p>
<a href="/business-development/planning-development/">development application</a>""")
STC_URL=n.STC_ROOT+"/news/posts/notice-of-complete-applications-and-open-house-8-gale-crescent/"
OAK_URL=n.OAK_INDEX+"notice-of-complete-application-for-a-proposed-opa-and-zba-for-118-132-cross-avenue/"

def fetch(url):
    if url==n.STC_INDEX:
        return '<a href="'+STC_URL+'">Notice of Complete Applications and Open House - 8 Gale Crescent</a>'
    if url.startswith(n.STC_INDEX.replace("?page=1","?page=")):
        return ""
    if url==n.OAK_INDEX:
        return '<a href="'+OAK_URL+'">Notice of complete application for proposed OPA and ZBA for 118-132 Cross Avenue</a>'
    if url==STC_URL:return STC_NOTICE
    if url==OAK_URL:return OAK_NOTICE
    raise AssertionError(url)

class PlanningNoticeRecovery(unittest.TestCase):
    def test_stc_exact_numbers_and_date(self):
        rows,links=n.parse_notice(STC_NOTICE,city="St. Catharines",
             title="Notice of Complete Applications - 8 Gale Crescent",url=STC_URL)
        self.assertEqual({x["file_number"] for x in rows},
                         {"26 112777 OP","26 112778 ZA"})
        self.assertTrue(all(x["notice_issued_date"]=="2026-11-10" for x in rows))
        self.assertEqual(rows[0]["site_address"],"8 Gale Crescent")
        self.assertEqual(rows[0]["verified_buyer"],"False")
    def test_oakville_two_planning_file_numbers(self):
        rows,links=n.parse_notice(OAK_NOTICE,city="Oakville",
             title="Notice at 118-132 Cross Avenue",url=OAK_URL)
        self.assertEqual({x["file_number"] for x in rows},
                         {"OPA1614.84","Z.1614.84"})
        self.assertEqual(rows[0]["notice_issued_date"],"2026-10-29")
        self.assertEqual(rows[0]["published_applicant_not_buyer"],
                         "Example Development Inc")
    def test_both_official_notices_recovered_without_escribe(self):
        with tempfile.TemporaryDirectory() as td:
            result=n.run(td,fetcher=fetch)
            self.assertEqual(result["validated_official_file_records"],4)
            self.assertEqual(result["reusable_commercial_records_cleared"],0)
            self.assertEqual(result["true_council_agendas_retrieved"],0)
            with (Path(td)/n.OUTPUT).open(encoding="utf-8-sig") as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),4)
    def test_missing_file_numbers_not_invented(self):
        rows,links=n.parse_notice("<p>General policy hearing at City Hall</p>",
             city="Oakville",title="General planning policy",url=OAK_URL)
        self.assertEqual(rows,[])
    def test_blocked_stc_isolated_from_oakville(self):
        def block(url):
            if "stcatharines.ca" in url:raise PermissionError("robots")
            return fetch(url)
        with tempfile.TemporaryDirectory() as td:
            result=n.run(td,fetcher=block)
            self.assertEqual(result["source_status"]["Oakville"]["file_ids_found"],2)
            self.assertEqual(result["source_status"]["St. Catharines"]["file_ids_found"],0)
    def test_no_untrusted_host_or_robots_bypass(self):
        self.assertFalse(n.permitted_origin("http://www.oakville.ca/", "Oakville"))
        self.assertFalse(n.permitted_origin("https://bad.example.com/", "Oakville"))
        with patch.object(n,"robots_allowed",return_value=False):
            with self.assertRaises(PermissionError):
                n.fetch(n.OAK_INDEX)
if __name__=="__main__":
    unittest.main()
