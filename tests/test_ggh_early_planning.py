import datetime as dt
from gta_ggh_early_planning import SOURCES,run
def test_sources_twelve_ggh_not_original_sixteen():
 assert len(SOURCES)==12
def test_niagara_brant_baseline_and_diff(tmp_path):
 sources={"Niagara Falls":"https://webpublic.niagarafalls.ca/Planning/",
          "County of Brant":"https://www.brant.ca/planning-and-development/active-applications/"}
 content={
  "Niagara Falls":'<table><tr><td><a href="/Planning/Details/411">AM-2026-013</a></td><td>8168 McLeod Road</td><td>Official Plan Amendment Retail Store</td></tr></table>',
  "County of Brant":'<table><tr><td>ZBA21-26-RF</td><td>75 Highway 53</td><td>Zoning By-law Amendment for Industrial Warehouse</td><td>TBD</td></tr></table>'}
 def fetch(url):return content["Niagara Falls" if "niagarafalls" in url else "County of Brant"]
 first=run(tmp_path,today=dt.date(2026,11,4),sources=sources,fetcher=fetch)
 assert first["application_id_rows"]==2 and first["new_or_changed"]==0
 again=run(tmp_path,today=dt.date(2026,11,5),sources=sources,fetcher=fetch)
 assert again["new_or_changed"]==0
 content["Niagara Falls"]=content["Niagara Falls"].replace("Retail Store","Retail Store Expansion")
 third=run(tmp_path,today=dt.date(2026,11,6),sources=sources,fetcher=fetch)
 assert third["new_or_changed"]==1
def test_peterborough_file_id(tmp_path):
 src={"Peterborough":SOURCES["Peterborough"]}
 page='<main><h3>1810 Fisher Drive</h3><p>Application for Site Plan Approval</p><p>File Number: SPC 1051</p><p>Proposed industrial warehouse and office</p></main>'
 r=run(tmp_path,sources=src,fetcher=lambda _:page)
 assert r["application_id_rows"]==1
def test_source_failure_isolated(tmp_path):
 src={"Niagara Falls":SOURCES["Niagara Falls"]}
 r=run(tmp_path,sources=src,fetcher=lambda _:(_ for _ in ()).throw(ValueError("ROBOTS_ACCESS_DENIED")))
 assert r["source_status"][0]["state"]=="FAILED"
 assert r["application_id_rows"]==0

def test_barrie_official_fileno_not_objectid():
 from gta_ggh_early_planning import _barrie_gis
 url="https://gispublic.barrie.ca/arcgis/rest/services/Public/AnnexedLand_ActiveApplications_WA_Static/MapServer/4"
 def fetch(endpoint,params):
  if not endpoint.endswith("/query"):
   return {"fields":[{"name":x} for x in ("OBJECTID","FILENO","LOCATION","STATUS","DESCRIPT")]}
  return {"features":[
    {"attributes":{"OBJECTID":15,"FILENO":"D12-2026-001","LOCATION":"100 Industrial Rd",
                   "DESCRIPT":"Industrial logistics warehouse","STATUS":"Under Review","TYPE":"Site Plan",
                   "APPLICANT":"Test Development Ltd"}},
    {"attributes":{"OBJECTID":16,"FILENO":"","LOCATION":"200 Main St","DESCRIPT":"Office"}},
  ]}
 rows=_barrie_gis(url,fetch=fetch)
 assert len(rows)==1
 assert rows[0]["application_id"]=="D12-2026-001"
 assert rows[0]["commercial_fit"]=="COMMERCIAL_TEXT_MATCH_REVIEW"
 assert rows[0]["source_date"]==""
