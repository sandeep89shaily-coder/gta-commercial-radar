"""Create customer-product *internal demonstration*, never external sales collateral.

Combines individually sourced Hamilton and Markham investigation cases into
readable evidence dossiers. Names are project applicants/site operators, not
automatically verified purchasing decision-makers. No emails sent, AI called
or private personal data obtained.
"""
from __future__ import annotations
import argparse
import html
import json
from pathlib import Path
from urllib.parse import urlparse

def safe_link(value):
    p=urlparse(str(value or ""))
    if p.scheme!="https" or not p.hostname or p.username or p.password:
        return ""
    return str(value)

def read_cases(hamilton_path,consultation_path,markham_path):
    company=json.loads(Path(hamilton_path).read_text(encoding="utf-8"))["entries"]
    consulted=json.loads(Path(consultation_path).read_text(encoding="utf-8"))["records"]
    markham=json.loads(Path(markham_path).read_text(encoding="utf-8"))["cases"]
    cases=[]
    for x in company:
        cases.append({
            "key":x["id"],"region":"HAMILTON","location":x["site"],
            "project":x["organization"],
            "scope":x["project_summary"],
            "published_role":x["company_role"],
            "source_type":x["lane"],
            "source_date":x.get("published_date") or "UNKNOWN",
            "date_basis":x["published_date_type"],
            "sources":[x.get("project_evidence_url",""),x.get("organization_corroboration_url",""),
                       x.get("contact_evidence_url","")],
            "contact_channel":x.get("public_business_contact",""),
            "contact_status":x.get("contact_role",""),
            "vendor_state":x["vendor_selection_status"],
            "buyer_state":x["purchasing_decision_maker"],
            "next_step":x["next_verification"],"procurement_status":x["contract_availability"],
            "lead_status":"NOT_SALE_READY_RESEARCH_ONLY"
        })
    for x in consulted:
        cases.append({
            "key":"HAMILTON-"+x["file_number"],"region":"HAMILTON",
            "location":x["location"],"project":x.get("related_organization") or "UNKNOWN",
            "scope":x["municipal_description"],
            "published_role":x["org_relation"],"source_type":"FORMAL_CONSULTATION",
            "source_date":"UNKNOWN","date_basis":"FILE_YEAR_ONLY_NOT_PUBLICATION_DATE",
            "sources":[x.get("organization_source",""),x.get("public_contact_source",""),
                       x.get("site_property_source",""),x.get("stage_evidence_url","")],
            "contact_channel":x.get("public_contact_route",""),
            "contact_status":"BUSINESS_GENERAL_ROUTE_NOT_PROCUREMENT",
            "vendor_state":x.get("procurement") or "UNKNOWN",
            "buyer_state":"UNVERIFIED","next_step":x["next"],
            "procurement_status":"UNKNOWN",
            "lead_status":"REVIEW_LATE_STAGE" if x.get("priority")=="DEPRIORITIZE_LATE_STAGE"
                        else "NOT_SALE_READY_RESEARCH_ONLY"
        })
    for x in markham:
        cases.append({
            "key":"MARKHAM-"+x["file_number"],"region":"MARKHAM","location":x["site"],
            "project":x["published_applicant"],"scope":x["proposal_use"],
            "published_role":"PUBLISHED_APPLICATION_ENTITY_BUYER_NOT_VERIFIED",
            "source_type":x["review_lane"],
            "source_date":x["circulation_date"],
            "date_basis":"CIRCULATION_DATE_NOT_FIRST_PUBLIC_POSTED",
            "sources":[x.get("origin_pdf_url","")],
            "contact_channel":x["public_contact"],
            "contact_status":"NO_VERIFIED_PROCUREMENT_CHANNEL",
            "vendor_state":x["procurement"],"buyer_state":x["buyer_role"],
            "next_step":x["next"],"procurement_status":"UNKNOWN",
            "lead_status":"NOT_SALE_READY_RESEARCH_ONLY"
        })
    if not cases:raise RuntimeError("No cases")
    if any(x["lead_status"]=="VERIFIED_SALE_READY" for x in cases):
        raise RuntimeError("Cannot certify records without verified bidding and buyer evidence")
    return cases

