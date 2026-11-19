"""Western Ontario source-rights intake and Windsor source audit.

The corridor is London, Sarnia, Chatham-Kent and existing city Windsor.

Do not treat an official planning webpage as an automatically licensed export.
Sarnia's website explicitly disallows robots/data mining and commercial reuse;
Chatham-Kent's ordinary site restricts reuse to non-commercial purposes.
London's specific planning MapServer licence is not demonstrated to be covered
by the City's distinct open-data licence. Consequently this daily stage does
NOT scrape any of those three unapproved sites.

Accept an independently licensed/authorized official export only when the
operator has provided both:
    authorized_western_sources/<city_slug>.csv
    authorized_western_sources/<city_slug>.source.json
The manifest must document actual publisher licence/permission evidence and
approved source URL; it cannot authorize scraping websites by itself.
Prior user/browser activity is never impersonated. No new AI/API expense.

If source rights are not established, produce a source-status report rather
than fabricated "live coverage". Windsor stays in the existing four-city feed.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

NEW=("London","Sarnia","Chatham-Kent")
SLUG={"London":"london","Sarnia":"sarnia","Chatham-Kent":"chatham_kent"}
WIND="Windsor"
IMPORT_DIR="authorized_western_sources"
OUTPUT="GTA_RADAR_WESTERN_3_AUTHORIZED_APPLICATIONS.csv"
STATUS="GTA_RADAR_WESTERN_CORRIDOR_SOURCE_STATUS.json"
ROWS=("city","application_id","address","scope","stage","category",
      "applicant","source_date","source_date_basis","source_url",
      "licence_evidence_url","source_file_sha256","rights_scope",
      "first_publication_verified","buyer_verified",
      "open_supplier_package_verified")
MAX_BYTES=10_000_000
MAX_ROWS=1500
ID_RX=re.compile(r"(?=.{3,120}$)[A-Z0-9][A-Z0-9 /._-]*[A-Z0-9]",re.I)
RIGHTS=("PUBLISHED_OPEN_DATA_LICENSED_FOR_COMMERCIAL_REUSE",
        "WRITTEN_PUBLISHER_AUTHORIZATION")

def clean(v,n=1200):
    return " ".join(str(v or "").split())[:n]

def approved_url(url,city):
    if not url or len(url)>1600:return False
    try:p=urlsplit(url)
    except ValueError:return False
    hosts={"London":{"london.ca","www.london.ca","opendata.london.ca",
                    "maps.london.ca"},
           "Sarnia":{"sarnia.ca","www.sarnia.ca",
                     "city-of-sarnia.hub.arcgis.com"},
           "Chatham-Kent":{"chatham-kent.ca","www.chatham-kent.ca",
                           "opendata-chatham-kent.opendata.arcgis.com"}}
    return p.scheme=="https" and p.hostname in hosts[city] and not p.username and not p.password

def source_restriction(city):
    restrictions={
        "London":"Specific planning MapServer not proven included under City's Open Data licence; City's general site terms separately restrict robots/commercial use",
        "Sarnia":"City website Terms of Service prohibit data mining/robots and commercial reuse; active portal currently only one city-wide item",
        "Chatham-Kent":"Municipal website Terms of Use restrict copied content to personal/non-commercial use; no independently licensed planning application dataset confirmed",
    }
    return restrictions[city]

def source_state(city):
    return {"city":city,"status":"SOURCE_RIGHTS_NOT_VERIFIED_NO_AUTOMATED_FETCH",
            "authorized_application_ids":0,"live_automatic_source":False,
            "commercial_rights_verified":False,
            "site_policy_problem":source_restriction(city),
            "original_publication_verified":False}

def validate_manifest(city,manifest):
    if not isinstance(manifest,dict) or manifest.get("city")!=city:
        raise ValueError("SOURCE_MANIFEST_CITY_MISMATCH")
    rights=manifest.get("rights_scope","")
    source=manifest.get("official_source_url","")
    licence=manifest.get("licence_evidence_url","")
    if rights not in RIGHTS:
        raise PermissionError("PUBLISHER_RIGHTS_UNVERIFIED")
    if not approved_url(source,city):
        raise ValueError("UNAPPROVED_PUBLISHER_SOURCE")
    if not (licence.startswith("https://") and
            urlsplit(licence).hostname is not None and
            not urlsplit(licence).username):
        raise PermissionError("LICENCE_EVIDENCE_REQUIRED")
    if (rights=="WRITTEN_PUBLISHER_AUTHORIZATION" and
            not clean(manifest.get("written_authorization_reference"))):
        raise PermissionError("PUBLISHER_AUTHORIZATION_REFERENCE_REQUIRED")
    return source,licence,rights

def read_source(city,folder):
    slug=SLUG[city]
    rawpath=folder/(slug+".csv")
    manifestpath=folder/(slug+".source.json")
    if not rawpath.exists() and not manifestpath.exists():
        return [],source_state(city)
    if (not rawpath.is_file() or rawpath.is_symlink() or
        not manifestpath.is_file() or manifestpath.is_symlink() or
        rawpath.stat().st_size>MAX_BYTES or
        manifestpath.stat().st_size>32_000):
        raise ValueError("INCOMPLETE_UNSAFE_AUTHORIZED_SOURCE_PAIR")
    manifest=json.loads(manifestpath.read_text(encoding="utf-8"))
    source,licence,rights=validate_manifest(city,manifest)
    data=rawpath.read_bytes()
    digest=hashlib.sha256(data).hexdigest()
    output=[];seen=set()
    with rawpath.open(encoding="utf-8-sig",newline="") as fp:
        reader=csv.DictReader(fp)
        if not reader.fieldnames or any(k not in reader.fieldnames for k in
            ("application_id","address","scope","source_url")):
            raise ValueError("MISSING_OFFICIAL_APPLICATION_COLUMNS")
        for i,row in enumerate(reader):
            if i>=MAX_ROWS:raise ValueError("TOO_MANY_SOURCE_ROWS")
            ident=clean(row.get("application_id"),120)
            if not ID_RX.fullmatch(ident):continue
            address=clean(row.get("address"),230)
            scope=clean(row.get("scope"),1400)
            row_source=clean(row.get("source_url"),1600)
            if (not address or not scope or not approved_url(row_source,city)):
                continue
            key="".join(ch for ch in ident.upper() if ch.isalnum())
            if key in seen:continue
            seen.add(key)
            output.append({"city":city,"application_id":ident,
                "address":address,"scope":scope,
                "stage":clean(row.get("stage"),160),
                "category":clean(row.get("category"),150),
                "applicant":clean(row.get("applicant"),220),
                "source_date":clean(row.get("source_date"),30),
                "source_date_basis":"SOURCE_REPORTED_DATE_NOT_FIRST_DISCLOSURE",
                "source_url":row_source,"licence_evidence_url":licence,
                "source_file_sha256":digest,
                "rights_scope":rights,
                "first_publication_verified":"False",
                "buyer_verified":"False",
                "open_supplier_package_verified":"False"})
    return output,{"city":city,"status":(
        "AUTHORIZED_IMPORTED_EXACT_APPLICATION_IDS_RESEARCH_ONLY" if output
        else "AUTHORIZED_EXPORT_ZERO_VALID_EXACT_APPLICATION_IDS"),
        "authorized_application_ids":len(output),"live_automatic_source":False,
        "commercial_rights_verified":False,
        "operator_attested_rights_manifest_present":True,
        "independent_publisher_licence_review_still_required":True,
        "source_file_sha256":digest,
        "official_source_url":source,
        "rights_scope":rights,
        "source_limitations":"Manually provided publisher-approved official export; source file is not a fresh daily web fetch"}

def windsor_audit(root):
    path=root/"GTA_RADAR_FOUR_CITY_SOURCE_STATUS.json"
    csvpath=root/"GTA_RADAR_FOUR_CITY_LIVE_APPLICATIONS.csv"
    result={"city":"Windsor","status":"EXISTING_28_CITY_SOURCE_NOT_VERIFIED",
            "live_current_application_ids":0,
            "duplicate_city_configuration_prevented":True}
    try:
        src=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError,UnicodeError):
        return result
    health=next((x for x in src.get("city_status",[])
                 if isinstance(x,dict) and x.get("city")=="Windsor"),None)
    if not health:
        result["status"]="WINDSOR_CURRENT_HEALTH_MISSING"
        return result
    result["existing_source_status"]=health.get("status","")
    if (health.get("status")!="LIVE_APPLICATION_IDS_RETRIEVED_PARTIAL_COVERAGE"
            or not csvpath.is_file() or csvpath.is_symlink()):
        result["status"]="WINDSOR_EXISTING_SOURCE_NOT_LIVE_CURRENT_RUN"
        return result
    seen=set()
    with csvpath.open(encoding="utf-8-sig",newline="") as f:
        for row in csv.DictReader(f):
            if row.get("city")!="Windsor":continue
            ident=clean(row.get("application_id"),120)
            if ident and clean(row.get("address")):
                seen.add("".join(c for c in ident.upper() if c.isalnum()))
    result["live_current_application_ids"]=len(seen)
    result["status"]="WINDSOR_EXISTING_FEED_LIVE_PARTIAL" if seen else (
        "WINDSOR_SOURCE_HEALTH_DISAGREES_WITH_ROWS")
    return result

def run(results):
    root=Path(results)
    if not root.is_dir():raise ValueError("RESULTS_DIRECTORY_REQUIRED")
    folder=root/IMPORT_DIR
    allrows=[];status={}
    for city in NEW:
        try:
            rows,state=read_source(city,folder)
            allrows.extend(rows)
            status[city]=state
        except (OSError,ValueError,PermissionError,UnicodeError) as err:
            status[city]={**source_state(city),
                "status":"UNAUTHORIZED_OR_INVALID_SOURCE_EXPORT",
                "error":type(err).__name__+":"+str(err)[:150]}
    status[WIND]=windsor_audit(root)
    with (root/OUTPUT).open("w",encoding="utf-8-sig",newline="") as fp:
        writer=csv.DictWriter(fp,fieldnames=ROWS)
        writer.writeheader()
        for row in allrows:
            writer.writerow({col:("'"+str(row.get(col) or "") if
                str(row.get(col) or "").lstrip().startswith(("=","+","-","@","\t","\r"))
                else str(row.get(col) or "")) for col in ROWS})
    outcome={"status":"WESTERN_CORRIDOR_SOURCE_RIGHTS_AND_APPLICATION_AUDIT",
        "target_cities":["London","Sarnia","Chatham-Kent","Windsor"],
        "existing_city":"Windsor","additional_city_configurations":3,
        "source_states":status,"authorized_imported_application_ids":len(allrows),
        "new_cities_with_automatically_verified_live_ids":0,
        "fully_covered_cities_verified":0,
        "buyer_verified":0,"original_publications_verified":0,
        "paid_ai_calls":0,"output_files":[OUTPUT,STATUS]}
    (root/STATUS).write_text(json.dumps(outcome,indent=2),encoding="utf-8")
    return outcome

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--results",required=True)
    print(json.dumps(run(p.parse_args().results),indent=2))
