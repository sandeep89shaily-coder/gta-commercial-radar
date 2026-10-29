"""Offline benchmark for actual five-property Toronto report, no model calls.

Measures property recall separately from grounding, avoiding deceptive
claims of accuracy from the synthetic CI fixtures.
"""
from __future__ import annotations
import argparse,csv,json,re
from pathlib import Path

def normalize(s):
    return re.sub(r"[^a-z0-9]","",str(s).casefold())

def evaluate(gold,records,coverage):
    expected=gold["expected_properties"]
    extracted=[r for r in records if str(r.get("grounded")).lower() in ("true","1")]
    actual={normalize(r.get("address","")) for r in extracted if r.get("address")}
    found=[]
    for item in expected:
        addresses=[item["address"]]
        # Grouped land parcels are one event-level record in this gold.
        names=[normalize(x) for x in addresses]
        hit=any(a in actual for a in names)
        found.append({"gold_address":item["address"],"detected":hit,
                      "source_page":item["page"]})
    processed=coverage.get("sections_unprocessed",0)==0 and coverage.get("sections_succeeded",0)==coverage.get("sections_total",0)
    return {"source_url":gold["source_url"],
            "fully_processed":processed,"coverage_sections_total":coverage.get("sections_total",0),
            "coverage_sections_succeeded":coverage.get("sections_succeeded",0),
            "expected_property_groups":len(expected),"detected_property_groups":sum(x["detected"] for x in found),
            "property_group_recall":sum(x["detected"] for x in found)/len(expected),
            "missed_properties":[x["gold_address"] for x in found if not x["detected"]],
            "property_checks":found,"no_sale_ready_leads_established":True,
            "not_a_complete_accuracy_measure":True}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--gold",default="validation/toronto_housing_multi_property_gold.json")
    p.add_argument("--coverage",required=True)
    p.add_argument("--evidence",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    gold=json.loads(Path(a.gold).read_text(encoding="utf-8"))
    coverage=json.loads(Path(a.coverage).read_text(encoding="utf-8"))
    with Path(a.evidence).open(encoding="utf-8-sig",newline="") as h:
        records=list(csv.DictReader(h))
    result=evaluate(gold,records,coverage)
    Path(a.out).write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))

if __name__=="__main__":main()
