"""Produce and retain an explicit first-seen ledger for source-dated projects."""
import csv,datetime as dt,json,sqlite3
from pathlib import Path
from gta_lead_time_proof import audit
FIELDS=("project_id","official_source_url","source_publication_at","radar_first_seen_at",
        "later_permit_url","later_permit_public_at","same_project_match_reviewed")
def track(queue,folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(folder/"RADAR_DISCOVERY_LEDGER.sqlite")
    db.execute("CREATE TABLE IF NOT EXISTS discovery(project_id TEXT PRIMARY KEY, first_seen_at TEXT NOT NULL, source_url TEXT)")
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    with Path(queue).open(encoding="utf-8-sig",newline="") as f:rows=list(csv.DictReader(f))
    for row in rows:
        pid=row.get("project_id","")
        if pid:
            db.execute("INSERT OR IGNORE INTO discovery VALUES (?,?,?)",
                       (pid,now,row.get("record_source_url","")))
    db.commit()
    # Store provenance from source data, never substitute polling time for publication.
    by_id={row.get("project_id"):row for row in rows if row.get("project_id")}
    matches=[]
    for pid,first,source in db.execute("SELECT project_id,first_seen_at,source_url FROM discovery"):
        row=by_id.get(pid,{})
        # A project_id in a queue is a candidate identity, not a confirmed same-site match.
        reviewed=row.get("same_project_match_reviewed") is True or str(row.get("same_project_match_reviewed","")).lower()=="true"
        matches.append({"official_project_id":row.get("official_project_id") or pid,
                        "radar_first_seen_at":first,
                        "first_public_url":row.get("first_public_url") or source,
                        "first_public_at":row.get("first_public_at") or row.get("source_publication_at"),
                        "later_permit_url":row.get("later_permit_url"),
                        "later_permit_public_at":row.get("later_permit_public_at"),
                        "same_project_match_reviewed":reviewed})
    result=audit(matches)
    (folder/"EARLY_DISCOVERY_PROOF.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    db.close()
    return result
if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--queue",required=True);p.add_argument("--folder",required=True)
    a=p.parse_args();r=track(a.queue,a.folder);print(json.dumps({"projects":r["total"],"measurable":r["measurable"]}))
