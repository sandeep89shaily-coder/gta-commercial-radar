"""Early discovery proof audit: do not conflate submission, publication and first seen.

Calculations are only produced for pairs of verified source timestamps and
stable same-project identities; missing records explicitly remain unknown.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,json
from pathlib import Path
def parse(value):
 if not value:return None
 try:return dt.datetime.fromisoformat(str(value).replace("Z","+00:00"))
 except ValueError:return None
def validate(record):
 needed=("official_project_id","first_public_url",
         "first_public_at","radar_first_seen_at","later_permit_url","later_permit_public_at")
 missing=[x for x in needed if not record.get(x)]
 if missing:return {"status":"INSUFFICIENT_PROVENANCE","missing":missing}
 if record["same_project_match_reviewed"] is not True:
  return {"status":"PROJECT_IDENTITY_NOT_VERIFIED","missing":[]}
 first=parse(record["first_public_at"]);seen=parse(record["radar_first_seen_at"])
 permit=parse(record["later_permit_public_at"])
 if not all((first,seen,permit)) or any(x.tzinfo is None for x in (first,seen,permit)):
  return {"status":"UNVERIFIED_TIMESTAMP","missing":[]}
 if seen<first or permit<first:
  return {"status":"CHRONOLOGY_CONFLICT","missing":[]}
 return {"status":"MEASURABLE","days_public_to_permit":round((permit-first).total_seconds()/86400,2),
         "days_radar_to_permit":round((permit-seen).total_seconds()/86400,2),
         "days_radar_after_first_public":round((seen-first).total_seconds()/86400,2)}
def audit(records):
 findings=[{"official_project_id":r.get("official_project_id"),**validate(r)} for r in records]
 valid=[r for r in findings if r["status"]=="MEASURABLE"]
 return {"total":len(findings),"measurable":len(valid),
         "not_measurable":len(findings)-len(valid),"findings":findings,
         "claim":"No measured advantage without independently verified same-project provenance"}
def main():
 p=argparse.ArgumentParser();p.add_argument("--records",required=True);p.add_argument("--out",required=True);a=p.parse_args()
 records=json.loads(Path(a.records).read_text(encoding="utf-8"))
 result=audit(records)
 dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps(result,indent=2),encoding="utf-8")
 print(json.dumps({"total":result["total"],"measurable":result["measurable"]},indent=2))
if __name__=="__main__":main()
