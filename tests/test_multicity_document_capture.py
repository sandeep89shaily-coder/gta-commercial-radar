"""Hermetic multi-city permitted document capture tests: no live web or AI."""
from __future__ import annotations
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

import requests
from pypdf import PdfWriter
from municipal_document_capture import (CITY_PAGES, _valid_city_url,
    _read_html, _fetch_pdf, run)
import gta_daily_intelligence as integrated

MISS = CITY_PAGES["Mississauga"]
PAGE = "https://www.mississauga.ca/council/planning-agenda/"
PDF = "https://www.mississauga.ca/council/planning-agenda/industrial-report.pdf"
OUTSIDE = "https://www.mississauga.ca.evil.example/report.pdf"


def dns(*a,**kw):
    return [(0,0,0,"",("8.8.8.8",443))]


def pdf_bytes():
    writer=PdfWriter()
    writer.add_blank_page(width=612,height=792)
    memory=io.BytesIO()
    writer.write(memory)
    return memory.getvalue()


class Response:
    def __init__(self,url,data,mime="text/html",status=200,final=None):
        self.url=final or url
        self.content=data
        self.headers={"Content-Type":mime}
        self.status_code=status
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def iter_content(self,chunk_size=65536):
        for p in range(0,len(self.content),chunk_size):
            yield self.content[p:p+chunk_size]


class Session:
    def __init__(self,pages=None):
        self.pages=pages or {}
        self.headers={}
        self.trust_env=True
        self.requested=[]
    def get(self,url,**kwargs):
        self.requested.append((url,kwargs))
        if url not in self.pages:
            raise requests.RequestException("Blocked in offline test: "+url)
        return self.pages[url]


