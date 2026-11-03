from gta_disabled_feed_acceptance import field_matches,run
def test_reject_unproven_feed(tmp_path):
    feed=[{"id":"x","name":"X","enabled":False,"collector":"arcgis",
           "key_fields":["FILE"],"description_fields":["USE"]}]
    result=run(tmp_path,config=feed,worker=lambda x:{"id":x["id"],"safe_to_stage":False,"status":"FETCH_OR_SCHEMA_FAILED"})
    assert result["safe_to_stage_count"]==0

def test_schema_requires_columns():
    actual=field_matches({"key_fields":["ID"],"description_fields":["SCOPE"],"date_fields":["UPDATED"]},["ID","SCOPE"])
    assert actual["identity"]==["ID"] and actual["scope"]==["SCOPE"] and not actual["dates"]
