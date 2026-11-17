"""Offline, no-network regression tests for Northern major-city evidence pilots."""
import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path

import gta_northern_major_cities as n

BARRIE_PLANNING = {
    "OBJECTID": 7,
    "File_No": "D12-2026-103", "Phase":"Phase 1",
    "Address_Location":"100 Industrial Parkway",
    "Description_Proposal":"New 13,000 sqm warehouse distribution building",
    "Status":"Under Review",
    "Applicant_Owner":"Northern Distribution Developments Inc.",
    "Application_Type":"Site Plan",
    "Date_Application_Received":1793491200000,
}
BARRIE_ISSUED = {
    "OBJECTID":8, "RECORD_ID":"BP-2026-0801",
    "Full_Address":"105 Commerce Crescent",
    "Description":"Addition to industrial manufacturing facility",
    "RECORD_STATUS":"Issued", "Sub_Type":"Industrial",
    "Date_Status":"2026-11-05",
}
BARRIE_ACTIVE = {
    "OBJECTID": 11, "RECORD_STATUS":"Applied",
    "Date_Opened":"2026-11-09", "Sub_Type":"Industrial",
}

NB_NOTICE = "https://northbay.ca/public-notices/planning-act-zoning-application-industrial-property/"
SUDBURY_HTML = """<html><main><h1>Pending Planning Applications</h1>
<h3>Janicijevic Holdings Inc.</h3>
<p>Location : 45 Southview Industrial Crescent (Sudbury)</p>
<p>Application : Construction of a commercial medical office plaza.
Application PL-ZBA-2026-00123. Received: October 31, 2026</p>
</main></html>"""
NB_INDEX = f"""<html><main><a href="{NB_NOTICE}">
Notice of Planning Act Zoning Application for Industrial Property</a>
<a href="/public-notices/general-election-info/">Election information</a>
</main></html>"""
NB_DETAIL = """<html><main><h1>Planning Act - Zoning Application for Industrial Property</h1>
<time datetime="2026-11-10T11:22:00"></time>
<p>Planning application ZBA-2026-0001 is proposed for lands located at
250 Industrial Avenue. The applicant requests a zoning amendment to
construct a manufacturing facility and office.</p></main></html>"""


def metadata(lane):
    if lane=="PLANNING":
        names=("OBJECTID","File_No","Phase","Address_Location",
               "Description_Proposal","Status","Applicant_Owner",
               "Application_Type","Date_Application_Received")
    elif lane=="ISSUED_PERMITS":
        names=("OBJECTID","RECORD_ID","Full_Address","Description",
               "RECORD_STATUS","Sub_Type","Date_Status")
    else:
        names=("OBJECTID","RECORD_STATUS","Date_Opened","Sub_Type")
    return {"objectIdField":"OBJECTID","fields":[{"name":a} for a in names]}


def gis(base,params):
    lane=next(key for key,value in n.BARRIE.items() if base.startswith(value))
    if params=={"f":"json"}:
        return metadata(lane)
    if lane=="PLANNING":
        return {"features":[{"attributes": BARRIE_PLANNING}]}
    if lane=="ISSUED_PERMITS":
        return {"features":[{"attributes": BARRIE_ISSUED}]}
    raise AssertionError("No per-record ID in active permit source: skip query")


def html(url):
    if url==n.SUDBURY:
        return SUDBURY_HTML
    if url.startswith(n.NORTH_BAY+"?page="):
        return NB_INDEX
    if url==NB_NOTICE:
        return NB_DETAIL
    raise AssertionError("Unexpected network path: "+url)


