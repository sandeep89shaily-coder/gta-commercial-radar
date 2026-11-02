"""Offline end-to-end regression for integrated DAILY collector, research and reports."""
from __future__ import annotations
import csv
import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import gta_daily_intelligence as daily

TODAY = dt.date(2026, 11, 2)


def write_csv(path,rows,fields=None):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fields=fields or list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w",encoding="utf-8-sig",newline="") as out:
        w=csv.DictWriter(out,fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


class DailyIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.calls=[]
        self.project={
            "project_id":"toronto_active_building_permits:26 333333",
            "address":"10 Industrial Parkway",
            "city":"Toronto","observation":"FIRST_OBSERVED",
            "description":"New industrial warehouse expansion with loading docks",
            "source_record_date":"2026-11-01",
            "first_seen_local":"2026-11-02",
            "freshness_band":"SOURCE_DATED_0_7_DAYS",
            "freshness_date_basis":"SOURCE_RECORD_DATE_NOT_PUBLICATION_PROOF",
            "source_id":"toronto_active_building_permits",
            "source_keys":"26 333333 BLD",
            "lane":"PERMIT_REVIEW","review_priority":"85",
            "current_source_status":"Under Review",
            "record_source_url":"https://secure.toronto.ca/council/agenda-item.do?item=2026.PH30.1",
        }
        write_csv(self.root/daily.PROJECT_INPUT,[self.project])
        (self.root/"EARLY_SIGNAL_FEED_AUDIT.json").write_text(json.dumps({
            "candidate_links":[{
                "feed":"brampton_planning",
                "url":"https://www1.brampton.ca/EN/City-Hall/Council-Committees/meetings-agendas/",
                "title":"Industrial development planning report",
                "first_seen_utc":"2026-11-02T13:00:00+00:00",
            }],
        }))
        self.pdf=self.root/"source.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\npreview test only")
        self.sha=hashlib.sha256(self.pdf.read_bytes()).hexdigest()

    def meeting(self,city,output,**kwargs):
        self.calls.append(("meeting",city))
        assert kwargs.get("include_procurement") is False
        Path(output).mkdir(parents=True,exist_ok=True)
        return {"city":city,"official_videos_discovered":0}

    def discovered(self,indexes,out,**kwargs):
        self.calls.append(("document_index",len(indexes)))
        write_csv(Path(out)/"AUTOMATIC_DOCUMENT_DISCOVERY.csv",[],
                  ["city","index_url","document_url","document_id",
                   "discovered_at","status","reason"])
        return {"indexes_checked":len(indexes),
                "discovered_csv":str(Path(out)/"AUTOMATIC_DOCUMENT_DISCOVERY.csv")}

    def agenda(self,seeds,out,**kwargs):
        self.calls.append(("agenda",kwargs.get("fetch")))
        assert kwargs.get("max_pdfs")==3
        write_csv(Path(out)/"TORONTO_PDF_FETCH_AUDIT.csv",[
            {"url":"https://secure.toronto.ca/doc.pdf","status":"CAPTURED",
             "saved_path":str(self.pdf),"sha256":self.sha},
        ],["url","status","reason","http_status","bytes","sha256","saved_path"])
        return {"meetings_fetched":1,"pdf_downloaded":1}

    def reports(self,seed,out,**kwargs):
        self.calls.append(("reports",kwargs.get("fetch")))
        write_csv(Path(out)/"VERIFIED_REPORT_FETCH_AUDIT.csv",[],
                  ["attachment_url","status","reason","http_status","bytes","sha256","saved_path"])
        return {"captured":0}

    def document_ai(self,audit,out,results,**kwargs):
        self.calls.append(("document_ai",kwargs.get("paid")))
        assert kwargs.get("limit")==2
        rows=daily._csv(audit)
        Path(out).mkdir(parents=True,exist_ok=True)
        for r in rows:
            model=Path(out)/"pdf_analysis.json"
            if kwargs["paid"]:
                model.write_text(json.dumps({"model_output":{
                    "address":"10 Industrial Parkway",
                    "proposed_scope":"Warehouse expansion",
                    "developer":"Possible Developer Ltd",
                }}),encoding="utf-8")
            write_csv(Path(out)/"TORONTO_AI_DOCUMENT_BATCH_AUDIT.csv",[
                {"source_url":r["url"],"sha256_download":r["sha256"],
                 "status":"AI_REVIEW_ONLY_NOT_SALE_READY" if kwargs["paid"] else "READY_NOT_SENT",
                 "result_file":str(model) if kwargs["paid"] else ""},
            ])
        return {"status":"DOCUMENTS_REVIEWED","review_outputs":len(rows) if kwargs["paid"] else 0,
                "ai_calls_reported":len(rows) if kwargs["paid"] else 0}

    def project_ai(self,source,root,review,**kwargs):
        self.calls.append(("project_ai",kwargs.get("paid")))
        self.assertEqual([r["project_id"] for r in daily._csv(source)],
                         [self.project["project_id"]])
        self.assertEqual(kwargs["max_projects"],2)
        return {"status":"REVIEW_ONLY_RESULTS","completed":1}

    def buyer_ai(self,review,root,**kwargs):
        self.calls.append(("buyer_ai",kwargs.get("paid")))
        return {"status":"NO_EXACT_SOURCE_EXCERPTS","verified_buyers":0}

    def procurement(self,source,review_dir,**kwargs):
        self.calls.append(("procurement",kwargs.get("limit")))
        return {"status":"NO_SOURCED_BUYER_OBSERVATIONS"}

    def buyer_batch(self,root,review,**kwargs):
        self.calls.append(("buyer_batch",kwargs.get("top")))
        return {"records":[],"verified_buyers":0,"verified_open_packages":0}

    def graph(self,root,review):
        self.calls.append(("graph",str(review)))
        return {"graph_nodes":0,"verified_private_leads":0}

    def execute(self,*,paid=True,**change):
        kw={"meeting_pipeline":self.meeting,"document_discover":self.discovered,
            "agenda_pipeline":self.agenda,"verified_reports":self.reports,
            "document_ai":self.document_ai,"project_ai":self.project_ai,
            "buyer_ai":self.buyer_ai,"procurement":self.procurement,
            "buyer_batch":self.buyer_batch,"graph":self.graph,
            "api_key_check":lambda:paid,"today":TODAY}
        kw.update(change)
        return daily.integrate(self.root,**kw)

    def test_daily_integrates_municipal_sources_doc_research_and_buyer_worklist(self):
        state=self.execute()
        self.assertEqual(state["status"],"INTEGRATED_REVIEW_READY")
        self.assertEqual(state["deepseek_shared_ceiling_usd"],0.25)
        self.assertEqual(state["new_source_dated_project_candidates"],1)
        self.assertEqual(state["pdfs_captured_in_union"],1)
        self.assertEqual(state["permit_planning_events"],1)
        self.assertEqual(state["municipal_documents_for_review"],1)
        self.assertEqual(state["new_source_index_links_for_review"],1)
        self.assertEqual(state["combined_records"],3)
        self.assertFalse(state["automated_sales_outreach"])
        self.assertTrue(state["manual_purchaser_and_supplier_verification_required"])
        rows=daily._csv(state["combined_csv"])
        self.assertEqual([r["kind"] for r in rows],
                         ["PROJECT","SOURCE_INDEX_LINK_REVIEW","MUNICIPAL_DOCUMENT_REVIEW"])
        self.assertEqual(rows[-1]["date_basis"],"PDF_CAPTURE_DATE_NOT_PUBLICATION")
        self.assertTrue(Path(state["combined_html"]).exists())
        self.assertTrue(any(x[0]=="project_ai" for x in self.calls))
        self.assertTrue(any(x[0]=="buyer_ai" for x in self.calls))
        text=Path(state["combined_html"]).read_text(encoding="utf-8")
        self.assertIn("purchasing authority",text.lower())
        self.assertIn("Original source",text)

    def test_same_pdf_bytes_are_not_paid_again(self):
        first=self.execute()
        self.assertEqual(first["document_ai"]["review_outputs"],1)
        self.calls.clear()
        second=self.execute()
        self.assertFalse(any(x[0]=="document_ai" for x in self.calls))
        self.assertEqual(second["document_ai"]["status"],"NO_NEW_DOCUMENT_BYTES")
        self.assertEqual(len(daily._json(self.root/daily.DOC_LEDGER)),1)
        self.assertEqual(len(daily._csv(second["combined_csv"])),2)

    def test_no_api_key_does_not_pay_for_document_or_project_or_buyer(self):
        outcome=self.execute(paid=False)
        self.assertFalse(any(x[0]=="project_ai" for x in self.calls))
        self.assertFalse(any(x[0]=="buyer_ai" for x in self.calls))
        self.assertIn(("document_ai",False),self.calls)
        self.assertEqual(outcome["deepseek_document_project_buyer_stages_authorized"],False)
        self.assertEqual(outcome["document_ai"]["review_outputs"],0)

    def test_collector_failure_blocks_all_additional_paid_calls(self):
        result=self.execute(allow_paid=False)
        self.assertFalse(any(x[0]=="project_ai" for x in self.calls))
        self.assertIn(("document_ai",False),self.calls)
        self.assertEqual(result["additional_paid_research_permitted"],False)

    def test_meeting_access_failure_is_visible_not_silently_marked_success(self):
        def failing_meeting(city,out,**kwargs):
            if city=="Brampton":
                raise RuntimeError("Official agenda access refused")
            return self.meeting(city,out,**kwargs)
        result=self.execute(meeting_pipeline=failing_meeting)
        self.assertEqual(result["status"],"PARTIAL_REVIEW_REQUIRED")
        self.assertIn("meeting_brampton",result["failed_stages"])
        self.assertTrue(Path(result["combined_html"]).exists())
        status=daily._json(self.root/daily.AUDIT)
        self.assertEqual(status["status"],"PARTIAL_REVIEW_REQUIRED")
        self.assertTrue(status["manual_purchaser_and_supplier_verification_required"])

    def test_historical_first_seen_does_not_get_deeper_paid_project_research(self):
        old=dict(self.project,project_id="toronto:old",source_record_date="2025-01-01",
                 freshness_band="HISTORICAL_SOURCE_DATE")
        write_csv(self.root/daily.PROJECT_INPUT,[old])
        status=self.execute()
        self.assertFalse(any(x[0]=="project_ai" for x in self.calls))
        self.assertEqual(status["new_source_dated_project_candidates"],0)
        rows=daily._csv(status["combined_csv"])
        self.assertEqual(rows[0]["project_id"],"toronto:old")

    def test_escape_untrusted_html_and_source_urls(self):
        bad=dict(self.project,description="<script>alert(1)</script>", 
                 record_source_url="javascript:alert(1)")
        write_csv(self.root/daily.PROJECT_INPUT,[bad])
        state=self.execute(paid=False)
        report=Path(state["combined_html"]).read_text(encoding="utf-8")
        self.assertIn("&lt;script&gt;",report)
        self.assertNotIn("<script>",report)
        self.assertNotIn("href='javascript:",report)


if __name__=="__main__":
    unittest.main()
