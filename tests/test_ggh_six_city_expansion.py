"""Six newly configured GGH planning authorities: trustworthy file-ID recovery."""
import datetime as dt
from gta_ggh_early_planning import SOURCES,run
from gta_ggh_six_city_sources import notice_links, extract_notice, extract_thorold


def test_ggh_now_twelve_sources():
    assert len(SOURCES)==12
    assert {"Richmond Hill","Newmarket","Innisfil","New Tecumseth",
            "Bradford West Gwillimbury","Thorold"}.issubset(SOURCES)


def test_bradford_notice_level_ids_and_first_seen(tmp_path):
    root=SOURCES["Bradford West Gwillimbury"]
    url="https://www.townofbwg.com/news/posts/notice-september-16-2025/"
    index=f'<main><a href="{url}">Notice of Complete Application and Public Meeting</a></main>'
    detail="""<main><h1>Notice: September 16, 2025</h1>
    <p>Owner: Sandstorm Development Inc.</p>
    <p>Agent: Jones Consulting Group Ltd.</p>
    <p>Location: PLAN 51M1259 BLK 91 and 92</p>
    <p>File No.: D14-25-09 (Zoning By-law) and D12-25-10 (Subdivision)</p>
    <p>Development review of a proposed commercial employment development.</p>
    <time datetime="2025-09-16">September 16</time></main>"""
    def fetch(url_arg):
        return index if url_arg==root else detail
    first=run(tmp_path,sources={"Bradford West Gwillimbury":root},
              fetcher=fetch,today=dt.date(2026,11,4))
    assert first["application_id_rows"]==2
    assert first["new_or_changed"]==0
    assert first["source_status"][0]["notice_pages_targeted"]==1
    assert first["source_status"][0]["notice_pages_fetched"]==1
    second=run(tmp_path,sources={"Bradford West Gwillimbury":root},
               fetcher=fetch,today=dt.date(2026,11,5))
    assert second["new_or_changed"]==0


def test_new_tecumseth_notice_with_explicit_id(tmp_path):
    root=SOURCES["New Tecumseth"]
    detail="https://www.newtecumseth.ca/news/posts/notice-of-complete-application/"
    site=f'<main><a href="{detail}">Notice of Complete Application and Public Meeting - 5742 14th Line</a></main>'
    page="""<main><h1>Proposed Industrial Property</h1>
    <p>Subject Land: 5742 14th Line, New Tecumseth</p>
    <p>City File Number: D14-2026-001</p>
    <p>Proposed warehouse construction and site planning.</p></main>"""
    result=run(tmp_path,sources={"New Tecumseth":root},
               fetcher=lambda u:site if u==root else page)
    assert result["application_id_rows"]==1
    assert result["source_status"][0]["notice_pages_targeted"]==1


def test_index_only_sources_are_not_application_success(tmp_path):
    src={k:SOURCES[k] for k in ("Richmond Hill","Newmarket","Innisfil")}
    page='<main><h1>Development Applications</h1><p>Review our online map.</p><p>Contact planning staff.</p></main>'
    result=run(tmp_path,sources=src,fetcher=lambda _:page)
    assert result["cities_configured"]==3
    assert result["cities_with_application_ids"]==0
    assert result["application_id_rows"]==0
    assert all(x["state"]=="NO_APPLICATION_ID_ROWS" for x in result["source_status"])


def test_notice_without_city_file_does_not_fabricate_id(tmp_path):
    root=SOURCES["Bradford West Gwillimbury"]
    detail="https://www.townofbwg.com/news/posts/new-warehouse-application/"
    page='<main><a href="'+detail+'">Notice of Complete Application</a></main>'
    content='<main><h1>New Warehouse 2026</h1><p>Proposed new warehouse site.</p><p>Phone: 905-775-5366</p></main>'
    x=run(tmp_path,sources={"Bradford West Gwillimbury":root},
          fetcher=lambda u:page if u==root else content)
    assert x["application_id_rows"]==0
    assert x["source_status"][0]["notice_pages_fetched"]==1


def test_notice_access_failure_still_reports_city_status(tmp_path):
    root=SOURCES["New Tecumseth"]
    page='<main><a href="/news/posts/notice-of-complete-application/">Notice of Complete Application</a></main>'
    def fetch(url):
        if url==root:return page
        raise ValueError("ROBOTS_ACCESS_DENIED")
    result=run(tmp_path,sources={"New Tecumseth":root},fetcher=fetch)
    x=result["source_status"][0]
    assert x["state"]=="NO_APPLICATION_ID_ROWS"
    assert x["notice_pages_targeted"]==1
    assert len(x["notice_page_errors"])==1
    assert result["application_id_rows"]==0


