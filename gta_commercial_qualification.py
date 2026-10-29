"""Commercial qualification board for GTA Radar: ranked candidates, not asserted sales leads.

No private individual contacts, no inferred supplier availability. Public city
solicitations are NOT the same as pre-procurement private construction projects.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,html,json,re
from pathlib import Path

CATEGORIES={
 "HVAC / refrigeration":("hvac","refrigerat","chiller","cooling","heat pump","ventilation","air handling","mechanical"),
 "Security / fire protection":("security","surveillance","access control","cctv","fire alarm","sprinkler","fire protection"),
 "Electrical / power":("electrical","transformer","substation","switchgear","generator","electric power","wiring"),
 "Industrial equipment":("factory","industrial","compressor","manufactur","warehouse","machinery","conveyor"),
}
REQUIRED=("project_source","project_identity","scope_evidence","buyer_org_evidence",
          "buying_authority_evidence","contact_route_evidence","procurement_evidence",
          "source_first_publication","radar_first_observed")
def classify(title):
 text=str(title or "").casefold()
 return [c for c,words in CATEGORIES.items() if any(re.search(r"(?<![a-z])"+re.escape(x),text) for x in words)]
def rank(record,as_of=None):
 as_of=as_of or dt.datetime.now(dt.timezone.utc).date()
 status=record.get("temporal_review")
 if status!="FUTURE_CLOSING_DATE_REQUIRES_LIVE_CONFIRMATION":return None
 groups=classify(" ".join(str(record.get(x) or "") for x in ("title","description","category")))
 date=str(record.get("closing_date") or "")[:10]
 try:days=(dt.date.fromisoformat(date)-as_of).days
 except ValueError:return None
 if days<0:return None
 score=25*bool(groups)+min(30,days)+10*bool(record.get("buyer_email_official_publication"))+10*bool(record.get("document_number"))
 return {"reference":record.get("document_number"),"description":record.get("title"),
   "service_categories":groups,"closing_date":date,"days_until_date":days,
   "published_buyer_name":record.get("buyer_name_official_publication"),
   "published_business_email":record.get("buyer_email_official_publication"),
   "source_url":record.get("source_url"),"portal_url":record.get("public_portal_url"),
   "score_for_research_only":score,"stage":"PUBLIC_TENDER_FUTURE_CLOSING_RECHECK",
   "current_status_verified":False,"private_project_opportunity":False,
   "supplier_selected":"UNKNOWN","sale_ready":False,
   "missing_verification":["current official portal/addenda status","trade eligibility and work package fit"]}
def create(source,out,*,as_of=None):
 obj=json.loads(Path(source).read_text(encoding="utf-8"))
 board=[v for r in obj.get("records",[]) if (v:=rank(r,as_of=as_of)) is not None]
 board.sort(key=lambda x:(not bool(x["service_categories"]),-x["score_for_research_only"],x["closing_date"],str(x["reference"])))
 data={"source_status":obj.get("status"),"source_complete":obj.get("complete",False),
  "records_examined":len(obj.get("records",[])),"future_closing_candidates":len(board),
  "relevant_trade_candidates":sum(bool(x["service_categories"]) for x in board),
  "verified_private_opportunities":0,"buyer_decision_makers_verified_for_private_projects":0,
  "verified_unawarded_private_work_packages":0,"leads":board,
  "limitations":["Source status not confirmed in live portal","Historical city tenders are not private-project early signals",
   "City procurement contact is not private purchasing authority",
   "Commercial project leads require independent source and buyer verification"]}
 out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8")
 fields=["reference","description","service_categories","closing_date","days_until_date",
         "published_buyer_name","published_business_email","stage","score_for_research_only",
         "portal_url","sale_ready"]
 with out.with_suffix(".csv").open("w",encoding="utf-8-sig",newline="") as h:
  w=csv.DictWriter(h,fieldnames=fields);w.writeheader()
  for r in board:w.writerow({**{k:r.get(k) for k in fields},"service_categories":"; ".join(r["service_categories"])})
 return data

def qualify_private(dossier):
 """Independent source IDs and positive confirmations required, never AI assertion alone."""
 checks={key:bool(dossier.get("verified",{}).get(key)) for key in REQUIRED}
 sources=dossier.get("source_evidence",{})
 for field in REQUIRED:
  evidence_id=dossier.get("evidence_ids",{}).get(field)
  proof=sources.get(evidence_id) if evidence_id else None
  if not isinstance(proof,dict) or not proof.get("official_url") or not proof.get("excerpt") or not proof.get("reviewer_confirmed"):
   checks[field]=False
 if dossier.get("supplier_status")!="INDEPENDENTLY_CHECKED_UNSELECTED":checks["procurement_evidence"]=False
 return {"sale_ready":all(checks.values()),"missing":[f for f,ok in checks.items() if not ok],
         "status":"SALE_READY_VERIFIED" if all(checks.values()) else "RESEARCH_ONLY"}
def main():
 p=argparse.ArgumentParser();p.add_argument("--source",required=True);p.add_argument("--out",required=True)
 a=p.parse_args();result=create(a.source,a.out)
 print(json.dumps({k:result[k] for k in ("records_examined","future_closing_candidates","relevant_trade_candidates","verified_private_opportunities")},indent=2))
if __name__=="__main__":main()
