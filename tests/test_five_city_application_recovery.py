"""Regression for recovery: no file number, no automatic application coverage."""
import csv,datetime as dt,json
from pathlib import Path
from gta_five_city_application_recovery import (
 run,OUTPUT,CHANGES,STATUS,VAUGHAN,BURLINGTON_INDEX,_burlington_records
)

BURLINGTON="https://www.burlington.ca/en/news/current-development-projects/1376-1382-plains-rd-e.aspx"
PAGE="""<main><h1>1376-1382 Plains Road East</h1>
 <div>Status - Under Review</div>
 <section><h2>Proposed Development</h2>
 <p>Development of a 25-storey mixed-use building with ground-floor retail space.</p></section>
 <section><h2>File Numbers</h2><p>Official Plan 505-10-26 and Zoning 520-11/26</p></section>
 </main>"""
VAUGHAN_HTML="""<main><h1>Public Notices</h1>
<p>City File No.: OP.26.005 & Z.26.018 Subject Land: 8000 Bathurst Street
Meeting Date: 11/24/2026 Meeting Type: Committee of the Whole (Public Meeting)
Notice Description: Proposed 35-storey mixed-use development with commercial units.</p>
</main>"""

def seed(root):
 with (root/"GTA_RADAR_BURLINGTON_GIS_PROJECTS.csv").open("w",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=["project_id","city","source_url"])
  w.writeheader()
  w.writerow({"project_id":"B1","city":"Burlington","source_url":BURLINGTON})
  w.writerow({"project_id":"B2","city":"Burlington","source_url":"https://evil.example/fake.aspx"})

def fetch(url):
 if url==BURLINGTON:return PAGE
 if url==VAUGHAN:return VAUGHAN_HTML
 raise ValueError("EXPLICITLY_BLOCKED_INDEX")

def test_real_official_ids_and_provenance_first_baseline(tmp_path):
 seed(tmp_path)
 result=run(tmp_path,today=dt.date(2026,11,6),fetcher=fetch)
 assert result["cities_targeted"]==5
 assert result["automatic_file_id_rows_this_stage"]==4
 assert result["automatically_recovered_cities"]==["Burlington","Vaughan"]
 assert result["new_or_changed"]==0
 with (tmp_path/OUTPUT).open(encoding="utf-8-sig") as f:
  rows=list(csv.DictReader(f))
 assert len(rows)==4
 assert {r["application_id"] for r in rows}=={"505-10-26","520-11/26","OP.26.005","Z.26.018"}
 assert all(r["source_record_date"]=="" for r in rows)
 assert all(r["observation"]=="INITIAL_BASELINE" for r in rows)
 assert result["verified_citywide_complete"]==0
 assert result["verified_new_commercial_leads"]==0

def test_repeat_is_unchanged_and_change_is_review_not_new_publication(tmp_path):
 seed(tmp_path)
 run(tmp_path,today=dt.date(2026,11,6),fetcher=fetch)
 repeat=run(tmp_path,today=dt.date(2026,11,7),fetcher=fetch)
 assert repeat["new_or_changed"]==0
 updated=run(tmp_path,today=dt.date(2026,11,8),
    fetcher=lambda u:fetch(u).replace("25-storey","26-storey") if u==BURLINGTON else fetch(u))
 assert updated["new_or_changed"]==2
 with (tmp_path/CHANGES).open(encoding="utf-8-sig") as f:
  changes=list(csv.DictReader(f))
 assert len(changes)==2
 assert all(r["first_seen_local"]=="2026-11-06" for r in changes)

def test_robots_block_preserves_first_seen_and_reports_failure(tmp_path):
 seed(tmp_path)
 run(tmp_path,today=dt.date(2026,11,6),fetcher=fetch)
 result=run(tmp_path,today=dt.date(2026,11,7),
    fetcher=lambda url: (_ for _ in ()).throw(ValueError("POLICY_DENIED:robots")))
 assert result["automatic_file_id_rows_this_stage"]==0
 assert not result["automatically_recovered_cities"]
 assert result["new_or_changed"]==0
 assert json.loads((tmp_path/"GTA_RADAR_FIVE_CITY_OFFICIAL_SEEN.json").read_text())["seen"]
 again=run(tmp_path,today=dt.date(2026,11,8),fetcher=fetch)
 assert again["new_or_changed"]==0

