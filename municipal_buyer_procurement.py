"""Evidence-first buyer/procurement research lane, review-only.

No private-contact harvesting. A procurement lead is OPEN only on direct
official solicitation evidence; a project/site mention never implies demand.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,json,re
from pathlib import Path
from urllib.parse import urlparse
from municipal_meeting_capture import public_https

PORTALS={
"Toronto":"https://www.toronto.ca/business-economy/doing-business-with-the-city/searching-bidding-on-city-contracts/toronto-bids-portal/",
"Brampton":"https://www.brampton.ca/EN/Business/Bids-Tenders/Pages/Welcome.aspx",
"Canada":"https://canadabuys.canada.ca/en",
}
ROLES=("developer","owner","operator","tenant","agent","architect","general_contractor",
       "purchasing_organization","procurement_contact")
STATES=("UNKNOWN","OPEN","AWARDED","CANCELLED","CLOSED","PENDING")
def evidence(source_url,quote,field,value,*,page=None,timestamp=None,source_kind="document"):
 if not public_https(source_url):raise ValueError("Evidence source must be HTTPS")
 if not quote or (page is None and timestamp is None):
  raise ValueError("Evidence requires quotation and page or timestamp")
 canonical=f"{source_url}|{page}|{timestamp}|{field}|{quote}"
 return {"evidence_id":hashlib.sha256(canonical.encode()).hexdigest()[:24],
         "source_url":source_url,"source_kind":source_kind,"page":page,
         "timestamp_seconds":timestamp,"quote":quote,"field":field,"value":value,
         "verified_semantically":False}
def dossier(project_id,project_address,observations,*,as_of=None):
 orgs=[];contracts=[];citations=[];unverified=[]
 for r in observations:
  if not r.get("source_url") or not r.get("quote") or (r.get("page") is None and r.get("timestamp_seconds") is None):
   unverified.append({"reason":"MISSING_EVIDENCE","observation":r});continue
  try:
   ev=evidence(r["source_url"],r["quote"],r.get("field","other"),r.get("value",""),
       page=r.get("page"),timestamp=r.get("timestamp_seconds"),
       source_kind=r.get("source_kind","document"))
  except ValueError:
   unverified.append({"reason":"INVALID_EVIDENCE","observation":r});continue
  citations.append(ev)
  role=str(r.get("role") or "").lower()
  if role in ROLES:
   orgs.append({"organization":r.get("organization",""),"role":role,
       "evidence_id":ev["evidence_id"],"verified":False,
       "public_business_contact":r.get("public_business_contact",""),
       "contact_source_verified":False})
  status=str(r.get("procurement_status") or "UNKNOWN").upper()
  if status not in STATES:status="UNKNOWN"
  # Never trust a user's unverified label as evidence of tender status.
  if status!="UNKNOWN":
   has_official=r.get("source_kind")=="official_procurement_notice"
   has_reference=bool(r.get("tender_reference"))
   has_human_confirmation=r.get("procurement_verified") is True
   if not (has_official and has_reference and has_human_confirmation):
    status="UNKNOWN"
  contracts.append({"service_package":r.get("service_package",""),
    "status":status,"tender_reference":r.get("tender_reference",""),
    "buyer":r.get("buyer",""),"evidence_id":ev["evidence_id"],
    "potential_only":status=="UNKNOWN"})
 return {"project_id":project_id,"address":project_address,
   "as_of_utc":as_of or dt.datetime.now(dt.timezone.utc).isoformat(),
   "organizations":orgs,"procurement_checks":contracts,"evidence":citations,
   "not_admissible":unverified,"candidate_buyer_count":len(orgs),
   "verified_purchasing_contacts":0,
   "open_contracts_verified":sum(x["status"]=="OPEN" for x in contracts),
   "sale_ready":False,
   "next_actions":["Verify business identity and purchasing responsibility from official organization sources",
    "Check official tender/award portal, specific notice and decision date",
    "Confirm applicable service package and whether supplier selection remains open"],
   "starting_portals":PORTALS}
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--project-id",required=True);p.add_argument("--address",required=True)
 p.add_argument("--observations",required=True);p.add_argument("--out",required=True)
 a=p.parse_args()
 records=json.loads(Path(a.observations).read_text(encoding="utf-8"))
 result=dossier(a.project_id,a.address,records)
 target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
 target.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
 print(json.dumps({"candidate_buyers":result["candidate_buyer_count"],
   "verified_open_contracts":result["open_contracts_verified"],"sale_ready":False},indent=2))
if __name__=="__main__":main()
