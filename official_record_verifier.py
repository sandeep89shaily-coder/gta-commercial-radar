"""Evidence from the EXACT published municipal record, never address-only web hits.

Read-only original Radar SQLite plus optional bounded, exact-key public ArcGIS
query. An unavailable ArcGIS service never silently becomes "confirmed live".
No private person is identified as a sales contact from permit applications.
"""
from __future__ import annotations
import datetime as dt
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parent
PERMIT_ID=re.compile(r"^[\w ./\-]{4,75}$",re.UNICODE)
SOURCES=json.loads((ROOT/"config"/"sources.json").read_text(encoding="utf-8"))
BY_ID={s["id"]:s for s in SOURCES}
FIELDS=("official_verification_level","official_permit_id","official_status",
        "official_status_basis","official_source_date","official_company",
        "official_company_role","official_record_url","official_checked_at",
        "official_verification_note")
MAP={"brampton_building_permits":("PERMITNUMBER","BUILDER","builder"),
     "mississauga_issued_building_permits":("BP_NO",None,None),
     "mississauga_site_plan_applications":("APP_FILE_NO","APPLICANT","applicant"),
     "mississauga_rezoning_applications":("APP_FILE_NO","APPLICANT","applicant"),
     "york_region_active_development_applications":("APPL_GISID","APPL_NAME","application_name")}
SKIP_COMPANY={"unknown","none","n/a","not available","na"}


def clean(value):
    return str(value if value is not None else "").strip()


def exact_id(row,source):
    """A grouped Toronto trade key is not an ArcGIS building-permit key."""
    keys=[k.strip() for k in clean(row.get("source_keys")).split(" | ") if k.strip()]
    if len(keys)!=1 or not PERMIT_ID.fullmatch(keys[0]):
        return ""
    return keys[0]


def source_record(data, source_id, permit_id):
    p=Path(data)/"radar.sqlite"
    if not p.is_file() or not source_id or not permit_id:
        return None
    try:
        with closing(sqlite3.connect(p.resolve().as_uri()+"?mode=ro",uri=True)) as db:
            found=db.execute(
                "SELECT source_date,normalized_json FROM records_current "
                "WHERE source_id=? AND record_key=? AND active=1",
                (source_id,permit_id)).fetchone()
    except (sqlite3.Error,ValueError):
        return None
    if not found:return None
    try:data=json.loads(found[1] or "{}")
    except (TypeError,ValueError):return None
    if not isinstance(data,dict):return None
    data["_db_source_date"]=found[0] or ""
    return data


def published_query(s, ident):
    """Allowlisted URL and key field, safely encoded SQL literal."""
    sid=s.get("id")
    if sid not in MAP or s.get("collector")!="arcgis":
        return ""
    query=clean(s.get("query_url"))
    if not query.startswith("https://") or not PERMIT_ID.fullmatch(ident):
        return ""
    key=MAP[sid][0]
    where=key+" = '"+ident.replace("'","''")+"'"
    return query+"?"+urlencode({"where":where,"outFields":"*","returnGeometry":"false","f":"json"})


def http_json(url):
    req=Request(url,headers={"User-Agent":"GTACommercialRadar/verification (public-record read-only)"})
    with urlopen(req,timeout=12) as response:
        return json.load(response)


def _source_company(record, role):
    name=clean(record.get("entity_name"))
    if name.lower() in SKIP_COMPANY or not name:return "",""
    return name,role or "published_source_entity"


def verify(row,data_dir,transport=None,live=True):
    """Return source veracity and business-role distinctions.

    Local collector row proves only a source observation. Exact public ArcGIS
    response plus equal ID proves a current published record, NOT new issuance.
    """
    sid=clean(row.get("source_id"))
    s=BY_ID.get(sid,{})
    result={k:"" for k in FIELDS}
    result.update(official_verification_level="NOT_VERIFIED",
                  official_verification_note="Exact source record unavailable")
    if not s:return result
    ident=exact_id(row,s)
    if not ident:return result
    result["official_permit_id"]=ident
    old=source_record(data_dir,sid,ident)
    if old:
        result.update(official_verification_level="COLLECTOR_SOURCE_MATCH",
                      official_status=clean(old.get("status")),
                      official_status_basis="local collector snapshot; may be stale",
                      official_source_date=clean(old.get("_db_source_date") or old.get("source_date")),
                      official_record_url=clean(s.get("official_page")),
                      official_verification_note="Exact source_id + source record_key in local database")
        role=MAP.get(sid,("",None,"source_entity"))[2]
        company,company_role=_source_company(old,role)
        result["official_company"]=company
        result["official_company_role"]=company_role
    url=published_query(s,ident)
    if not live or not url:return result
    try:
        packet=(transport or http_json)(url)
        features=packet.get("features",[])
        if packet.get("error") or not isinstance(features,list):
            raise ValueError("Official GIS service returned an error")
        key=MAP[sid][0]
        matched=[f.get("attributes") for f in features
                 if isinstance(f,dict) and isinstance(f.get("attributes"),dict)
                 and clean(f["attributes"].get(key)).casefold()==ident.casefold()]
        if len(matched)!=1:
            result["official_verification_note"]="Live source returned no unique exact-key match"
            return result
        a=matched[0]
        status=next((clean(a.get(f)) for f in s.get("status_fields",[]) if clean(a.get(f))),"")
        company_field=MAP[sid][1]
        company=clean(a.get(company_field)) if company_field else ""
        desc=" ".join(clean(a.get(f)) for f in s.get("description_fields",[]) if clean(a.get(f)))
        current_address=next((clean(a.get(f)) for f in s.get("address_fields",[]) if clean(a.get(f))),"")
        # Reject apparent ID reuse/foreign project, but don't claim an address
        # match from city names or ambiguous business websites.
        try:
            from commercial_research_policy import _civic_address
            local_addr=_civic_address(row);live_addr=_civic_address({"address":current_address})
        except (ValueError,TypeError):
            local_addr=live_addr=""
        if local_addr and live_addr and local_addr!=live_addr:
            result["official_verification_note"]="Exact ID exists but civic addresses disagree"
            return result
        record_date=next((clean(a.get(f)) for f in s.get("date_fields",[]) if clean(a.get(f))),"")
        result.update(official_verification_level="OFFICIAL_ID_AND_STATUS_MATCH",
                      official_status=status,
                      official_status_basis="official live public GIS record",
                      official_source_date=record_date or result["official_source_date"],
                      official_company=(company if company.lower() not in SKIP_COMPANY else "") or result["official_company"],
                      official_company_role=(MAP[sid][2] if company and company.lower() not in SKIP_COMPANY else result["official_company_role"]),
                      official_record_url=url,
                      official_checked_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                      official_verification_note="Exact application/permit ID matched; not proof of buying intent")
        # A selected candidate may have a fragment of its own description;
        # use official longer text as AI input, but never erase the source.
        if desc and len(desc)>len(clean(row.get("description"))):
            result["official_description"]=desc[:2000]
    except (OSError,TimeoutError,ValueError,KeyError,TypeError) as exc:
        result["official_verification_note"]="Live verification unavailable: "+type(exc).__name__
    return result
