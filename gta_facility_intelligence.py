"""Shared GTA Radar facility intelligence: deterministic, audited, review-only.

This is an OFFLINE post-processing layer for the normal daily discovery CSV and
both isolated pilot review CSVs. It never writes the Radar collector database,
does not fetch URLs, does not spend AI tokens, and cannot verify purchasing
authority, tenant identity, occupancy, opening dates or an open contract.

A common civic address identifies a PLACE for research, not a legal entity, a
single project, or a vendor-selection opportunity.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

INPUTS = (
    ("radar", "GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv"),
    ("planning", "GTA_RADAR_COLLECTION_MASTER.csv"),
    ("industrial", "INDUSTRIAL_PILOT/GTA_RADAR_INDUSTRIAL_EQUIPMENT_REVIEW.csv"),
    ("activation", "COMMERCIAL_ACTIVATION_PILOT/GTA_RADAR_COMMERCIAL_ACTIVATION_REVIEW.csv"),
)
OUTPUT_EVENTS = "GTA_RADAR_FACILITY_EVIDENCE_EVENTS.csv"
OUTPUT_FACILITIES = "GTA_RADAR_FACILITY_HISTORY.csv"
OUTPUT_LINKS = "GTA_RADAR_FACILITY_SOURCE_LINKS.csv"
OUTPUT_REVIEW = "GTA_RADAR_FACILITY_COMMERCIAL_REVIEW.csv"
OUTPUT_HTML = "GTA_RADAR_FACILITY_INTELLIGENCE.html"
OUTPUT_STATUS = "GTA_RADAR_FACILITY_INTELLIGENCE_STATUS.json"

EVENT_FIELDS = (
    "event_id", "source_family", "source_id", "source_record_id",
    "source_url", "url_evidence_level", "record_hash", "source_date",
    "radar_first_seen_at", "city", "site_address", "site_unit", "site_id",
    "site_identity_status", "organization", "organization_role", "project_id",
    "signal_type", "stage_label", "source_status", "description",
    "scope_specificity", "supplier_segments_possible", "procurement_status",
    "buyer_verified", "opening_confirmed", "review_tier",
    "verification_required",
)
FACILITY_FIELDS = (
    "site_id", "city", "site_address", "source_families",
    "evidence_events", "distinct_source_records", "first_observed_at",
    "latest_source_date", "organization_mentions_unverified", "signal_types",
    "cross_source_civic_matches", "unit_conflicts",
    "status", "verification_required",
)
LINK_FIELDS = (
    "site_id", "left_event_id", "right_event_id", "left_source_family",
    "right_source_family", "left_record_id", "right_record_id",
    "relationship", "relationship_verified", "notes",
)
REVIEW_FIELDS = (
    "event_id", "site_id", "city", "site_address", "organization",
    "organization_role", "signal_type", "stage_label", "scope_specificity",
    "supplier_segments_possible", "source_date", "radar_first_seen_at",
    "source_url", "review_tier", "procurement_status", "buyer_verified",
    "opening_confirmed", "verification_required",
)
SOURCE_CITY = {
    "toronto_active_building_permits": "Toronto",
    "toronto_business_licences": "Toronto",
    "brampton_building_permits": "Brampton",
    "mississauga_issued_building_permits": "Mississauga",
}
KNOWN_CITIES = {
    "toronto","brampton","mississauga","hamilton","burlington","oakville",
    "vaughan","kitchener","markham","oshawa","milton","halton hills",
    "caledon","cambridge","waterloo","guelph","richmond hill","newmarket",
    "ajax","pickering","whitby","clarington","bradford west gwillimbury",
    "bradford","aurora","king","st catharines","niagara falls",
    "welland","grimsby","barrie","innisfil","new tecumseth","bolton",
    "east gwillimbury","whitchurch-stouffville","stouffville",
}
STREET_ABBREVS = {
    "street":"st", "st":"st","road":"rd","rd":"rd",
    "avenue":"ave","ave":"ave","drive":"dr","dr":"dr",
    "boulevard":"blvd","blvd":"blvd","court":"crt","crt":"crt","ct":"crt",
    "circle":"cir","cir":"cir","crescent":"cres","cres":"cres",
    "parkway":"pkwy","pkwy":"pkwy","highway":"hwy","hwy":"hwy",
    "lane":"ln","ln":"ln","place":"pl","pl":"pl",
}
STREET_TYPES = r"st(?:reet)?|rd|road|ave(?:nue)?|dr(?:ive)?|blvd|boulevard|court|crt|cir(?:cle)?|cres(?:cent)?|pkwy|parkway|hwy|highway|lane|ln|pl(?:ace)?"
CIVIC_EMBEDDED = re.compile(
    r"(?<!\w)(\d{1,6}[A-Za-z]?\s+(?:[A-Za-z0-9][A-Za-z0-9'./-]*\s+){1,5}"
    r"(?:" + STREET_TYPES + r"))\b", re.I,
)
TERMINAL = re.compile(
    r"\b(?:withdrawn|cancelled|canceled|revoked|refused|rejected|"
    r"expired|awarded|completed|closed|terminated|denied)\b", re.I,
)
FUTURE_WORDS = re.compile(
    r"\b(?:propos(?:e|ed|al)|application|planned|intended|"
    r"under review|pending|submitted|requested)\b", re.I,
)
CANADIAN_POSTAL = re.compile(r"\b[A-Za-z]\d[A-Za-z]\s?\d[A-Za-z]\d\b")
UNIT = re.compile(r"\b(?:unit|suite|ste|#)\s*([A-Za-z0-9-]+)\b", re.I)


def clean(value):
    return " ".join(str(value if value is not None else "").split()).strip()


def first(row, *names):
    for name in names:
        value = clean(row.get(name, ""))
        if value:
            return value
    return ""


def iso_day(value):
    value = clean(value)
    match = re.match(r"^(\d{4}-\d{2}-\d{2})(?:$|T|\s)", value)
    if not match:
        return ""
    try:
        return dt.date.fromisoformat(match.group(1)).isoformat()
    except ValueError:
        return ""


def https(url):
    url = clean(url)
    try:
        parsed = urlsplit(url)
        if (parsed.scheme.lower() != "https" or not parsed.hostname or
                parsed.username or parsed.password or parsed.port not in (None, 443)):
            return ""
        if parsed.hostname == "localhost" or parsed.hostname.endswith(".localhost"):
            return ""
        return url[:1500]
    except ValueError:
        return ""


def normalized_city(value):
    city = clean(value).lower().replace(".", "")
    city = re.sub(r",?\s+(?:on|ontario|canada)$", "", city)
    city = re.sub(r"\s+", " ", city)
    if city == "etobicoke" or city == "scarborough" or city == "north york":
        return "Toronto"
    if city not in KNOWN_CITIES:
        return ""
    return city.title()


def normalize_address(value):
    """Return conservative normalized civic street key and unit; no geocoding."""
    addr = clean(value).strip(" ,;")
    if not addr:
        return "", ""
    if re.search(r"\b(?:p\.?\s*o\.?\s*box|mailing\s+address|lot\s+\d+\s+concession)\b", addr, re.I):
        return "", ""
    addr = CANADIAN_POSTAL.sub("", addr).strip(" ,;")
    # Toronto's active-permit feed sometimes has only the first postal triplet.
    addr = re.sub(r"\s+[A-Za-z]\d[A-Za-z]$", "", addr).strip(" ,;")
    addr = re.sub(r",?\s+(?:Toronto|Brampton|Mississauga|Oakville|Burlington|"
                  r"Vaughan|Hamilton|Kitchener|Markham|Oshawa|Milton|Guelph|Ontario|ON|Canada)"
                  r"(?:\s*,?\s*(?:Ontario|ON|Canada))?\s*$", "", addr, flags=re.I)
    unit = ""
    found = UNIT.search(addr)
    if found:
        unit = found.group(1).upper()
        addr = clean(addr[:found.start()] + " " + addr[found.end():])
    addr = re.sub(r"[,.]", " ", addr)
    parts = [STREET_ABBREVS.get(x.lower(), x.lower()) for x in addr.split()]
    address = " ".join(parts)
    address = re.sub(r"[^a-z0-9 -]", "", address)
    address = clean(address)
    if not re.match(r"^[1-9]\d{0,5}[a-z]?\s+[a-z0-9]", address):
        return "", ""
    if len(address) > 110:
        return "", ""
    return address, unit


def site_id(city, address):
    return hashlib.sha256((city.lower()+"|"+address).encode("utf-8")).hexdigest()[:20]


def event_id(family, source, key):
    return hashlib.sha256((family+"|"+source+"|"+key).encode("utf-8")).hexdigest()[:20]


def read_csv(path):
    try:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except (FileNotFoundError, UnicodeError, csv.Error):
        return []


def adapt(family, row):
    """All fields have explicit provenance. Never promote contact/name hints."""
    if family == "radar":
        if first(row, "observation") not in {"FIRST_OBSERVED", "RECORD_CHANGED"}:
            return None, "NOT_NEW_OR_CHANGED"
        source_id = first(row, "source_id")
        key = first(row, "project_id")
        city = first(row, "city")
        address = first(row, "address")
        organization = ""
        role = "UNKNOWN"
        description = first(row, "description")
        stage = first(row, "stage_from_local_status", "current_source_status")
        scope = "MUNICIPAL_PROJECT_RECORD"
        segments = first(row, "service_hypotheses")
        event_date = first(row, "source_record_date", "event_date")
        observed = first(row, "first_seen_local")
        source_url = first(row, "record_source_url")
        project = key
        signal = "MUNICIPAL_PERMIT_OR_PROJECT_ACTIVITY"
        procurement = "UNKNOWN"
        buyer = "NO"
        opened = "UNKNOWN"
        evidence_hash = first(row, "source_record_sha256")
    elif family == "planning":
        if first(row, "record_kind") != "APPLICATION_ID":
            return None, "NOT_PLANNING_APPLICATION"
        source_id = first(row, "source_id") or "municipal_planning"
        key = first(row, "canonical_id")
        city = first(row, "city")
        address = first(row, "address")
        organization = ""
        role = "UNKNOWN"
        description = first(row, "description")
        stage = first(row, "current_status", "status")
        scope = "PLANNING_APPLICATION"
        segments = ""
        event_date = first(row, "date")
        observed = first(row, "first_seen_local")
        source_url = first(row, "evidence_urls").split(" | ")[0].split("; ")[0]
        project = key
        signal = "MUNICIPAL_PLANNING_APPLICATION"
        procurement = "UNKNOWN"
        buyer = "NO"
        opened = "UNKNOWN"
        evidence_hash = first(row, "source_record_sha256")
        if not address and len(description) <= 1200:
            # A city index can contain MULTIPLE unrelated applications; never
            # attribute its first street address to every file number.
            matches = list(CIVIC_EMBEDDED.finditer(description))
            unique = {normalize_address(m.group(1))[0] for m in matches}
            unique.discard("")
            if (len(unique) == 1 and
                    description.lower().count("featured application") <= 1 and
                    description.lower().count("city file:") <= 1 and
                    "no municipal address" not in description.lower()):
                address = matches[0].group(1)
                scope = "PLANNING_DESCRIPTION_ADDRESS_UNVERIFIED"
    elif family == "industrial":
        source_id = "ero_gta_environmental_instruments"
        key = first(row, "ero_number") + "|" + first(row, "signal_id")
        city = first(row, "city")
        address = first(row, "site_address")
        organization = first(row, "proponent")
        role = "REGULATORY_PROPONENT_NOT_VERIFIED_BUYER" if organization else "UNKNOWN"
        description = first(row, "official_excerpt")
        stage = first(row, "notice_stage", "review_status")
        scope = "EXPLICIT_EQUIPMENT_CHANGE"
        segments = ";".join(
            x for x in (first(row, "equipment"), first(row, "replacement_equipment")) if x
        )
        event_date = first(row, "proposal_posted")
        observed = first(row, "radar_first_seen_at")
        source_url = first(row, "official_notice_url")
        project = first(row, "related_project_id")
        signal = "INDUSTRIAL_" + (first(row, "action") or "EQUIPMENT")
        procurement = first(row, "procurement_status") or "UNKNOWN"
        buyer = first(row, "buyer_verified") or "NO"
        opened = "UNKNOWN"
        evidence_hash = first(row, "source_text_sha256")
    elif family == "activation":
        source_id = first(row, "source_id")
        key = first(row, "source_record_key")
        city = first(row, "municipality")
        address = first(row, "site_address")
        if first(row, "site_unit"):
            address = clean(address+" Unit "+first(row, "site_unit"))
        organization = first(row, "business_name")
        role = "LICENCE_OPERATING_NAME_NOT_VERIFIED_TENANT" if organization else "UNKNOWN"
        description = first(row, "source_excerpt")
        stage = first(row, "activation_stage", "source_status")
        scope = "LICENCE_OR_PERMIT_ACTIVITY"
        segments = first(row, "potential_supplier_segments")
        event_date = first(row, "source_event_date")
        observed = first(row, "radar_first_seen_at")
        source_url = first(row, "source_dataset_url")
        project = ""
        signal = "COMMERCIAL_ACTIVATION_SIGNAL"
        procurement = first(row, "purchasing_status") or "UNKNOWN"
        buyer = first(row, "buyer_verified") or "NO"
        opened = first(row, "opening_confirmed") or "NO"
        evidence_hash = first(row, "source_record_sha256")
    else:
        return None, "UNSUPPORTED_SOURCE_FAMILY"
    if not key or not source_id:
        return None, "MISSING_SOURCE_IDENTITY"
    explicit_city = normalized_city(city)
    jurisdiction_city = SOURCE_CITY.get(source_id, "")
    city_conflict = bool(explicit_city and jurisdiction_city and
                         explicit_city != jurisdiction_city)
    city_derived = not explicit_city and bool(jurisdiction_city)
    city = "" if city_conflict else (explicit_city or jurisdiction_city)
    civic, unit = normalize_address(address)
    if not civic or not city:
        site = ""
        site_status = "NO_SAFE_SITE_IDENTITY"
    else:
        site = site_id(city, civic)
        site_status = ("DESCRIPTION_ONLY_UNVERIFIED_ADDRESS" if
                       scope == "PLANNING_DESCRIPTION_ADDRESS_UNVERIFIED" else
                       "SOURCE_JURISDICTION_CITY_NOT_INDEPENDENTLY_CHECKED" if city_derived else
                       "STRUCTURED_CIVIC_ADDRESS_NOT_INDEPENDENTLY_GEOCODED")
    url = https(source_url)
    evidence_level = ("RECORD_URL_NOT_LIVE_CHECKED" if url and family in {"radar", "industrial"} else
                      "SOURCE_REFERENCE_NOT_RECORD_SPECIFIC" if url else "SOURCE_URL_MISSING")
    closed = bool(TERMINAL.search(stage))
    archived_baseline = (family == "planning" and
                         first(row, "observation") not in {"FIRST_OBSERVED", "RECORD_CHANGED"})
    if closed:
        tier = "HISTORICAL_OR_TERMINAL_REVIEW_ONLY"
    elif not site:
        tier = "IDENTITY_REPAIR_REQUIRED"
    elif archived_baseline:
        tier = "HISTORICAL_PLANNING_BASELINE_SITE_CONTEXT_ONLY"
    elif scope == "EXPLICIT_EQUIPMENT_CHANGE":
        tier = "EQUIPMENT_CHANGE_RESEARCH"
    elif family == "activation":
        tier = "FACILITY_ACTIVATION_RESEARCH"
    elif family == "planning":
        tier = "PLANNING_APPLICATION_RESEARCH"
    else:
        tier = "GENERAL_PROJECT_REVIEW"
    blockers = ["BUYER_NOT_VERIFIED", "PROCUREMENT_NOT_VERIFIED",
                "SCOPE_AND_SITE_RELATIONSHIP_NOT_VERIFIED"]
    if not url:
        blockers.append("NO_SOURCE_URL")
    elif evidence_level == "SOURCE_REFERENCE_NOT_RECORD_SPECIFIC":
        blockers.append("INDIVIDUAL_SOURCE_RECORD_RECHECK_REQUIRED")
    if not iso_day(event_date):
        blockers.append("SOURCE_DATE_NOT_VERIFIED")
    if not observed:
        blockers.append("RADAR_FIRST_OBSERVED_TIMESTAMP_MISSING")
    if archived_baseline:
        blockers.append("PLANNING_BASELINE_NOT_NEW_DISCOVERY")
    if not site:
        blockers.append("SITE_ADDRESS_OR_CITY_UNVERIFIED")
    if city_conflict:
        blockers.append("SOURCE_CITY_CONFLICT")
    if city_derived:
        blockers.append("CITY_DERIVED_FROM_CONFIGURED_SOURCE_JURISDICTION")
    if site_status == "DESCRIPTION_ONLY_UNVERIFIED_ADDRESS":
        blockers.append("ADDRESS_EXTRACTED_FROM_DESCRIPTION_ONLY")
    if closed:
        blockers.append("HISTORICAL_OR_TERMINAL_STATUS")
    output = {
        "event_id":event_id(family, source_id, key),
        "source_family":family, "source_id":source_id, "source_record_id":key,
        "source_url":url, "url_evidence_level":evidence_level,
        "record_hash":evidence_hash, "source_date":iso_day(event_date),
        "radar_first_seen_at":observed, "city":city,
        "site_address":civic, "site_unit":unit, "site_id":site,
        "site_identity_status":site_status,
        "organization":organization, "organization_role":role,
        "project_id":project, "signal_type":signal, "stage_label":stage,
        "source_status":stage, "description":description[:750],
        "scope_specificity":scope, "supplier_segments_possible":segments,
        # Never convert a model hint, publication date, licence issue or source
        # stage into VERIFIED procurement/occupancy.
        "procurement_status":"NOT_OPEN_OR_TERMINAL_STATUS" if closed else "UNKNOWN",
        "buyer_verified":"NO",
        "opening_confirmed":"NO" if family=="activation" else "UNKNOWN",
        "review_tier":tier, "verification_required":";".join(blockers),
    }
    return output, None


def relationships(events):
    by_site = defaultdict(list)
    for e in events:
        if e["site_id"]:
            by_site[e["site_id"]].append(e)
    links = []
    for site, group in sorted(by_site.items()):
        group.sort(key=lambda x:x["event_id"])
        # Bounded link generation: 1000 records at one building would otherwise
        # produce half a million relationship rows.
        for pos,left in enumerate(group[:200]):
            for right in group[pos+1:200]:
                if left["source_family"]==right["source_family"]:
                    continue
                if (left["site_identity_status"]=="DESCRIPTION_ONLY_UNVERIFIED_ADDRESS" or
                    right["site_identity_status"]=="DESCRIPTION_ONLY_UNVERIFIED_ADDRESS"):
                    label = "DESCRIPTION_ADDRESS_SAME_SITE_CANDIDATE_ONLY"
                elif left["site_unit"] and right["site_unit"] and left["site_unit"]!=right["site_unit"]:
                    label = "DIFFERENT_UNITS_NOT_SAME_TENANT"
                elif bool(left["site_unit"])!=bool(right["site_unit"]):
                    label = "SAME_BUILDING_UNIT_UNKNOWN"
                elif left["site_unit"] and right["site_unit"]:
                    label = "SAME_ADDRESS_AND_UNIT_TENANT_UNVERIFIED"
                else:
                    label = "SAME_CIVIC_SITE_PROJECT_UNVERIFIED"
                links.append({
                    "site_id":site, "left_event_id":left["event_id"],
                    "right_event_id":right["event_id"],
                    "left_source_family":left["source_family"],
                    "right_source_family":right["source_family"],
                    "left_record_id":left["source_record_id"],
                    "right_record_id":right["source_record_id"],
                    "relationship":label, "relationship_verified":"NO",
                    "notes":"Address match only; no verified same tenant, project, buyer or procurement",
                })
    return links


def facility_profiles(events, links):
    groups=defaultdict(list)
    for e in events:
        if e["site_id"]:
            groups[e["site_id"]].append(e)
    linkgroups=defaultdict(list)
    for link in links:
        linkgroups[link["site_id"]].append(link)
    profiles=[]
    for site,group in sorted(groups.items()):
        source_ids=sorted({x["source_family"] for x in group})
        values=sorted({x["organization"] for x in group if x["organization"]})
        observed=sorted(x["radar_first_seen_at"] for x in group if x["radar_first_seen_at"])
        dates=sorted(x["source_date"] for x in group if x["source_date"])
        related=linkgroups[site]
        profiles.append({
            "site_id":site, "city":group[0]["city"],
            "site_address":group[0]["site_address"],
            "source_families":";".join(source_ids),
            "evidence_events":len(group),
            "distinct_source_records":len({(x["source_id"],x["source_record_id"]) for x in group}),
            "first_observed_at":observed[0] if observed else "",
            "latest_source_date":dates[-1] if dates else "",
            "organization_mentions_unverified":";".join(values)[:900],
            "signal_types":";".join(sorted({x["signal_type"] for x in group})),
            "cross_source_civic_matches":sum(
                x["relationship"] != "DIFFERENT_UNITS_NOT_SAME_TENANT"
                for x in related),
            "unit_conflicts":sum(x["relationship"]=="DIFFERENT_UNITS_NOT_SAME_TENANT" for x in related),
            "status":"SITE_HISTORY_NOT_VERIFIED_PROJECT_OR_COMPANY_GRAPH",
            "verification_required":"Confirm exact facility, tenant/operator, stage, purchasing authority",
        })
    profiles.sort(key=lambda x:(x["cross_source_civic_matches"],x["latest_source_date"]),reverse=True)
    return profiles


def write_csv(path, rows, fields):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as out:
        writer=csv.DictWriter(out,fieldnames=fields,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run(results, out=None, *, max_events=100000):
    results=Path(results)
    out=Path(out) if out is not None else results/"FACILITY_INTELLIGENCE_PILOT"
    # A post-processing layer must never overwrite the source results.
    out.mkdir(parents=True, exist_ok=True)
    if out.resolve()==results.resolve():
        raise ValueError("The graph must write to a distinct report folder")
    ingested=[]
    exclusions=Counter()
    input_counts={}
    for family,filename in INPUTS:
        rows=read_csv(results/filename)
        input_counts[family]=len(rows)
        for row in rows[:max_events]:
            event,reason=adapt(family,row)
            if event:
                ingested.append(event)
            else:
                exclusions[f"{family}:{reason}"]+=1
        if len(rows)>max_events:
            exclusions[f"{family}:INPUT_TRUNCATED"]+=len(rows)-max_events
    by_id={}
    for e in ingested:
        existing=by_id.get(e["event_id"])
        if existing is not None:
            exclusions["DUPLICATE_EVENT_ID"]+=1
            # Prefer rows with direct exact-record URLs, never concatenate hints.
            if existing["url_evidence_level"]=="RECORD_URL_NOT_LIVE_CHECKED":
                continue
        by_id[e["event_id"]]=e
    events=sorted(by_id.values(),key=lambda x:(x["source_date"],x["event_id"]),reverse=True)
    links=relationships(events)
    profiles=facility_profiles(events,links)
    write_csv(out/OUTPUT_EVENTS,events,EVENT_FIELDS)
    write_csv(out/OUTPUT_FACILITIES,profiles,FACILITY_FIELDS)
    write_csv(out/OUTPUT_LINKS,links,LINK_FIELDS)
    write_csv(out/OUTPUT_REVIEW,events,REVIEW_FIELDS)
    cols=("city","site_address","source_families","evidence_events",
          "cross_source_civic_matches","latest_source_date","status")
    html_rows="".join("<tr>"+"".join("<td>"+html.escape(clean(r[k]))+"</td>" for k in cols)+"</tr>"
                      for r in profiles[:500])
    (out/OUTPUT_HTML).write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>Facility evidence</title>"
        "<style>body{font:14px Arial;margin:24px}table{border-collapse:collapse}"
        "th,td{border:1px solid #ccc;padding:7px;vertical-align:top}</style></head><body>"
        "<h1>Facility intelligence — manual research only</h1>"
        "<p>A matching address does not verify the same business, project, buying authority, "
        "supplier need, available contract or opening date. First 500 sites only; full CSV attached."
        "</p><table><tr>"+ "".join("<th>"+html.escape(c)+"</th>" for c in cols)+
        "</tr>"+html_rows+"</table></body></html>",encoding="utf-8")
    status={
        "mode":"OFFLINE_POSTPROCESS_READ_ONLY_SOURCES_NO_AI_NO_LIVE_FETCH",
        "source_rows_seen":input_counts, "source_event_count":len(events),
        "sites_with_civic_identity":len(profiles),
        "source_records_without_safe_site":sum(not e["site_id"] for e in events),
        "cross_source_civic_relationships":len(links),
        "cross_source_candidate_links":sum(
            link["relationship"] != "DIFFERENT_UNITS_NOT_SAME_TENANT" for link in links),
        "unit_conflicts_blocked":sum(
            link["relationship"] == "DIFFERENT_UNITS_NOT_SAME_TENANT" for link in links),
        "cross_source_links_verified_as_same_project":0,
        "verified_open_supplier_contracts":0,
        "verified_buyers":0, "verified_business_openings":0,
        "exclusions":dict(sorted(exclusions.items())),
        "limitations":[
            "Only existing CSV snapshots; no statement of current publication freshness",
            "Civic address links do not identify the same company, tenant, project or purchasing authority",
            "Source URLs are not independently rechecked against the exact individual records",
            "No outreach, contact scraping, new collector runs or scheduling",
            "No automatic promotion of output to the main opportunity feed",
        ],
        "outputs":{k:str(out/v) for k,v in {
            "events":OUTPUT_EVENTS,"facility_history":OUTPUT_FACILITIES,
            "relationships":OUTPUT_LINKS,"commercial_review":OUTPUT_REVIEW,
            "html":OUTPUT_HTML,
        }.items()},
    }
    (out/OUTPUT_STATUS).write_text(json.dumps(status,indent=2),encoding="utf-8")
    return status


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results",type=Path,required=True,help="Existing GTA_RADAR_RESULTS folder")
    parser.add_argument("--out",type=Path,help="Separate reporting folder")
    parser.add_argument("--max-events",type=int,default=100000)
    args=parser.parse_args()
    print(json.dumps(run(args.results,args.out,max_events=args.max_events),indent=2))


if __name__=="__main__":
    main()