def test_false_positive_phone_without_city_id(tmp_path):
 seed(tmp_path)
 fake='<main><h1>Industrial Warehouse</h1><section><h2>File Numbers</h2><p>Telephone 905-555-1234</p></section></main>'
 result=run(tmp_path,fetcher=lambda u:fake)
 assert result["automatic_file_id_rows_this_stage"]==0
 assert result["verified_citywide_complete"]==0

def test_other_three_cities_only_audited_no_fake_gis_recovery(tmp_path):
 (tmp_path/"GTA_RADAR_GGH_OFFICIAL_GIS_STATUS.json").write_text(json.dumps({
  "source_status":[{"city":"Richmond Hill","state":"FAILED","application_id_rows":0,
          "error":"ROBOTS_ACCESS_DENIED"},{"city":"Newmarket","state":"FAILED",
          "application_id_rows":0,"error":"ROBOTS_ACCESS_DENIED"}]}))
 (tmp_path/"GTA_RADAR_ADDITIONAL_CITY_GIS_STATUS.json").write_text(json.dumps({
  "source_status":[{"city":"Kitchener","status":"FAILED","commercial_candidates":0,
          "error":"POLICY_DENIED:robots"}]}))
 r=run(tmp_path,fetcher=lambda u:(_ for _ in ()).throw(ValueError("403")))
 remaining={x["city"]:x for x in r["source_status"]}
 for city in ("Kitchener","Richmond Hill","Newmarket"):
  assert remaining[city]["application_id_rows_this_stage"]==0
  assert remaining[city]["automated_source_recovered_this_stage"] is False
 assert remaining["Newmarket"]["source_failure"]=="ROBOTS_ACCESS_DENIED"


def test_conflicting_burlington_file_number_on_distinct_city_pages_is_held(tmp_path):
 # Two individually parseable City pages use identical official file numbers.
 # Do not let whichever page appears first fabricate a project identity.
 page_a="https://www.burlington.ca/news-and-notices/posts/current-development-projects/first-project/"
 page_b="https://www.burlington.ca/news-and-notices/posts/current-development-projects/second-project/"
 index="<main><a href='"+page_a+"'>Project A</a><a href='"+page_b+"'>Project B</a></main>"
 def official(url):
  if url==BURLINGTON_INDEX:return index
  if url==page_a:return PAGE
  if url==page_b:return PAGE.replace("1376-1382 Plains Road East","Different Industrial Site")
  raise ValueError("POLICY_BLOCKED_OR_UNAVAILABLE")
 report=run(tmp_path,today=dt.date(2026,11,10),fetcher=official)
 assert report["identity_conflicts_held_count"]==2
 assert report["automatic_file_id_rows_this_stage"]==0
 assert report["new_or_changed"]==0
 burl=next(x for x in report["source_status"] if x["city"]=="Burlington")
 assert burl["links_parsed"]==2
 assert burl["identity_conflicts_held"]==2
 assert burl["application_id_rows_this_stage"]==0
 assert burl["status"]=="PARTIAL_OFFICIAL_PAGE_COLLECTION_IDENTITY_HOLD"
 with (tmp_path/OUTPUT).open(encoding="utf-8-sig",newline="") as handle:
  assert list(csv.DictReader(handle))==[]
 # A held first visit must not become an accepted baseline.
 state=json.loads((tmp_path/"GTA_RADAR_FIVE_CITY_OFFICIAL_SEEN.json").read_text()) if (
  tmp_path/"GTA_RADAR_FIVE_CITY_OFFICIAL_SEEN.json").exists() else {"seen":{}}
 assert not state["seen"]


def test_conflicting_followup_does_not_replace_successful_identity_ledger(tmp_path):
 page_a="https://www.burlington.ca/news-and-notices/posts/current-development-projects/first-project/"
 page_b="https://www.burlington.ca/news-and-notices/posts/current-development-projects/second-project/"
 def official(url,conflict=False):
  if url==BURLINGTON_INDEX:
   anchors="<a href='"+page_a+"'>Project A</a>"
   if conflict: anchors+="<a href='"+page_b+"'>Project B</a>"
   return "<main>"+anchors+"</main>"
  if url in (page_a,page_b):return PAGE
  raise ValueError("POLICY_BLOCKED_OR_UNAVAILABLE")
 first=run(tmp_path,today=dt.date(2026,11,8),fetcher=lambda u:official(u))
 assert first["automatic_file_id_rows_this_stage"]==2
 ledger_path=tmp_path/"GTA_RADAR_FIVE_CITY_OFFICIAL_SEEN.json"
 original=ledger_path.read_bytes()
 second=run(tmp_path,today=dt.date(2026,11,9),
            fetcher=lambda u:official(u,conflict=True))
 assert second["identity_conflicts_held_count"]==2
 assert second["new_or_changed"]==0
 assert original==ledger_path.read_bytes()
 third=run(tmp_path,today=dt.date(2026,11,10),fetcher=lambda u:official(u))
 assert third["automatic_file_id_rows_this_stage"]==2
 assert third["new_or_changed"]==0



