"""Offline comparison of independent public signals — exact-address REVIEW matches.

No auto-merge, no new geographic inference from vague names, no claim that
receipt date = first posted date. Does not change any source database or V8.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import re
import sqlite3
from collections import defaultdict
from itertools import combinations
from pathlib import Path

DBS = ("early_signals_review.sqlite","early_cues_review.sqlite",
       "early_public_notices_review.sqlite","early_discovery_review.sqlite",
       "early_investment_procurement_review.sqlite","early_aic_email_review.sqlite",
       "early_ajax_review.sqlite","early_oakville_review.sqlite",
       "early_hamilton_review.sqlite")
CITIES=("BRAMPTON","MISSISSAUGA","TORONTO","BURLINGTON","MILTON","PICKERING",
        "VAUGHAN","MARKHAM","RICHMOND HILL","OAKVILLE","AJAX","OSHAWA",
        "WHITBY","HAMILTON")
STREETS={"STREET":"ST","ROAD":"RD","AVENUE":"AVE","DRIVE":"DR",
         "BOULEVARD":"BLVD","COURT":"CT","CRESCENT":"CRES",
         "PARKWAY":"PKWY","LANE":"LN","NORTH":"N","SOUTH":"S",
         "EAST":"E","WEST":"W"}
SUFFIXES={"ST","RD","AVE","DR","BLVD","CT","CRES","PKWY","LN",
          "WAY","CIR","CIRCLE","PL","PLACE","TRAIL","TER","TERRACE"}
DATE_BASIS_POSTED={"PICKERING_OFFICIAL_DATE_POSTED","MILTON_NEWS_LIST_DATE","ERO_PROPOSAL_POSTED",
                   "OFFICIAL_NOTICE_PUBLISHED_DATE"}
META=("source_id","item_id","city","site","address_key","title","company",
      "company_role","stage","source_application_date","source_public_posted",
      "radar_first_seen","record_url","commercial_signal","status",
      "procurement_status")
MATCH=("city","normalized_site","first_source","first_record_id",
       "first_official_link","other_source","other_record_id","other_official_link",
       "match_status","first_seen_earliest","first_seen_other",
       "first_posted_earliest","first_posted_other","earlier_public_date_advantage_days",
       "earliness_caveat","buyer_proven","procurement_proven")
GATE=("source_id","item_id","city","site","title","record_url",
      "commercial_signal","published_entity","entity_role","application_date",
      "official_public_posting_date","radar_first_seen","matched_sources",
      "preprocurement_evidence","verified_owner_or_operator","public_business_contact",
      "work_package_verified","vendor_status","lead_status","next_manual_verification")


def norm_city(raw):
    city=re.sub(r"\s+"," ",str(raw or "").strip()).upper()
    if city in CITIES:return city
    # York Region is not itself a verified city; don't merge or infer.
    if city.startswith("YORK REGION"):return ""
    for candidate in CITIES:
        if city==candidate+", ON" or city==candidate+", ONTARIO":
            return candidate
    return ""


def norm_address(value):
    """Conservative numbered street matching, never fuzzy across buildings."""
    raw=re.sub(r"\s+"," ",re.sub(r"[,.#]"," ",str(value or "").upper())).strip()
    match=re.search(r"(?<![A-Z0-9])([1-9]\d{0,5}[A-Z]?)\s+"
                    r"((?:[A-Z0-9'-]+\s+){1,6}?"
                    r"(?:STREET|ST|ROAD|RD|AVENUE|AVE|DRIVE|DR|"
                    r"BOULEVARD|BLVD|COURT|CT|CRESCENT|CRES|PARKWAY|PKWY|"
                    r"LANE|LN|WAY|CIRCLE|CIR|PLACE|PL|TRAIL|TERRACE|TER))\b"
                    r"((?:\s+(?:NORTH|SOUTH|EAST|WEST|N|S|E|W))?)",raw)
    if not match:return ""
    street=match.group(1)+" "+match.group(2)+match.group(3)
    tokens=[STREETS.get(token,token) for token in street.strip().split()]
    # Reject range/list-only to avoid one site's number linking another site's.
    prefix=raw[:match.start()].strip()
    if prefix and re.search(r"\d",prefix):return ""
    return " ".join(tokens)


def iso(value):
    raw=str(value or "").strip()
    if not re.fullmatch(r"20\d{2}-[01]\d-[0-3]\d",raw):return ""
    try:
        return dt.date.fromisoformat(raw).isoformat()
    except ValueError:return ""


def unpack(item,source,seen):
    sid=str(item.get("source_id") or source)
    city=norm_city(item.get("city") or item.get("municipality"))
    # Tagged municipality from the three official borough-specific source lists.
    if not city:
        if sid.startswith("burlington_"):city="BURLINGTON"
        if sid.startswith("milton_"):city="MILTON"
        if sid.startswith("pickering_"):city="PICKERING"
        if sid.startswith("ajax_"):city="AJAX"
        if sid.startswith("oakville_"):city="OAKVILLE"
        if sid.startswith("hamilton_"):city="HAMILTON"
        if sid.startswith("brampton_"):city="BRAMPTON"
        if sid.startswith("mississauga_"):city="MISSISSAUGA"
        if sid.startswith("toronto_"):city="TORONTO"
    location=str(item.get("location") or item.get("site") or "")
    city=city if city in CITIES else ""
    address=norm_address(location)
    app=iso(item.get("source_application_date"))
    posted=iso(item.get("source_date")) if item.get("date_basis") in DATE_BASIS_POSTED else ""
    name=str(item.get("title") or item.get("description") or "").strip()[:210]
    return dict(source_id=sid,item_id=str(item.get("record_id") or
           item.get("record_key") or item.get("application_id") or item.get("feature_id") or ""),
           city=city,site=location,address_key=address,title=name,
           company=str(item.get("published_company_unverified_role") or
                item.get("company") or ""),company_role=str(item.get("company_role") or
                "UNVERIFIED_PUBLISHED_ENTITY"),stage=str(item.get("stage") or ""),
           source_application_date=app,source_public_posted=posted,radar_first_seen=seen,
           record_url=str(item.get("exact_source_record_url") or item.get("source_url") or ""),
           commercial_signal=str(item.get("commercial_signal") or item.get("commercial_fit") or "USE_UNKNOWN"),
           status=str(item.get("status") or ""),procurement_status="UNKNOWN")


def load_all(root):
    root=Path(root)
    records=[]
    coverage=[]
    for filename in DBS:
        file=root/filename
        if not file.exists():
            coverage.append((filename,"MISSING"))
            continue
        try:
            db=sqlite3.connect("file:"+str(file.absolute())+"?mode=ro",uri=True)
            if filename=="early_signals_review.sqlite":
                rows=db.execute("SELECT source_id,first_seen,content FROM observations")
            else:
                rows=db.execute("SELECT source_id,first_seen_at,content FROM snapshots")
            number=0
            for sid,first,content in rows:
                try:item=json.loads(content)
                except (TypeError,ValueError):continue
                if not isinstance(item,dict):continue
                records.append(unpack(item,sid,first))
                number+=1
            coverage.append((filename,str(number)))
        except sqlite3.DatabaseError as exc:
            coverage.append((filename,"ERROR:"+type(exc).__name__))
        finally:
            try:db.close()
            except Exception:pass
    return records,coverage


def join_signals(records):
    by_site=defaultdict(list)
    for r in records:
        if r["city"] and r["address_key"]:
            by_site[(r["city"],r["address_key"])].append(r)
    pairs=[]
    seen=set()
    for (city,address),items in by_site.items():
        # Multi-tenant/large complex addresses can cross-match unrelated
        # investments. A large bucket is set aside rather than exploding N^2.
        unique={}
        for r in items:
            unique[(r["source_id"],r["item_id"])]=r
        items=list(unique.values())
        if len(items)>25:continue
        for a,b in combinations(items,2):
            if a["source_id"]==b["source_id"]:continue
            key=tuple(sorted((a["source_id"]+"|"+a["item_id"],
                              b["source_id"]+"|"+b["item_id"])))
            if key in seen:continue
            seen.add(key)
            ordered=sorted((a,b),key=lambda r:r["radar_first_seen"] or "9999")
            early,late=ordered[0],ordered[1]
            pa,pb=early["source_public_posted"],late["source_public_posted"]
            days=""
            if pa and pb:
                days=(dt.date.fromisoformat(pb)-dt.date.fromisoformat(pa)).days
            pairs.append(dict(city=city,normalized_site=address,
                 first_source=early["source_id"],first_record_id=early["item_id"],
                 first_official_link=early["record_url"],
                 other_source=late["source_id"],other_record_id=late["item_id"],
                 other_official_link=late["record_url"],
                 match_status="POSSIBLE_SAME_ADDRESS_NOT_VERIFIED_SAME_PROJECT",
                 first_seen_earliest=early["radar_first_seen"],
                 first_seen_other=late["radar_first_seen"],
                 first_posted_earliest=pa,first_posted_other=pb,
                 earlier_public_date_advantage_days=days,
                 earliness_caveat=("POSTED_DATE_COMPARISON_NOT_PERMIT_ADVANTAGE"
                         if days!="" else "PUBLIC_POSTING_DATES_NOT_BOTH_AVAILABLE"),
                 buyer_proven="NO",procurement_proven="NO"))
    return sorted(pairs,key=lambda x:(x["city"],x["normalized_site"]))


def gates(records,links):
    sites=defaultdict(set)
    for x in links:
        k=(x["city"],x["normalized_site"])
        sites[k].update((x["first_source"],x["other_source"]))
    result=[]
    dedup=set()
    for row in records:
        if row["commercial_signal"] not in ("POSSIBLE_COMMERCIAL","MIXED_USE_REVIEW","REVIEW"):
            continue
        key=(row["source_id"],row["item_id"])
        if key in dedup:continue
        dedup.add(key)
        potential=sites.get((row["city"],row["address_key"]),set())
        result.append(dict(
          source_id=row["source_id"],item_id=row["item_id"],city=row["city"],
          site=row["site"],title=row["title"],record_url=row["record_url"],
          commercial_signal=row["commercial_signal"],published_entity=row["company"],
          entity_role=row["company_role"],application_date=row["source_application_date"],
          official_public_posting_date=row["source_public_posted"],
          radar_first_seen=row["radar_first_seen"],matched_sources=";".join(sorted(potential)),
          preprocurement_evidence="UNKNOWN",verified_owner_or_operator="NO",
          public_business_contact="UNVERIFIED",work_package_verified="NO",
          vendor_status="UNKNOWN",lead_status="NOT_SALE_READY_RESEARCH_ONLY",
          next_manual_verification="Open official application; verify actual site and "
           "owner/operator; identify work-package buyer; check public procurement "
           "status and document timestamp. Matching address is NOT project proof."))
    return sorted(result,key=lambda x:(x["official_public_posting_date"] or "",
                                      x["radar_first_seen"]),reverse=True)


def write(path,fields,items):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+".tmp")
    with temp.open("w",newline="",encoding="utf-8-sig") as stream:
        w=csv.DictWriter(stream,fieldnames=fields,extrasaction="ignore")
        w.writeheader();w.writerows(items)
    temp.replace(path)


def run(data_dir="data",output_dir="GTA_RADAR_RESULTS"):
    records,coverage=load_all(data_dir)
    links=join_signals(records)
    queue=gates(records,links)
    folder=Path(output_dir)
    write(folder/"EARLY_SOURCE_CROSS_MATCH_REVIEW.csv",MATCH,links)
    write(folder/"EARLY_EVIDENCE_ACTIONABILITY_GATES.csv",GATE,queue)
    write(folder/"EARLY_SOURCE_COVERAGE_AUDIT.csv",("database","loaded_rows"),
          [dict(database=a,loaded_rows=b) for a,b in coverage])
    print("Read-only source evidence",len(records),"| exact-address possible links",
          len(links),"| actionability review candidates",len(queue))
    print("Verified sale-ready leads: ZERO (no buyer/procurement verification here)")
    return 1 if any(x.startswith("ERROR") for a,x in coverage) else 0


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir",default="data")
    p.add_argument("--output-dir",default="GTA_RADAR_RESULTS")
    a=p.parse_args();raise SystemExit(run(a.data_dir,a.output_dir))
