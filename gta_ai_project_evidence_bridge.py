"""No-cost AI review -> exact-project role, lifecycle and supplier triage bridge.

Consumes immutable source-backed research files from the existing AI harness.
Never re-runs the model, scrapes websites, writes the collector database,
deduplicates corporate entities or promotes a buyer/open contract. Every
extracted role is a *candidate* linked to an exact existing application ID.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

OUTPUT = "GTA_RADAR_AI_PROJECT_EVIDENCE_BRIDGE.json"
REVIEW_DIR = "AGENT_HARNESS_REVIEW/PROJECT_RESEARCH"
MAX_REVIEWS = 200
MAX_BYTES = 2_000_000
ROLES = {"owner": "PROPERTY_OWNER", "developer": "DEVELOPER",
         "tenant": "TENANT", "contractor": "CONTRACTOR",
         "operator": "OPERATOR"}
ROLE_TERMS = {
    "owner": ("registered owner", "owner of", "property owner", "landowner"),
    "developer": ("developer", "development by", "developed by"),
    "tenant": ("tenant", "leased to"),
    "contractor": ("contractor", "general contractor", "builder"),
    "operator": ("operator", "operated by", "operates"),
}
DENIED_NAME = {"", "unknown", "none", "n/a", "not identified", "unverified"}
IDENTITY = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,70}:[A-Za-z0-9][A-Za-z0-9_-]{4,65}$")
HASH = re.compile(r"^[a-f0-9]{64}$")
FIELD = re.compile(r'"([A-Z][A-Z0-9_]*)"\s*:\s*"((?:[^"\\]|\\.)*)"')


def _https(value):
    from urllib.parse import urlparse
    url = str(value or "")
    if len(url) > 1600:
        return ""
    try:
        u = urlparse(url)
        if u.scheme == "https" and u.hostname and not u.username and not u.password:
            return url
    except ValueError:
        pass
    return ""


def _clean(value, maximum=200):
    return " ".join(str(value or "").split())[:maximum]


def _official_fields(text, application_id):
    # ArcGIS attributes may be clipped at 2,300 characters by the native
    # DeepSeek research executor. Parse only individual field values when the
    # exact application number occurs in this same saved source excerpt.
    if not re.search(r'"APPLICATION_NUMBER"\s*:\s*"' +
                     re.escape(application_id) + r'"', text):
        return {}
    fields = {}
    for key, raw in FIELD.findall(text):
        if key in ("APPLICATION_NUMBER", "FULL_ADDRESS", "FOLDERNAME",
                   "STATUS_DESC", "STATUS_GROUP", "LATEST_MILESTONE",
                   "FOLDERDESCRIPTION", "ASSIGNEDPLANNER2", "FOLDERTYPE_DESC",
                   "LATEST_MILESTONE_DATE", "SUBMIT_DATE"):
            try:
                fields[key] = json.loads('"' + raw + '"')
            except ValueError:
                fields[key] = raw
    return fields


def _role_proof(text, name, role):
    # Exact literal quoted name in a page is NOT enough. Nearby language must
    # describe the stated role, not just a company or street-address mention.
    folded = text.casefold()
    match = re.search(re.escape(name.casefold()), folded)
    if not match:
        return ""
    before = folded[max(0, match.start()-90):match.start()]
    after = folded[match.end():match.end()+115]
    if not any(term in before or term in after for term in ROLE_TERMS[role]):
        return ""
    return _clean(text[max(0,match.start()-125):min(len(text),match.end()+165)], 340)


def _sector(description):
    body = description.casefold()
    if any(t in body for t in ("industrial", "manufactur", "warehouse",
                               "self-storage", "production", "distribution",
                               "cleanroom", "factory", "logistics")):
        return "INDUSTRIAL_OR_WAREHOUSE_RESEARCH"
    if any(t in body for t in ("hotel", "office", "retail", "restaurant",
                               "commercial", "business park")):
        return "COMMERCIAL_OR_MIXED_USE_RESEARCH"
    if any(t in body for t in ("residential", "condominium", "dwelling", "storey",
                               "rental units", "apartments", "housing")):
        return "RESIDENTIAL_DOMINANT_LOW_SUPPLIER_PRIORITY"
    return "SECTOR_UNKNOWN"


def _date(value):
    # Only official milestone timestamps are treated as source event dates,
    # never first publication or Radar first-observed dates.
    try:
        stamp = int(value)
        if 946684800000 <= stamp <= 4102444800000:
            return dt.datetime.fromtimestamp(
                stamp/1000, dt.timezone.utc).date().isoformat()
    except (ValueError, TypeError, OverflowError, OSError):
        pass
    return ""


def _review(path):
    if path.is_symlink() or path.stat().st_size > MAX_BYTES:
        return None, "UNSAFE_OR_OVERSIZED_AI_REVIEW"
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeError):
        return None, "UNREADABLE_AI_REVIEW"
    if not isinstance(entry, dict):
        return None, "AI_REVIEW_NOT_OBJECT"
    project_id = entry.get("project_id")
    if not isinstance(project_id, str) or not IDENTITY.fullmatch(project_id):
        return None, "INVALID_EXACT_PROJECT_ID"
    if not HASH.fullmatch(str(entry.get("input_hash") or "")):
        return None, "UNVERSIONED_AI_REVIEW_HELD"
    if (entry.get("research_status") != "AI_REVIEW_ONLY" or
            entry.get("qualification_status") != "RESEARCH_ONLY" or
            entry.get("sale_ready") is not False or
            not isinstance(entry.get("model_suggestions"), dict) or
            not isinstance(entry.get("sources"), list)):
        return None, "AI_REVIEW_EVIDENCE_GATE_MISSING"
    if not project_id.startswith("toronto_development_applications:"):
        # Other cities may be supported after source-specific official-ID
        # schema tests; avoid treating e.g. a municipal parcel as a permit.
        return None, "CITY_APPLICATION_ID_ADAPTER_NOT_YET_VALIDATED"
    application_id = project_id.split(":", 1)[1]
    approved_sources = []
    official = {}
    for source in entry["sources"][:20]:
        if not isinstance(source, dict):
            continue
        url = _https(source.get("url"))
        body = str(source.get("text") or "")[:12000]
        if (not url or source.get("page_identity") !=
                "EXACT_CURRENT_PERMIT_ID_IN_PAGE" or
                not re.search(r'(?<![A-Za-z0-9])' + re.escape(application_id) +
                              r'(?![A-Za-z0-9])', body, flags=re.I)):
            continue
        if source.get("kind") == "OFFICIAL_ARCGIS_ATTRIBUTES":
            attributes = _official_fields(body, application_id)
            if not attributes:
                continue
            official.update(attributes)
        approved_sources.append({"url": url, "text": body,
                                 "kind": source.get("kind")})
    if not official:
        return None, "NO_EXACT_OFFICIAL_APPLICATION_ATTRIBUTES"

    claims = []
    holds = []
    model = entry["model_suggestions"]
    for field, role in ROLES.items():
        name = _clean(model.get(field))
        if not name or name.casefold() in DENIED_NAME:
            continue
        proof = []
        for src in approved_sources:
            quote = _role_proof(src["text"], name, field)
            if quote:
                proof.append({"source_url": src["url"], "evidence_excerpt": quote})
        if not proof:
            holds.append({"reason": "ROLE_NOT_EXPLICIT_IN_EXACT_ID_SOURCE",
                          "role": role, "name": name})
            continue
        claims.append({
            "project_id": project_id, "city": "Toronto", "application_id": application_id,
            "role": role, "organization": name,
            "source_url": proof[0]["source_url"],
            "evidence_excerpt": proof[0]["evidence_excerpt"],
            "source_record_id": application_id,
            "review_only": True,
            "verified_legal_entity": False, "verified_buyer": False,
            "verified_procurement": False,
        })

    # Municipal planner is a public-government role, never an operator,
    # developer, vendor or commercial purchasing contact.
    planner = _clean(official.get("ASSIGNEDPLANNER2"))
    planner_contact = _clean(model.get("contact"))
    municipal_contact = {
        "role": "MUNICIPAL_PLANNING_REVIEWER",
        "name": planner, "source": "OFFICIAL_APPLICATION_ATTRIBUTES",
        "is_commercial_buyer": False
    } if planner and planner_contact and (
        planner_contact.casefold() == planner.casefold()) else None

    app_address = _clean(entry.get("address")).upper()
    official_address = _clean(official.get("FULL_ADDRESS") or official.get("FOLDERNAME")).upper()
    if app_address and official_address and app_address != official_address:
        holds.append({"reason": "APPLICATION_ADDRESS_VARIANT_REVIEW",
                      "candidate_address": app_address,
                      "official_address": official_address,
                      "auto_merged": False})

    status = _clean(official.get("STATUS_DESC"))
    narrative = _clean(model.get("project_stage"), 500)
    if (re.search(r"\b(approved|issued)\b", status, re.I) and
            re.search(r"(ongoing|under review|approval.*not.*confirmed|no approval)", narrative, re.I)):
        holds.append({"reason": "AI_LIFECYCLE_CONTRADICTS_OFFICIAL_STATUS",
                      "official_status": status,
                      "model_narrative": narrative, "authoritative_source": "OFFICIAL_APPLICATION_ATTRIBUTES"})
    description = _clean(official.get("FOLDERDESCRIPTION"), 1500)
    sector = _sector(description)
    if "RESIDENTIAL" in sector:
        holds.append({"reason": "RESIDENTIAL_DOMINANT_NOT_AUTO_COMMERCIAL_PRIORITY"})
    if "approved" in status.casefold() or "issued" in status.casefold():
        maturity = "POST_APPROVAL_OR_ISSUANCE_RECHECK"
    elif "review" in status.casefold():
        maturity = "PLANNING_UNDER_REVIEW"
    else:
        maturity = "UNKNOWN_NO_AWARD_INFERENCE"

    return {
        "project_id": project_id, "city": "Toronto",
        "application_id": application_id, "candidate_address": app_address,
        "official_address": official_address,
        "official_status": status, "official_milestone": _clean(official.get("LATEST_MILESTONE")),
        "official_milestone_date": _date(official.get("LATEST_MILESTONE_DATE")),
        "date_basis": "OFFICIAL_MILESTONE_NOT_PUBLICATION",
        "model_stage_claim_not_authoritative": narrative,
        "maturity_for_review": maturity, "commercial_sector_for_review": sector,
        "source_description": description,
        "selection_score": entry.get("selection_score"),
        "current_input_hash": entry["input_hash"],
        "project_source_url": _https(entry.get("source_url")),
        "claims": claims, "holds": holds,
        "municipal_contact": municipal_contact,
        "verified_buying_authority": False,
        "verified_open_supplier_package": False,
        "sale_ready": False,
    }, None


def build(results):
    root = Path(results).resolve()
    folder = root / REVIEW_DIR
    statuses = []
    projects = []
    holds = []
    if not folder.exists():
        return {"status": "NO_AI_REVIEW_FILES", "projects": [], "role_claims": [],
                "holds": [], "files_considered": 0,
                "verified_buyers": 0, "verified_open_supplier_packages": 0}
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("UNSAFE_AI_REVIEW_DIRECTORY")
    files = sorted(p for p in folder.glob("AI_PROJECT_*.json")
                   if "_EVIDENCE_" not in p.name and
                   "MANIFEST" not in p.name and "_FAILURE_" not in p.name)
    if len(files) > MAX_REVIEWS:
        raise ValueError("EXCESSIVE_AI_REVIEW_FILE_COUNT")
    # Versioned checkpoints for the same project are kept as evidence, but
    # never combined into one current lifecycle without an input-version key.
    ids, ambiguous = set(), set()
    for path in files:
        item, error = _review(path)
        if error:
            holds.append({"file": path.name, "reason": error})
            continue
        if item["project_id"] in ids:
            ambiguous.add(item["project_id"])
            holds.append({"file": path.name,
                          "reason": "MULTIPLE_REVIEW_VERSIONS_NO_CURRENT_INPUT_AUTHORITY"})
            projects = [p for p in projects if p["project_id"] != item["project_id"]]
            continue
        ids.add(item["project_id"])
        projects.append(item)
    # A later third/fourth checkpoint may never reintroduce an ambiguous ID.
    projects = [p for p in projects if p["project_id"] not in ambiguous]
    for item in projects:
        for hold in item["holds"]:
            holds.append({"project_id": item["project_id"], **hold})

    # Supplier review order is an analyst priority heuristic, not probability
    # of an unawarded package. Industrial/commercial before residential,
    # outstanding source contradictions and late approvals held for review.
    sector_order = {"INDUSTRIAL_OR_WAREHOUSE_RESEARCH": 0,
                    "COMMERCIAL_OR_MIXED_USE_RESEARCH": 1,
                    "SECTOR_UNKNOWN": 2,
                    "RESIDENTIAL_DOMINANT_LOW_SUPPLIER_PRIORITY": 3}
    projects.sort(key=lambda p: (
        sector_order[p["commercial_sector_for_review"]],
        p["maturity_for_review"] != "PLANNING_UNDER_REVIEW",
        bool(p["holds"]), p["project_id"]))
    claims = [claim for p in projects for claim in p["claims"]]
    return {
        "status": "AI_PROJECT_SOURCE_EVIDENCE_REVIEW_ONLY",
        "files_considered": len(files), "project_candidates": len(projects),
        "source_supported_role_claims_not_legal_verification": len(claims),
        "projects_with_address_or_lifecycle_conflicts": sum(any(
            x["reason"] in ("APPLICATION_ADDRESS_VARIANT_REVIEW",
                            "AI_LIFECYCLE_CONTRADICTS_OFFICIAL_STATUS")
            for x in p["holds"]) for p in projects),
        "verified_buyers": 0, "verified_open_supplier_packages": 0,
        "paid_ai_calls_by_bridge": 0,
        "warning": "Only exact-ID role excerpts qualify as source-linked review claims. "
                   "No legal identity, purchasing authority or unawarded contract is established. "
                   "Official milestone dates are not first-publication dates.",
        "projects": projects, "role_claims": claims, "holds": holds[:200],
    }


def run(results):
    root = Path(results)
    result = build(root)
    path = root / OUTPUT
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    tmp.replace(path)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    result = run(args.results)
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ("projects", "role_claims", "holds")}, indent=2))
