"""Offline acceptance tests for the Commercial Activation read-only pilot."""
import csv
import datetime as dt
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import gta_commercial_activation_pilot as p

TODAY=dt.date(2026,11,7)

def record(source,key,raw,*,first_seen="2026-11-06T10:00:00Z"):
    return {"source":source,"key":key,"first_seen":first_seen,
            "source_date":"2026-11-04","raw":raw,
            "sha":hashlib.sha256(json.dumps(raw).encode()).hexdigest()}

def licence(key="LIC-001",address="100 Queen Street West",unit="",status="Active",issue="2026-11-03"):
    return record("toronto_business_licences",key,{
        "LICENCE_NO":key,"ADDRESS":address,"UNIT":unit,
        "OPERATING_NAME":"Example Cafe","CATEGORY":"EATING OR DRINKING ESTABLISHMENT",
        "LICENCE_ISSUED_DATE":issue,"STATUS":status
    })

def permit(key="PER-1",number="100",street="Queen",unit="",status="Permit Issued"):
    return record("toronto_active_building_permits",key,{
        "PERMIT_NUM":key,"STREET_NUM":number,"STREET_NAME":street,
        "STREET_TYPE":"Street","STREET_DIRECTION":"West","UNIT_NO":unit,
        "WORK":"Interior Alterations",
        "PROPOSED_USE":"Restaurant","CURRENT_USE":"Commercial",
        "STATUS":status,"STATUS_DATE":"2026-11-04",
    })

