"""Evidence-first buyer/procurement review for Radar client candidates.

Offline and read-only with respect to original sources. An analyst-provided
verification file is an assertion to review, never automatic proof of a sale.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from urllib.parse import urlparse

INPUT = "GTA_RADAR_CLIENT_FRESH_NONREPEAT_TOP_10.csv"
REVIEW = "GTA_RADAR_BUYER_PROCUREMENT_REVIEW.csv"
AUDIT = "GTA_RADAR_BUYER_PROCUREMENT_STATUS.json"
EVIDENCE = "GTA_RADAR_BUYER_EVIDENCE.csv"
FIELDS = (
    "rank", "opportunity_id", "city", "address", "project_name",
    "named_company_role_unverified", "source_url",
    "buyer_organization", "buyer_role", "buyer_evidence_url",
    "public_business_contact", "contact_role", "contact_evidence_url",
    "procurement_stage", "procurement_evidence_url",
    "review_state", "review_flags", "next_action",
)
ROLES = {"OWNER", "DEVELOPER", "TENANT", "OPERATOR", "GENERAL_CONTRACTOR", "PROCUREMENT_TEAM"}
STAGES = {"OPEN", "AWARDED", "UNKNOWN"}
REQUIRED_EVIDENCE = ("buyer_evidence_url", "contact_evidence_url", "procurement_evidence_url")


def _rows(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _http_url(value):
    try:
        uri = urlparse(str(value).strip())
        return uri.scheme.lower() in {"http", "https"} and bool(uri.netloc) and not uri.username
    except ValueError:
        return False


def _safe(value):
    value = str(value or "")
    if value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _save(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{field: _safe(row.get(field, "")) for field in fields} for row in rows])


def run(root):
    root = Path(root)
    if not root.is_dir() or not (root / INPUT).is_file():
        raise FileNotFoundError("CLIENT_FRESHNESS_SHORTLIST_REQUIRED")
    candidates = _rows(root / INPUT)
    evidence = _rows(root / EVIDENCE)
    indexed = {}
    for item in evidence:
        identity = str(item.get("opportunity_id") or "").strip()
        if identity:
            indexed.setdefault(identity, []).append(item)
    reviewed = []
    issues = []
    for candidate in candidates:
        identity = str(candidate.get("opportunity_id") or "").strip()
        matches = indexed.get(identity, [])
        # Exact ID AND site required; an address alone never identifies the buyer.
        valid = [e for e in matches
                 if str(e.get("city", "")).strip().casefold() == str(candidate.get("city", "")).strip().casefold()
                 and str(e.get("address", "")).strip().casefold() == str(candidate.get("address", "")).strip().casefold()]
        flags = []
        if len(matches) > 1 or (matches and len(valid) != 1):
            flags.append("EVIDENCE_IDENTITY_CONFLICT")
        proof = valid[0] if len(valid) == 1 and len(matches) == 1 else {}
        role = str(proof.get("buyer_role") or "").strip().upper()
        stage = str(proof.get("procurement_stage") or "UNKNOWN").strip().upper()
        if role not in ROLES and role:
            flags.append("UNRECOGNIZED_BUYER_ROLE")
        if stage not in STAGES:
            flags.append("UNRECOGNIZED_PROCUREMENT_STAGE")
            stage = "UNKNOWN"
        if proof.get("buyer_organization") and (role not in ROLES or not _http_url(proof.get("buyer_evidence_url"))):
            flags.append("BUYER_SOURCE_REQUIRED")
        if proof.get("public_business_contact") and (not proof.get("contact_role") or not _http_url(proof.get("contact_evidence_url"))):
            flags.append("CONTACT_ROLE_AND_SOURCE_REQUIRED")
        if stage != "UNKNOWN" and not _http_url(proof.get("procurement_evidence_url")):
            flags.append("PROCUREMENT_SOURCE_REQUIRED")
            stage = "UNKNOWN"
        for field in REQUIRED_EVIDENCE:
            if proof.get(field) and not _http_url(proof[field]):
                flags.append("INVALID_" + field.upper())
        buyer_ok = bool(proof.get("buyer_organization") and role in ROLES and _http_url(proof.get("buyer_evidence_url")))
        contact_ok = bool(proof.get("public_business_contact") and proof.get("contact_role") and _http_url(proof.get("contact_evidence_url")))
        stage_ok = stage in {"OPEN", "AWARDED"} and _http_url(proof.get("procurement_evidence_url"))
        if not buyer_ok: flags.append("BUYER_NOT_EVIDENCED")
        if not contact_ok: flags.append("PUBLIC_CONTACT_NOT_EVIDENCED")
        if not stage_ok: flags.append("PROCUREMENT_NOT_EVIDENCED")
        if not proof: flags.append("ORIGINAL_REVIEW_REQUIRED")
        if stage == "AWARDED": flags.append("AWARDED_NOT_OPEN")
        # Even a complete self-attested analyst row still requires independent
        # human checking of URLs and active package timing.
        review_state = "EVIDENCE_READY_FOR_INDEPENDENT_RECHECK" if not flags else "HOLD_MANUAL_VERIFICATION"
        reviewed.append({
            **{k:candidate.get(k, "") for k in ("rank","opportunity_id","city","address","project_name","named_company_role_unverified","source_url")},
            "buyer_organization":proof.get("buyer_organization", "") if buyer_ok else "",
            "buyer_role":role if buyer_ok else "",
            "buyer_evidence_url":proof.get("buyer_evidence_url", "") if buyer_ok else "",
            "public_business_contact":proof.get("public_business_contact", "") if contact_ok else "",
            "contact_role":proof.get("contact_role", "") if contact_ok else "",
            "contact_evidence_url":proof.get("contact_evidence_url", "") if contact_ok else "",
            "procurement_stage":stage if stage_ok else "UNKNOWN",
            "procurement_evidence_url":proof.get("procurement_evidence_url", "") if stage_ok else "",
            "review_state":review_state,
            "review_flags":";".join(dict.fromkeys(flags)),
            "next_action":"Independently inspect original buyer, business contact and current unawarded package evidence; never infer OPEN from permits.",
        })
        if flags: issues.append({"opportunity_id":identity,"flags":list(dict.fromkeys(flags))})
    _save(root / REVIEW, FIELDS, reviewed)
    result = {
        "status":"RESEARCH_REVIEW_ONLY_NOT_SALE_READY",
        "candidate_count":len(reviewed),
        "evidence_ready_for_independent_recheck":sum(r["review_state"]=="EVIDENCE_READY_FOR_INDEPENDENT_RECHECK" for r in reviewed),
        "independently_verified_open_packages":0,
        "customer_ready_claims":0,
        "issues":issues,
        "input_evidence_file":EVIDENCE,
        "output":REVIEW,
        "policy":"Manual evidence submissions are untrusted until independent original-source review; never automatically publish or send.",
    }
    (root / AUDIT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--results", required=True)
    args = p.parse_args()
    print(json.dumps(run(args.results), indent=2))
