"""Ten evidence-labelled research dossiers from the existing V8 investigations.

Offline/read-only inputs. An incomplete dossier is NOT a verified lead.
No collectors, paid services, database writes, or production scheduler changes.
"""
from __future__ import annotations
import csv
import html
from pathlib import Path
from urllib.parse import urlparse

INPUT = "GTA_RADAR_GENUINE_OPPORTUNITY_REVIEW.csv"
OUTPUT = "GTA_RADAR_TEN_RESEARCH_DOSSIERS.html"
CSV = "GTA_RADAR_TEN_RESEARCH_DOSSIERS.csv"
FIELDS = ("project_id", "address", "city", "description", "source_id",
          "research_status", "project_verification", "operator_or_developer",
          "buyer_status", "public_contact", "contact_source_url",
          "supplier_contract_status", "opportunity_class", "source_urls",
          "missing_evidence", "next_action", "dossier_status")


def source_links(value):
    links = []
    for part in str(value or "").split(" | "):
        url = part.strip()
        p = urlparse(url)
        if p.scheme == "https" and p.hostname and not p.username and not p.password:
            if url not in links:
                links.append(url)
    return links


def pack(item):
    project = item.get("project_id", "").strip()
    verified = str(item.get("official_verification_level") or "NOT_VERIFIED").strip()
    operator = str(item.get("operator") or item.get("developer") or "").strip()
    role = str(item.get("official_company_role") or "").upper()
    if not operator and role in {"OWNER", "OPERATOR", "DEVELOPER"}:
        operator = str(item.get("official_company") or "").strip()
    contact = str(item.get("contact") or "").strip()
    contact_url = str(item.get("contact_source_url") or "").strip()
    # Never represent an unsupported contact as a verified purchasing authority.
    if not source_links(contact_url):
        contact, contact_url = "", ""
    supplier = str(item.get("supplier_contract_status") or "UNKNOWN").strip()
    links = source_links(item.get("source_urls")) + source_links(item.get("record_source_url"))
    links = list(dict.fromkeys(links))
    gaps = []
    if not links: gaps.append("NO_PUBLIC_EVIDENCE_LINK")
    if verified not in {"OFFICIAL_ID_AND_STATUS_MATCH", "COLLECTOR_SOURCE_MATCH"}:
        gaps.append("EXACT_PROJECT_VERIFICATION_NEEDED")
    if not operator: gaps.append("BUYER_OPERATOR_NOT_ESTABLISHED")
    gaps.append("PURCHASING_DECISION_MAKER_NOT_VERIFIED")
    if not contact: gaps.append("PUBLIC_COMPANY_CONTACT_NOT_VERIFIED")
    if supplier.upper() in {"", "UNKNOWN", "NOT_VERIFIED"}:
        gaps.append("SUPPLIER_SELECTION_UNKNOWN")
    return dict(project_id=project, address=item.get("address", ""),
                city=item.get("city", ""), description=item.get("description", ""),
                source_id=item.get("source_id", ""),
                research_status=item.get("research_status", ""),
                project_verification=verified,
                operator_or_developer=operator or "UNKNOWN",
                buyer_status="PURCHASING_AUTHORITY_NOT_VERIFIED",
                public_contact=contact or "UNKNOWN", contact_source_url=contact_url,
                supplier_contract_status=supplier,
                opportunity_class=item.get("opportunity_class", ""),
                source_urls=" | ".join(links), missing_evidence="; ".join(gaps),
                next_action=item.get("opportunity_next_action") or item.get("next_system_action")
                  or "Verify project identity, buyer and procurement stage",
                dossier_status="RESEARCH_ONLY_NOT_SALE_READY")


def build(root, limit=10):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    source = root / INPUT
    with source.open(encoding="utf-8-sig", newline="") as fh:
        raw = list(csv.DictReader(fh))
    # The parent report has already ranked the entire historical research output.
    # Deduplicate by project ID; do not backfill with unresearched V8 queue entries.
    seen = set()
    selected = []
    for row in raw:
        ident = str(row.get("project_id") or "").strip()
        if not ident or ident in seen:
            continue
        seen.add(ident)
        selected.append(pack(row))
        if len(selected) == limit:
            break
    csv_path = root / CSV
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(selected)
    esc = lambda value: html.escape(str(value or ""), quote=True)
    page = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
            '<title>GTA Radar — Ten Research Dossiers</title>',
            '<style>body{font:15px Arial;max-width:1000px;margin:25px auto;padding:0 15px;line-height:1.5}',
            'article{border:1px solid #ddd;border-radius:9px;padding:16px;margin:15px 0}',
            'dt{font-weight:bold}dd{margin:0 0 9px}a{overflow-wrap:anywhere}</style></head><body>',
            '<h1>GTA Radar — Ten Research Dossiers</h1>',
            '<p>Generated from existing investigations only; ' + str(len(selected)) +
            ' of maximum 10. All dossiers are research-only, not verified sales leads. '
            'Missing evidence and supplier-selection unknowns are explicit.</p>']
    labels = (("description","Project / proposed work"),
              ("source_id","Original source"), ("project_verification","Verification"),
              ("operator_or_developer","Possible operator / developer"),
              ("buyer_status","Buyer / decision maker"),
              ("public_contact","Published business contact"),
              ("supplier_contract_status","Supplier / contract status"),
              ("opportunity_class","Opportunity stage"),
              ("missing_evidence","Evidence still missing"),
              ("next_action","Next research action"))
    for idx, item in enumerate(selected, 1):
        page.append("<article><h2>" + esc(str(idx) + ". " + (item["address"] or item["project_id"])) +
                    "</h2><p>" + esc(item["city"]) + " · " + esc(item["project_id"]) + "</p><dl>")
        for key, label in labels:
            page.append("<dt>" + esc(label) + "</dt><dd>" + esc(item[key]) + "</dd>")
        page.append("</dl><p>Official evidence: ")
        for url in source_links(item["source_urls"]):
            page.append('<a rel="noopener noreferrer" href="' + esc(url) + '">' + esc(url) + "</a> ")
        page.append("</p></article>")
    if not selected:
        page.append("<p>No existing research records available. No dossiers fabricated.</p>")
    page.append("</body></html>")
    (root / OUTPUT).write_text("".join(page), encoding="utf-8")
    return {"dossiers": len(selected), "dossier_html": OUTPUT, "dossier_csv": CSV}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=Path("GTA_RADAR_RESULTS"))
    args = parser.parse_args()
    print(build(args.results_dir))
