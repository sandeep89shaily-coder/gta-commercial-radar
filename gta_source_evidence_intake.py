"""Free bounded source-text recovery and claim verification intake.

Only direct record excerpts are proposed, never AI summaries. Missing official
identity, publication dates, purchasing authority and supplier status remain unknown.
"""
from __future__ import annotations
import argparse,csv,json,datetime as dt,re
from urllib.parse import urlparse
from html.parser import HTMLParser
from pathlib import Path
import auto_verify
import gta_select_first_investigations as first
import candidate_scoring as scoring

SOURCE_FILES=("GTA_RADAR_V8_PENDING_QUEUE.csv","GTA_RADAR_V8_PROJECTS.csv",
              "GTA_RADAR_V4_PROJECTS_FOR_AI.csv","GTA_RADAR_PROJECT_OPPORTUNITIES.csv")
def load_csv(path):
    try:
        with Path(path).open(encoding="utf-8-sig",newline="") as stream:return list(csv.DictReader(stream))
    except (OSError,UnicodeError,ValueError):return []
def recover(results,top=10):
    results=Path(results)
    source=results/first.DEFAULT_FILE
    candidates=first.load_records(source) if source.is_file() else []
    by_id={}
    for filename in SOURCE_FILES:
        for item in load_csv(results/filename):
            pid=(item.get("project_id") or "").strip()
            desc=(item.get("official_description") or item.get("description") or "").strip()
            if pid and desc and item.get("record_source_url","").startswith("https://"):
                if pid not in by_id or len(desc)>len(by_id[pid].get("description","")):
                    by_id[pid]={**item,"description":desc}
    recovered=[];needs=[]
    for item in candidates:
        pid=item.get("project_id","")
        if first.has_source_text(item):
            recovered.append(item)
        elif pid in by_id:
            recovered.append({**item,"description":by_id[pid]["description"],
                               "record_source_url":by_id[pid]["record_source_url"],
                               "source_recovery_basis":"EXISTING_SOURCED_QUEUE_NOT_LIVE_REFETCH"})
        else:
            needs.append({"project_id":pid,"address":item.get("address",""),
                          "source_url":item.get("record_source_url",""),
                          "reason":"NO_MATCHING_SOURCED_RECORD_IN_LOCAL_FILES"})
    selection=first.prioritize(recovered,top)
    return selection,needs,{r.get("project_id"):r for r in recovered}

def propose(row):
    """Use exact source description, without inventing missing milestones."""
    url=(row.get("record_source_url") or "").strip()
    desc=(row.get("official_description") or row.get("description") or "").strip()
    pid=(row.get("project_id") or "").strip()
    if not pid or not url.startswith("https://") or len(desc)<25:return None
    # A quoted source record can support scope, but cannot establish company
    # ownership, a direct government page identity, or historical publication.
    claim={"official_url":url,"excerpt":desc[:450]}
    return {"project_id":pid,"address":row.get("address",""),
            "organization":row.get("official_company","") or "",
            "supplier_status":"UNKNOWN","claims":{"scope_evidence":claim,
                                                          "project_source":claim}}

class Visible(HTMLParser):
    def __init__(self):
        super().__init__();self.parts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.skip+=1
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)

def refresh_official(rows,recovered,fetcher,limit=8):
    audits=[];updated=0
    for item in rows:
        if len(audits)>=limit:break
        pid=str(item.get('project_id') or '')
        url=str(item.get('source_url') or item.get('record_source_url') or '')
        host=(urlparse(url).hostname or '').lower()
        ident=pid.split(':',1)[-1].strip()
        audit={'project_id':pid,'source_url':url}
        if not url.startswith('https://') or not any(host==h or host.endswith('.'+h) for h in ('toronto.ca','brampton.ca','mississauga.ca','ontario.ca')):
            audit['status']='UNSUPPORTED_OFFICIAL_SOURCE';audits.append(audit);continue
        if len(ident)<6:
            audit['status']='IDENTITY_TOO_SHORT';audits.append(audit);continue
        response=fetcher(url)
        if not response.get('ok'):
            audit['status']='FETCH_FAILED';audit['reason']=response.get('reason','');audits.append(audit);continue
        html=Visible();html.feed(str(response.get('text') or '')[:2000000])
        visible=' '.join(' '.join(html.parts).split())
        match=re.search(re.escape(ident),visible,re.I)
        if not match:
            audit['status']='EXACT_ID_NOT_IN_PAGE';audits.append(audit);continue
        excerpt=visible[max(0,match.start()-180):min(len(visible),match.end()+450)]
        if len(excerpt)<25:
            audit['status']='INSUFFICIENT_TEXT';audits.append(audit);continue
        recovered[pid]={'project_id':pid,'address':item.get('address',''),'description':excerpt,'record_source_url':url,'source_recovery_basis':'LIVE_OFFICIAL_EXACT_ID_MATCH'}
        audit['status']='RECOVERED_EXACT_ID_SOURCE_TEXT';audits.append(audit);updated+=1
    return audits,updated
def run(results,out,*,top=10,fetcher=None):
    results=Path(results);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    selection,missing,recovered=recover(results,top)
    refresh_audit=[];refreshed=0
    if fetcher is not None:
        refresh_audit,refreshed=refresh_official(missing+selection["needs_source_refresh"],recovered,fetcher)
        selection=first.prioritize(list(recovered.values()),top)
    chosen=selection["top"]
    specs=[spec for item in chosen
           if (spec:=propose(recovered.get(item["project_id"],{}))) is not None]
    outstanding=[x for x in missing+selection["needs_source_refresh"] if x.get("project_id") not in recovered]
    summary={"candidate_count":len(chosen),"claim_specs":len(specs),
             "source_refresh_required":outstanding,
             "source_records_recovered_live":refreshed,"live_refresh_audit":refresh_audit,
             "verified_claims":0,"human_confirmations_created":0}
    if fetcher is not None and specs:
        reviews=[];status=[]
        for spec in specs:
            review,details=auto_verify.build_review(spec,fetcher)
            reviews.append(review);status.append({"project_id":spec["project_id"],"claims":details})
            summary["verified_claims"]+=sum(x["status"]=="AUTO_VERIFIED" for x in details.values())
        auto_verify.write_auto_file(results,reviews)
        summary["claim_status"]=status
    # Never touch the owner's reviewed evidence or source databases.
    dated=out/("SOURCE_INTAKE_"+dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+".json")
    dated.write_text(json.dumps({"summary":summary,"specs":specs},indent=2),encoding="utf-8")
    return summary

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--results",required=True);p.add_argument("--out",required=True)
    p.add_argument("--top",type=int,default=10);p.add_argument("--verify",action="store_true")
    a=p.parse_args()
    fetcher=(lambda url:auto_verify.fetch_page(url)) if a.verify else None
    print(json.dumps(run(a.results,a.out,top=a.top,fetcher=fetcher),indent=2))
if __name__=="__main__":main()
