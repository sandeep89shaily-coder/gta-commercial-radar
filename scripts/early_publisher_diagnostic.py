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
