"""Produce a human project-verification list from genuine new/changed Radar records.

This is NOT a verified buyer/supplier list. It displays source-linked DeepSeek
public contact hints alongside original project information. This module
makes no network, AI or contact enrichment calls of its own.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,html,json
from pathlib import Path
from urllib.parse import urlparse,quote_plus
from gta_supplier_scope import classify
from gta_freshness import assess as freshness_assess

SOURCE="GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv"
AI_SOURCE="GTA_RADAR_V8_INVESTIGATIONS.csv"
OUTPUT="GTA_RADAR_PROJECTS_TO_VERIFY.csv"
HTML="GTA_RADAR_PROJECTS_TO_VERIFY.html"
SUMMARY="GTA_RADAR_PROJECTS_TO_VERIFY_STATUS.json"
SUPPLIER_MATCH_FIELDS=("observation","project_id","city","address",
                       "source_description","source_url","local_source_status",
                       "supplier_family","supplier_category","match_tier",
                       "likely_service_phase","scope_phrase","qualification")
FIELDS=("observation","project_id","city","address","source_description",
        "source_record_date","date_basis","radar_first_seen","freshness_band",
        "source_age_days","freshness_date_basis","changed_fields","local_source_status",
        "source_url","deepseek_initial_status","deepseek_initial_queries",
        "deepseek_checked_on","deepseek_project_stage_hint",
        "deepseek_corroborating_urls","organization_hint_unverified",
        "public_business_contact_hint_unverified","public_contact_source_url",
        "contact_hint_status","supplier_scope_linked","supplier_possible_project_services",
        "supplier_possible_operations_services","supplier_match_status",
        "manual_project_verification","manual_notes")

def rows_of(file):
    if not Path(file).is_file():
        return []
    with Path(file).open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def _https(url):
    try:
        p=urlparse(str(url or ""))
        return p.scheme=="https" and bool(p.hostname) and not p.username and not p.password
    except ValueError:
        return False

def build(results,*,today=None):
    root=Path(results)
    if not (root/SOURCE).is_file():
        raise FileNotFoundError("Missing "+SOURCE+"; live collection must run first.")
    daily=rows_of(root/SOURCE)
    # Historical AI notes are not assumed to be from the current collection.
    recent={}
    for item in rows_of(root/AI_SOURCE):
        pid=str(item.get("project_id") or "").strip()
        if pid:
            recent[pid]=item
    today=(today or dt.date.today()).isoformat()
    selected=[];seen=set()
    for source in daily:
        pid=str(source.get("project_id") or "").strip()
        if not pid or pid in seen or source.get("observation") not in ("FIRST_OBSERVED","RECORD_CHANGED"):
            continue
        seen.add(pid)
        ai=recent.get(pid,{})
        checked=str(ai.get("investigated_local_date") or "")[:10]
        # AI output is shown only if its *recorded execution date* is today.
        # Older AI work must not be silently passed off as a fresh query.
        fresh=bool(checked==today and str(ai.get("api_attempted") or "").upper()=="YES")
        status=str(ai.get("status") or "") if fresh else "NOT_QUERIED_THIS_RUN"
        source_url=str(source.get("record_source_url") or "").strip()
        if not _https(source_url):source_url=""
        corroboration=str(ai.get("source_urls") or "") if fresh else ""
        # Preserve initial DeepSeek public business contact research as hints.
        # A candidate contact does NOT establish buying authority or award status.
        name=(str(ai.get("operator") or ai.get("related_company") or
                  ai.get("official_company") or "").strip() if fresh else "")
        contact=(str(ai.get("contact") or ai.get("related_company_contact") or "").strip()
                 if fresh else "")
        contact_source=(str(ai.get("contact_source_url") or ai.get("related_company_contact_url") or "").strip()
                        if fresh else "")
        if not _https(contact_source):
            contact_source=""
        if not contact_source:
            contact=""  # Never display an unsupported AI-guessed contact.
        contact_status=("PUBLIC_SOURCE_CONTACT_HINT_REVIEW_REQUIRED" if contact else
                        "NO_SOURCE_BACKED_BUSINESS_CONTACT")
        supplier_matches=classify(source.get("description",""))
        tiers=lambda tier: " | ".join(x["supplier_category"] for x in supplier_matches
                                      if x["match_tier"]==tier)
        freshness=freshness_assess(source,today)
        selected.append({
            "observation":source["observation"],"project_id":pid,
            "city":source.get("city",""),"address":source.get("address",""),
            "source_description":source.get("description",""),
            "source_record_date":source.get("source_record_date",""),
            "date_basis":source.get("date_basis",""),
            "radar_first_seen":source.get("first_seen_local",""),
            "freshness_band":freshness["freshness_band"],
            "source_age_days":freshness["source_age_days"],
            "freshness_date_basis":freshness["freshness_date_basis"],
            "changed_fields":source.get("changed_fields",""),
            "local_source_status":source.get("current_source_status",""),
            "source_url":source_url,
            "deepseek_initial_status":status,
            "deepseek_initial_queries":str(ai.get("native_searches") or "0") if fresh else "0",
            "deepseek_checked_on":checked if fresh else "",
            "deepseek_project_stage_hint":str(ai.get("project_stage") or "") if fresh else "",
            "deepseek_corroborating_urls":corroboration,
            "organization_hint_unverified":name,
            "public_business_contact_hint_unverified":contact,
            "public_contact_source_url":contact_source,
            "contact_hint_status":contact_status,
            "supplier_scope_linked":tiers("SCOPE_LINKED"),
            "supplier_possible_project_services":tiers("POSSIBLE_PROJECT_SERVICE"),
            "supplier_possible_operations_services":tiers("POSSIBLE_OPERATIONS_SERVICE"),
            "supplier_match_status":"UNVERIFIED_SUGGESTIONS" if supplier_matches else "INSUFFICIENT_SCOPE",
            "manual_project_verification":"","manual_notes":"",
        })
    bands={"SOURCE_DATED_0_7_DAYS":0,"SOURCE_DATED_8_30_DAYS":1,
           "SOURCE_DATED_31_90_DAYS":2,"OLDER_PROJECT_SCOPE_CHANGED_REVIEW":3,
           "HISTORICAL_SOURCE_DATE":4,"SOURCE_DATE_UNKNOWN":5}
    selected.sort(key=lambda x:(bands.get(x["freshness_band"],6),
         x["city"],x["address"],x["project_id"]))
    root.mkdir(parents=True,exist_ok=True)
    # Unique dated files preserve any notes the owner adds to previous lists.
    suffix=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    csv_name="GTA_RADAR_PROJECTS_TO_VERIFY_"+suffix+".csv"
    html_name="GTA_RADAR_PROJECTS_TO_VERIFY_"+suffix+".html"
    supplier_name="GTA_RADAR_SUPPLIER_MATCHES_"+suffix+".csv"
    supplier_rows=[]
    for item in selected:
        for match in classify(item["source_description"]):
            supplier_rows.append({
                **{field:item.get(field,"") for field in
                   ("observation","project_id","city","address","source_description",
                    "source_url","local_source_status")},**match})
    with (root/supplier_name).open("w",encoding="utf-8-sig",newline="") as output:
        writer=csv.DictWriter(output,fieldnames=SUPPLIER_MATCH_FIELDS)
        writer.writeheader()
        writer.writerows(supplier_rows)
    with (root/csv_name).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(selected)
    esc=lambda value:html.escape(str(value or ""),quote=True)
    page=["<!doctype html><html><head><meta charset='utf-8'><title>GTA Radar manual project list</title>",
          "<style>body{font:15px Segoe UI,Arial,sans-serif;max-width:1100px;margin:28px auto;padding:0 20px;background:#fafafa;color:#222}article{background:white;border:1px solid #ddd;border-radius:8px;margin:12px 0;padding:15px}small{color:#555}a{color:#175ba2}</style></head><body>",
          "<h1>GTA Radar — projects to verify (freshness-first)</h1>",
          "<p>Ranked by source-date freshness, NOT the date Radar noticed the record. "
          "A source date may be a filing or status date rather than first publication. "
          "Old or undated projects remain visible for manual verification. "
          "Supplier categories are unverified fits, NOT confirmed bid packages, buyers, suppliers, needs or available contracts.</p>",
          "<p><a href='"+csv_name+"'>Download review list (CSV)</a> · <a href='"+supplier_name+"'>Download supplier-sector matches (CSV)</a> · "+str(len(selected))+" records this run</p>"]
    for item in selected:
        page.extend(["<article><h3>"+esc(item["address"] or item["project_id"])+"</h3>",
                     "<p>"+esc(item["source_description"])+"</p>",
                     "<small>"+esc(item["observation"])+" | "+esc(item["city"])+
                     " | source date: "+esc(item["source_record_date"] or "unknown")+
                     " | freshness: "+esc(item["freshness_band"])+
                     " | basis: "+esc(item["freshness_date_basis"])+
                     " | local status: "+esc(item["local_source_status"] or "unknown")+"</small>",
                     "<p>DeepSeek initial screening: "+esc(item["deepseek_initial_status"])+
                     " | project stage (AI hint): "+esc(item["deepseek_project_stage_hint"] or "not assessed")+"</p>",
                     "<p>Possible organization (unverified): "+esc(item["organization_hint_unverified"] or "not identified")+"</p>",
                     "<p>Public business contact hint (unverified): "+esc(item["public_business_contact_hint_unverified"] or "not found")+"</p>",
                     "<p><b>Scope-linked supplier sectors (not awarded or buyer-verified):</b> "+
                        esc(item["supplier_scope_linked"] or "Not enough scope detail")+"</p>",
                     "<p><b>Other possible project services:</b> "+
                        esc(item["supplier_possible_project_services"] or "None inferred")+"</p>",
                     "<p><b>Possible occupancy/operations services:</b> "+
                        esc(item["supplier_possible_operations_services"] or "None inferred")+"</p>",
                     "<p>Manual verification: Confirm the project, any contact, scope, timing, and supplier availability independently. No purchasing authority or supplier status is claimed.</p>"])
        if item["source_url"]:
            page.append("<a href='"+esc(item["source_url"])+"' rel='noopener noreferrer'>Open source record (verify yourself)</a>")
        if item["public_contact_source_url"]:
            page.append(" · <a href='"+esc(item["public_contact_source_url"])+"' rel='noopener noreferrer'>Public business contact source</a>")
        if item["address"] and item["city"]:
            lookup=quote_plus(item["address"]+", "+item["city"]+", Ontario")
            page.append(" · <a href='https://www.google.com/maps/search/?api=1&amp;query="+lookup+
                        "' rel='noopener noreferrer'>Open Google Maps</a>")
            page.append(" · <a href='https://www.google.com/search?q="+lookup+
                        "' rel='noopener noreferrer'>Google project search</a>")
        page.append("</article>")
    if not selected:
        page.append("<p>No first-observed or changed source records in this run. No projects invented.</p>")
    page.append("</body></html>")
    (root/html_name).write_text("".join(page),encoding="utf-8")
    summary={"generated_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
             "mode":"DISCOVERY_ONLY_MANUAL_VERIFICATION",
             "new_or_changed_source_records":len(selected),
             "source_dated_0_7_days":sum(x["freshness_band"]=="SOURCE_DATED_0_7_DAYS" for x in selected),
             "source_dated_8_30_days":sum(x["freshness_band"]=="SOURCE_DATED_8_30_DAYS" for x in selected),
             "historical_or_undated":sum(x["freshness_band"] in ("HISTORICAL_SOURCE_DATE","SOURCE_DATE_UNKNOWN") for x in selected),
             "first_observed":sum(x["observation"]=="FIRST_OBSERVED" for x in selected),
             "changed":sum(x["observation"]=="RECORD_CHANGED" for x in selected),
             "deepseek_initial_review_records":sum(x["deepseek_initial_status"]!="NOT_QUERIED_THIS_RUN" for x in selected),
             "initial_public_contact_hints":sum(bool(x["public_business_contact_hint_unverified"]) for x in selected),
             "verified_buyers_claimed":0,"supplier_packages_claimed":0,
             "supplier_sector_suggestions":len(supplier_rows),
             "supplier_projects_with_scope_matches":sum(bool(x["supplier_scope_linked"]) for x in selected),
             "supplier_matches_csv":str(root/supplier_name),
             "manual_review_csv":str(root/csv_name),"manual_review_html":str(root/html_name),
             "limitations":"New/changed means first observed/changed by Radar, not freshly announced or independently verified."}
    (root/SUMMARY).write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--results",required=True)
    args=p.parse_args()
    print(json.dumps(build(args.results),indent=2))
if __name__=="__main__":
    main()
