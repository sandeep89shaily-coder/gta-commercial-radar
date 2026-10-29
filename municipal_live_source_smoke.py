"""Live, non-paid source verification for GitHub CI; no scrape bypass."""
import datetime as dt,json
from pathlib import Path
from municipal_meeting_capture import discover
from toronto_procurement_odata import collect
from toronto_current_open_ckan import collect as collect_current
def main(out="LIVE_SOURCE_SMOKE"):
 root=Path(out);root.mkdir(parents=True,exist_ok=True)
 audit={"checked_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"results":[],"deepseek_calls":0}
 for city in ("Toronto","Brampton"):
  try:
   found=discover(city)
   audit["results"].append({"source":city+"_MEETING_INDEX",
      "status":"FETCHED_OFFICIAL_INDEX","videos":found["discovered"],
      "source_url":found["official_page"]})
  except Exception as e:
   audit["results"].append({"source":city+"_MEETING_INDEX",
      "status":"UNAVAILABLE","error_type":type(e).__name__})
 try:
  bids=collect(root/"TORONTO_OFFICIAL_PROCUREMENT.json",max_pages=1,page_size=20,recent_first=False)
  audit["results"].append({"source":"TORONTO_PUBLIC_PROCUREMENT_ODATA",
      "status":bids["status"],"records":len(bids["records"]),
      "page_audit":bids["page_audit"],
      "sample_statuses":{status:sum(r.get("status")==status for r in bids["records"]) for status in sorted({r.get("status") for r in bids["records"]})},
      "first_five_closing_dates":[r.get("closing_date") for r in bids["records"][:5]],
      "future_closing_open_candidates":sum(r.get("status")=="OPEN" and r.get("temporal_review")=="FUTURE_CLOSING_DATE_REQUIRES_LIVE_CONFIRMATION" for r in bids["records"]),
      "sample_public_buyer_names":sum(bool(r.get("buyer_name_official_publication")) for r in bids["records"]),
      "sample_public_buyer_emails":sum(bool(r.get("buyer_email_official_publication")) for r in bids["records"]),
      "sample_awarded_supplier_lines":sum(len(r.get("awarded_suppliers",[])) for r in bids["records"])})
 except Exception as e:
  audit["results"].append({"source":"TORONTO_PUBLIC_PROCUREMENT_ODATA",
      "status":"UNAVAILABLE","error_type":type(e).__name__})
 try:
  current=collect_current(root/"TORONTO_CURRENT_OPEN_CKAN.json",limit=1200)
  audit["results"].append({"source":"TORONTO_CKAN_CURRENT_OPEN",
    "status":current["status"],"records":len(current["records"]),
    "future_closing_candidates":current["candidate_future_closing"],
    "complete":current["complete"],
    "audit":current["audit"]})
 except Exception as exc:
  audit["results"].append({"source":"TORONTO_CKAN_CURRENT_OPEN",
    "status":"FAILED","error_type":type(exc).__name__,"detail":str(exc)[:160]})
 (root/"LIVE_SOURCE_AUDIT.json").write_text(json.dumps(audit,indent=2),encoding="utf-8")
 print(json.dumps(audit,indent=2))
 return audit
if __name__=="__main__":main()
