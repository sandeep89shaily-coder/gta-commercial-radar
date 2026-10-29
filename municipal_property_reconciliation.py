"""Conservative document-level synthesis of section AI observations.

One observed address can have multiple events; no unsupported merged projects.
Source quotes are always retained. No AI, API costs or V8 edits here.
"""
from __future__ import annotations
import csv,json,re
from pathlib import Path

def address_key(value):
    return " ".join(re.sub(r"[^a-z0-9 ]"," ",str(value).casefold()).split())

def reconcile(records):
    properties={}
    ungrounded=[]
    for record in records:
        entry=dict(record)
        if not entry.get("grounded"):
            ungrounded.append(entry)
            continue
        key=address_key(entry.get("address"))
        if not key:
            ungrounded.append(entry)
            continue
        prop=properties.setdefault(key,{"address":entry["address"],"observations":[],"source_count":0,
              "commercial_opportunity_status":"UNVERIFIED",
              "buyer_verified":False,"supplier_selection":"UNKNOWN"})
        prop["observations"].append({
          "section":entry["section"],"page":entry["evidence_page"],
          "quote":entry["evidence_excerpt"],"event_type":entry["event_type"],
          "organization":entry["organization"],"organization_role":entry["organization_role"],
          "stage":entry["stage"],"source_url":entry["source_url"]})
        prop["source_count"]+=1
    return {"properties":list(properties.values()),"unresolved_mentions":ungrounded,
            "sale_ready":0,"verified_procurement_opportunities":0,
            "method":"Grounded exact-address mentions grouped for review only; not confirmed project identities"}

def write(records,out):
    target=Path(out)
    target.mkdir(parents=True,exist_ok=True)
    result=reconcile(records)
    (target/"MULTI_PROPERTY_RECONCILIATION.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result
