"""Probe official catalog and exports for three blocked GIS sources, respecting robots."""
import json,requests
from urllib.parse import urlparse,urljoin
from robots_policy import evaluate
AGENT="GTARadarOfficialExportProbe/1.0"
TARGETS={
 "MISS_SITE_HUB":"https://opendata-mississauga.hub.arcgis.com/datasets/mississauga::site-plan-applications",
 "MISS_REZONE_HUB":"https://opendata-mississauga.hub.arcgis.com/datasets/mississauga::rezoning-applications",
 "MISS_SITE_META":"https://www.arcgis.com/sharing/rest/content/items/9b25caf083d54593a7db21ea056cfb3d",
 "NIAGARA_PACKAGE":"https://www.niagaraopendata.ca/api/3/action/package_show?id=building-permits-public",
 "NIAGARA_PACKAGE_ALT":"https://niagaraopendata.ca/api/3/action/package_show?id=building-permits-public",
 "NIAGARA_DATASET":"https://www.niagaraopendata.ca/dataset/building-permits-public",
 "NIAGARA_RESOURCE_CSV":"https://www.niagaraopendata.ca/dataset/building-permits-public/resource",
}
def probe(name,url):
    sess=requests.Session();sess.trust_env=False;sess.headers["User-Agent"]=AGENT
    report={"name":name,"url":url}
    try:
        allow,reason=evaluate(sess,url,AGENT,timeout=5)
        report.update(allowed=allow,policy=reason)
        if not allow:return report
        res=sess.get(url,timeout=(5,12),stream=True,allow_redirects=False)
        report.update(status=res.status_code,type=res.headers.get("Content-Type",""),
                      redirect=res.headers.get("Location","")[:240])
        if res.status_code==200:
            body=res.raw.read(170000,decode_content=True)
            content=body.decode("utf-8","replace")
            if "json" in report["type"]:
                parsed=json.loads(content)
                value=parsed.get("result",parsed)
                if "resources" in value:
                    report["resources"]=[{"name":x.get("name"),"format":x.get("format"),"url":x.get("url")}
                                         for x in value["resources"]][:25]
                else:
                    report["metadata"]={k:value.get(k) for k in ("id","title","name","url","type","owner","access")}
            else:
                import re
                report["download_hints"]=list(dict.fromkeys(re.findall(r'https?[^" ]{5,160}(?:csv|download)[^" ]*',content,re.I)))[:8]
                report["bytes_read"]=len(body)
        res.close()
    except Exception as e:report["error"]=type(e).__name__+":"+str(e)[:180]
    finally:sess.close()
    return report
if __name__=="__main__":
 for name,url in TARGETS.items():
    print("EXPORT_PROBE",json.dumps(probe(name,url)),flush=True)
