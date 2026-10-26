"""Offline tests for document extraction, project identity, review gates and scheduling."""
import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import radar_workspace as workspace
import radar_project_engine as engine
import radar_production as production


class ProjectIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)/"GTA_RADAR"
        self.master=workspace.setup(self.home)

    def record(self, sid, rid, *, city="Brampton", app="", address="42 Queen Street",
               desc="Proposed industrial manufacturing facility",
               url="https://www.brampton.ca/public/application",
               stage="PRE_CONSULTATION"):
        item=dict(city=city,application_id=app,location=address,
                  description=desc,source_url=url,stage=stage)
        with sqlite3.connect(self.master) as db:
            db.execute("""INSERT INTO records
                (source_id,record_id,first_seen_at,last_seen_at,source_date,
                 payload_json,payload_hash,last_imported_at,provenance)
                 VALUES(?,?,?,?,?,?,?,?,?)""",
                 (sid,rid,"2026-10-20T10:00:00+00:00","2026-10-25T10:00:00+00:00",
                  "2024-01-03",json.dumps(item),"hash","2026-10-26","test"))

    def csvread(self, name):
        with (self.home/"Results"/name).open(encoding="utf-8-sig",newline="") as f:
            return list(csv.DictReader(f))

    def test_same_city_and_published_application_collapses_sources(self):
        self.record("brampton_site_plans","A",app="SP-123")
        self.record("brampton_rezoning_opa","B",app="SP-123")
        report=engine.build(self.home)
        self.assertEqual(report["research_candidates"],1)
        rows=self.csvread(engine.PROJECT_FILE)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["source_count"],"2")
        self.assertEqual(rows[0]["buyer_status"],"UNVERIFIED")
        self.assertEqual(rows[0]["supplier_selection_status"],"UNKNOWN")
        with sqlite3.connect(self.master) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM project_record_edges").fetchone()[0],2)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM project_facts WHERE field_name='application_id'").fetchone()[0],2)

    def test_different_municipalities_never_group_same_reference(self):
        self.record("brampton_site_plans","A",app="SP-123")
        self.record("mississauga_site_plans","B",city="Mississauga",app="SP-123")
        self.assertEqual(engine.build(self.home)["research_candidates"],2)

    def test_address_similarity_creates_review_link_not_auto_merge(self):
        self.record("brampton_site_plans","A",app="SP-123",address="42 Queen Street")
        self.record("brampton_rezoning_opa","B",app="RZ-999",address="42 Queen St")
        report=engine.build(self.home)
        self.assertEqual(report["research_candidates"],2)
        self.assertEqual(report["possible_links_for_review"],1)
        links=self.csvread(engine.LINK_FILE)
        self.assertEqual(links[0]["status"],"REVIEW_REQUIRED")
        self.assertEqual(len(self.csvread(engine.PROJECT_FILE)),2)

    def test_weak_identity_and_missing_evidence_are_not_published(self):
        self.record("brampton_site_plans","A",address="unknown",app="",url="")
        engine.build(self.home)
        self.assertEqual(self.csvread(engine.PROJECT_FILE),[])
        review=self.csvread(engine.REVIEW_FILE)
        self.assertEqual(len(review),1)
        self.assertIn("IDENTITY_UNCERTAIN",review[0]["review_reason"])
        self.assertIn("SOURCE_URL_MISSING",review[0]["review_reason"])

    def test_inactive_or_noncommercial_records_excluded(self):
        self.record("brampton_site_plans","A",stage="Withdrawn")
        self.record("brampton_site_plans","B",desc="Single family residence")
        report=engine.build(self.home)
        self.assertEqual(report["research_candidates"],0)
        self.assertEqual(report["needs_review"],1)

    def test_document_excerpt_and_provenance(self):
        folder=self.home/"Data"/"official_documents"
        folder.mkdir()
        (folder/"staff.txt").write_text(
            "Official staff report for public consideration. Proposed "
            "industrial warehouse facility with loading docks and new storage.",
            encoding="utf-8")
        with (folder/"manifest.csv").open("w",encoding="utf-8",newline="") as f:
            writer=csv.writer(f)
            writer.writerow(["filename","source_url","document_type","public_date",
                             "city","address","application_id"])
            writer.writerow(["staff.txt","https://www.brampton.ca/report/1",
                             "STAFF_REPORT","2026-10-02","Brampton",
                             "42 Queen Street","SP-123"])
        report=engine.build(self.home)
        self.assertEqual(report["documents_checked"],1)
        self.assertEqual(report["research_candidates"],1)
        with sqlite3.connect(self.master) as db:
            actual=db.execute("SELECT extraction_status FROM project_documents").fetchone()[0]
            self.assertEqual(actual,"READY")
            fact=db.execute("SELECT verification,source_url,field_value FROM project_facts "
                            "WHERE field_name='document_scope_excerpt'").fetchone()
            self.assertEqual(fact[0],"DOCUMENT_TEXT_EXTRACTION_NOT_FACT_CHECKED")
            self.assertEqual(fact[1],"https://www.brampton.ca/report/1")
            self.assertIn("warehouse",fact[2])
        self.assertEqual(engine.build(self.home)["research_candidates"],1)

    def test_no_paid_ai_and_pipeline_integration(self):
        self.record("brampton_site_plans","A",app="SP-999")
        # Test production integration with synthetic existing V8 using its fixture.
        from test_radar_v8_migration import make_v8
        from radar_v8_migration import adopt_database
        incoming=Path(self.tmp.name)/"old"/"radar.sqlite"
        make_v8(incoming)
        adopt_database(self.home,incoming,workspace._has_fields)
        report=production.run(self.home,core=lambda _:0,
                              early=lambda _:{"status":"SUCCESS","source_issues":0})
        self.assertEqual(report["project_status"],"SUCCESS")
        self.assertEqual(report["project_intelligence"]["research_candidates"],1)
        self.assertEqual(report["deepseek_calls"],0)
        self.assertIn("Evidence-linked project research",
                      (self.home/"Results"/"GTA_RADAR_OPERATIONS.html").read_text(encoding="utf-8"))


if __name__=="__main__":
    unittest.main()
