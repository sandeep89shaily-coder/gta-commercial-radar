"""Join meeting observations and buyer research in review-only project evidence graph."""
from __future__ import annotations
import argparse,hashlib,json,re
from pathlib import Path
def key(address):
 return " ".join(re.findall(r"[a-z0-9]+",str(address).lower()))
def graph(synthesis=None,buyer=None,meeting=None):
 nodes={};edges=[];uncertain=[]
 if synthesis:
  source=json.loads(Path(synthesis).read_text(encoding="utf-8"))
  for x in source.get("ai_suggestions",{}).get("project_candidates",[]):
   addr=x.get("address") or ""
   k=key(addr)
   if not k:
    uncertain.append({"type":"UNLOCATED_PROJECT","claim":x});continue
   nid="site_"+hashlib.sha256(k.encode()).hexdigest()[:18]
   n=nodes.setdefault(nid,{"id":nid,"address":addr,"project_identity_verified":False,
                              "evidence_ids":[],"buyer_status":"UNVERIFIED","procurement_status":"UNKNOWN"})
   n["evidence_ids"].extend(x.get("source_evidence_ids",[]))
 if buyer:
  research=json.loads(Path(buyer).read_text(encoding="utf-8"))
  addr=research.get("address","");k=key(addr)
  if k:
   nid="site_"+hashlib.sha256(k.encode()).hexdigest()[:18]
   n=nodes.setdefault(nid,{"id":nid,"address":addr,"project_identity_verified":False,
      "evidence_ids":[],"buyer_status":"UNVERIFIED","procurement_status":"UNKNOWN"})
   for o in research.get("organizations",[]):
    identity=o.get("organization","")
    if not identity:continue
    oid="org_"+hashlib.sha256(identity.casefold().encode()).hexdigest()[:18]
    nodes.setdefault(oid,{"id":oid,"name":identity,"organization_verified":False})
    edges.append({"from":nid,"to":oid,"role":o.get("role","UNVERIFIED"),
                  "evidence_id":o.get("evidence_id"),"verified":False})
   n["candidate_buyers"]=len(research.get("organizations",[]))
 if meeting:
  records=json.loads(Path(meeting).read_text(encoding="utf-8"))
  for r in records.get("meetings",[]):
   mid="meeting_"+hashlib.sha256(r["recording_url"].encode()).hexdigest()[:18]
   nodes[mid]={"id":mid,"recording_url":r["recording_url"],
               "official_discovery_url":r["official_discovery_url"],
               "agenda_match":r["agenda_match"],"project_identity_verified":False}
 return {"schema":"gta_evidence_graph_v1","nodes":list(nodes.values()),
   "edges":edges,"unresolved":uncertain,"sale_ready_opportunities":0,
   "requires_human_review":True}
def main():
 p=argparse.ArgumentParser();p.add_argument("--synthesis");p.add_argument("--buyer")
 p.add_argument("--meeting");p.add_argument("--out",required=True);a=p.parse_args()
 result=graph(a.synthesis,a.buyer,a.meeting)
 target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
 target.write_text(json.dumps(result,indent=2),encoding="utf-8")
 print(json.dumps({"graph_nodes":len(result["nodes"]),"graph_edges":len(result["edges"]),
                  "verified_opportunities":0},indent=2))
if __name__=="__main__":main()
