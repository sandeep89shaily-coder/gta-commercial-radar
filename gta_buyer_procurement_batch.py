"""Free, evidence-gated buyer/procurement triage for at most 10 Radar candidates.

Reads existing local worklists and reviewed evidence. All unconfirmed buyer,
contractor and supplier details remain UNKNOWN. Never performs paid research,
mutates source data, or promotes AI hints to proof.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,json
from pathlib import Path
import gta_select_first_investigations as first
import reviewed_evidence as gate

FIELDS=("rank","project_id","address","operator_hint","operator_status",
        "buyer_authority_status","contact_route_status","supplier_status",
        "general_contractor_status","open_package_verified","live_sourced_observations",
        "sale_ready","priority","source_url","next_action")

def choose(results,top=10):
    source=Path(results)/first.DEFAULT_FILE
    if not source.exists():return []
    rows=first.load_records(source)
    selection=first.prioritize(rows,top=max(top,1))
    # Keep the batch bounded, prefer source-ranked rows. Unscorable items are
    # visible separately in the report, not converted into verified projects.
    return selection["top"][:top]

def evaluate(results,review,top=10):
    chosen=choose(results,top)
    # Human-reviewed evidence is authoritative; never trust legacy "verified"
    # booleans or unreviewed company / contractor names.
    proofs=gate.evaluate_folder(review)["results"]
    # Live matches are research observations, never authority or contract proofs.
    live={}
    live_stage_status="NO_LIVE_EVIDENCE_REPORT"
    live_unlinked=0
    live_input=0
    reports=sorted(Path(review).glob("LIVE_PROCUREMENT_EVIDENCE_*.json"))
    if reports:
        try:
            audit=json.loads(reports[-1].read_text(encoding="utf-8"))
            observations=audit.get("records",[])
            live_stage_status=audit.get("status","UNKNOWN_LIVE_STAGE")
            live_unlinked=int(audit.get("unlinked_observations") or 0)
            live_input=int(audit.get("input_observations") or 0)
            for observation in observations:
                pid=observation.get("project_id")
                if pid and observation.get("proof_status")=="SOURCE_TEXT_MATCHED":
                    live.setdefault(pid,[]).append(observation)
        except (OSError,ValueError,TypeError):
            live={}
    records=[]
    for n,item in enumerate(chosen,1):
        pid=item["project_id"]
        p=proofs.get(pid,{})
        buyer=bool(p.get("buyer_authority_verified"))
        contact=bool(p.get("contact_route_verified"))
        supplier=bool(p.get("supplier_selection_verified"))
        ready=bool(p.get("sale_ready"))
        records.append({
          "rank":n,"project_id":pid,"address":item.get("address",""),
          "operator_hint":item.get("operator_name",""),
          "operator_status":"UNVERIFIED_HINT",
          "buyer_authority_status":"VERIFIED_REVIEW" if buyer else "UNKNOWN",
          "contact_route_status":"VERIFIED_REVIEW" if contact else "UNKNOWN",
          "supplier_status":p.get("supplier_status","UNKNOWN") if supplier else "UNKNOWN",
          "general_contractor_status":"UNKNOWN",
          "open_package_verified":supplier,"sale_ready":ready,
          "live_sourced_observations":len(live.get(pid,[])),
          "priority":item.get("score",""),
          "source_url":item.get("record_source_url",""),
          "next_action":("REVALIDATE_EVIDENCE" if ready else
            "HUMAN_REVIEW_MATCHED_PURCHASING_EVIDENCE" if live.get(pid) else
            "VERIFY_PURCHASING_AUTHORITY_CONTACT_AND_CURRENT_PACKAGE_AWARD_STATUS")
        })
    return {"created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "selection":"UP_TO_TEN_EXISTING_OPERATOR_ASSOCIATED_RECORDS",
            "projects_checked":len(records),
            "live_stage_status":live_stage_status,
            "live_input_observations":live_input,
            "live_unlinked_observations":live_unlinked,
            "verified_buyers":sum(x["buyer_authority_status"]=="VERIFIED_REVIEW" for x in records),
            "verified_open_packages":sum(x["open_package_verified"] for x in records),
            "sale_ready":sum(x["sale_ready"] for x in records),
            "ai_calls":0,"source_databases_modified":False,"records":records,
            "limitation":"No live purchasing contacts or award claims are inferred; no reviewed evidence means no verified lead."}

def write(report,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    base=out/("BUYER_PROCUREMENT_BATCH_"+stamp)
    (Path(str(base)+".json")).write_text(json.dumps(report,indent=2),encoding="utf-8")
    with Path(str(base)+".csv").open("w",newline="",encoding="utf-8-sig") as stream:
        writer=csv.DictWriter(stream,fieldnames=FIELDS);writer.writeheader();writer.writerows(report["records"])
    return str(base)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--results",required=True)
    parser.add_argument("--review",required=True)
    parser.add_argument("--out",required=True)
    parser.add_argument("--top",type=int,default=10)
    args=parser.parse_args()
    if not 1<=args.top<=10:parser.error("top must be 1..10")
    data=evaluate(args.results,args.review,args.top)
    print(json.dumps({"summary":{k:v for k,v in data.items() if k!="records"},
                      "output_prefix":write(data,args.out)},indent=2))
if __name__=="__main__":main()
