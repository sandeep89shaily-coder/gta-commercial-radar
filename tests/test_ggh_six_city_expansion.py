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
