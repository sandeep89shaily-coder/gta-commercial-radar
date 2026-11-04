import datetime as dt
from gta_regional_early_intelligence import run,SOURCES,_extract
def test_all_nine_authorities():
 assert set(SOURCES)=={"Toronto","Hamilton","York","Peel","Halton","Durham","Waterloo","Niagara","Simcoe"}
def test_link_parse_and_baseline(tmp_path):
 src={"York":{"url":"https://www.york.ca/projects","kind":"INFRASTRUCTURE_INDEX"}}
 page="""<html><main><a href="/projects/reservoir">King City water reservoir expansion</a>
 <a href="https://evil.example/irrelevant">Unrelated development</a>
 <a href="/privacy">Privacy policy</a></main></html>"""
 f=lambda url:page
 first=run(tmp_path,today=dt.date(2026,11,4),sources=src,fetcher=f)
 assert first["records"]==1 and first["new_or_changed"]==0
 second=run(tmp_path,today=dt.date(2026,11,5),sources=src,fetcher=f)
 assert second["new_or_changed"]==0
 later=run(tmp_path,today=dt.date(2026,11,6),sources=src,
            fetcher=lambda url:page.replace("reservoir expansion","reservoir expansion project phase 2"))
 assert later["new_or_changed"]==1
 assert later["verified_commercial_opportunities"]==0
def test_fetch_failure_keeps_existing_state(tmp_path):
 src={"York":{"url":"https://www.york.ca/projects","kind":"INFRASTRUCTURE_INDEX"}}
 page='<main><a href="/projects/water">King City water reservoir expansion</a></main>'
 run(tmp_path,sources=src,fetcher=lambda _:page)
 result=run(tmp_path,sources=src,fetcher=lambda _:(_ for _ in ()).throw(ValueError("ROBOTS_ACCESS_DENIED")))
 assert result["authorities_failed"]==1
 again=run(tmp_path,sources=src,fetcher=lambda _:page)
 assert again["records"]==1 and again["new_or_changed"]==0
def test_waterloo_table_requires_project_and_status(tmp_path):
 src={"Waterloo":{"url":"https://www.regionofwaterloo.ca/projects","kind":"INFRASTRUCTURE_INDEX"}}
 page="""<main><table><tr><th>Project</th><th>Where</th><th>Current status</th></tr>
 <tr><td>Cedar Creek Water Tower</td><td>North Dumfries</td><td>Design</td></tr></table></main>"""
 r=run(tmp_path,sources=src,fetcher=lambda _:page)
 assert r["records"]==1
 assert r["new_or_changed"]==0
