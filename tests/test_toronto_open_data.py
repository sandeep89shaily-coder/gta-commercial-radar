"""Toronto open-data collector offline schema, policy and baseline tests."""
from gta_toronto_open_data import _resource,_parse_csv,run
import datetime as dt

def test_resource_rejects_non_official_download():
    meta={"success":True,"result":{"resources":[
      {"format":"CSV","url":"https://attacker.example/file.csv"}]}}
    try:_resource(meta)
    except ValueError as e:assert "NO_PERMITTED" in str(e)
    else:raise AssertionError("unsafe CSV resource accepted")

def test_realistic_toronto_csv_columns():
    data=b"APPLICATION_NUMBER,FULL_ADDRESS,FOLDERDESCRIPTION,STATUS_DESC,SUBMIT_DATE,APPLICATION_TYPE\n25 123 ABC,20 Main St,Industrial warehouse,Under Review,2025-03-12,OZ\n"
    rows,n=_parse_csv(data,dt.date(2026,11,2))
    assert n==1 and len(rows)==1
    item=next(iter(rows.values()))
    assert item["source_record_date"]=="2025-03-12"

def test_baseline_first_fetch_no_new_records(tmp_path):
    meta={"success":True,"result":{"resources":[{
        "format":"CSV","name":"Development Applications.csv",
        "url":"https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/file.csv"}]}}
    data=b"APPLICATION_NUMBER,FULL_ADDRESS,DESCRIPTION,STATUS,SUBMIT_DATE\n25 123 ABC,20 Main St,Industrial warehouse,Under Review,2025-03-12\n"
    one=run(tmp_path,today=dt.date(2026,11,2),metadata=meta,csv_data=data)
    two=run(tmp_path,today=dt.date(2026,11,2),metadata=meta,csv_data=data)
    assert one["status"]=="BASELINED" and one["new_or_changed"]==0
    assert two["status"]=="COLLECTED" and two["new_or_changed"]==0
