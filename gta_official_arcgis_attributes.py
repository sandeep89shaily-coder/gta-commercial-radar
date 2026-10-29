"""Read specific official ArcGIS FeatureServer records without paid AI tokens."""
from __future__ import annotations
import json
from urllib.parse import urlparse,parse_qs
from urllib.request import Request,urlopen
ALLOWED_HOSTS=("gis.toronto.ca","maps1.brampton.ca","services6.arcgis.com")
def is_official_query(url):
    try:
        p=urlparse(url)
        q=parse_qs(p.query)
        return p.scheme=="https" and p.hostname in ALLOWED_HOSTS and "/FeatureServer/" in p.path and p.path.endswith("/query") and q.get("f",[""])[0]=="json" and bool(q.get("where"))
    except (TypeError,ValueError,IndexError):
        return False
def parse_features(raw,expected_key=None):
    data=json.loads(raw) if isinstance(raw,(str,bytes,bytearray)) else raw
    if not isinstance(data,dict):return None
    features=data.get("features")
    if not isinstance(features,list) or not features:return None
    matches=[]
    for item in features:
        attrs=item.get("attributes",{}) if isinstance(item,dict) else {}
        if not isinstance(attrs,dict):continue
        if expected_key and not any(str(v).strip().casefold()==str(expected_key).strip().casefold() for v in attrs.values()):
            continue
        # Only application attributes; omit geometry and giant schema/field metadata.
        priority=("APPLICATION_NUMBER","PERMITNUMBER","BP_NO","STATUS","DESCRIPTION","SCOPE","ADDRESS","UNIT_NO","FILE_TYPE","BLDG_TYPE","APP_DETAIL","APPLICANT","OWNER","CONTRACTOR","ISSUED_DATE")
        pairs=[(str(k),str(v)[:750]) for k,v in attrs.items() if v is not None and str(v).strip()]
        pairs.sort(key=lambda item:(priority.index(item[0].upper()) if item[0].upper() in priority else len(priority),item[0]))
        compact=dict(pairs)
        if compact:matches.append(compact)
    return {"attributes":matches[:3],"matched":len(matches)} if matches else None
def retrieve(url,expected_key,*,transport=None):
    if not is_official_query(url):return None
    if transport is not None:
        raw=transport(url)
    else:
        request=Request(url,headers={"Accept":"application/json","User-Agent":"GTARadar/1.0"})
        with urlopen(request,timeout=18) as res:
            if res.status!=200:raise ValueError("ArcGIS HTTP status invalid")
            raw=res.read(600_001)
        if len(raw)>600_000:raise ValueError("ArcGIS response too large")
    result=parse_features(raw,expected_key)
    if not result:return None
    return json.dumps(result,ensure_ascii=False)
