"""Optional OFFLINE Toronto AIC email notice import; no inbox access or subscription.

The user must subscribe through Toronto.ca and export .eml messages. Sender From
can be forged, so no records are sale-ready or officially authenticated.
"""
import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime,timezone
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr,parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from early_cue_watch import db_setup,save_source,_write_csv

SOURCE="toronto_aic_eupdates"
STATUS=("source_id","status","scanned_files","records","new","updated",
        "baseline","warning","error")
FIELDS=("source_id","record_id","title","site","company","company_role",
        "stage","signal_type","source_date","source_url","commercial_fit",
        "procurement_status","verification","first_seen_at","last_seen_at",
        "current_snapshot_status")
COMMERCIAL=re.compile(r"\b(?:industrial|warehouse|manufactur\w*|hotel|"
    r"data cent(?:re|er)|commercial|retail|office|cold storage)\b",re.I)
RESIDENTIAL=re.compile(r"\b(?:residential|townhouse|apartment|condominium)\b",re.I)

class Links(HTMLParser):
    def __init__(self):
        super().__init__();self.href=None;self.text=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            self.href=dict(attrs).get("href","");self.text=[]
    def handle_data(self,data):
        if self.href is not None:self.text.append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.href is not None:
            self.links.append((self.href," ".join(self.text).strip()))
            self.href=None;self.text=[]

def extract_message(raw):
    message=BytesParser(policy=policy.default).parsebytes(raw)
    sender=parseaddr(message.get("From",""))[1].lower()
    if not sender.endswith("@toronto.ca"):return []
    try:received=parsedate_to_datetime(message.get("Date","")).date().isoformat()
    except (ValueError,TypeError,IndexError):received=""
    links=[]
    for part in message.walk():
        if part.get_content_type() not in ("text/html","text/plain"):continue
        try:body=part.get_content()
        except (UnicodeError,LookupError):continue
        if not isinstance(body,str):continue
        if part.get_content_type()=="text/html":
            p=Links();p.feed(body[:100000]);links+=p.links
        else:
            links += [(x,"") for x in re.findall(r"https://[^\s<>'\"]+",body)]
    rows={}
    for href,label in links:
        href=href.replace("&amp;","&").strip()
        url=urlparse(href)
        if url.scheme!="https" or url.hostname not in ("www.toronto.ca","toronto.ca"):
            continue
        if not any(x in (url.path+"?"+url.query).lower()
                   for x in ("application","planning","aic","development")):
            continue
        if len(href)>550:continue
        rid=hashlib.sha256(href.encode("utf-8")).hexdigest()[:24]
        if rid in rows:continue
        headline=(label or message.get("Subject","Toronto AIC update"))[:200]
        full=headline+" "+str(message.get("Subject",""))
        commercial=bool(COMMERCIAL.search(full))
        homes=bool(RESIDENTIAL.search(full))
        rows[rid]=dict(source_id=SOURCE,record_id=rid,title=headline,
             site="",company="",company_role="BUYER_NOT_IDENTIFIED",
             stage="EMAIL_LINK_UNVERIFIED",signal_type="AIC_WARD_EMAIL",
             source_date="",source_url=href,
             commercial_fit=("MIXED_USE_REVIEW" if commercial and homes else
               "POSSIBLE_COMMERCIAL" if commercial else
               "RESIDENTIAL_LIKELY" if homes else "USE_UNKNOWN"),
             procurement_status="UNKNOWN",
             verification="FROM_SENDER_UNAUTHENTICATED;OFFICIAL_LINK_NEEDS_CHECK",
             attributes={"email_header_date_not_publication":received})
    return list(rows.values())

def run(folder="data/toronto_aic_eml",data_dir="data",output_dir="GTA_RADAR_RESULTS"):
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    root=Path(folder)
    files=sorted(root.glob("*.eml"))[:100] if root.is_dir() else []
    d=Path(data_dir);d.mkdir(parents=True,exist_ok=True)
    if not files:
        _write_csv(out/"EARLY_AIC_EMAIL_STATUS.csv",STATUS,[
            dict(source_id=SOURCE,status="NO_EMAIL_INPUT",scanned_files=0,
                 records=0,new=0,updated=0,baseline="NO",
                 warning="SUBSCRIPTION_AND_EXPORT_NEED_EXPLICIT_USER_ACTION",error="")])
        print("No Toronto AIC emails imported; no connection/subscription attempted")
        return 0
    items={}
    for path in files:
        try:
            if path.stat().st_size>2_000_000:continue
            for row in extract_message(path.read_bytes()):items[row["record_id"]]=row
        except (OSError,ValueError):continue
    if not items:
        _write_csv(out/"EARLY_AIC_EMAIL_STATUS.csv",STATUS,[
            dict(source_id=SOURCE,status="NO_VERIFIED_CITY_LINKS",
                 scanned_files=len(files),records=0,new=0,updated=0,baseline="NO",
                 warning="NEEDS_ORIGINAL_EMAIL_AND_CITY_LINK_REVIEW",error="")])
        return 1
    db=sqlite3.connect(d/"early_aic_email_review.sqlite")
    db_setup(db)
    try:
        stamped=datetime.now(timezone.utc).isoformat(timespec="seconds")
        status=save_source(db,SOURCE,list(items.values()),stamped)
        _write_csv(out/"EARLY_AIC_EMAIL_STATUS.csv",STATUS,[
           dict(source_id=SOURCE,status="IMPORTED_REVIEW_ONLY",
             scanned_files=len(files),records=len(items),
             warning="SENDER_UNAUTHENTICATED;NO_PUBLICATION_DATE",
             error="",**status)])
        queue=[]
        for sid,rid,first,last,content in db.execute(
             "SELECT source_id,record_id,first_seen_at,last_seen_at,content "
             "FROM snapshots WHERE source_id=?",(SOURCE,)):
            item=json.loads(content)
            if item["commercial_fit"] not in ("POSSIBLE_COMMERCIAL","MIXED_USE_REVIEW"):
                continue
            queue.append(dict(item,first_seen_at=first,last_seen_at=last,
                 current_snapshot_status="UNVERIFIED_EMAIL_IMPORTED"))
        _write_csv(out/"EARLY_AIC_EMAIL_RESEARCH.csv",FIELDS,queue)
        print("AIC email-linked review records",len(queue),"| no AI or V8 changes")
        return 0
    finally:db.close()

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--eml-folder",default="data/toronto_aic_eml")
    p.add_argument("--data-dir",default="data")
    p.add_argument("--output-dir",default="GTA_RADAR_RESULTS")
    a=p.parse_args();raise SystemExit(run(a.eml_folder,a.data_dir,a.output_dir))
