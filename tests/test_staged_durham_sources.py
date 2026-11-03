"""Staged Durham snapshots cannot publish false new leads or partial pages."""
import datetime as dt
from gta_staged_durham_sources import _collect,run,SELECTED
def config():
    return [{"id":name,"name":name,"enabled":False,"url":"https://maps.durham.ca/test/"+name,
             "query_url":"https://maps.durham.ca/test/"+name+"/query",
             "key_fields":["OBJECTID"],"description_fields":["DESCRIPTION"],
             "date_fields":["UPDATED"],"jurisdiction":"Durham"} for name in SELECTED]
def reader(url,params):
    if url.endswith("/query"):
        if params.get("returnCountOnly")=="true":return {"count":1}
        return {"features":[{"attributes":{"OBJECTID":1,"DESCRIPTION":"Industrial development",
                  "UPDATED":"2026-10-23"}}]}
    return {"fields":[{"name":n} for n in ("OBJECTID","DESCRIPTION","UPDATED")],
            "objectIdField":"OBJECTID"}
def test_initial_baseline_no_qualified_leads(tmp_path):
    first=run(tmp_path,today=dt.date(2026,11,3),sources=config(),fetcher=reader)
    assert first["total_rows"]==4 and first["new_or_changed_reference_records"]==0
    again=run(tmp_path,today=dt.date(2026,11,4),sources=config(),fetcher=reader)
    assert all(x["status"]=="SKIPPED_MONTHLY_CADENCE" for x in again["sources"])
def test_partial_snapshots_refused():
    c=config()[0]
    def broken(url,params):
        if url.endswith("/query"):
            if params.get("returnCountOnly")=="true":return {"count":3}
            return {"features":[]}
        return {"fields":[{"name":n} for n in ("OBJECTID","DESCRIPTION","UPDATED")],"objectIdField":"OBJECTID"}
    try:_collect(c,broken)
    except ValueError as exc:assert "EMPTY_OR_INVALID_PAGE" in str(exc)
    else:raise AssertionError("Partial source silently accepted")


def test_source_repeated_geometries_deduplicate_one_file():
    one=config()[0]
    def duplicates(url,params):
        if not url.endswith("/query"):
            return {"fields":[{"name":n} for n in ("OBJECTID","DESCRIPTION","UPDATED")],
                    "objectIdField":"OBJECTID"}
        if params.get("returnCountOnly")=="true":return {"count":2}
        return {"features":[
          {"attributes":{"OBJECTID":9,"DESCRIPTION":"Commercial facility","UPDATED":"2026-11-01"}},
          {"attributes":{"OBJECTID":9,"DESCRIPTION":"Commercial facility expansion","UPDATED":"2026-11-01"}}]}
    rows,_=_collect(one,duplicates)
    assert len(rows)==1
    assert rows[0]["project_description"]=="Commercial facility expansion"