def render(cases):
    esc=lambda x:html.escape(str(x or ""),quote=True)
    def row(c):
        links=[u for u in c["sources"] if safe_link(u)]
        refs=" ".join('<a href="'+esc(url)+'" rel="noopener noreferrer">'+
            esc(urlparse(url).hostname)+'</a>' for url in list(dict.fromkeys(links))[:4])
        return f"""<article class="case">
<h2>{esc(c['project'])} <small>{esc(c['location'])}</small></h2>
<p><strong>Scope:</strong> {esc(c['scope'])}</p>
<p><strong>Evidence role:</strong> {esc(c['published_role'])}</p>
<p><strong>Source timing:</strong> {esc(c['source_date'])} ({esc(c['date_basis'])})</p>
<p><strong>General contact:</strong> {esc(c['contact_channel'])} — {esc(c['contact_status'])}</p>
<p><strong>Procurement:</strong> {esc(c['procurement_status'])}; <strong>Vendor selection:</strong> {esc(c['vendor_state'])}; <strong>Buyer:</strong> {esc(c['buyer_state'])}</p>
<p class="warning">RESEARCH ONLY — NOT A VERIFIED OPEN CONTRACT</p>
<p><strong>Next evidence needed:</strong> {esc(c['next_step'])}</p>
<p class="sources">Original sources: {refs or 'No independent URL recorded for this row'}</p>
</article>"""
    cases=sorted(cases,key=lambda c:(c["region"],c["key"]))
    title="GTA Commercial Radar | Internal Evidence Dossiers"
    header=f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{font-family:Arial,sans-serif;max-width:1100px;margin:36px auto;padding:0 20px;color:#17283b;background:#f7f9fc}}
h1{{font-size:29px}}.lead{{line-height:1.55}}.summary{{border:1px solid #d7dee7;border-radius:10px;padding:16px;background:#fff}}
.case{{background:#fff;border:1px solid #d9e1ea;border-radius:10px;margin:18px 0;padding:18px;line-height:1.5}}
.case h2{{font-size:19px;margin:0 0 8px}}small{{font-weight:normal;color:#52657a;display:block;margin-top:5px}}
p{{margin:7px 0}}.warning{{font-weight:bold;color:#9a440d}}.sources{{font-size:13px;overflow-wrap:anywhere}}a{{color:#0755a2;margin-right:8px}}
footer{{margin:28px 0;font-size:13px;color:#51647a}}</style></head><body>
<h1>{title}</h1><div class="summary"><p class="lead">This is an <strong>internal prototype</strong> to test
whether original public documents can become usable supplier intelligence. It is not a
lead-sales brochure and must not be emailed as evidence of available contracts.</p>
<p><strong>Cases with published project evidence:</strong> {len(cases)}.
<strong>Independently verified purchasing decision-makers:</strong> 0.
<strong>Verified currently open private work packages:</strong> 0.
<strong>Customer-tested paid pilots:</strong> not established.</p>
<p>Application receipt, circulation date, first public posting and Radar first observed date
are not interchangeable. Company sales or commercial leasing contacts are not the
decision-maker for every project.</p></div>
"""
    return header+"".join(row(c) for c in cases)+"""<footer>
Research snapshot: 2026-10-24. Real procurement verification, current-stage
confirmation and source licensing checks are still necessary before selling a lead.
No messages sent. No DeepSeek used. V8 remains unchanged.
</footer></body></html>"""

def run(out_dir="GTA_RADAR_RESULTS",
    company="research/hamilton_public_business_evidence_20261024.json",
    consultation="research/hamilton_formal_consultation_followups_20261024.json",
    markham="research/markham_2026_10_circulation_review.json"):
    items=read_cases(company,consultation,markham)
    folder=Path(out_dir);folder.mkdir(parents=True,exist_ok=True)
    path=folder/"GTA_RADAR_INTERNAL_EVIDENCE_DOSSIERS.html"
    path.write_text(render(items),encoding="utf-8")
    metrics=dict(research_cases=len(items),
        verified_purchasing_decision_makers=0,
        verified_open_private_work_packages=0,
        proven_paying_pilots=0,
        created_from="2026-10-24 offline manually sourced investigations",
        external_distribution_approved=False)
    (folder/"GTA_RADAR_INTERNAL_QUALIFICATION_SCORECARD.json").write_text(
        json.dumps(metrics,indent=2)+"\n",encoding="utf-8")
    print("Internal evidence dossiers",len(items),"| verified open private packages 0")
    return 0

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir",default="GTA_RADAR_RESULTS")
    a=p.parse_args();raise SystemExit(run(a.output_dir))