def test_thorold_file_label_required():
    from gta_ggh_early_planning import _record
    url=SOURCES["Thorold"]
    page="""<main><h2>90 and 100 Hayes Road (Bioveld)</h2>
    <p>Proposed industrial intermodal yard under review.</p>
    <p>Historical zoning by-law amendment D14-02-2019 is mentioned for context.</p>
    <h2>Confederation Heights Subdivision</h2>
    <p>City File No. D14-09-2026. A residential subdivision.</p></main>"""
    x=extract_thorold(page,url,_record)
    assert len(x)==1
    assert x[0]["application_id"]=="D14-09-2026"
    assert x[0]["city"]=="Thorold"


def test_external_notice_link_not_followed():
    url=SOURCES["Bradford West Gwillimbury"]
    html='<main><a href="https://evil.example/news/posts/notice-of-complete-application/">Notice of Complete Application</a></main>'
    assert notice_links(html,"Bradford West Gwillimbury",url)==[]



def test_thorold_official_supporting_document_label():
    from gta_ggh_early_planning import _record
    url=SOURCES["Thorold"]
    html="""<main>
    <h2>1201 Egerter Road - Zoning By-law Amendment</h2>
    <p>The application concerns the existing rural industrial property.</p>
    <a href="https://media-003-ca.cdn.govstack.com/file.pdf">
    D14-09-2026 - Development Approvals Application</a>
    <h2>26 Clairmont Street</h2><p>Existing unrelated consent D10-18-2025</p>
    </main>"""
    found=extract_thorold(html,url,_record)
    assert {r["application_id"] for r in found}=={"D14-09-2026"}
    assert found[0]["address"].startswith("1201 Egerter")
    assert found[0]["official_record_url"]==url


def test_new_tec_official_full_notice_pdf_link():
    from gta_ggh_six_city_sources import new_tec_pdf_links
    notice_url="https://www.newtecumseth.ca/news-and-notices/notice-of-complete-application/"
    html="""<main><a href="/en/news/resources/Planning-Notices-/Notice-of-Complete-App--PM.pdf">
    Click here to view the full notice for more information.</a>
    <a href="https://evil.example/fake.pdf">full notice</a></main>"""
    assert new_tec_pdf_links(html,notice_url)==[
      "https://www.newtecumseth.ca/en/news/resources/Planning-Notices-/Notice-of-Complete-App--PM.pdf"]


def test_new_tec_pdf_extract_file_id_with_mock_pdf_reader(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import gta_ggh_six_city_sources as mod
    from gta_ggh_early_planning import _record
    page=SimpleNamespace(extract_text=lambda:(
      "The Corporation of the Town of New Tecumseth Notice of a Complete Application "
      "and Public Meeting concerning a Proposed Zoning By-law Amendment. "
      "File No. D14-2026-003. The southern portion of the property is municipally known as "
      "5742 14th Line, in the Town of New Tecumseth. "
      "The proposed zoning changes concern a low-rise residential project. "
      "All application materials are available for public review. "))
    monkeypatch.setattr("pypdf.PdfReader",lambda fp:SimpleNamespace(is_encrypted=False,pages=[page]))
    url="https://www.newtecumseth.ca/en/news/resources/notice.pdf"
    rows=mod.extract_new_tec_pdf(b"%PDF-1.7\nfixture",url,SOURCES["New Tecumseth"],_record)
    assert len(rows)==1
    assert rows[0]["application_id"]=="D14-2026-003"
    assert rows[0]["official_record_url"]==url
    assert rows[0]["source_date"]==""
    assert rows[0]["commercial_fit"]=="UNCLASSIFIED_REVIEW"


def test_new_tec_end_to_end_pdf_stage_injected(tmp_path,monkeypatch):
    from types import SimpleNamespace
    pdf="https://www.newtecumseth.ca/en/news/resources/notice.pdf"
    detail="https://www.newtecumseth.ca/news-and-notices/notice-of-complete-application/"
    index=SOURCES["New Tecumseth"]
    index_html=f'<main><a href="{detail}">Notice of Complete Application</a></main>'
    notice_html=f'<main><h1>Development Notice</h1><a href="{pdf}">full notice</a></main>'
    text=("Notice of Complete Application and Public Meeting. File No. D14-2026-003. "
          "The application is for a commercial distribution warehouse and office. "
          "The lands are municipally known as 100 Industrial Road, New Tecumseth.")
    monkeypatch.setattr("pypdf.PdfReader",lambda fp:SimpleNamespace(
        is_encrypted=False,pages=[SimpleNamespace(extract_text=lambda:text)]))
    result=run(tmp_path,sources={"New Tecumseth":index},
       fetcher=lambda u:index_html if u==index else notice_html,
       pdf_fetcher=lambda url:b"%PDF-1.7\nmock")
    assert result["application_id_rows"]==1
    status=result["source_status"][0]
    assert status["notice_pdfs_attempted"]==1
    assert status["notice_pdfs_fetched"]==1
    assert result["new_or_changed"]==0
