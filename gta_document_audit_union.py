"""Safely combine official PDF audit records without conflating discovery and capture."""
import csv
from pathlib import Path

FIELDS=("url","status","reason","http_status","bytes","sha256","saved_path")

def union(paths, target):
    selected={}
    for source in paths:
        if not Path(source).exists():
            continue
        with Path(source).open(encoding="utf-8-sig",newline="") as file:
            for row in csv.DictReader(file):
                url=(row.get("attachment_url") or row.get("url") or "").strip()
                if not url:continue
                item={name:row.get(name,"") for name in FIELDS}
                item["url"]=url
                # A real captured document outranks a failed attempt for the same URL.
                if url not in selected or (item["status"]=="CAPTURED" and selected[url]["status"]!="CAPTURED"):
                    selected[url]=item
    target=Path(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("w",encoding="utf-8-sig",newline="") as file:
        writer=csv.DictWriter(file,fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(selected.values())
    return {"distinct_documents":len(selected),"captured":sum(row["status"]=="CAPTURED" for row in selected.values())}