def test_repaired_city_parser_backfills_old_undated_file_numbers_without_fresh_alert(tmp_path):
 # Prior ZIP (Nov 10) had 11 Burlington ledger IDs, but live source (Nov 11)
 # parsed 16, including a quarry page last publicly dated months earlier.
 # Missing from an old parser is NOT newly published on the municipal site.
 page_a="https://www.burlington.ca/news-and-notices/posts/current-development-projects/first/"
 page_b="https://www.burlington.ca/news-and-notices/posts/current-development-projects/second/"
 first_page=PAGE
 extra_page=PAGE.replace("505-10-26 and Zoning 520-11/26",
                         "505-04/20 and Zoning 520-12/20").replace(
                         "1376-1382 Plains Road East","Old Quarry Extension")
 def official(url,include_old):
  if url==BURLINGTON_INDEX:
   return "<main><a href='"+page_a+"'>First</a>"+(
       "<a href='"+page_b+"'>Old but underparsed</a>" if include_old else "")+"</main>"
  if url==page_a:return first_page
  if url==page_b:return extra_page
  raise ValueError("POLICY_DENIED")
 prior=run(tmp_path,today=dt.date(2026,11,6),
           fetcher=lambda url:official(url,False))
 assert prior["automatic_file_id_rows_this_stage"]==2
 assert prior["new_or_changed"]==0
 now=run(tmp_path,today=dt.date(2026,11,11),
         fetcher=lambda url:official(url,True))
 assert now["automatic_file_id_rows_this_stage"]==4
 assert now["newly_observed_undated_file_ids_held_for_publication_review"]==2
 assert now["new_or_changed"]==0
 with (tmp_path/OUTPUT).open(encoding="utf-8-sig",newline="") as f:
  rows=list(csv.DictReader(f))
 assert len([x for x in rows if x["observation"]=="FIRST_OBSERVED_UNDATED_HELD"])==2
 assert len([x for x in rows if x["observation"]=="UNCHANGED"])==2
 assert {x["first_seen_local"] for x in rows if
         x["observation"]=="FIRST_OBSERVED_UNDATED_HELD"}=={"2026-11-11"}
 with (tmp_path/CHANGES).open(encoding="utf-8-sig",newline="") as f:
  assert list(csv.DictReader(f))==[]
 repeat=run(tmp_path,today=dt.date(2026,11,12),
            fetcher=lambda url:official(url,True))
 assert repeat["newly_observed_undated_file_ids_held_for_publication_review"]==0
 assert repeat["new_or_changed"]==0


def test_real_observed_changes_remain_reviewable_after_undated_id_hold(tmp_path):
 page_a="https://www.burlington.ca/news-and-notices/posts/current-development-projects/first/"
 page_b="https://www.burlington.ca/news-and-notices/posts/current-development-projects/old/"
 def make(url,changed=False,new=False):
  if url==BURLINGTON_INDEX:
   return "<main><a href='"+page_a+"'>A</a>"+(
    "<a href='"+page_b+"'>Old</a>" if new else "")+"</main>"
  if url==page_a:return PAGE.replace("25-storey","26-storey") if changed else PAGE
  if url==page_b:return PAGE.replace("505-10-26 and Zoning 520-11/26",
     "505-04/20 and Zoning 520-12/20")
  raise ValueError("BLOCKED")
 run(tmp_path,today=dt.date(2026,11,6),fetcher=lambda url:make(url))
 result=run(tmp_path,today=dt.date(2026,11,11),
            fetcher=lambda url:make(url,changed=True,new=True))
 assert result["new_or_changed"]==2
 assert result["newly_observed_undated_file_ids_held_for_publication_review"]==2
 with (tmp_path/CHANGES).open(encoding="utf-8-sig",newline="") as f:
  rows=list(csv.DictReader(f))
 assert len(rows)==2
 assert all(x["observation"]=="RECORD_CHANGED" for x in rows)
