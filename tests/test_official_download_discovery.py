from gta_official_download_discovery import probe,run
def test_blocked_export_is_never_downloaded():
    calls=[]
    item="85536f145719436ebde8d31f36d11d83"
    cfg={"city":"Mississauga","item":item,"owner":"MississaugaData",
          "title":"Site Plan Applications"}
    def getter(session,url):
        calls.append(url)
        if "sharing/rest" in url:
            return {"id":item,"owner":"MississaugaData","title":"Site Plan Applications",
                    "url":"https://services6.arcgis.com/abc/FeatureServer"}
        return {"status":"Completed","resultUrl":"https://services6.arcgis.com/abc/FeatureServer/replicafilescache/export.csv"}
    def policy(session,url):
        calls.append("POLICY:"+url)
        return False,"ROBOTS_ACCESS_DENIED"
    result=probe("miss",cfg,None,getter=getter,policy=policy)
    assert result["status"]=="EXPORT_TARGET_ACCESS_RESTRICTED"
    assert len(calls)==3 and calls[-1].startswith("POLICY:")
    assert result["application_records"]==0

def test_cadence_cache_never_claims_live_records(tmp_path):
    def scanner(id,config,session):
        return {"source_id":id,"status":"EXPORT_TARGET_ACCESS_RESTRICTED"}
    first=run(tmp_path,scanner=scanner)
    assert len(first["sources"])==3
    cached=run(tmp_path,scanner=lambda *a: (_ for _ in ()).throw(AssertionError("not cached")))
    assert cached["status"]=="CACHED_MONTHLY" and cached["application_records"]==0
