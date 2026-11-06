from gta_city_coverage_report import build

def test_live_official_file_ids_count_only_when_successful(tmp_path):
    data={"source_status":[
      {"city":"Burlington","automated_source_recovered_this_stage":True,
       "application_id_rows_this_stage":2},
      {"city":"Vaughan","automated_source_recovered_this_stage":False,
       "application_id_rows_this_stage":50},
      {"city":"Kitchener","automated_source_recovered_this_stage":False,
       "application_id_rows_this_stage":99},
    ]}
    output=build(tmp_path,{}, {}, {},{},five_city=data)
    by_city={r["city"]:r for r in output["city_status"]}
    assert by_city["Burlington"]["live_official_notice_application_rows"]==2
    assert by_city["Burlington"]["total_source_candidate_rows_not_deduplicated"]==2
    assert by_city["Vaughan"]["total_source_candidate_rows_not_deduplicated"]==0
    assert by_city["Kitchener"]["total_source_candidate_rows_not_deduplicated"]==0
    assert output["cities_with_extracted_application_candidates"]==1
    assert output["verified_citywide_complete_coverage"]==0
