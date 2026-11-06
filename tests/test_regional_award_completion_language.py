import csv
import datetime as dt
from gta_regional_commercial_review import run, _affirmative_closed, EXCLUDED, OUTPUT


def write(root,name,records):
    with (root/name).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)

def test_negated_award_is_not_closed():
    assert not _affirmative_closed("The contract has not been awarded")
    assert not _affirmative_closed("The contract is not yet awarded")
    assert _affirmative_closed("The contract has not been awarded but an earlier phase was awarded to XYZ")
    assert _affirmative_closed("The project was completed in 2024")
    assert _affirmative_closed("Construction has been completed")
    assert _affirmative_closed("Contract awarded to a contractor in 2025")

def test_source_exclusion_and_nonaward_review(tmp_path):
    base={"authority":"Waterloo","project_url":"https://www.regionofwaterloo.ca/projects/road",
          "project_title":"Waterloo bridge expansion","evidence_excerpt":"",
          "stage_evidence":"ASSESSMENT","observation":"RECORD_CHANGED",
          "source_verification":"OFFICIAL_HOST_DETAIL_HTML_EXTRACTED"}
    rows=[
        {**base,"project_id":"old","project_title":"Old bridge expansion",
         "project_url":"https://www.regionofwaterloo.ca/projects/old",
         "evidence_excerpt":"The existing bridge replacement project was completed in 2024."},
        {**base,"project_id":"active","project_title":"New bridge expansion",
         "project_url":"https://www.regionofwaterloo.ca/projects/new",
         "evidence_excerpt":"New bridge construction is in design; the contract has not yet been awarded."},
    ]
    write(tmp_path,"GTA_RADAR_REGIONAL_PROJECT_DETAILS.csv",rows)
    result=run(tmp_path,today=dt.date(2026,11,6))
    assert result["review_records"]==1
    with (tmp_path/OUTPUT).open(encoding="utf-8-sig") as f:
        active=list(csv.DictReader(f))
    with (tmp_path/EXCLUDED).open(encoding="utf-8-sig") as f:
        excluded=list(csv.DictReader(f))
    assert active[0]["project_name"]=="New bridge expansion"
    assert excluded[0]["project_name"]=="Old bridge expansion"
