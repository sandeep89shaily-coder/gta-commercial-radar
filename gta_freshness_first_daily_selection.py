"""Daily freshness FIRST: two research lanes and a separate older-project watchlist.

Uses actual daily observations, saved equipment notices/investments and existing
client-report history. Does NOT declare first public announcements, buyers or
open RFQs from a dated permit, source observation or funding agreement.
No network, paid AI, customer release or writes to collectors' ledgers.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from gta_freshness import _date
from gta_client_freshness import _read_history, _site_key

DAILY = "GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv"
UNIFIED_DAILY = "GTA_RADAR_UNIFIED_MUNICIPAL_DAILY_CHANGES.csv"
EQUIPMENT = "GTA_RADAR_EQUIPMENT_COMMERCIAL_INDEX.csv"
ANNOUNCEMENTS = "GTA_RADAR_FRESH_INDUSTRIAL_ANNOUNCEMENTS.csv"
FULLTEXT = "GTA_RADAR_FULLTEXT_EQUIPMENT_FRESH_RESEARCH.csv"
FEDDEV_ALL40 = "GTA_RADAR_FEDDEV_ALL40_EVIDENCE.csv"
FEDERAL = "GTA_RADAR_FEDERAL_CAPEX_TOP20_RESEARCH.csv"
GENERAL_TOP = "GTA_RADAR_FRESH_GENERAL_RESEARCH_TOP10.csv"
EQUIPMENT_TOP = "GTA_RADAR_FRESH_EQUIPMENT_RESEARCH_TOP10.csv"
WATCHLIST = "GTA_RADAR_OLDER_ACTIVE_OPPORTUNITY_WATCHLIST.csv"
STATUS = "GTA_RADAR_FRESHNESS_FIRST_SELECTION_STATUS.json"
FIELDS = (
    "rank","lane","city","address_or_company_site_unverified","project_or_company",
    "source_project_id","scope","source_event_date","source_event_date_basis",
    "radar_first_observed","observation","stage","company_source_claim",
    "public_business_email_unverified_for_purchasing","source_url",
    "exact_project_source_verified","first_publication_verified",
    "buyer_verified","open_supplier_package_verified",
    "freshness_class","decision","next_verification_action",
)
INDUSTRIAL = re.compile(r"\b(?:industrial|manufactur|machin|cnc|automat|robot|"
    r"production|processing|packaging|fabricat|welding|equipment|scrubber|"
    r"collector|battery|extrusion|assembly|injection mould|boiler)\b",re.I)
COMMERCIAL = re.compile(r"\b(?:commercial|restaurant|clinic|dental|retail|"
    r"office|daycare|tenant|warehouse|industrial|manufactur|hotel|"
    r"commissary|kitchen|store|health|business|distribution|shop|"
    r"self.storage|data cent|fit.out|service|veterinary|alterations?)\b",re.I)
CLOSED = re.compile(r"\b(?:cancelled|canceled|withdrawn|inactive|closed|"
    r"completed|occupied|demolished)\b",re.I)
LATE = re.compile(r"\b(?:issued|inspection|completed)\b",re.I)
SCOPED = re.compile(r"\b(?:interior alterations?|renovat|conver|fit.out|"
    r"expan|construction|build|install|demolish|addition|modif|"
    r"alteration|tenant improvement|relocat|new)\b",re.I)
OBSERVATIONS = {"FIRST_OBSERVED","RECORD_CHANGED"}
RECENT_MAX_DAYS = 2  # Fri November 20 includes Wed Nov 18 through Fri Nov 20.

def _read(path):
    if not path.is_file(): return []
    if path.is_symlink() or path.stat().st_size > 50_000_000:
        raise ValueError("UNSAFE_FRESH_SELECTION_INPUT")
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def _url(value):
    for url in re.split(r"[|;]",str(value or "")):
        url=url.strip()
        try:
            parsed=urlsplit(url)
            if parsed.scheme=="https" and parsed.hostname and not parsed.username and not parsed.password:
                return url[:1200]
        except ValueError:
            pass
    return ""

def _write(path, rows):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k:("'"+str(row.get(k,"")) if str(row.get(k,"")).lstrip().startswith(
                ("=","+","-","@")) else row.get(k,"")) for k in FIELDS})

def _base(**kwargs):
    return {
        **dict.fromkeys(FIELDS,""), **kwargs,
        "exact_project_source_verified":"False","first_publication_verified":"False",
        "buyer_verified":"False","open_supplier_package_verified":"False",
    }

def run(results, *, today=None):
    root=Path(results)
    if not root.is_dir(): raise FileNotFoundError("RESULTS_DIRECTORY_REQUIRED")
    day=_date(today) or dt.date.today()
    history=_read_history(root,day)
    recent_general=[]; recent_equipment=[]; older=[]; counts=Counter()
    seen=set()
    # The full run materializes the cross-city union immediately before this
    # stage. Standalone/older exports may still use the original V6 feed.
    daily_path = root/UNIFIED_DAILY if (root/UNIFIED_DAILY).is_file() else root/DAILY
    for r in _read(daily_path):
        counts["daily_input"]+=1
        obs=str(r.get("observation") or "").strip().upper()
        city=str(r.get("city") or "").strip()
        addr=str(r.get("address") or "").strip()
        scope=" ".join(str(r.get("description") or "").split())
        ident=str(r.get("project_id") or "").strip()
        date=_date(r.get("source_record_date"))
        seen_day=_date(r.get("first_seen_local"))
        if not city or not addr or not ident or len(scope)<35 or not COMMERCIAL.search(scope):
            counts["daily_insufficient_commercial_evidence"]+=1
            continue
        if obs not in OBSERVATIONS:
            counts["daily_no_new_observation"]+=1
            continue
        if _date(r.get("last_seen_local"))!=day:
            counts["daily_not_from_current_run"]+=1
            continue
        if seen_day and seen_day>day:
            counts["daily_bad_first_seen"]+=1
            continue
        key=(city.casefold(),ident.casefold())
        if key in seen:
            counts["duplicate_project_id"]+=1
            continue
        seen.add(key)
        stage=str(r.get("stage_from_local_status") or r.get("current_source_status") or "")
        status_text=str(r.get("current_source_status") or "")
        if (CLOSED.search(stage) or CLOSED.search(status_text) or
                status_text.upper().startswith(("INACTIVE","CLOSED","WITHDRAWN"))):
            counts["closed_excluded"]+=1
            continue
        if date is None or not 0<=(day-date).days<=RECENT_MAX_DAYS:
            counts["older_or_undated_source_event"]+=1
            freshness="OLD_OR_UNDATED_SOURCE_EVENT_WATCHLIST"
        else:
            freshness="RECENT_SOURCE_EVENT_NOT_PUBLICATION_PROOF"
        if _site_key(city,addr) in history:
            counts["previously_sent_site"]+=1
            freshness="PREVIOUSLY_REPORTED_SITE_WATCHLIST"
        if obs=="RECORD_CHANGED" and "description" not in str(r.get("changed_fields") or "").lower():
            # A status/permit-component change is not new scope.
            counts["nonmaterial_change"]+=1
            freshness="NONMATERIAL_CHANGE_WATCHLIST"
        if LATE.search(stage) or LATE.search(status_text):
            counts["late_stage"]+=1
            freshness="LATE_STAGE_WATCHLIST"
        if not SCOPED.search(scope):
            counts["no_specific_work"]+=1
            freshness="NO_SPECIFIC_WORK_WATCHLIST"
        if obs=="FIRST_OBSERVED" and seen_day!=day:
            counts["not_first_observed_today"]+=1
            freshness="PREVIOUSLY_OBSERVED_WATCHLIST"
        row=_base(lane="GENERAL_COMMERCIAL",
            city=city,address_or_company_site_unverified=addr,
            project_or_company=addr,source_project_id=ident,
            scope=scope[:850],
            source_event_date=date.isoformat() if date else "",
            source_event_date_basis="SOURCE_RECORD_DATE_NOT_FIRST_PUBLICATION",
            radar_first_observed=r.get("first_seen_local",""),
            observation=obs,stage=status_text or stage,
            company_source_claim="",source_url=_url(r.get("record_source_url")),
            freshness_class=freshness,decision="RESEARCH_ONLY",
            next_verification_action="Get exact permit source and first public posting; identify owner/tenant, GC and any unawarded work.")
        if freshness=="RECENT_SOURCE_EVENT_NOT_PUBLICATION_PROOF":
            recent_general.append(row)
        else:
            older.append(row)
    # Recently publisher-dated industrial announcements are a separate
    # independently sourced intake. A reported RSS date is NOT authenticated
    # first publication, nor evidence of equipment procurement.
    for r in _read(root/ANNOUNCEMENTS):
        counts["official_announcement_input"]+=1
        date=_date(r.get("publisher_reported_date"))
        if (not date or not 0<=(day-date).days<=RECENT_MAX_DAYS
                or not str(r.get("classification") or "").startswith("RECENT_")
                or not _url(r.get("source_url"))):
            counts["announcement_not_recent_for_daily"]+=1
            continue
        row=_base(lane="EQUIPMENT_INTELLIGENCE",
            city=r.get("city_mentioned") or "Ontario (city to verify)",
            address_or_company_site_unverified="",
            project_or_company=r.get("title",""),
            source_project_id="OFFICIAL_ANNOUNCEMENT:"+r.get("source",""),
            scope=r.get("industrial_scope_quote","")[:850],
            source_event_date=date.isoformat(),
            source_event_date_basis=r.get("publisher_date_basis",""),
            radar_first_observed=r.get("first_seen_by_radar",""),
            observation=r.get("observation",""),
            source_url=_url(r.get("source_url")),
            freshness_class="RECENT_PUBLISHER_REPORTED_DATE_UNVERIFIED",
            decision="SOURCE_RESEARCH_ONLY_NOT_EQUIPMENT_ORDER",
            next_verification_action="Check original dated release, manufacturer identity, exact equipment scope, vendor selection and purchasing contact.")
        recent_equipment.append(row)
    # Full-text dated announcements from the FedDev fallback, InvestOntario
    # and manufacturer newsrooms are research evidence, not open orders.
    existing_urls={x.get("source_url","") for x in recent_equipment}
    for r in _read(root/FULLTEXT):
        counts["fulltext_announcement_input"]+=1
        date=_date(r.get("publisher_reported_date"))
        url=_url(r.get("source_url"))
        if (not date or not 0<=(day-date).days<=RECENT_MAX_DAYS
                or r.get("opportunity_class")!="RECENT_DATED_RESEARCH"
                or not url or url in existing_urls):
            counts["fulltext_not_recent_or_duplicate"]+=1
            continue
        stage=r.get("procurement_stage") or "TIMING_UNKNOWN_REQUIRES_VERIFICATION"
        row=_base(lane="EQUIPMENT_INTELLIGENCE",
            city=r.get("city_mentioned") or "Ontario (site to verify)",
            address_or_company_site_unverified="",
            project_or_company=r.get("title",""),
            source_project_id="FULLTEXT:"+str(r.get("source","")),
            scope=r.get("industrial_scope_quote","")[:850],
            source_event_date=date.isoformat(),
            source_event_date_basis=r.get("publisher_date_basis",""),
            radar_first_observed=r.get("first_seen_by_radar",""),
            observation=r.get("observation",""),
            source_url=url,
            freshness_class="RECENT_PUBLISHER_DATED_ARTICLE_NOT_VERIFIED_FIRST_PUBLICATION",
            decision=("RESEARCH_ONLY_COMPLETED_STAGE" if
                      "COMPLETED" in stage or "ALREADY_AWARDED" in stage
                      else "RESEARCH_ONLY_PROCUREMENT_UNVERIFIED"),
            next_verification_action="Verify full original article, Ontario project location, equipment need and purchasing stage.")
        row["stage"]=stage
        recent_equipment.append(row)
        existing_urls.add(url)
    # The exhaustive FedDev archive retains all 40 input records, but only
    # independently article-dated, recent industrial articles can enter
    # research; completed projects stay research-only and no buyer is proven.
    existing_urls={x.get("source_url","") for x in recent_equipment}
    for r in _read(root/FEDDEV_ALL40):
        counts["feddev_all40_rows"]+=1
        date=_date(r.get("article_reported_date"))
        url=_url(r.get("source_url"))
        if (not url or url in existing_urls or not date or
                not 0<=(day-date).days<=RECENT_MAX_DAYS or
                r.get("article_retrieval_status")!="FETCHED" or
                r.get("manufacturing_expansion_explicit")!="True"):
            counts["feddev_all40_not_fresh_or_duplicate"]+=1
            continue
        stage=r.get("procurement_stage") or "TIMING_UNKNOWN_REQUIRES_VERIFICATION"
        row=_base(lane="EQUIPMENT_INTELLIGENCE",
            city=r.get("city_mentioned_unverified") or "Ontario (site unverified)",
            address_or_company_site_unverified="",
            project_or_company=r.get("company_identified") or r.get("headline",""),
            source_project_id="FEDDEV_ALL40:"+str(r.get("feed_position","")),
            scope=r.get("equipment_evidence_quote") or r.get("evidence_excerpt",""),
            source_event_date=date.isoformat(),
            source_event_date_basis=r.get("date_basis",""),
            radar_first_observed=r.get("first_seen_by_radar",""),
            observation="SOURCE_ANNOUNCEMENT_RESEARCH",
            company_source_claim=r.get("company_identified",""),
            source_url=url,
            freshness_class="RECENT_PUBLISHER_DATED_FEDDEV_RESEARCH_NOT_PURCHASE",
            decision=("COMPLETED_OR_AWARDED_RESEARCH_ONLY"
                      if "COMPLETED" in stage or "ALREADY_AWARDED" in stage
                      else "FUTURE_EQUIPMENT_RESEARCH_PROCUREMENT_UNVERIFIED"),
            next_verification_action="Verify company legal name, plant location, specific unawarded machinery and official purchasing contact.")
        row["stage"]=stage
        recent_equipment.append(row)
        existing_urls.add(url)
    # Environment/funding data is separate; no reuse of an old funding
    # agreement as a 'new' equipment disclosure.
    for r in _read(root/EQUIPMENT):
        counts["equipment_input"]+=1
        scope=str(r.get("equipment_or_scope") or "").strip()
        name=str(r.get("company") or "").strip()
        city=str(r.get("municipality") or "").strip()
        date=_date(r.get("source_date"))
        if not name or not scope or not INDUSTRIAL.search(scope):
            counts["equipment_insufficient_scope"]+=1
            continue
        source_type=str(r.get("source_type") or "")
        freshness=("RECENT_SOURCE_EVENT_NOT_PUBLICATION_PROOF"
                   if date and 0<=(day-date).days<=RECENT_MAX_DAYS
                   else "OLD_OR_UNDATED_EQUIPMENT_NOTICE_WATCHLIST")
        row=_base(lane="EQUIPMENT_INTELLIGENCE",city=city,
            address_or_company_site_unverified=r.get("physical_project_address_unverified",""),
            project_or_company=name,source_project_id=source_type,
            scope=scope[:850],source_event_date=date.isoformat() if date else "",
            source_event_date_basis=r.get("source_date_basis",""),
            company_source_claim=name,
            public_business_email_unverified_for_purchasing=r.get("contact_email_verified",""),
            source_url=_url(r.get("source_url")),
            freshness_class=freshness,decision="RESEARCH_ONLY",
            next_verification_action="Verify first equipment announcement, installation site, vendor selection and purchasing contact.")
        if freshness=="RECENT_SOURCE_EVENT_NOT_PUBLICATION_PROOF":
            recent_equipment.append(row)
        else:
            older.append(row)
    # The funding snapshot is a historical research register. Keep records in
    # the watchlist; agreement dates must not create fresh equipment leads.
    for r in _read(root/FEDERAL):
        counts["federal_top20_old_research"]+=1
        older.append(_base(lane="EQUIPMENT_INTELLIGENCE",
            city=r.get("recipient_city_not_project_site",""),
            project_or_company=r.get("recipient",""),
            source_project_id=r.get("funding_record_id",""),
            scope=r.get("evidence_scope",""),
            source_event_date=r.get("agreement_date_not_publication",""),
            source_event_date_basis="FEDERAL_AGREEMENT_DATE_NOT_PUBLICATION",
            company_source_claim=r.get("recipient",""),
            freshness_class="FUNDING_AGREEMENT_WATCHLIST_NOT_NEW_EQUIPMENT_DISCLOSURE",
            decision="RESEARCH_ONLY",
            next_verification_action="Find independent current equipment procurement or official announcement; agreement date is not publication."))
    # Prefer first observations to material changes. Never pad with old projects.
    recent_general.sort(key=lambda r:(
        0 if r["observation"]=="FIRST_OBSERVED" else 1,
        0 if INDUSTRIAL.search(r["scope"]) else 1,
        r["source_event_date"],r["city"],r["source_project_id"]))
    # Remove equipment duplicates by source link + company before selection.
    uniq={}
    for r in recent_equipment:
        key=(r["company_source_claim"].casefold(),r["source_url"])
        uniq.setdefault(key,r)
    recent_equipment=sorted(uniq.values(),key=lambda r:(
        r["source_event_date"],r["city"],r["project_or_company"]),reverse=True)
    for filename,items in ((GENERAL_TOP,recent_general[:10]),
                           (EQUIPMENT_TOP,recent_equipment[:10]),
                           (WATCHLIST,older)):
        for i,item in enumerate(items,1):
            item["rank"]=i
        _write(root/filename,items)
    result={
        "status":"FRESHNESS_FIRST_DAILY_RESEARCH_ONLY",
        "run_date":day.isoformat(),
        "daily_input_source":daily_path.name,
        "cross_city_reconciliation_used":daily_path.name==UNIFIED_DAILY,
        "general_recent_source_event_candidates":len(recent_general),
        "general_top10_count":min(10,len(recent_general)),
        "equipment_recent_source_event_candidates":len(recent_equipment),
        "equipment_top10_count":min(10,len(recent_equipment)),
        "older_watchlist_count":len(older),
        "verified_first_publications":0,
        "verified_buyers":0,"verified_open_supplier_contracts":0,
        "selection_window_days_inclusive":3,
        "source_event_not_first_publication":True,
        "previously_reported_history_coverage":"ONLY_REGISTERED_LOCAL_HISTORY_AND_SEED; EXTERNAL_REPORTS_NOT_AUTOMATICALLY_SYNCED",
        "ai_research_applied_to_this_shortlist":False,
        "no_paid_calls":True,
        "no_unverified_older_project_padding":True,
        "counts":dict(counts),
        "outputs":[GENERAL_TOP,EQUIPMENT_TOP,WATCHLIST],
    }
    (root/STATUS).write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results",required=True)
    p.add_argument("--as-of",default=None)
    args=p.parse_args()
    print(json.dumps(run(args.results,today=args.as_of),indent=2))

if __name__=="__main__":main()
