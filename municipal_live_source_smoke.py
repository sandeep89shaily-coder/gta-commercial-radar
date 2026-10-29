"""Live, non-paid source verification for GitHub CI; no scrape bypass."""
import datetime as dt,json
from pathlib import Path
from municipal_meeting_capture import discover
from toronto_procurement_odata import collect
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
  bids=collect(root/"TORONTO_OFFICIAL_PROCUREMENT.json",max_pages=1,page_size=10)
  audit["results"].append({"source":"TORONTO_PUBLIC_PROCUREMENT_ODATA",
      "status":bids["status"],"records":len(bids["records"]),
      "page_audit":bids["page_audit"]})
 except Exception as e:
  audit["results"].append({"source":"TORONTO_PUBLIC_PROCUREMENT_ODATA",
      "status":"UNAVAILABLE","error_type":type(e).__name__})
 (root/"LIVE_SOURCE_AUDIT.json").write_text(json.dumps(audit,indent=2),encoding="utf-8")
 print(json.dumps(audit,indent=2))
 return audit
if __name__=="__main__":main()
