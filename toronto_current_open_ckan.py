"""Official Toronto CKAN current open-solicitations dataset.

Use the city's dedicated open list, not page 1 of a decade-spanning OData
archive. Dates still determine eligibility; public status is never proof.
"""
from __future__ import annotations
import argparse,datetime as dt,json,re
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen,Request
from toronto_procurement_odata import temporal_review,PORTAL

API="https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/"
DATASET="tobids-all-open-solicitations"

def fetch_json(url):
 if not url.startswith(API):raise ValueError("Only official Toronto CKAN action API")
 with urlopen(Request(url,headers={"Accept":"application/json","User-Agent":"GTARadarEvidenceReview/1.0"}),timeout=25) as f:
  if f.status!=200:raise RuntimeError("Official Toronto CKAN unavailable")
  raw=f.read(2_500_001)
 if len(raw)>2_500_000:raise ValueError("CKAN result exceeds size bound")
 return json.loads(raw)

def action(op,params,fetch=fetch_json):
 if op not in ("package_show","datastore_search"):raise ValueError("Invalid action")
 data=fetch(API+op+"?"+urlencode(params))
 if not data.get("success"):raise ValueError("Toronto CKAN returned unsuccessful response")
 return data["result"]

def normalize(row,today=None):
 doc=str(row.get("Document Number") or "").strip().removeprefix("Doc-")
 if not re.fullmatch(r"\d{8,12}",doc):return None
 closing=row.get("Submission Deadline")
 status=temporal_review("OPEN",closing,today=today)
 return {"document_number":doc,"status":"OPEN","raw_status":"CKAN_OPEN_DATASET",
   "temporal_review":status,"title":row.get("Solicitation Document Description") or "",
   "description":row.get("Solicitation Document Description"),
   "category":row.get("High Level Category"),"issue_date":row.get("Issue Date"),
   "closing_date":closing,"client_division":row.get("Division"),
   "buyer_name_official_publication":row.get("Buyer Name"),
   "buyer_email_official_publication":row.get("Buyer Email"),
   "buyer_phone_official_publication":row.get("Buyer Phone Number"),
   "awarded_suppliers":[],"source_url":API+"package_show?id="+DATASET,
   "public_portal_url":PORTAL,"verified_private_work_package":False,
   "current_status_rechecked":False}

def collect(out,*,fetch=fetch_json,limit=500,today=None):
 if not 1<=limit<=3000:raise ValueError("CKAN row cap 1-3000")
 audit=[];records=[]
 try:
  package=action("package_show",{"id":DATASET},fetch)
  resources=[r for r in package.get("resources",[]) if r.get("datastore_active")]
  if not resources:raise ValueError("Official CKAN open solicitations has no active datastore")
  resource=resources[0]["id"]
  offset=0;count=0;total=None;seen=set()
  while count<limit:
   page_size=min(200,limit-count)
   data=action("datastore_search",{"resource_id":resource,"limit":page_size,"offset":offset},fetch)
   raw=data.get("records",[])
   total=data.get("total",total)
   for row in raw:
    record=normalize(row,today=today)
    if record and record["document_number"] not in seen:
     seen.add(record["document_number"]);records.append(record)
   count+=len(raw);offset+=len(raw)
   if not raw or len(raw)<page_size:break
  audit.append({"status":"SUCCESS","raw_rows":count,"resource_id":resource,
                "total_reported":total})
 except Exception as exc:
  audit.append({"status":"FAILED","error_type":type(exc).__name__,"error_detail":str(exc)[:200]})
 eligible=sum(r["temporal_review"]=="FUTURE_CLOSING_DATE_REQUIRES_LIVE_CONFIRMATION" for r in records)
 result={"status":"FETCHED" if audit[0]["status"]=="SUCCESS" else "UNAVAILABLE",
   "source":"OFFICIAL_TORONTO_CKAN_OPEN_SOLICITATIONS","records":records,
   "candidate_future_closing":eligible,"audit":audit,
   "complete":bool(audit[0]["status"]=="SUCCESS" and (audit[0].get("total_reported") or 0)<=limit),
   "note":"Dedicated city OPEN dataset; verify each live event and addenda before presenting as available"}
 path=Path(out);path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(result,indent=2),encoding="utf-8")
 return result
def main():
 p=argparse.ArgumentParser();p.add_argument("--out",required=True);p.add_argument("--limit",type=int,default=1200)
 a=p.parse_args();r=collect(a.out,limit=a.limit)
 print(json.dumps({"status":r["status"],"records":len(r["records"]),
   "future_closing_candidates":r["candidate_future_closing"],"audit":r["audit"]},indent=2))
if __name__=="__main__":main()
