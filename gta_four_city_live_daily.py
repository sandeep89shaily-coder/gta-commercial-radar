"""Four added municipal sources: real, policy-aware automatic daily collection.

The normal manual full-run launches this stage automatically. Every city
attempt is independent, and a blocked official source is a visible failure,
never silently reused as a newly retrieved record. No AI/API spend, no SQLite.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from gta_ajax_newmarket_source_pilot import query as arcgis_query, SOURCES
from gta_windsor_pickering_source_pilot import (
    WINDSOR, PICKERING, parse_windsor_index, parse_pickering_index,
    parse_pickering_detail, approved_url,
)

CITIES = ("Ajax", "Newmarket", "Windsor", "Pickering")
MASTER = "GTA_RADAR_FOUR_CITY_LIVE_APPLICATIONS.csv"
STATUS = "GTA_RADAR_FOUR_CITY_SOURCE_STATUS.json"
LEDGER = "GTA_RADAR_FOUR_CITY_FIRST_SEEN.json"
MAX_HTML_BYTES = 2_500_000
MAX_PICKERING_DETAIL_PAGES = 25
COLS = ("city", "application_id", "address", "scope", "applicant",
        "stage", "category", "date", "date_basis", "source_url",
        "original_publication_verified", "buyer_verified",
        "procurement_verified", "first_seen_local",
        "source_observation", "source_kind", "changed_fields")

class SourceBlocked(Exception):
    pass

def robots_allowed(url):
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        return False
    robot = RobotFileParser()
    robot.set_url(f"{p.scheme}://{p.netloc}/robots.txt")
    try:
        robot.read()
        # A robots fetch with an HTTP error must not become permission.
        # Python's RobotFileParser returns False for explicit disallow.
        return bool(robot.can_fetch("GTA-Radar-source-research",url))
    except (OSError, ValueError):
        return False

def fetch_html(url, *, fetcher=None, check_robots=True):
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        raise SourceBlocked("INVALID_SOURCE_URL")
    if check_robots and not robots_allowed(url):
        raise SourceBlocked("ROBOTS_NOT_PERMITTED_OR_UNVERIFIED")
    if fetcher is not None:
        result = fetcher(url)
        if not isinstance(result, str):
            raise ValueError("INVALID_FETCHER_PAYLOAD")
        if len(result.encode("utf-8")) > MAX_HTML_BYTES:
            raise ValueError("RESPONSE_TOO_LARGE")
        return result
    req = Request(url, headers={"User-Agent": "GTA-Radar-source-research/1.0"})
    try:
        with urlopen(req, timeout=18) as response:
            final = urlsplit(response.geturl())
            if (final.scheme != "https" or final.hostname != p.hostname):
                raise SourceBlocked("CROSS_HOST_REDIRECT")
            raw = response.read(MAX_HTML_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise SourceBlocked("OFFICIAL_SOURCE_HTTP_OR_NETWORK_FAILURE") from exc
    if len(raw) > MAX_HTML_BYTES:
        raise SourceBlocked("OFFICIAL_RESPONSE_TOO_LARGE")
    return raw.decode("utf-8", errors="replace")

def _normalize(row, city):
    if city in SOURCES:
        return {
            "city":city,"application_id":row["application_id"],
            "address":row["address"],"scope":row["scope"],
            "applicant":row.get("applicant_source_claim",""),
            "stage":row.get("current_status",""),
            "category":row.get("category",""),
            "date":row.get("source_date",""),
            "date_basis":row.get("source_date_basis",""),
            "source_url":row.get("source_url",""),
            "source_kind":"OFFICIAL_ARCGIS_FEATURE",
        }
    return {
        "city":city,"application_id":row["application_id"],
        "address":row["address"],"scope":row["scope"],
        "applicant":row.get("applicant_source_claim",""),
        "stage":row.get("research_status",""),
        "category":row.get("record_type",""),
        "date":row.get("source_date",""),
        "date_basis":row.get("source_date_basis",""),
        "source_url":row.get("source_url",""),
        "source_kind":row.get("source_level","OFFICIAL_INDEX"),
    }

def collect_city(city, *, arcgis_fetcher=None, html_fetcher=None,
                 check_robots=True, max_arcgis_rows=300):
    if city in SOURCES:
        records = arcgis_query(city, fetcher=arcgis_fetcher,
                 robots_check=check_robots, max_rows=max_arcgis_rows)
        return [_normalize(r,city) for r in records], {
            "requested_feature_cap":max_arcgis_rows,
            "truncated_or_full_feed_unverified":len(records)>=max_arcgis_rows,
            "source":SOURCES[city]["url"],
        }
    if city == "Windsor":
        data = fetch_html(WINDSOR, fetcher=html_fetcher,
                          check_robots=check_robots)
        records=parse_windsor_index(data)
        return [_normalize(r,city) for r in records], {
            "source":WINDSOR, "index_records":len(records),
            "detail_pages_checked":0,
            "original_publication_unverified":True,
        }
    if city == "Pickering":
        data=fetch_html(PICKERING, fetcher=html_fetcher,
                        check_robots=check_robots)
        index=parse_pickering_index(data)
        detailed=[]; blocked=0; attempted=0
        for entry in index[:MAX_PICKERING_DETAIL_PAGES]:
            url=approved_url("Pickering",entry.get("project_page_url",""))
            if not url or "/news/posts/" not in urlsplit(url).path:
                continue
            attempted+=1
            try:
                page=fetch_html(url, fetcher=html_fetcher,
                                check_robots=check_robots)
                detailed.extend(parse_pickering_detail(page,page_url=url))
            except (SourceBlocked, ValueError, UnicodeError):
                blocked+=1
        return [_normalize(r,city) for r in detailed], {
            "source":PICKERING,"index_records":len(index),
            "detail_pages_attempted":attempted,
            "detail_pages_failed":blocked,
            "detail_pages_cap":MAX_PICKERING_DETAIL_PAGES,
            "full_index_checked":len(index)<=MAX_PICKERING_DETAIL_PAGES,
            "original_publication_unverified":True,
        }
    raise ValueError("CITY_NOT_CONFIGURED")

def run(results, *, collector=None, today=None, check_robots=True):
    root=Path(results)
    if not root.is_dir():
        raise FileNotFoundError("EXISTING_RESULTS_DIRECTORY_REQUIRED")
    day=today or dt.date.today()
    old={}
    ledger=root/LEDGER
    if ledger.is_file() and not ledger.is_symlink():
        try:
            doc=json.loads(ledger.read_text(encoding="utf-8"))
            if isinstance(doc,dict):old=doc
        except (OSError, ValueError, UnicodeError):
            old={}
    next_ledger=dict(old)
    accepted=[]; health=[]
    for city in CITIES:
        info={"city":city,"status":"SOURCE_NOT_ATTEMPTED",
              "retrieved_application_id_records":0,
              "verified_citywide_coverage":False,
              "buyer_verified":0,"original_publication_verified":0,
              "new_project_publications_verified":0}
        try:
            result=(collector or collect_city)(city,check_robots=check_robots)
            found,details=result
            info.update(details)
            if not isinstance(found,list):
                raise ValueError("COLLECTOR_ROWS_INVALID")
            unique={}
            for raw in found:
                if not isinstance(raw,dict):
                    continue
                key=(city+"|"+str(raw.get("application_id") or "")).upper()
                if not raw.get("application_id") or not raw.get("address") or not raw.get("scope"):
                    continue
                unique.setdefault(key,raw)
            for key,r in unique.items():
                fields={k:r.get(k,"") for k in ("address","scope","applicant","stage","date")}
                fingerprint=hashlib.sha256(json.dumps(fields,sort_keys=True).encode()).hexdigest()
                prior=next_ledger.get(key,{})
                new=not bool(prior)
                changed=bool(prior and prior.get("fingerprint")!=fingerprint)
                previous_fields=prior.get("fields")
                changed_fields=(" | ".join("description" if k=="scope" else k
                    for k,v in fields.items() if previous_fields.get(k)!=v)
                    if changed and isinstance(previous_fields,dict) else "")
                next_ledger[key]={"first_seen":prior.get("first_seen") or day.isoformat(),
                                  "fingerprint":fingerprint,"fields":fields}
                accepted.append({**r,
                    "first_seen_local":next_ledger[key]["first_seen"],
                    "source_observation":("FIRST_OBSERVED_NOT_FIRST_PUBLICATION" if new
                        else "SOURCE_UPDATED_NOT_FIRST_PUBLICATION" if changed
                        else "UNCHANGED"),
                    "changed_fields":changed_fields,
                    "original_publication_verified":"False",
                    "buyer_verified":"False","procurement_verified":"False"})
            info["retrieved_application_id_records"]=len(unique)
            info["status"]=("LIVE_APPLICATION_IDS_RETRIEVED_PARTIAL_COVERAGE"
                if unique else "LIVE_SOURCE_RETRIEVED_NO_VALID_APPLICATION_IDS")
        except (PermissionError, SourceBlocked, ValueError, OSError,
                KeyError, TypeError, RuntimeError, UnicodeError) as exc:
            info["status"]="BLOCKED_OR_FAILED_NO_NEW_LIVE_RECORDS"
            info["failure"]=type(exc).__name__+": "+str(exc)[:180]
        health.append(info)
    # Incomplete source fetches never borrow yesterday's rows as live.
    # Prior first-seen ledger is retained for continuity only.
    out=root/MASTER
    with out.open("w",encoding="utf-8-sig",newline="") as fp:
        w=csv.DictWriter(fp,fieldnames=COLS)
        w.writeheader()
        for row in accepted:
            w.writerow({k:("'"+str(row.get(k) or "")
                if str(row.get(k) or "").lstrip().startswith(("=","+","-","@","\\t","\\r"))
                else str(row.get(k) or "")) for k in COLS})
    temp=ledger.with_suffix(".json.tmp")
    temp.write_text(json.dumps(next_ledger,indent=2),encoding="utf-8")
    temp.replace(ledger)
    report={
        "status":"FOUR_CITY_LIVE_COLLECTION_AUDITED_PARTIAL_UNLESS_VERIFIED",
        "configured_added_municipalities":4,
        "city_status":health,
        "cities_with_live_application_ids":sum(
            i["retrieved_application_id_records"]>0 for i in health),
        "four_city_live_application_rows":len(accepted),
        "all_four_live":all(i["retrieved_application_id_records"]>0 for i in health),
        "verified_citywide_complete":False,
        "verified_buyers":0,"verified_new_original_publications":0,
        "additional_ai_calls":0,"csv":str(out),
    }
    (root/STATUS).write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results",required=True)
    a=p.parse_args()
    print(json.dumps(run(a.results),indent=2))

if __name__=="__main__":
    main()
