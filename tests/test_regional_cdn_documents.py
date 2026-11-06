"""Protect Waterloo official document CDN against domain/path spoofing."""
import csv
import json
from gta_regional_project_details import _evidence,_approved_document_url
from gta_regional_document_evidence import _candidates


PAGE="https://www.regionofwaterloo.ca/programs-and-services/roads-and-transportation/road-construction/construction-projects/maple-grove-road/"
CDN="https://media-003-ca.cdn.govstack.com/regionofwaterloo-018-ca/media/abc123/notice.pdf"


def test_only_waterloo_publisher_linked_cdn_and_same_host_are_allowed():
 assert _approved_document_url(CDN,PAGE,"Waterloo")
 assert not _approved_document_url(CDN,PAGE,"York")
 assert not _approved_document_url(CDN.replace("govstack.com","govstack.com.evil.example"),PAGE,"Waterloo")
 assert not _approved_document_url(CDN.replace("/regionofwaterloo-018-ca/media/","/elsewhere/"),PAGE,"Waterloo")
 assert not _approved_document_url(CDN+"?token=private",PAGE,"Waterloo")
 assert not _approved_document_url(CDN.replace("https:","http:"),PAGE,"Waterloo")
 assert not _approved_document_url(CDN.replace(".pdf",".exe"),PAGE,"Waterloo")
 assert _approved_document_url("https://www.regionofwaterloo.ca/files/report.pdf",PAGE,"Waterloo")


def test_notice_is_prioritized_before_large_old_appendices():
 html="""<main><h1>Maple Grove Road</h1>
 <p>The Region is undertaking road widening and bridge rehabilitation.</p>
 <a href="https://media-003-ca.cdn.govstack.com/regionofwaterloo-018-ca/media/study/report.pdf">Environmental study report</a>
 <a href="https://media-003-ca.cdn.govstack.com/regionofwaterloo-018-ca/media/a/appendix.pdf">Appendix A</a>
 <a href="https://media-003-ca.cdn.govstack.com/regionofwaterloo-018-ca/media/abc123/notice.pdf">Construction notice</a>
 <a href="https://media-003-ca.cdn.govstack.com/elsewhere/unsafe.pdf">Not owned by this region</a>
 </main>"""
 record=_evidence(html,{"authority":"Waterloo","source_url":PAGE,"project_title":"Maple Grove Road"})
 urls=json.loads(record["official_pdf_urls_json"])
 assert record["document_links_count"]==4
 assert urls[0]==CDN
 assert len(urls)==3
 assert "unsafe" not in json.dumps(urls)


def test_approved_document_queue_remains_bounded_and_city_specific():
 project={"authority":"Waterloo","project_id":"P1","project_url":PAGE,
          "official_pdf_urls_json":json.dumps([CDN,CDN])}
 york={"authority":"York","project_id":"P2","project_url":"https://www.york.ca/road-project",
       "official_pdf_urls_json":json.dumps([CDN])}
 queue=_candidates([project,york])
 assert len(queue)==1
 assert queue[0][1]==CDN
