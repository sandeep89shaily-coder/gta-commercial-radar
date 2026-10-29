"""Official Toronto procurement OData: bounded solicitation/award verification.

Source: City of Toronto public pmmd_solicitations OData service. Public purchasing
contacts in this feed represent municipal bids, NOT private project buyers.
No auth, no artificial pagination or made-up contract status.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,json,re,ssl,subprocess
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen

BASE="https://secure.toronto.ca/c3api_data/v2/DataAccess.svc/pmmd_solicitations/"
ENTITY="feis_solicitation_published"
FIELDS=("Solicitation_Document_Number","Status","Solicitation_Document_Type",
        "Posting_Title","Solicitation_Document_Description","Issue_Date",
        "Closing_Date","Buyer_Name","Buyer_Email","Buyer_Phone_Number",
        "Client_Division","Awarded_Suppliers")
PORTAL="https://www.toronto.ca/business-economy/doing-business-with-the-city/searching-bidding-on-city-contracts/toronto-bids-portal/"
def endpoint(skip,top,*,recent_first=False):
 if top<1 or top>200 or skip<0:raise ValueError("Bounded paging required")
 return BASE+ENTITY+"?"+urlencode({**{"$top":top,"$skip":skip,
                       "$format":"application/json;odata.metadata=none"},**({"$orderby":"Closing_Date desc"} if recent_first else {})})
def download_json(url):
 if not url.startswith(BASE+ENTITY+"?"):raise ValueError("Only approved OData endpoint")
 try:
  with urlopen(Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; GTARadarEvidenceReview/1.0)","Accept":"application/json"}),timeout=20) as f:
   if f.status!=200:raise RuntimeError("Official OData endpoint unavailable")
   body=f.read(1_500_001)
 except (ssl.SSLError, OSError) as original:
  # Some Windows Python distributions lack an up-to-date CA store. The
  # built-in curl.exe can use the Windows trust store; NEVER disable TLS.
  if __import__("os").name!="nt" or not isinstance(original,ssl.SSLError) and "CERTIFICATE_VERIFY_FAILED" not in str(original):
   raise
  try:
   response=subprocess.run(["curl.exe","--fail","--silent","--show-error","--location",
    "--max-time","25","--max-filesize","1500000",url],
    capture_output=True,timeout=30,check=False)
  except (OSError,subprocess.TimeoutExpired) as exc:
   raise RuntimeError("Windows TLS fallback unavailable") from exc
  if response.returncode:raise RuntimeError("Windows TLS fallback failed: "+response.stderr.decode("utf-8","replace")[:160]) from original
  body=response.stdout
 if len(body)>1_500_000:raise ValueError("OData page too large")
 return json.loads(body)
def normalized_status(raw):
 s=str(raw or "").strip().upper().replace(" ","_")
 if s in ("OPEN","ACTIVE","AWARDED","CANCELLED","CANCELED","CLOSED",
           "PENDING_AWARD","PENDING"):return s
 return "UNKNOWN"
def temporal_review(status,closing_date,*,today=None):
 today=today or dt.datetime.now(dt.timezone.utc).date()
 raw=str(closing_date or "").strip()
 parsed=None
 if raw:
  try:
   if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*",raw):
    parsed=dt.date.fromisoformat(raw[:10])
   elif re.fullmatch(r"\d{4}/\d{2}/\d{2}.*",raw):
    parsed=dt.datetime.strptime(raw[:10],"%Y/%m/%d").date()
  except ValueError:
   pass
 if status not in ("OPEN","ACTIVE"):
  return "NOT_OPEN_IN_SOURCE"
 if parsed is None:
  return "DATE_MISSING_OR_INVALID_UNVERIFIED"
 if parsed<today:
  return "PAST_CLOSING_DATE_STALE_OPEN_STATUS"
 return "FUTURE_CLOSING_DATE_REQUIRES_LIVE_CONFIRMATION"

def normalize(row,*,observed=None):
 if any(k not in row for k in ("Solicitation_Document_Number","Status")):
  raise ValueError("Required procurement schema fields are missing")
 doc=str(row["Solicitation_Document_Number"] or "").strip()
 if not re.fullmatch(r"\d{8,12}",doc):return None
 raw_status=str(row.get("Status") or "")
 awards=[]
 for item in row.get("Awarded_Suppliers") or []:
  if isinstance(item,dict) and item.get("Successful_Bidder"):
   awards.append({"supplier":str(item["Successful_Bidder"])[:200],
       "award_date":item.get("Date_Awarded"),"amount_unparsed":item.get("Award_Amount")})
 return {"document_number":doc,"status":normalized_status(raw_status),
   "raw_status":raw_status,"temporal_review":temporal_review(normalized_status(raw_status),row.get("Closing_Date")),"title":row.get("Posting_Title"),
   "description":row.get("Solicitation_Document_Description"),
   "category":row.get("Solicitation_Document_Type"),
   "issue_date":row.get("Issue_Date"),"closing_date":row.get("Closing_Date"),
   "buying_organization":"City of Toronto",
   "buyer_name_official_publication":row.get("Buyer_Name"),
   "buyer_email_official_publication":row.get("Buyer_Email"),
   "buyer_phone_official_publication":row.get("Buyer_Phone_Number"),
   "client_division":row.get("Client_Division"),
   "awarded_suppliers":awards,"source_url":BASE+ENTITY,
   "public_portal_url":PORTAL,"first_observed_utc":observed or dt.datetime.now(dt.timezone.utc).isoformat(),
   "verified_private_work_package":False,
   "official_feed_record_not_independently_rechecked":True}
def collect(out,*,fetch=download_json,max_pages=2,page_size=50,recent_first=True):
 if not 1<=max_pages<=10:raise ValueError("Page cap 1-10")
 records=[];page_audit=[];seen=set()
 now=dt.datetime.now(dt.timezone.utc).isoformat()
 for n in range(max_pages):
  url=endpoint(n*page_size,page_size,recent_first=recent_first)
  try:
   data=fetch(url)
   items=data.get("value",[])
   if not isinstance(items,list):raise ValueError("OData missing value array")
   for item in items:
    obj=normalize(item,observed=now)
    if obj and obj["document_number"] not in seen:
     seen.add(obj["document_number"]);records.append(obj)
   page_audit.append({"page":n+1,"status":"OK","received":len(items),"source_url":url})
   if len(items)<page_size:break
  except Exception as e:
   page_audit.append({"page":n+1,"status":"FAILED","error_type":type(e).__name__,"error_detail":str(e)[:220],"source_url":url})
   break
 result={"status":"REVIEW_ONLY_FETCHED" if records else "NO_RECORDS_OR_SOURCE_UNAVAILABLE",
   "official_source":BASE+ENTITY,"observed_at":now,"records":records,
   "recent_first_requested":recent_first,
   "page_audit":page_audit,"verified_private_opportunities":0,
   "limitation":"Only fetched page(s) are covered; current bid status must be rechecked at official portal before outreach."}
 dest=Path(out);dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
 tags=("hvac","cooling","refrigeration","mechanical","security","fire alarm",
       "industrial","factory","warehouse","electrical","data centre","data center")
 columns=["document_number","status","title","description","category","client_division",
   "issue_date","closing_date","buyer_name","buyer_email","buyer_phone",
   "awarded_supplier_names","potential_supplier_keywords","public_portal_url",
   "source_url","temporal_review","current_status_rechecked","private_buyer_verified"]
 with dest.with_suffix(".csv").open("w",encoding="utf-8-sig",newline="") as h:
  w=csv.DictWriter(h,fieldnames=columns);w.writeheader()
  for item in records:
   content=(" "+str(item.get("title") or "")+" "+str(item.get("description") or "")+" ").lower()
   w.writerow({"document_number":item["document_number"],"status":item["status"],
      "title":item.get("title"),"description":item.get("description"),
      "category":item.get("category"),"client_division":item.get("client_division"),
      "issue_date":item.get("issue_date"),"closing_date":item.get("closing_date"),
      "buyer_name":item.get("buyer_name_official_publication"),
      "buyer_email":item.get("buyer_email_official_publication"),
      "buyer_phone":item.get("buyer_phone_official_publication"),
      "awarded_supplier_names":"; ".join(x["supplier"] for x in item["awarded_suppliers"]),
      "potential_supplier_keywords":"; ".join(t for t in tags if t in content),
      "public_portal_url":item["public_portal_url"],"source_url":item["source_url"],
      "temporal_review":item["temporal_review"],"current_status_rechecked":False,"private_buyer_verified":False})
 return result
def main():
 p=argparse.ArgumentParser();p.add_argument("--out",required=True)
 p.add_argument("--pages",type=int,default=2);p.add_argument("--page-size",type=int,default=50)
 a=p.parse_args();r=collect(a.out,max_pages=a.pages,page_size=a.page_size)
 print(json.dumps({"status":r["status"],"records":len(r["records"]),
   "pages_checked":len(r["page_audit"]),"source":r["official_source"]},indent=2))
if __name__=="__main__":main()
