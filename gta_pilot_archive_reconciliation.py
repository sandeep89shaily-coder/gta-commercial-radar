"""Compare two owner-provided Radar results archives without mutating original data.

An archive-to-archive hash match proves only that saved Radar output did not
change. It NEVER verifies an original municipal publication, actual opening,
site owner, buyer, open supplier opportunity or new public posting date.
Supports ZIPs created by the existing manual Windows collection runner.
"""
from __future__ import annotations
import argparse
import csv
import io
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

from gta_pilot_acceptance_pack import _activation_sample, _facility_queue, _write_csv

ROOT = "GTA_RADAR_RESULTS/"
ACTIVATION = "COMMERCIAL_ACTIVATION_PILOT/GTA_RADAR_COMMERCIAL_ACTIVATION_REVIEW.csv"
INDUSTRIAL = "INDUSTRIAL_PILOT/GTA_RADAR_INDUSTRIAL_EQUIPMENT_REVIEW.csv"
BURLINGTON = "GTA_RADAR_FIVE_CITY_RECOVERY_STATUS.json"
LEDGER = "GTA_RADAR_FIVE_CITY_OFFICIAL_SEEN.json"
SUMMARY = "GTA_RADAR_TWO_ARCHIVE_EVIDENCE_STATUS.json"
SAMPLE = "ACTIVATION_20_ARCHIVE_CROSSCHECK.csv"
SITES = "ACTIVATION_10_FACILITY_ARCHIVE_CROSSCHECK.csv"
INDUSTRIAL_OUT = "INDUSTRIAL_NOTICE_ARCHIVE_CROSSCHECK.csv"
MAX_SOURCE_BYTES = 12_000_000

def _read_bytes(path, filename):
    """No extraction. Only exact named expected outputs, never arbitrary ZIP files."""
    path = Path(path)
    name = ROOT + filename
    if path.is_dir():
        source = path / name
        if not source.is_file():
            source = path / filename
        return source.read_bytes() if source.is_file() and source.stat().st_size <= MAX_SOURCE_BYTES else b""
    with zipfile.ZipFile(path) as archive:
        try:
            info = archive.getinfo(name)
        except KeyError:
            try:info = archive.getinfo(filename)
            except KeyError:return b""
        if info.file_size > MAX_SOURCE_BYTES:
            raise ValueError("SOURCE_SNAPSHOT_TOO_LARGE:" + filename)
        return archive.read(info)

def _rows(path, filename):
    raw = _read_bytes(path, filename)
    if not raw:
        return []
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))

def _status(path, filename):
    raw = _read_bytes(path, filename)
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value,dict) else {}
    except (ValueError,UnicodeError):
        return {}

def _index(rows, fields):
    index={}
    duplicates=set()
    for row in rows:
        key=tuple(row.get(f,"") for f in fields)
        if not all(key) or key in index:
            duplicates.add(key)
        else:
            index[key]=row
    for key in duplicates:
        index.pop(key,None)
    return index, duplicates

def _state(row, previous):
    if previous is None:
        return "FIRST_PRESENT_IN_LATER_ARCHIVE_NOT_NEW_PUBLICATION"
    if row.get("source_record_sha256")!=previous.get("source_record_sha256"):
        return "SOURCE_HASH_CHANGED_IN_SAVED_OUTPUT_RECHECK_REQUIRED"
    if any(row.get(k)!=previous.get(k) for k in (
        "activation_stage","municipality","site_address","site_unit","source_event_date")):
        return "CLASSIFICATION_OR_SITE_CHANGED_RECHECK_REQUIRED"
    return "SAVED_RECORD_STABLE_NOT_INDEPENDENTLY_SOURCE_VERIFIED"

