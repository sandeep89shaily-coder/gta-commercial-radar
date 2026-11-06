"""Regression for Toronto's official capital PDF and Peel source recovery."""
import csv
import datetime as dt
import json
from gta_toronto_capital_pipeline import run,_pdf_link,_normalise_table,ALL,CHANGES,STATUS
from gta_regional_early_intelligence import SOURCES,run as regional_run


class Page:
 def __init__(self,rows):
  self.rows=rows
 def extract_tables(self,**kw):
  assert kw["table_settings"]["vertical_strategy"]=="lines"
  return [self.rows]

class Document:
 def __init__(self,pages):
  self.pages=pages
 def __enter__(self):
  return self
 def __exit__(self,*args):
  return False

PDF_URL="https://www.toronto.ca/wp-content/uploads/2026/05/upcoming-capital.pdf"
INDEX_HTML='<main><a href="/wp-content/uploads/2026/05/upcoming-capital.pdf">a list of capital projects planned for procurement in 2026</a></main>'

def rows(scope="Construct new modular building and associated services",year="2026"):
 return [["No.","Name and Construction Contract Number","Type of Work","Scope of Work",
          "Delivery Division","Project Owner","Target Sourcing Year","Target Award Year",
          "Sourcing Type","Estimated Range","Estimated Contract Term (Months)"],
         ["1","Dufferin Transfer Station New Office Building - 26ECS-MI-03SW",
          "Construction",scope,"Engineering & Construction","Solid Waste Management Services",
          year,"2027","nRFP","Over $50M","41"],
         ["2","Humber Treatment Plant Tank Restoration - 26ECS-MI-02HU",
          "Construction","Replace collection systems, rehabilitate concrete, upgrade electrical and controls",
          "Engineering & Construction","Toronto Water","2026","2027","RFT",
          "$5M to $50M","36"]]

def _parse(rows_value):
 return lambda byte_stream:Document([Page(rows_value)])

def test_official_pdf_link_avoids_nav_links():
 html=INDEX_HTML+'<a href="https://evil.example/project.pdf">capital projects</a>'
 assert _pdf_link(html)==PDF_URL
 assert _pdf_link('<main><a href="/procurement">procurement policies</a></main>')==""

def test_table_requires_real_sourcing_fields():
 assert _normalise_table(rows()[1])["target_sourcing_year"]=="2026"
 assert _normalise_table(rows()[1])["estimated_range"]=="Over $50M"
 assert _normalise_table(["77"]*11) is None

def test_baseline_repeated_and_modified(tmp_path):
 source=lambda _:INDEX_HTML
 fetch=lambda _:b"%PDF-1.7\nsynthetic"
 first=run(tmp_path,today=dt.date(2026,11,5),html_fetcher=source,
           pdf_fetcher=fetch,pdf_parser=_parse(rows()),min_complete_rows=2)
 assert first["status"]=="BASELINE_COMPLETE"
 assert first["parsed_projects"]==2 and first["new_or_changed"]==0
 second=run(tmp_path,today=dt.date(2026,11,6),html_fetcher=source,
           pdf_fetcher=fetch,pdf_parser=_parse(rows()),min_complete_rows=2)
 assert second["new_or_changed"]==0
 change=run(tmp_path,today=dt.date(2026,11,7),html_fetcher=source,
           pdf_fetcher=fetch,pdf_parser=_parse(rows(scope="Build office and refurbish storage equipment")),
           min_complete_rows=2)
 assert change["new_or_changed"]==1
 with (tmp_path/CHANGES).open(encoding="utf-8-sig") as fp:
  changed=list(csv.DictReader(fp))
 assert changed[0]["first_seen_local"]=="2026-11-05"
 assert changed[0]["procurement_status"]=="PLANNED_PIPELINE_NOT_VERIFIED_OPEN_TENDER"
 assert changed[0]["source_publication_date"]==""

def test_partial_parse_does_not_move_ledger(tmp_path):
 report=run(tmp_path,html_fetcher=lambda _:INDEX_HTML,
    pdf_fetcher=lambda _:b"%PDF-1.7\nsynthetic",
    pdf_parser=_parse(rows()[:2]),min_complete_rows=10)
 assert report["status"]=="INCOMPLETE_OFFICIAL_PDF_PARSE"
 assert report["parsed_projects"]==1
 assert not (tmp_path/"GTA_RADAR_TORONTO_CAPITAL_PIPELINE_SEEN.json").exists()
 with (tmp_path/ALL).open(encoding="utf-8-sig") as fp:
  assert list(csv.DictReader(fp))==[]

def test_pdf_denied_leaves_no_fabricated_project(tmp_path):
 def blocked(_):
  raise ValueError("POLICY_DENIED:ROBOTS_ACCESS_DENIED")
 r=run(tmp_path,html_fetcher=lambda _:INDEX_HTML,pdf_fetcher=blocked)
 assert r["status"]=="FAILED"
 assert r["parsed_projects"]==0
 assert "POLICY_DENIED" in r["error"]


def test_peel_uses_real_named_projects_and_early_ea(tmp_path):
 index="https://peelregion.ca/construction/projects/current-construction-projects"
 early="https://peelregion.ca/construction/environmental-assessments/bolton-zone-7-water-elevated-storage-transmission-mains"
 assert SOURCES["Peel"]["url"]==index
 fetch=lambda url: (
    '<main><h1>Current construction projects</h1>'
    '<a href="/construction/project-25-2300-d">Denison Avenue and West Street watermain replacement</a>'
    '<a href="/construction/projects/work-zone-safety">Work zone safety</a></main>'
    if url==index else
    '<main><h1>Bolton Zone 7 Water Elevated Storage and Transmission Mains</h1>'
    '<p>Proposed elevated tanks and transmission mains at environmental assessment stage.</p></main>')
 r=regional_run(tmp_path,sources={"Peel":SOURCES["Peel"]},
                fetcher=fetch,today=dt.date(2026,11,5))
 assert r["records"]==2
 assert r["application_id_records"]==0
 assert r["new_or_changed"]==0
 assert r["source_status"][0]["supplemental_sources_configured"]==1

def test_toronto_navigation_not_capital_projects(tmp_path):
 url=SOURCES["Toronto"]["url"]
 html='<main><a href="/business/understanding-the-procurement-process/procurement-metrics">Procurement Metrics</a><a href="/business/social-procurement-program/">Social Procurement Program</a></main>'
 r=regional_run(tmp_path,sources={"Toronto":SOURCES["Toronto"]},fetcher=lambda _:html)
 assert r["records"]==0
 assert r["source_status"][0]["status"]=="INDEX_FETCHED_NO_IDENTIFIABLE_PROJECTS"
 assert "PDF" in r["source_status"][0]["reason"]
