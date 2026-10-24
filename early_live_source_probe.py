"""One-shot small read-only live-source health probe.

Never auto-runs in the daily pipeline. It asks 8 official public endpoints
about the minimum HTML schema we actually parse and emits a source-health
report only. Neither company contact research nor any export of publisher
content is attempted. A failed source is NOT a zero-opportunities finding.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
from pathlib import Path
import requests
from early_oakville_watch import BASE as OAKVILLE, ward_urls
from early_public_notices import MILTON, PICKERING, ERO, parse_milton, parse_pickering
from early_cue_watch import IESO_URL, parse_ieso
from early_discovery_watch import BURLINGTON_HOME, BRAMPTON_CALENDAR, discover_burlington_ward_urls, parse_calendar
from early_ajax_watch import URL as AJAX, parse_ajax

PROBES=(
 ("oakville_ward_index",OAKVILLE,"oakville"),
 ("milton_notices",MILTON,"milton"),
 ("pickering_proposals",PICKERING,"pickering"),
 ("ieso_connections",IESO_URL,"ieso"),
 ("burlington_ward_index",BURLINGTON_HOME,"burlington"),
 ("brampton_planning_calendar",BRAMPTON_CALENDAR,"brampton"),
 ("ajax_planning_properties",AJAX,"ajax"),
)
FIELDS=("source_id","url","tested_at_utc","network_status",
        "parsed_items","coverage_limit","error")
USER_AGENT="GTA-Radar-Source-Health-Probe/0.1 (+manual-one-shot)"
SCHEMAS={
 "oakville":lambda text:(len(ward_urls(text)),"SEVEN_WARDS_INDEX_ONLY"),
 "milton":lambda text:(len(parse_milton(text)[0]),"FIRST_PAGE_ONLY"),
 "pickering":lambda text:(len(parse_pickering(text)[0]),"ACTIVE_PROPOSALS_TABLE_ONLY"),
 "ieso":lambda text:(len(parse_ieso(text)[0]),"VISIBLE_IESO_TABLE_MAY_BE_PAGINATED"),
 "burlington":lambda text:(len(discover_burlington_ward_urls(text)),
                           "WARD_NAVIGATION_LINKS_ONLY"),
 "brampton":lambda text:(len(parse_calendar(text)),"LINKED_MEETINGS_ONLY"),
 "ajax":lambda text:(len(parse_ajax(text)[0]),"PROPERTY_APPLICATION_INDEX_ONLY")
}

def check(sid,url,parser,session=None,time=None):
    from urllib.parse import urlparse
    p=urlparse(url)
    if p.scheme!="https" or not p.hostname:
        raise ValueError("Official probe must have a HTTPS endpoint")
    session=session or requests.Session()
    stamp=time or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    try:
        r=session.get(url,headers={"User-Agent":USER_AGENT},timeout=(8,20))
        r.raise_for_status()
        body=r.text
        if len(body)>4_000_000:raise RuntimeError("HTML exceeds safety cap")
        if "<html" not in body[:5000].lower():
            raise RuntimeError("Non-HTML content or publisher challenge")
        count,limit=SCHEMAS[parser](body)
        if count==0:raise RuntimeError("Parser returned empty index, not trustworthy")
        return dict(source_id=sid,url=url,tested_at_utc=stamp,
            network_status="REACHABLE_SCHEMA_PARSED_NOT_FULL_FEED",
            parsed_items=count,coverage_limit=limit,error="")
    except (requests.RequestException,ValueError,RuntimeError) as e:
        return dict(source_id=sid,url=url,tested_at_utc=stamp,
            network_status="UNAVAILABLE_OR_SCHEMA_CHANGED",
            parsed_items=0,coverage_limit="NO_COVERAGE_VERIFIED",
            error=(str(e) or type(e).__name__)[:220])

def run(output_dir="GTA_RADAR_RESULTS",session=None):
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    findings=[check(sid,url,parser,session=session)
              for sid,url,parser in PROBES]
    target=out/"EARLY_LIVE_SOURCE_HEALTH_ONLY.csv"
    temp=target.with_suffix(".tmp")
    with temp.open("w",encoding="utf-8-sig",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=FIELDS,extrasaction="ignore")
        w.writeheader();w.writerows(findings)
    temp.replace(target)
    for f in findings:
        print(f["source_id"],f["network_status"],
             f["parsed_items"],f["coverage_limit"],
             ("error="+f["error"] if f["error"] else ""))
    return findings

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir",default="GTA_RADAR_RESULTS")
    a=p.parse_args()
    run(a.output_dir)
