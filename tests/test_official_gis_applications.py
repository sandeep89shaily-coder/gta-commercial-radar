"""Toronto/Brampton official application GIS adapter: offline regression tests."""
from __future__ import annotations
import csv
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

import gta_official_gis_applications as gis

DAY=dt.date(2026,11,2)

def ts(day):
    return int(dt.datetime.fromisoformat(day+"T12:00:00+00:00").timestamp()*1000)

def toronto(**change):
    attrs={
        "APPLICATION_NUMBER":"26 200555 STE 10 SA",
        "FULL_ADDRESS":"22 Industry Street",
        "FOLDERDESCRIPTION":"Proposed new industrial warehouse and logistics facility",
        "FOLDERNAME":"Site Plan Approval",
        "APPLICATION_TYPE":"SA",
        "FOLDERTYPE_DESC":"Site Plan Approval",
        "SUBMIT_DATE":ts("2026-09-10"),"STATUS_DESC":"Under Review",
        "AIC_URL":"https://www.toronto.ca/city-government/planning-development/application-information-centre/",
        "OBJECTID":12,
    }
    attrs.update(change);return {"attributes":attrs}

def brampton(**change):
    attrs={
        "FILE_NUMBER":"SP-2026-101","LOCATION":"12 Sample Road",
        "DATE_RECEIVED":ts("2026-10-01"),"APPLICATION_TYPE":"Site Plan",
        "APPLICATION_TITLE":"Warehouse","DESCRIPTION":"New industrial warehouse",
        "PROPOSAL_DESCRIPTION":"New industrial warehouse, factory",
        "STATUS":"In Review","APPLICANT_COMPANY":"Example Applicant Ltd",
        "AGENT_COMPANY":"Example Agent","POLY_ID":21,
    }
    attrs.update(change);return {"attributes":attrs}

class StructuredGISApplicationTests(unittest.TestCase):
    def test_toronto_and_brampton_are_official_record_layers(self):
        self.assertEqual(set(gis.SOURCES),{
            "TORONTO_AIC","BRAMPTON_OPA_ZBA","BRAMPTON_SITE_PLAN"})
        for name,src in gis.SOURCES.items():
            self.assertTrue(src["url"].startswith("https://"))
            self.assertIn(src["date"],src["fields"])

    def test_parses_commercial_not_residential_or_closed(self):
        t=gis._parse("TORONTO_AIC",toronto()["attributes"])
        b=gis._parse("BRAMPTON_SITE_PLAN",brampton()["attributes"])
        self.assertEqual(t["application_id"],"26 200555 STE 10 SA")
        self.assertEqual(t["source_record_date"],"2026-09-10")
        self.assertEqual(t["record_source_url_basis"],"TORONTO_AIC_RECORD_LINK_FROM_OFFICIAL_GIS")
        self.assertEqual(b["applicant_company_unverified"],"Example Applicant Ltd")
        self.assertFalse(b["record_source_url"])
        self.assertEqual(b["record_source_url_basis"],"NO_DIRECT_RECORD_LINK_GIS_LAYER_ONLY")
        self.assertIsNone(gis._parse("TORONTO_AIC",toronto(
            FOLDERDESCRIPTION="A residential condominium with 120 apartments")["attributes"]))
        self.assertIsNone(gis._parse("BRAMPTON_SITE_PLAN",brampton(
            STATUS="Closed")["attributes"]))
        self.assertEqual(gis._parse("BRAMPTON_SITE_PLAN",brampton(
            PROPOSAL_DESCRIPTION="Residential condominiums above ground floor retail")["attributes"])["commercial_fit"],
                         "MIXED_RESIDENTIAL_COMMERCIAL_NEEDS_REVIEW")

    def test_baseline_then_changed_then_stable(self):
        with tempfile.TemporaryDirectory() as td:
            src={"TORONTO_AIC":gis.SOURCES["TORONTO_AIC"]}
            state={"description":"Proposed new industrial warehouse and logistics facility"}
            def fetch(url,args):
                self.assertEqual(args["resultRecordCount"],str(gis.PAGE))
                return {"features":[toronto(FOLDERDESCRIPTION=state["description"])]}
            first=gis.run(td,today=DAY,fetcher=fetch,sources=src)
            self.assertEqual(first["application_candidates"],1)
            self.assertEqual(first["new_or_changed"],0)
            with (Path(td)/gis.ALL).open(encoding="utf-8-sig") as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(rows[0]["observation"],"INITIAL_BASELINE")
            state["description"]="Proposed expanded industrial warehouse with new logistics units"
            second=gis.run(td,today=DAY+dt.timedelta(days=1),fetcher=fetch,sources=src)
            self.assertEqual(second["new_or_changed"],1)
            self.assertEqual(gis.run(td,today=DAY+dt.timedelta(days=2),
                              fetcher=fetch,sources=src)["new_or_changed"],0)

    def test_one_failed_source_does_not_erase_working_city_or_fake_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            sources={k:gis.SOURCES[k] for k in ("TORONTO_AIC","BRAMPTON_OPA_ZBA")}
            def first_fetch(url,args):
                if "gis.toronto.ca" in url:raise PermissionError("GIS_HTTP_403")
                return {"features":[brampton()]}
            first=gis.run(td,today=DAY,sources=sources,fetcher=first_fetch)
            self.assertEqual(first["sources_successful"],1)
            self.assertEqual(first["new_or_changed"],0)
            self.assertEqual(first["application_candidates"],1)
            self.assertEqual(json.loads((Path(td)/gis.STATE).read_text())["sources"].keys(),
                             {"BRAMPTON_OPA_ZBA"})
            def both_fetch(url,args):
                return {"features":[toronto()] if "gis.toronto.ca" in url else [brampton()]}
            second=gis.run(td,today=DAY+dt.timedelta(days=1),sources=sources,fetcher=both_fetch)
            self.assertEqual(second["sources_successful"],2)
            self.assertEqual(second["new_or_changed"],0)
            rows=list(csv.DictReader((Path(td)/gis.ALL).open(encoding="utf-8-sig")))
            self.assertEqual(set(r["observation"] for r in rows),
                             {"INITIAL_BASELINE","UNCHANGED"})

    def test_incomplete_pagination_preserves_state(self):
        with tempfile.TemporaryDirectory() as td:
            def all_full(url,args):
                # Exactly PAGE fresh rows at limit, never a verified complete slice.
                return {"features":[toronto()]*gis.PAGE}
            got=gis.run(td,today=DAY,sources={"TORONTO_AIC":gis.SOURCES["TORONTO_AIC"]},
                        fetcher=all_full,max_pages=1)
            self.assertEqual(got["sources_successful"],0)
            self.assertEqual(got["application_candidates"],0)
            self.assertEqual(json.loads((Path(td)/gis.STATE).read_text())["sources"],{})

if __name__=="__main__":
    unittest.main()