class MultiCityPDFTests(unittest.TestCase):
    def test_city_host_allowlist_stops_external_urls_and_query_redirects(self):
        self.assertEqual(len(CITY_PAGES),7)
        self.assertTrue(_valid_city_url("Mississauga",PAGE))
        self.assertTrue(_valid_city_url("Mississauga",PDF,pdf=True))
        self.assertFalse(_valid_city_url("Mississauga",OUTSIDE,pdf=True))
        self.assertFalse(_valid_city_url("Hamilton",PDF,pdf=True))
        self.assertFalse(_valid_city_url("Mississauga","http://www.mississauga.ca/council/a.pdf",pdf=True))
        self.assertFalse(_valid_city_url("Mississauga","https://attacker@www.mississauga.ca/report.pdf",pdf=True))
        self.assertFalse(_valid_city_url("Mississauga","https://pub-mississauga.escribemeetings.com/x.pdf",pdf=True))
        self.assertFalse(_valid_city_url("Mississauga","https://www.mississauga.ca.evil.net/a.pdf",pdf=True))

    def test_robots_denial_fails_closed_before_any_page_fetch(self):
        response=Response(PAGE,b'<a href="industrial.pdf">Planning</a>')
        session=Session({PAGE:response})
        data=_read_html(session,"Mississauga",PAGE,dns,lambda _: "User-agent: *\nDisallow: /")
        self.assertEqual(data["status"],"BLOCKED")
        self.assertEqual(data["reason"],"ROBOTS_DISALLOWED")
        self.assertFalse(session.requested)

    def test_html_discovery_and_nonpublic_dns_does_not_download(self):
        html=b'''<a href="industrial-report.pdf">Industrial development report</a>
                  <a href="https://evil.example/agenda.pdf">External</a>
                  <a href="https://www.mississauga.ca.evil.net/a.pdf">Spoof</a>'''
        session=Session({PAGE:Response(PAGE,html)})
        result=_read_html(session,"Mississauga",PAGE,dns,lambda _: "User-agent: *\nAllow: /")
        self.assertEqual(result["status"],"FETCHED")
        self.assertEqual([x["url"] for x in result["pdf_links"]],[PDF])
        bad=_read_html(session,"Mississauga",PAGE,lambda *a,**k:[(0,0,0,"",("127.0.0.1",443))],lambda _:"User-agent: *\nAllow: /")
        self.assertEqual(bad["reason"],"NONPUBLIC_OR_UNAVAILABLE_DNS")

    def test_reject_redirect_and_disguised_html_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/"report.pdf"
            redir=Session({PDF:Response(PDF,pdf_bytes(),"application/pdf",final="https://evil.example/report.pdf")})
            x=_fetch_pdf(redir,"Mississauga",PAGE,PDF,dest,dns,lambda _:"User-agent: *\nAllow: /")
            self.assertEqual(x["status"],"FAILED")
            self.assertTrue(x["reason"].startswith("HTTP_OR_REDIRECT"))
            not_pdf=Session({PDF:Response(PDF,b"<html>blocked</html>","application/pdf")})
            x=_fetch_pdf(not_pdf,"Mississauga",PAGE,PDF,dest,dns,lambda _:"User-agent: *\nAllow: /")
            self.assertEqual(x["reason"],"INVALID_PDF_SIGNATURE")
            self.assertFalse(dest.exists())

    def test_capture_city_pdf_and_cite_official_agenda(self):
        markup=("<a href='/council/planning-agenda/'>Planning agenda</a>").encode()
        agenda=("<a href='industrial-report.pdf'>Industrial development staff report</a>"+
                "<a href='https://evil.example/other.pdf'>External report</a>").encode()
        session=Session({MISS:Response(MISS,markup),PAGE:Response(PAGE,agenda),
                         PDF:Response(PDF,pdf_bytes(),"application/pdf")})
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);manifest=root/"meeting.json"
            manifest.write_text(json.dumps({"agenda_candidates":[{"url":PAGE}]}))
            result=run({"Mississauga":{"meeting_index":str(manifest)}},root/"docs",
                       session=session,resolver=dns,policy_reader=lambda _:"User-agent: *\nAllow: /")
            self.assertEqual(result["cities_attempted"],7)
            self.assertEqual(result["direct_pdf_captured"],1)
            self.assertEqual(result["successful_document_cities"],["Mississauga"])
            row=integrated._csv(result["audit_csv"])[0]
            self.assertEqual(row["city"],"Mississauga")
            self.assertEqual(row["source_page"],PAGE)
            self.assertEqual(row["url"],PDF)
            self.assertEqual(row["publisher_date_verified"],"False")
            self.assertTrue(Path(row["saved_path"]).exists())
            self.assertNotIn("evil.example",str(session.requested))
            city=next(x for x in result["city_audit"] if x["city"]=="Mississauga")
            self.assertEqual(city["pdf_captured"],1)

    def test_deepseek_doc_backlog_survives_source_disappearance_and_spending_limit(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            review=root/"DAILY_INTEGRATED_REVIEW"
            review.mkdir()
            all_docs=[]
            for i,city in enumerate(("Mississauga","Toronto","Hamilton")):
                doc=root/("document_"+str(i)+".pdf")
                doc.write_bytes(("document"+str(i)).encode())
                all_docs.append({"url":"https://www.mississauga.ca/council/doc"+str(i)+".pdf",
                                 "status":"CAPTURED","sha256":hashlib.sha256(doc.read_bytes()).hexdigest(),
                                 "saved_path":str(doc),"city":city,
                                 "source_page":PAGE})
            union=root/"union.csv"
            cols=["url","status","sha256","saved_path","city","source_page"]
            with union.open("w",newline="",encoding="utf-8-sig") as h:
                w=csv.DictWriter(h,fieldnames=cols);w.writeheader();w.writerows(all_docs)
            seen={}
            attempted=[]
            def fake_ai(audit,out,results,**kw):
                out=Path(out);out.mkdir(exist_ok=True)
                selected=integrated._csv(audit)
                attempted.extend(row["sha256"] for row in selected)
                with (out/"TORONTO_AI_DOCUMENT_BATCH_AUDIT.csv").open("w",newline="") as h:
                    w=csv.DictWriter(h,fieldnames=["source_url","sha256_download","status","result_file"])
                    w.writeheader()
                    for doc in selected:
                        w.writerow({"source_url":doc["url"],
                                    "sha256_download":doc["sha256"],
                                    "status":"AI_REVIEW_ONLY_NOT_SALE_READY",
                                    "result_file":""})
                return {"review_outputs":len(selected)}
            first,summary,seen=integrated._build_document_worklist(
                union,review,seen,paid=True,ai_processor=fake_ai,
                ranker=lambda _:{"score":18,"eligible_for_paid_ai":True})
            self.assertEqual(len(first),2)
            self.assertEqual(summary["document_ai_backlog_pending"],1)
            # The pending source disappears from the next daily index: keep
            # the downloaded document and complete its research regardless.
            with union.open("w",newline="",encoding="utf-8-sig") as h:
                w=csv.DictWriter(h,fieldnames=cols);w.writeheader()
            second,summary,seen=integrated._build_document_worklist(
                union,review,seen,paid=True,ai_processor=fake_ai,
                ranker=lambda _:{"score":18,"eligible_for_paid_ai":True})
            self.assertEqual(len(second),1)
            self.assertEqual(summary["document_ai_backlog_pending"],0)
            self.assertEqual(len(set(attempted)),3)
            self.assertEqual(len(attempted),3)

    def test_city_pdf_consumed_by_same_budgeted_document_ai_and_combined_review(self):
        from tests.test_daily_integrated_intelligence import DailyIntegrationTests, write_csv
        test=DailyIntegrationTests("test_daily_integrates_municipal_sources_doc_research_and_buyer_worklist")
        test.setUp()
        try:
            doc=test.root/"another_city.pdf"
            doc.write_bytes(pdf_bytes())
            import hashlib
            digest=hashlib.sha256(doc.read_bytes()).hexdigest()
            def multicity(meetings,out):
                out=Path(out);out.mkdir(parents=True,exist_ok=True)
                write_csv(out/"MULTICITY_PDF_FETCH_AUDIT.csv",[{
                    "city":"Mississauga","source_page":PAGE,"url":PDF,
                    "status":"CAPTURED","sha256":digest,"saved_path":str(doc),
                }],["city","source_page","url","status","reason","http_status","bytes","sha256","saved_path"])
                return {"cities_attempted":7,"direct_pdf_captured":1,
                        "successful_document_cities":["Mississauga"],"city_audit":[]}
            result=test.execute(multicity_capture=multicity)
            self.assertEqual(result["meeting_documents_fetched_outside_toronto"],1)
            self.assertEqual(result["pdfs_captured_in_union"],2)
            self.assertEqual(result["municipal_documents_for_review"],2)
            rows=integrated._csv(result["combined_csv"])
            docs=[r for r in rows if r["kind"]=="MUNICIPAL_DOCUMENT_REVIEW"]
            self.assertEqual({r["city"] for r in docs},{"Mississauga","Toronto"})
            mississauga=next(r for r in docs if r["city"]=="Mississauga")
            self.assertEqual(mississauga["source_url"],PDF)
            self.assertEqual(result["document_ai"]["review_outputs"],2)
            register=integrated._csv(result["document_project_candidates"]["review_only_csv"])
            self.assertEqual(len(register),2)
            self.assertEqual({r["city"] for r in register},{"Mississauga","Toronto"})
            self.assertTrue(all(r["canonical_project_match_status"]=="UNVERIFIED_NO_AUTO_MERGE"
                                for r in register))
            self.assertTrue(all(r["verified_purchasing_authority"]=="False" for r in register))
            self.assertEqual(result["deepseek_shared_ceiling_usd"],0.25)
            second=test.execute(multicity_capture=multicity)
            self.assertEqual(second["document_ai"]["status"],"NO_NEW_DOCUMENT_BYTES")
            self.assertEqual(second["persistent_document_project_candidates"],2)
        finally:
            test.doCleanups()


if __name__=="__main__":
    unittest.main()