class ActivationPilotTests(unittest.TestCase):
    def test_recent_licence_does_not_establish_opening(self):
        row,why=p.classify(licence(),TODAY,120)
        self.assertIsNone(why)
        self.assertEqual(row["source_event_date"],"2026-11-03")
        self.assertEqual(row["activation_stage"],"LICENCE_ISSUED_NOT_OPENING_CONFIRMED")
        self.assertEqual(row["business_name"],"Example Cafe")
        self.assertEqual(row["opening_confirmed"],"NO")
        self.assertEqual(row["opening_date"],"")
        self.assertEqual(row["purchasing_status"],"UNKNOWN")
        self.assertEqual(row["buyer_verified"],"NO")
        self.assertIn("POS",row["potential_supplier_segments"])

    def test_licence_renewals_cancellations_and_signs_are_not_leads(self):
        for r in [
            licence(status="Renewed"),licence(status="Cancelled"),
            record("toronto_business_licences","SIGN-1",{
                "ADDRESS":"100 Queen Street West","CATEGORY":"TEMPORARY SIGN - MOBILE",
                "ISSUED_DATE":"2026-11-01","OPERATING_NAME":"Example Cafe",
            }),
        ]:
            with self.subTest(key=r["key"]):
                result,why=p.classify(r,TODAY,120)
                self.assertIsNone(result)
                self.assertIsNotNone(why)

    def test_recent_permit_distinguishes_issued_and_inspection_from_open(self):
        for status,expected in [
            ("Permit Issued","FITOUT_PERMIT_ISSUED_NOT_OPENING_CONFIRMED"),
            ("Inspection","PERMIT_INSPECTION_NOT_OPENING_CONFIRMED"),
            ("Under Review","PREPARATION_PERMIT_NOT_OPENING_CONFIRMED"),
        ]:
            row,why=p.classify(permit(status=status),TODAY,120)
            self.assertIsNone(why)
            self.assertEqual(row["activation_stage"],expected)
            self.assertFalse(row["business_name"]) # contractor is not operator
            self.assertEqual(row["opening_confirmed"],"NO")

    def test_real_world_toronto_early_stages_not_claimed_open(self):
        for status in ("Application Acceptable","Ready for Issuance",
                       "Issuance Pending","Not Started - Express"):
            row,why=p.classify(permit(status=status),TODAY,120)
            with self.subTest(status=status):
                self.assertIsNone(why)
                self.assertEqual(row["activation_stage"],
                                 "PREPARATION_PERMIT_NOT_OPENING_CONFIRMED")
                self.assertEqual(row["opening_confirmed"],"NO")

    def test_decommissioning_is_not_commercial_opening_signal(self):
        r=permit()
        r["raw"]["DESCRIPTION"]="Interior alterations for tenant decommissioning and removal of vault"
        row,why=p.classify(r,TODAY,120)
        self.assertIsNone(row)
        self.assertEqual(why,"DEACTIVATION_NOT_OPENING")

    def test_residential_or_terminal_permit_excluded(self):
        residential=record("toronto_active_building_permits","RX",{
            "STREET_NUM":"12","STREET_NAME":"Yonge","STREET_TYPE":"Street",
            "DESCRIPTION":"Interior alterations to single-family dwelling",
            "PROPOSED_USE":"Residential Dwelling",
            "STATUS":"Permit Issued","STATUS_DATE":"2026-11-04",
        })
        self.assertEqual(p.classify(residential,TODAY,120)[1],"RESIDENTIAL_ONLY")
        self.assertEqual(p.classify(permit(status="Permit Revoked"),TODAY,120)[1],
                         "CLOSED_CANCELLED_OR_TERMINAL_PERMIT")

    def test_outdated_source_date_not_rebranded_as_new_by_first_seen(self):
        r=licence(issue="2020-04-02")
        r["first_seen"]="2026-11-07T10:00:00Z"
        self.assertEqual(p.classify(r,TODAY,120)[1],"OUTSIDE_SOURCE_DATE_WINDOW")

    def test_mississauga_and_brampton_source_shapes(self):
        miss=record("mississauga_issued_building_permits","MISS-1",{
            "ADDRESS":"2200 Dundas Road","UNIT_NO":"4",
            "DESCRIPTION":"Tenant fit-out of a retail store",
            "STATUS":"Issued","ISSUE_DATE":"2026-10-28","FILE_TYPE":"COMMERCIAL",
        })
        bram=record("brampton_building_permits","BRAM-1",{
            "ADDRESS":"45 Main Street","WORKDESC":"Interior alteration for dental office",
            "STATUSDESC":"Inspection","PROCESSDATE":"2026-10-25",
        })
        row,_=p.classify(miss,TODAY,120)
        self.assertEqual(row["municipality"],"Mississauga")
        self.assertEqual(row["sector"],"Retail")
        self.assertEqual(row["site_unit"],"4")
        row,_=p.classify(bram,TODAY,120)
        self.assertEqual(row["sector"],"Healthcare")
        self.assertEqual(row["activation_stage"],"PERMIT_INSPECTION_NOT_OPENING_CONFIRMED")

    def test_exact_site_links_not_tenant_identity(self):
        a,_=p.classify(licence(),TODAY,120)
        b,_=p.classify(permit(),TODAY,120)
        p.add_site_links([a,b])
        self.assertEqual(a["same_site_link_status"],"SAME_CIVIC_SITE_TENANT_UNVERIFIED")
        self.assertIn("toronto_active_building_permits:PER-1",a["related_source_keys"])
        self.assertEqual(b["business_name"],"")
        self.assertEqual(a["opening_confirmed"],"NO")

    def test_unit_mismatch_never_produces_same_tenant_link(self):
        a,_=p.classify(licence(unit="A"),TODAY,120)
        b,_=p.classify(permit(unit="B"),TODAY,120)
        p.add_site_links([a,b])
        self.assertEqual(a["same_site_link_status"],"DIFFERENT_UNITS_NO_LINK")
        self.assertEqual(a["related_source_keys"],"")
        b["site_unit"]=""
        p.add_site_links([a,b])
        self.assertEqual(a["same_site_link_status"],"SAME_BUILDING_UNIT_UNKNOWN")

    def test_no_ambiguous_dates_or_nonphysical_address(self):
        self.assertIsNone(p.event_date("11/07/2026"))
        self.assertIsNone(p.event_date("2026-13-40"))
        self.assertEqual(p.physical_site({"ADDRESS":"PO Box 123"},"toronto_business_licences"),("",""))
        self.assertEqual(p.event_date("2026-10-31").isoformat(),"2026-10-31")

    def test_sqlite_reader_is_read_only_and_outputs_are_isolated(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);db=root/"radar.sqlite"
            con=sqlite3.connect(db)
            con.executescript("""
                CREATE TABLE records_current(
                  source_id TEXT,record_key TEXT,first_seen_at TEXT,source_date TEXT,active INTEGER);
                CREATE TABLE record_versions(
                  version_id INTEGER PRIMARY KEY,source_id TEXT,record_key TEXT,payload_json TEXT);
            """)
            source="toronto_business_licences"
            raw=licence()["raw"]
            con.execute("INSERT INTO records_current VALUES (?,?,?,?,?)",
                        (source,"LIC-001","2026-11-06T10:00:00Z","2026-11-03",1))
            con.execute("INSERT INTO record_versions VALUES (?,?,?,?)",
                        (1,source,"LIC-001",json.dumps(raw)))
            con.commit();con.close()
            original=hashlib.sha256(db.read_bytes()).hexdigest()
            status=p.run(db,root/"pilot",as_of=TODAY,max_per_source=100)
            self.assertEqual(status["activation_review_candidates"],1)
            self.assertEqual(status["verified_openings"],0)
            self.assertEqual(status["verified_open_supplier_contracts"],0)
            self.assertEqual(hashlib.sha256(db.read_bytes()).hexdigest(),original)
            with (root/"pilot"/p.CSV_NAME).open(encoding="utf-8-sig",newline="") as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(rows[0]["business_name"],"Example Cafe")
            self.assertEqual(rows[0]["source_record_key"],"LIC-001")
            self.assertTrue((root/"pilot"/p.HTML_NAME).is_file())
            self.assertTrue((root/"pilot"/p.STATUS_NAME).is_file())


    def test_recent_licence_recovered_beyond_source_date_cap(self):
        # The 2026-11-09 real ledger put 40k older taxi/contractor
        # updates ahead of all food/garage licence categories.
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);db=root/"radar.sqlite"
            with sqlite3.connect(db) as con:
                con.executescript("""
                    CREATE TABLE records_current(
                      source_id TEXT,record_key TEXT,first_seen_at TEXT,
                      source_date TEXT,active INTEGER);
                    CREATE TABLE record_versions(
                      version_id INTEGER PRIMARY KEY,source_id TEXT,
                      record_key TEXT,payload_json TEXT);
                """)
                examples=[
                    ("TAXI-1","2026-11-09",{
                        "CATEGORY":"TAXICAB OWNER","ISSUED":"2026-11-08",
                        "LICENCE_ADDRESS_LINE_1":"100 Bay Street"}),
                    ("OLD-FOOD","2026-11-08",{
                        "CATEGORY":"EATING OR DRINKING ESTABLISHMENT",
                        "ISSUED":"2018-01-01",
                        "LICENCE_ADDRESS_LINE_1":"110 Bay Street"}),
                    ("FOOD-CANCELLED","2026-11-07",{
                        "CATEGORY":"EATING OR DRINKING ESTABLISHMENT",
                        "ISSUED":"2026-11-07","CANCEL_DATE":"2026-11-09",
                        "LICENCE_ADDRESS_LINE_1":"120 Bay Street"}),
                    ("FOOD-NEW","2020-01-01",{
                        "CATEGORY":"EATING OR DRINKING ESTABLISHMENT",
                        "ISSUED":"2026-11-08","CANCEL_DATE":"",
                        "OPERATING_NAME":"New Cafe",
                        "LICENCE_ADDRESS_LINE_1":"130 Bay Street"}),
                    ("GARAGE-NEW","2019-01-01",{
                        "CATEGORY":"PUBLIC GARAGE","ISSUED":"2026-11-06",
                        "LICENCE_ADDRESS_LINE_1":"140 Bay Street"})
                ]
                for i,(key,source_date,raw) in enumerate(examples,1):
                    con.execute("INSERT INTO records_current VALUES (?,?,?,?,1)",
                                ("toronto_business_licences",key,
                                 "2026-11-09T10:00:00Z",source_date))
                    con.execute("INSERT INTO record_versions VALUES (?,?,?,?)",
                                (i,"toronto_business_licences",key,json.dumps(raw)))
                con.commit()
                con.close()
            records,counts=p.read_snapshots(db,2,as_of=TODAY,window_days=120)
            selected=[r for r in records if r["source"]=="toronto_business_licences"]
            self.assertEqual(counts["toronto_business_licences"],2)
            self.assertEqual([r["key"] for r in selected],
                             ["FOOD-NEW","GARAGE-NEW"])
            status=p.run(db,root/"pilot",as_of=TODAY,max_per_source=2)
            self.assertEqual(status["source_diagnostics"]["toronto_business_licences"]["candidates"],2)
            self.assertEqual(status["toronto_licence_selection"],
                             "FULL_ACTIVE_LEDGER_SCANNED_RECENT_ISSUED_ELIGIBLE_BEFORE_LIMIT")
            self.assertEqual(status["verified_openings"],0)
            self.assertEqual(status["verified_buyers"],0)

if __name__=="__main__":unittest.main()
