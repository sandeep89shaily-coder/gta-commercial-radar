"""One evidence-first continuation report for municipal discovery, purchasing and timing.

No paid calls, no inferred buyer authority, and no stale-run successes.
"""
from __future__ import annotations
import csv,json,datetime as dt
from pathlib import Path
from collections import Counter

def read(path):
    try:return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError,ValueError):return {}
def rows(path):
    try:
        with Path(path).open(encoding="utf-8-sig",newline="") as h:return list(csv.DictReader(h))
    except (OSError,ValueError):return []
def report(review,results):
    review=Path(review);results=Path(results)
    base=review/"MEETING_DOCUMENTS"/"Toronto"
    files=rows(base/"COMBINED_PDF_FETCH_AUDIT.csv")
    unique={r.get("url"):r for r in files if r.get("url")}
    captured=[r for r in unique.values() if r.get("status")=="CAPTURED"]
    ai=rows(review/"DOCUMENT_AI"/"TORONTO_AI_DOCUMENT_BATCH_AUDIT.csv")
    analyzed={r.get("source_url") for r in ai if r.get("result_file") and r.get("status") not in ("ERROR","MISSING_PDF","CHECKSUM_MISMATCH","READY_NOT_SENT")}
    meeting=rows(base/"TORONTO_MEETING_AUDIT.csv")
    buyers=rows(review/"BUYER_VERIFICATION_WORKLIST.csv")
    proof=read(results/"EARLY_DISCOVERY_PROOF.json")
    release=read(review/"RELEASE_ACCEPTANCE.json")
    results_data={
      "created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "documents":{"unique_attempted":len(unique),"captured":len(captured),"analyzed":len(analyzed),
          "download_reasons":dict(Counter(r.get("reason") or "UNKNOWN" for r in unique.values() if r.get("status")!="CAPTURED")),
          "agenda_reasons":dict(Counter(r.get("reason") or "UNKNOWN" for r in meeting if r.get("status")!="FETCHED")),
          "new_unseeded_document_discovery_proven":False},
      "buyer":{"research_candidates":len(buyers),"verified_purchasing_authorities":int(release.get("verified_buying_authorities") or 0),
          "verified_unawarded_packages":int(release.get("verified_unawarded_packages") or 0),
          "research_only":True},
      "lead_time":{"projects":int(proof.get("total") or 0),"measurable_pairs":int(proof.get("measurable") or 0),
          "unmeasurable_reasons":dict(Counter(x.get("status","UNKNOWN") for x in proof.get("findings",[])))},
      "actions":[
         "Verify public dated agenda links and permitted retrieval, then expand beyond preverified document queue",
         "Validate purchasing authority from official contacts and independently confirm supplier/award status",
         "Match early signal and subsequent permit with reviewed identity and verified publication dates",
      ]}
    (review/"EVIDENCE_CONTINUATION_REPORT.json").write_text(json.dumps(results_data,indent=2),encoding="utf-8")
    return results_data
if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--review",required=True);p.add_argument("--results",required=True)
    a=p.parse_args();print(json.dumps(report(a.review,a.results),indent=2))
