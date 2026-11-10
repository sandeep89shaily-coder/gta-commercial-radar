"""GTA Radar's evidence-based official municipal source access recovery worklist.

No emails are sent. No blocked ArcGIS access is bypassed. Every normal daily
run emits a concise file-by-file request packet for municipalities without
verified automated application-level collection. This is a *remediation*
worklist, not a lead generator or a source coverage score.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

CONTACTS = {
    "Vaughan": {
        "email": "developmentplanning@vaughan.ca",
        "source": "https://www.vaughan.ca/about-city-vaughan/departments/development-and-parks-planning",
        "blocked": "City public planning notices require a permitted feed or city-approved export; the automated HTTP collector has returned HTTP 403.",
        "requested": "Current public development applications and notice records with City file number, site address, application type, status, project summary, applicant organization where publishable, and the original public notice/posting date.",
        "option": "City-approved PLANit/planning application data feed, downloadable official CSV, public notification email registry, or documented permitted repeat-access method. York Region application data is a separate regional review source, not an exact substitute for municipal PLANit.",
    },
    "Kitchener": {
        "email": "gis@kitchener.ca",
        "source": "https://www.kitchener.ca/council-and-city-administration/data-and-maps/open-data/",
        "blocked": "City Planning Applications Active ArcGIS layer exposes file IDs and named applicant/owner fields, but Radar's policy-aware automated queries have been robots-denied.",
        "requested": "Official Planning Applications Active records with APPLICATION_NO, ADDRESS, DESCRIPTION, APPLICANT, PROPERTY_OWNER, STATUS, FOLDERTYPE, ISSUED_BY, INDATE and original public notice date if available.",
        "option": "A City GeoHub CSV download, approved recurring CSV/GeoJSON export or documented ArcGIS REST API query access consistent with robots policy and open-data licence.",
    },
    "Richmond Hill": {
        "email": "planning@richmondhill.ca",
        "source": "https://www.richmondhill.ca/en/learn-more/Planning-Development.aspx",
        "blocked": "Official GIS development application map has file numbers; policy-aware automated ArcGIS access denied.",
        "requested": "Published active development applications with FILENUMBER, ADDRESS, DESCRIPTIONOFAPPLICATION, OWNER, APPLICATIONTYPE, STATUS, and an explicit posting/change date where available.",
        "option": "Publisher-approved CSV/GeoJSON download, permitted API/FeatureServer endpoint, or an officially supplied recurring export.",
    },
    "Newmarket": {
        "email": "planning@newmarket.ca",
        "source": "https://www.newmarket.ca/business-development/development-planning/development-applications/current-applications",
        "blocked": "Official active development ArcGIS layer exposes FILE_NUM but policy-aware automated ArcGIS access denied.",
        "requested": "Current application records with FILE_NUM, LOCATION, DESCRIPTION, OWNER, APP_TYPE, APP_STATUS, PROPOSE_LAND_USE, and the original notice/posting date if published.",
        "option": "Permitted official public data export from Open Newmarket, a compliant feed, or a publisher-provided recurring CSV.",
    },
    "Innisfil": {
        "email": "planningservices@innisfil.ca",
        "source": "https://www.innisfil.ca/building-development/planning-development/proposed-developments",
        "blocked": "The proposed-developments page lists projects and links to an engagement platform; no verified application-level feed has been identified.",
        "requested": "Current planning application register listing file number, site address, owner/applicant when publicly disclosable, application type, status, summary and original publication date.",
        "option": "A public per-application CSV/Excel/GIS export or an authorized recurring municipal planning register.",
    },
    "New Tecumseth": {
        "email": "planning@newtecumseth.ca",
        "source": "https://www.newtecumseth.ca/build-here/development/proposed-developments/",
        "blocked": "Official planning-notice detail pages link to full-notice PDF URLs that returned HTTP 404 in live checks.",
        "requested": "Accessible current Notice of Complete Application records and PDFs, with File No., site address, application type, public notice posting date, applicant and proposal summary.",
        "option": "Corrected official PDF links, official notice archive, public CSV export, or a permitted RSS/API feed.",
    },
}
CSV = "GTA_RADAR_GGH_SOURCE_ACCESS_REQUESTS.csv"
MARKDOWN = "GTA_RADAR_GGH_SOURCE_ACCESS_REQUESTS.md"
STATUS = "GTA_RADAR_GGH_SOURCE_ACCESS_RECOVERY_STATUS.json"
FIELDS = ("municipality","recipient","official_source","current_blocker",
          "request_fields","acceptable_access_methods","automated_status",
          "assisted_export_status","action","subject","email_body")
GIS_STATUS = "GTA_RADAR_GGH_OFFICIAL_GIS_STATUS.json"
GGH_STATUS = "GTA_RADAR_GGH_EXPANSION_SOURCE_STATUS.json"
EXPORT_STATUS = "GTA_RADAR_OFFICIAL_CSV_IMPORT_STATUS.json"
OTHER_GIS_STATUS = "GTA_RADAR_ADDITIONAL_CITY_GIS_STATUS.json"
FIVE_CITY_STATUS = "GTA_RADAR_FIVE_CITY_RECOVERY_STATUS.json"


def _read(path):
    try:
        value=json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value,dict) else {}
    except (ValueError,OSError):
        return {}


def _index(report, *, name="city"):
    return {r.get(name):r for r in report.get("source_status",[])
            if isinstance(r,dict) and r.get(name)}


def _email(city,data):
    return (
        "Hello Planning/Open Data team,\n\n"
        "I am working with publicly available municipal development and planning"
        " application data and am trying to access the source in a permitted,"
        " machine-readable format. I have not automated access to any restricted"
        " source endpoints.\n\n"
        f"Could you advise whether the Town/City can provide the following"
        f" publicly disclosable information for {city}:\n"
        f"{data['requested']}\n\n"
        f"An ideal option would be: {data['option']}\n\n"
        "If an official source is already available, please provide its public"
        " URL, download instructions, permitted refresh frequency and any"
        " reuse/license terms. If a published export or corrected notice link"
        " is not available, could you direct me to the appropriate open-data or"
        " records contact and explain the process or applicable fees?\n\n"
        "I only need published public planning metadata; no private applicant"
        " contact details or restricted submissions are requested.\n\n"
        "Thank you."
    )


def run(results, *, today=None):
    root=Path(results)
    root.mkdir(parents=True,exist_ok=True)
    run_date=(today or dt.date.today()).isoformat()
    gis=_index(_read(root/GIS_STATUS))
    ggh=_index(_read(root/GGH_STATUS))
    exports=_index(_read(root/EXPORT_STATUS))
    other_gis=_index(_read(root/OTHER_GIS_STATUS))
    five_city=_index(_read(root/FIVE_CITY_STATUS))
    rows=[]
    for city,data in CONTACTS.items():
        # Keep live official source observations distinct from assisted
        # exports; neither means a buyer or citywide coverage is verified.
        if city=="Kitchener":
            auto=other_gis.get(city,{})
            state=auto.get("status","NO_LIVE_STATUS")
            count=(int(auto.get("commercial_candidates",0) or 0)
                   if state in ("BASELINE_COMPLETE","COLLECTED") else 0)
        elif city=="Vaughan":
            # This source status may be from the preceding manual run,
            # because five-city collection runs after this request packet.
            auto=five_city.get(city,{})
            state=auto.get("status","NO_LIVE_STATUS")
            count=(int(auto.get("application_id_rows_this_stage",0) or 0)
                   if auto.get("automated_source_recovered_this_stage") else 0)
        else:
            auto=gis.get(city) if city in ("Richmond Hill","Newmarket") else ggh.get(city)
            state=(auto or {}).get("state","NO_LIVE_STATUS")
            count=int((auto or {}).get("application_id_rows",0) or 0)
        e=exports.get(city,{})
        assisted=e.get("status","MISSING_AUTHORIZED_EXPORT")
        need="REVIEW_SOURCE_ACCESS_AND_REQUEST_PERMITTED_EXPORT"
        if count and state in ("BASELINE_COMPLETE","COLLECTED","OFFICIAL_NOTICE_COLLECTION"):
            need="VERIFY_COVERAGE_AND_FIRST_PUBLICATION_DATES"
        elif assisted.startswith("ASSISTED_EXPORT"):
            need="VALIDATE_PUBLISHER_PROVENANCE_AND_REQUEST_RECURRING_FEED"
        rows.append({
            "municipality":city,
            "recipient":data["email"],
            "official_source":data["source"],
            "current_blocker":data["blocked"],
            "request_fields":data["requested"],
            "acceptable_access_methods":data["option"],
            "automated_status":f"{state}; extracted_application_ids={count}",
            "assisted_export_status":assisted,
            "action":need,
            "subject":f"Request for permitted public planning-application data feed — {city}",
            "email_body":_email(city,data),
        })
    with (root/CSV).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS,extrasaction="ignore")
        w.writeheader()
        for row in rows:
            # CSV injection protection, without mangling multiline emails.
            w.writerow({k:("'"+v if isinstance(v,str) and v.startswith(("=","+","-","@")) else v)
                        for k,v in row.items() if k in FIELDS})
    lines=[
        "# GGH official source access recovery — "+run_date,
        "",
        "These are unsent municipal requests. Radar has not contacted the",
        "municipalities and does not assume access permission or citywide coverage.",
        "An existing ArcGIS source blocked by publisher policy must not be bypassed.",
        "",
    ]
    for row in rows:
        lines.extend([
            "## "+row["municipality"],"",
            "**Recipient:** "+row["recipient"],
            "**Official source:** "+row["official_source"],
            "**Automated status:** "+row["automated_status"],
            "**Assisted export:** "+row["assisted_export_status"],
            "**Next action:** "+row["action"],"",
            "**Subject:** "+row["subject"],"",
            row["email_body"],"","---","",
        ])
    (root/MARKDOWN).write_text("\n".join(lines),encoding="utf-8")
    audit={
        "municipalities":len(rows),
        "ready_to_send_requests":len(rows),
        "emails_sent":0,
        "automated_access_granted_by_municipality":0,
        "municipal_replies_received":0,
        "source_status_read":{GIS_STATUS:bool(gis),GGH_STATUS:bool(ggh),
                              EXPORT_STATUS:bool(exports),
                              OTHER_GIS_STATUS:bool(other_gis),
                              FIVE_CITY_STATUS:bool(five_city)},
        "request_csv":str(root/CSV),"request_markdown":str(root/MARKDOWN),
        "warning":"This is an unsent request packet. Publisher approval, actual application access, source authenticity, and citywide coverage are not established.",
    }
    (root/STATUS).write_text(json.dumps(audit,indent=2),encoding="utf-8")
    return audit
