from gta_three_city_recovery_gate import build
def test_three_gap_cities_not_promoted_by_project_signals(tmp_path):
 data=[
 {"city":"Burlington","total_source_candidate_rows_not_deduplicated":0,"project_only_signals":95},
 {"city":"Vaughan","total_source_candidate_rows_not_deduplicated":0,"project_only_signals":0},
 {"city":"Kitchener","total_source_candidate_rows_not_deduplicated":0,"project_only_signals":14}
 ]
 report=build(tmp_path,coverage=data)
 assert report["cities_without_application_candidates"]==3
 assert report["cities_with_application_candidates"]==0
 assert sum(x["project_only_signals"] for x in report["records"])==109
 assert all("BLOCKED" in r["acceptance"] for r in report["records"])

def test_one_actual_application_does_not_inflate_citywide_verification(tmp_path):
 data=[{"city":"Burlington","total_source_candidate_rows_not_deduplicated":1}]
 report=build(tmp_path,coverage=data)
 assert report["cities_with_application_candidates"]==1
 assert report["cities_verified_citywide_complete"]==0
