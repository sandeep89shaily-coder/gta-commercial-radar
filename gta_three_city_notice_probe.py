"""Live diagnostics for alternative official application notices in 3 missing cities.

No crawling, no GIS workaround: one explicitly listed official HTML URL each.
"""
import json,requests,bs4,socket
from urllib.parse import urlparse
from robots_policy import evaluate
from toronto_pdf_download import public_dns
SOURCES={
 "Vaughan":"https://www.vaughan.ca/about-city-vaughan/departments/office-city-clerk/public-notices",
 "Burlington":"https://www.burlington.ca/Modules/News/en/Development",
 "Kitchener":"https://app2.kitchener.ca/appdocs/GISImages/GIS_Web_External/GIS_Metadata_Open_Data/Planning_Applications_Active.html",
 "Burlington GIS catalog":"https://mapping.burlington.ca/arcgisweb/rest/services/COB/Development_Apps/MapServer?f=pjson",
 "Burlington GIS layer":"https://mapping.burlington.ca/arcgisweb/rest/services/COB/Development_Apps/MapServer/0?f=pjson",
 "Kitchener GeoHub":"https://open-kitchenergis.opendata.arcgis.com/datasets/KitchenerGIS::planning-applications-active"
}
AGENT="GTARadarEarlyPlanningPublicNotice/1.0"
def one(city,url):
 r={"city":city,"url":url}
 s=requests.Session();s.trust_env=False;s.headers["User-Agent"]=AGENT
 try:
  p=urlparse(url)
  if not public_dns(p.hostname,socket.getaddrinfo):raise ValueError("UNSAFE_DNS")
  allowed,reason=evaluate(s,url,AGENT,timeout=8)
  r.update(policy=reason,allowed=allowed)
  if not allowed:return r
  with s.get(url,timeout=(8,20),allow_redirects=False,stream=True) as response:
   r["http_status"]=response.status_code
   r["content_type"]=response.headers.get("Content-Type")
   if response.status_code!=200:return r
   body=response.raw.read(1_500_001,decode_content=True)
   if len(body)>1_500_000:raise ValueError("TOO_LARGE")
  if "json" in response.headers.get("Content-Type","") or "f=pjson" in url:
   data=json.loads(body)
   r["layer_list"]=[{"id":x.get("id"),"name":x.get("name")} for x in data.get("layers",[])[:50]]
   r["field_names"]=[x.get("name") for x in data.get("fields",[])[:80]]
   r["capabilities"]=data.get("capabilities")
   return r
  soup=bs4.BeautifulSoup(body,"html.parser")
  t=soup.get_text(" ",strip=True)
  r["html_length"]=len(body)
  r["city_file_occurrences"]=t.lower().count("city file no")
  r["application_no_occurrences"]=t.lower().count("application_no")
  r["notice_occurrences"]=t.lower().count("notice of public meeting")
  r["sample_context"]=[]
  for key in ("City File No.","Notice of Public Meeting","APPLICATION_NO","Application No"):
   idx=t.lower().find(key.lower())
   if idx>=0:r["sample_context"].append(t[max(0,idx-120):idx+480])
  r["sample_parents"]=[]
  for tag in soup.find_all(string=lambda x:x and "City File No." in x,limit=3):
   node=tag.parent
   for _ in range(3):
    if node.parent:node=node.parent
   r["sample_parents"].append({"tag":node.name,"class":node.get("class"),"text":node.get_text(" ",strip=True)[:700]})
  r["pdf_links"]=[a.get("href") for a in soup.select('a[href$=".pdf"]')[:6]]
 except Exception as exc:r["error"]=type(exc).__name__+":"+str(exc)[:150]
 finally:s.close()
 return r
if __name__=="__main__":
 for city,url in SOURCES.items():print("THREE_CITY_NOTICE_PROBE",json.dumps(one(city,url)),flush=True)
