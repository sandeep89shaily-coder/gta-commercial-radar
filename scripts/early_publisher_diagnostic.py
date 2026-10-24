"""One-shot diagnostic for public publishers; no records stored or authentication."""
import requests, re, json
from bs4 import BeautifulSoup
S=requests.Session();S.headers.update({"User-Agent":"GTA-Radar-Source-Public-Health/0.2"})
urls={
 "ieso":"https://www.ieso.ca/Sector-Participants/Connection-Process/Application-Status",
 "brampton_calendar":"https://pub-brampton.escribemeetings.com/MeetingsCalendarView.aspx",
 "brampton_city":"https://www.brampton.ca/EN/City-Hall/Council-Committees/meetings-agendas",
 "burlington_4103":"https://www.burlington.ca/en/news/current-development-projects/better-life-living-4103-palladium-way.aspx",
 "ajax0":"https://ajaxmaps.ajax.ca/gisernie/rest/services/Planning/Apps_Dev/MapServer/0?f=pjson",
 "ajax1":"https://ajaxmaps.ajax.ca/gisernie/rest/services/Planning/Apps_Dev/MapServer/1?f=pjson",
 "ajax3":"https://ajaxmaps.ajax.ca/gisernie/rest/services/Planning/Apps_Dev/MapServer/3?f=pjson",
}
for key,url in urls.items():
 print("\n==",key,url,flush=True)
 try:
  r=S.get(url,timeout=(7,19)); print("HTTP",r.status_code,"bytes",len(r.content),"type",r.headers.get("Content-Type",""),"redirect",r.url[:160],flush=True)
  if key.startswith("ajax"):
   obj=r.json()
   print("LAYER",json.dumps({k:obj.get(k) for k in ("id","name","type","objectIdField","maxRecordCount","capabilities","error")})[:1500])
   print("FIELDS",json.dumps([(f.get("name"),f.get("type")) for f in obj.get("fields",[])])[:2400],flush=True)
   continue
  soup=BeautifulSoup(r.text,"html.parser")
  print("TITLE",soup.title.get_text(" ",strip=True)[:170] if soup.title else "NONE")
  print("BODY_HEAD",soup.get_text(" ",strip=True)[:350])
  print("TABLES",[(len(t.find_all("tr")),t.get_text(" ",strip=True)[:280]) for t in soup.select("table")[:4]])
  print("SCRIPT_SRCS",[a.get("src","")[:150] for a in soup.select("script[src]") if re.search("applic|conn|api|table|stat|jquery|angular",a.get("src",""),re.I)][:18])
  if key=="ieso":
   for term in ["CAA ID","connectionApplications","ApplicationStatus","Last Updated"]:
    print("FIND",term,r.text.lower().find(term.lower()))
   print("IFRAMES",[a.get("src") for a in soup.select("iframe[src]")][:8])
  if key.startswith("brampton"):
   print("AGENDA_URLS",[(a.get_text(" ",strip=True)[:70],a.get("href","")[:180]) for a in soup.select("a[href]") if "planning" in a.get_text(" ",strip=True).lower() or "meeting" in a.get("href","").lower()][:14])
 except Exception as e: print("ERROR",type(e).__name__,str(e)[:240],flush=True)


print("\n== TARGETED INSPECTION ==",flush=True)
try:
 html=S.get(urls["ieso"],timeout=(7,20)).text
 for needle in ("ApplicationStatus","CAA ID","Last Updated"):
  pos=html.find(needle)
  print("IESO_CONTEXT",needle,pos,re.sub(r"\s+"," ",html[max(0,pos-450):pos+850])[:1250])
 links=re.findall(r'''(?:/[-A-Za-z0-9_/]+(?:\.json|\.ashx|\.asmx|\.svc|/Get[-A-Za-z]+))''',html,re.I)
 print("IESO_SERVICE_LINK_HINTS",list(dict.fromkeys(links))[:15])
except Exception as e:print("IESO_DETAIL_ERROR",e)
try:
 html=S.get(urls["brampton_calendar"],timeout=(7,20)).text
 soup=BeautifulSoup(html,"html.parser")
 marker=soup.find(string=re.compile(r"Planning and Development Committee",re.I))
 for i,item in enumerate(soup.find_all(string=re.compile(r"Planning and Development Committee",re.I))[:2]):
  e=item.parent
  print("BRAMPTON_CONTAINER",i,re.sub(r"\s+"," ",str(e.parent.parent))[:2400])
 href=next((a.get("href","") for a in soup.find_all("a",href=True) if "/Meeting.aspx?Id=" in a.get("href","")),None)
 if href:
  from urllib.parse import urljoin
  u=urljoin(urls["brampton_calendar"],href)
  x=S.get(u,timeout=(7,20))
  print("BRAMPTON_MEETING",x.status_code,len(x.content),x.url[:180])
  bs=BeautifulSoup(x.text,"html.parser")
  print("BRAMPTON_MEETING_BODY",bs.get_text(" ",strip=True)[:1400])
  print("BRAMPTON_MEETING_LINKS",[(a.get_text(" ",strip=True)[:50],a.get("href","")[:160]) for a in bs.select("a[href]") if re.search("Agenda|PDF|Attachments",a.get_text(" ",strip=True)+" "+a.get("href",""),re.I)][:12])
except Exception as e:print("BRAMPTON_DETAIL_ERROR",str(e)[:180])
for num in (0,1):
 try:
  base="https://ajaxmaps.ajax.ca/gisernie/rest/services/Planning/Apps_Dev/MapServer/"+str(num)
  j=S.get(base+"/query",params={"where":"1=1","returnIdsOnly":"true","f":"json"},timeout=(8,25)).json()
  ids=j.get("objectIds") or []
  print("AJAX_IDS",num,len(ids),"error",str(j.get("error",""))[:150])
  if ids:
   row=S.get(base+"/query",params={"objectIds":str(ids[0]),"outFields":"OBJECTID,REF_ID,ADDRESS,LOCATION,APPLICANT,DESCRIPTION,STATUS,SUBMISSION_DATE,TOTAL_NONRES_SQ,TYPE","returnGeometry":"false","f":"json"},timeout=(8,25)).json()
   print("AJAX_SAMPLE",num,json.dumps(row.get("features",[]),ensure_ascii=False)[:950],"error",str(row.get("error",""))[:150])
 except Exception as e:print("AJAX_DETAIL_ERROR",num,str(e)[:220])