def compare(prior,current,out,*,sample_limit=20,site_limit=10):
    prior,current=Path(prior),Path(current)
    if prior.resolve()==current.resolve():
        raise ValueError("TWO_INDEPENDENT_ARCHIVES_REQUIRED")
    root=Path(out);root.mkdir(parents=True,exist_ok=True)
    earlier=_rows(prior,ACTIVATION)
    later=_rows(current,ACTIVATION)
    p,dup1=_index(earlier,("source_id","source_record_key"))
    n,dup2=_index(later,("source_id","source_record_key"))
    shared=set(p)&set(n)
    states=Counter(_state(n[k],p.get(k)) for k in n)
    stable=sum(_state(n[k],p[k])=="SAVED_RECORD_STABLE_NOT_INDEPENDENTLY_SOURCE_VERIFIED"
               for k in shared)
    diff=len(shared)-stable
    selected=_activation_sample(list(n.values()),sample_limit)
    rows=[]
    for item in selected:
        key=(item["source_id"],item["source_record_key"])
        old=p.get(key)
        rows.append({
            **{k:item.get(k,"") for k in ("source_id","source_record_key",
                "municipality","site_address","site_unit","source_event_date",
                "activation_stage","source_dataset_url","source_record_sha256")},
            "prior_source_sha256":old.get("source_record_sha256","") if old else "",
            "prior_activation_stage":old.get("activation_stage","") if old else "",
            "archive_comparison":_state(item,old),
            "publisher_original_rechecked":"NO",
            "actual_business_opening_verified":"NO",
            "buyer_verified":"NO",
        })
    fields=("source_id","source_record_key","municipality","site_address","site_unit",
            "source_event_date","activation_stage","source_dataset_url",
            "source_record_sha256","prior_source_sha256","prior_activation_stage",
            "archive_comparison","publisher_original_rechecked",
            "actual_business_opening_verified","buyer_verified")
    _write_csv(root/SAMPLE,fields,rows)
    facilities=_facility_queue(list(n.values()),site_limit)
    for site in facilities:
        city=site["municipality"].casefold()
        addr=re.sub(r"[^a-z0-9]+"," ",site["site_address"].casefold()).strip()
        unit=re.sub(r"[^a-z0-9]+","",site["site_unit"].casefold())
        existing=[x for x in p.values()
                  if x.get("municipality","").casefold()==city
                  and re.sub(r"[^a-z0-9]+"," ",x.get("site_address","").casefold()).strip()==addr
                  and re.sub(r"[^a-z0-9]+","",x.get("site_unit","").casefold())==unit]
        site.update(prior_archive_same_site_rows=len(existing),
                    original_facility_identity_verified="NO",
                    buyer_verified="NO")
    _write_csv(root/SITES,tuple(facilities[0]) if facilities else (
        "municipality","site_address","site_unit","source_records_count",
        "prior_archive_same_site_rows","original_facility_identity_verified","buyer_verified"),
        facilities)
    def industrial(path):
        records=_rows(path,INDUSTRIAL)
        index,duplicates=_index(records,("signal_id",))
        return index,duplicates
    old_ind,old_dup=industrial(prior)
    new_ind,new_dup=industrial(current)
    industrial_rows=[]
    for key,item in sorted(new_ind.items(),key=lambda p:p[1].get("ero_number",""),reverse=True):
        earlier_signal=old_ind.get(key)
        industrial_rows.append({
            "ero_number":item.get("ero_number",""),
            "official_notice_url":item.get("official_notice_url",""),
            "equipment":item.get("equipment",""),"action":item.get("action",""),
            "notice_stage":item.get("notice_stage",""),
            "archived_signal_status":(
                "SOURCE_HASH_AND_STAGE_STABLE_NOT_A_NEW_ORDER"
                if earlier_signal and all(earlier_signal.get(c)==item.get(c)
                   for c in ("source_text_sha256","notice_stage","equipment","action"))
                else "NEW_OR_CHANGED_SAVED_SIGNAL_RECHECK_ORIGINAL"),
            "buyer_verified":"NO","supplier_package_verified":"NO",
        })
    _write_csv(root/INDUSTRIAL_OUT,(
        "ero_number","official_notice_url","equipment","action","notice_stage",
        "archived_signal_status","buyer_verified","supplier_package_verified"),
        industrial_rows)
    old_b=_status(prior,BURLINGTON);new_b=_status(current,BURLINGTON)
    old_by={x.get("city"):x for x in old_b.get("source_status",[]) if isinstance(x,dict)}
    new_by={x.get("city"):x for x in new_b.get("source_status",[]) if isinstance(x,dict)}
    def burlington_valid(item):
        return item.get("status")=="OFFICIAL_PAGE_COLLECTION" and int(
            item.get("application_id_rows_this_stage",0) or 0)>0
    old_ledger=_status(prior,LEDGER).get("seen",{})
    new_ledger=_status(current,LEDGER).get("seen",{})
    status={
        "status":"ARCHIVED_OUTPUTS_CROSSCHECKED_NOT_ORIGINAL_SOURCE_ACCEPTED",
        "source_1":str(prior),"source_2":str(current),
        "old_accepted_activation_rows":len(earlier),
        "new_accepted_activation_rows":len(later),
        "common_exact_source_keys":len(shared),
        "stable_saved_source_hash_and_stage_rows":stable,
        "modified_saved_source_hash_or_stage_rows":diff,
        "added_records_in_later_archive_not_new_publications":len(set(n)-set(p)),
        "missing_records_in_later_archive_not_confirmed_closed":len(set(p)-set(n)),
        "duplicate_or_missing_source_keys_held":len(dup1)+len(dup2),
        "source_change_categories":dict(states),
        "industrial_old_signal_rows":len(old_ind),
        "industrial_new_signal_rows":len(new_ind),
        "industrial_distinct_ero_notice_count":len({
            x.get("ero_number") for x in new_ind.values() if x.get("ero_number")}),
        "industrial_ambiguous_signals_held":len(old_dup)+len(new_dup),
        "burlington_prior_live_collected":burlington_valid(old_by.get("Burlington",{})),
        "burlington_current_live_collected":burlington_valid(new_by.get("Burlington",{})),
        "burlington_stored_ledger_ids_in_both":len(set(old_ledger)&set(new_ledger)),
        "burlington_stored_ledger_ids_changed":len(set(old_ledger)^set(new_ledger)),
        "publisher_original_source_records_rechecked":0,
        "supplier_packages_verified":0,"actual_openings_verified":0,
        "review_queue_20":str(root/SAMPLE),"facility_queue_10":str(root/SITES),
        "industrial_comparison":str(root/INDUSTRIAL_OUT),
        "warning":"Saved file matches do NOT verify municipal records, publication age, buyer, supplier package, opening, or separate fresh Windows runs.",
    }
    (root/SUMMARY).write_text(json.dumps(status,indent=2,sort_keys=True),encoding="utf-8")
    return status

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior",type=Path,required=True)
    parser.add_argument("--current",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(compare(args.prior,args.current,args.output),indent=2))