class NorthernMajorCityTests(unittest.TestCase):
    def setUp(self):
        work=tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.root=Path(work.name)
        self.today=dt.date(2026,11,17)

    def csv(self,name):
        with (self.root/name).open(encoding="utf-8-sig",newline="") as fp:
            return list(csv.DictReader(fp))

    def test_barrie_planning_schema_and_applicant_scope_received_date(self):
        rows,audit=n._barrie("PLANNING",gis,today=self.today)
        self.assertEqual(len(rows),1)
        row=rows[0]
        self.assertEqual(row["application_id"],"D12-2026-103")
        self.assertEqual(row["address"],"100 Industrial Parkway")
        self.assertEqual(row["applicant_name_source_claim"],
                         "Northern Distribution Developments Inc.")
        self.assertEqual(row["source_date"],"2026-11-01")
        self.assertEqual(row["source_date_basis"],
                         "OFFICIAL_APPLICATION_RECEIVED_NOT_PUBLICATION")
        self.assertEqual(row["publication_date_verified"],"False")
        self.assertEqual(row["buyer_verified"],"False")
        self.assertFalse(audit["sampled_or_truncated"])

    def test_issued_permits_and_active_permit_metadata_truth(self):
        issued,_=n._barrie("ISSUED_PERMITS",gis,today=self.today)
        self.assertEqual(issued[0]["source_date"],"2026-11-05")
        self.assertEqual(issued[0]["scope"],
                         "Addition to industrial manufacturing facility")
        active,audit=n._barrie("ACTIVE_PERMITS",gis,today=self.today)
        self.assertEqual(active,[])
        self.assertEqual(audit["status"],"NO_PUBLISHED_PERMIT_NUMBER_HOLD")

    def test_barrie_unknown_schema_cannot_guess_objectid_as_file_id(self):
        def broken(base,params):
            if params=={"f":"json"}:
                return {"fields":[{"name":"OBJECTID"}, {"name":"Status"}]}
            raise AssertionError("MUST_NOT_QUERY_INVALID_SCHEMA")
        with self.assertRaisesRegex(ValueError,"BARRIE_GIS_SCHEMA_MISMATCH"):
            n._barrie("PLANNING",broken,today=self.today)

    def test_sudbury_requires_exact_id_and_commercial_scope(self):
        records=n._sudbury(SUDBURY_HTML)
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]["application_id"],"PL-ZBA-2026-00123")
        self.assertEqual(records[0]["applicant_name_source_claim"],
                         "Janicijevic Holdings Inc.")
        self.assertIn("medical office",records[0]["scope"])
        self.assertEqual(records[0]["source_date"],"2026-10-31")
        self.assertEqual(records[0]["source_date_basis"],
                         "OFFICIAL_APPLICATION_RECEIVED_NOT_PUBLICATION")
        self.assertEqual(n._sudbury(SUDBURY_HTML.replace(
            "PL-ZBA-2026-00123","No file number issued")),[])

    def test_northbay_notice_exact_id_not_original_publication(self):
        links=n._nb_links(NB_INDEX)
        self.assertEqual(links,[(NB_NOTICE,
            "Notice of Planning Act Zoning Application for Industrial Property")])
        record=n._nb_detail(NB_DETAIL,NB_NOTICE)
        self.assertEqual(record["application_id"],"ZBA-2026-0001")
        self.assertEqual(record["source_date"],"2026-11-10")
        self.assertEqual(record["source_date_basis"],
                         "OFFICIAL_NOTICE_TIME_METADATA_NOT_FIRST_DISCLOSURE")
        self.assertEqual(record["publication_date_verified"],"False")

    def test_northbay_no_id_is_notice_only_and_no_fake_date(self):
        raw=NB_DETAIL.replace("ZBA-2026-0001","an unnumbered project")
        raw=raw.replace('<time datetime="2026-11-10T11:22:00"></time>',"")
        record=n._nb_detail(raw,NB_NOTICE)
        self.assertEqual(record["application_id"],"")
        self.assertEqual(record["record_kind"],
                         "OFFICIAL_NOTICE_LINK_ONLY_NO_APPLICATION_ID")
        self.assertEqual(record["source_date"],"")

    def test_first_run_baseline_is_not_new_publication(self):
        first=n.run(self.root,today=self.today,html_fetch=html,json_fetch=gis)
        self.assertEqual(first["total_evidence_records"],4)
        self.assertEqual(first["source_changed_not_new_publications"],0)
        self.assertEqual(first["buyers_verified"],0)
        self.assertEqual(first["new_cities_added_to_core_16"],0)
        self.assertTrue(all(r["observation"]=="INITIAL_BASELINE_NOT_NEW"
                            for r in self.csv(n.SOURCE_FILE)))
        again=n.run(self.root,today=self.today,html_fetch=html,json_fetch=gis)
        self.assertEqual(again["source_changed_not_new_publications"],0)
        def revised(url):
            return SUDBURY_HTML.replace("medical office plaza",
                   "industrial warehousing distribution facility") if url==n.SUDBURY else html(url)
        change=n.run(self.root,today=self.today,html_fetch=revised,json_fetch=gis)
        self.assertEqual(change["source_changed_not_new_publications"],1)
        self.assertEqual(change["first_project_publications_verified"],0)
        self.assertEqual(self.csv(n.CHANGED_FILE)[0]["city"],"Greater Sudbury")

    def test_blocked_gis_does_not_block_sudbury_and_northbay(self):
        def blocked(url,params):
            raise ValueError("ROBOTS_DENIED")
        result=n.run(self.root,today=self.today,html_fetch=html,json_fetch=blocked)
        self.assertEqual(result["total_evidence_records"],2)
        self.assertTrue(all(x["status"]=="SOURCE_HELD"
                            for x in result["source_details"][:3]))
        self.assertEqual(result["open_procurement_verified"],0)

    def test_northbay_cross_domain_rejected(self):
        bad=NB_INDEX.replace("northbay.ca/public-notices/",
                            "northbay.ca.evil.test/public-notices/")
        self.assertEqual(n._nb_links(bad),[])
        with self.assertRaisesRegex(ValueError,"NORTH_BAY_OFFICIAL_HOST_ONLY"):
            n._nb_detail(NB_DETAIL,"https://example.test/public-notices/id/")


if __name__=="__main__":
    unittest.main()
