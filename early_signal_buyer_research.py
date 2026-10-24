"""Evidence-gated early commercial investigation queue.

No customer details are inferred as facts. Buyer/contract procurement status stays
UNVERIFIED until independently corroborated; no paid AI calls or outreach.
"""
from __future__ import annotations
import csv
import datetime as dt
import re
from pathlib import Path

FIELDS = (
    "rank", "priority", "project_group_key", "source_id", "municipality", "stage",
    "application_id", "municipal_reference", "source_application_date",
    "first_observed_at", "days_since_application", "description", "location",
    "commercial_signal", "published_entity", "published_entity_role",
    "specific_scope_terms", "potential_service_categories",
    "source_url", "exact_source_record_url", "source_record_status", "project_identity",
    "date_integrity", "purchasing_decision_maker",
    "vendor_selection_status", "procurement_status", "verified_business_contact",
    "evidence_tier", "next_investigation", "not_sale_ready_reason"
)
SCOPES = (
    ("INDUSTRIAL_COLD_CHAIN", ("cold storage", "cold-storage", "walk-in cooler",
     "walk in cooler", "freezer", "refrigerat"), ("Industrial refrigeration", "HVAC", "Fire/life safety")),
    ("MANUFACTURING", ("manufactur", "production facility", "processing plant",
     "fabrication", "industrial addition"), ("Mechanical systems", "Industrial equipment", "Electrical")),
    ("POWER_PROCESS", ("energy-from-waste", "waste-to-energy", "power generation",
     "data center", "data centre"), ("Industrial equipment", "Electrical", "Mechanical systems")),
    ("WAREHOUSE_LOGISTICS", ("warehouse", "distribution centre", "distribution center",
     "logistics", "loading dock", "truck bay"), ("Warehouse equipment", "Security/access", "Fire/life safety")),
    ("HOSPITALITY", ("hotel", "hospitality", "restaurant"), ("HVAC", "Fire/life safety", "Security/access")),
    ("COMMERCIAL_FACILITY", ("retail", "commercial", "office", "medical clinic", "car wash"),
     ("HVAC", "Security/access", "Commercial insurance prospecting")),
)
EARLY = {"PRE_CONSULTATION", "REZONING_OPA", "REZONING"}
INACTIVE = re.compile(r"\b(?:inactive|withdrawn|cancelled|canceled|refused|rejected|abandoned|closed)\b", re.I)
REVIEW = ("MISSING_VERIFIED_PURCHASER", "PROCUREMENT_NOT_VERIFIED",
          "CONTACT_ROUTE_NOT_VERIFIED", "PROJECT_STAGE_NOT_LIVE_VERIFIED")


def _read(path):
    with Path(path).open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))


def _date(value):
    try:
        return dt.date.fromisoformat(str(value or "")[:10])
    except (ValueError,TypeError):
        return None


def _scope(description):
    t = " ".join(str(description or "").lower().split())
    match = [x for x in SCOPES if any(term in t for term in x[1])]
    categories = sorted({label for x in match for label in x[2]})
    return ";".join(x[0] for x in match), ";".join(categories)


def queue(rows, *, today=None):
    today = today or dt.datetime.now(dt.timezone.utc).date()
    seen, selected = set(), []
    for item in rows:
        if item.get("commercial_signal") not in ("POSSIBLE_COMMERCIAL","MIXED_USE_REVIEW"):
            continue
        status = str(item.get("status") or "").strip()
        if INACTIVE.search(status):
            continue
        key = str(item.get("project_group_key") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        date = _date(item.get("source_application_date"))
        days = (today-date).days if date else None
        if days is not None and (days < -7 or days > 1096):
            continue
        if days is None:
            # Undated records are kept in date-audit review, not misrepresented
            # in a new/early procurement queue.
            continue
        description = str(item.get("description") or "")
        terms, service = _scope(description)
        step = str(item.get("stage") or "")
        published_company = str(item.get("published_company") or "")
        role = str(item.get("company_role") or "UNVERIFIED_PUBLISHED_ENTITY")
        source_date_basis = str(item.get("source_date_basis") or "")
        identity = str(item.get("record_identity_confidence") or "")
        rank = (30 if days <= 90 else 20 if days <= 365 else 10)
        rank += 15 if step in EARLY else 8
        rank += 15 if terms else 0
        rank += 10 if len(description) >= 100 else 0
        rank += 5 if published_company and published_company.lower() not in ("n/a","none","unknown") else 0
        rank += 5 if item.get("application_id") and identity != "FEATURE_NOT_CONFIRMED_PROJECT" else 0
        rank -= 10 if item.get("commercial_signal") == "MIXED_USE_REVIEW" else 0
        # These are INVESTIGATION priorities, not probabilities of sale.
        priority = ("RESEARCH_FIRST" if rank >= 55 else "RESEARCH_LATER")
        next_steps = [
            "Verify exact current municipal application and its project stage",
            "Identify owner/tenant/developer and confirm who procures relevant services",
            "Verify original public company contact/procurement channel",
            "Check whether vendors have already been awarded or selected",
            "Match concrete work package to interested service provider",
        ]
        selected.append(dict(
            rank=rank, priority=priority, project_group_key=key,
            source_id=item.get("source_id",""), municipality=item.get("city",""),
            stage=step, application_id=item.get("application_id",""),
            municipal_reference=item.get("municipal_reference",""),
            source_application_date=item.get("source_application_date",""),
            first_observed_at=item.get("first_observed_at",""),
            days_since_application=days, description=description,
            location=item.get("location",""),
            commercial_signal=item.get("commercial_signal",""),
            published_entity=published_company, published_entity_role=role,
            specific_scope_terms=terms, potential_service_categories=service,
            source_url=item.get("source_url",""),
            exact_source_record_url=item.get("exact_source_record_url",""),
            source_record_status=status,
            project_identity=identity, date_integrity=source_date_basis,
            purchasing_decision_maker="UNVERIFIED",
            vendor_selection_status="UNKNOWN",
            procurement_status="UNKNOWN",
            verified_business_contact="NOT_FOUND",
            evidence_tier="MUNICIPAL_RECORD_RESEARCH_ONLY",
            next_investigation=" | ".join(next_steps),
            not_sale_ready_reason=";".join(REVIEW),
        ))
    selected.sort(key=lambda x: (-x["rank"], -( _date(x["source_application_date"]).toordinal()
                                  if _date(x["source_application_date"]) else 0),
                                  x["source_id"], x["project_group_key"]))
    return selected


def write_queue(review_csv, output_dir, *, today=None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True,exist_ok=True)
    result = queue(_read(review_csv),today=today)
    dest = output_dir/"EARLY_SIGNALS_BUYER_RESEARCH_QUEUE.csv"
    temp = dest.with_suffix(".tmp")
    with temp.open("w",encoding="utf-8-sig",newline="") as f:
        writer = csv.DictWriter(f,fieldnames=FIELDS,extrasaction="ignore")
        writer.writeheader();writer.writerows(result)
    temp.replace(dest)
    return {"investigation_candidates":len(result),"research_first":sum(
        x["priority"]=="RESEARCH_FIRST" for x in result)}
