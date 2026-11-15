"""Evidence check for DeepSeek company-role proposals in the existing top-ten step.

The model proposes organizations from fetched official/project pages. A role
claim is saved only when the same fetched page contains the quoted wording,
the literal company name, and an explicit matching role term. Address-only
pages remain site CONTEXT, never established project roles. Even exact-ID
quotes are review candidates, not legal-identity or purchasing verification.
"""
from __future__ import annotations

import re

ROLE_WORDS = {
    "OWNER": ("registered owner", "property owner", "owner of", '"owner"', "landowner"),
    "DEVELOPER": ("developer", "developed by", "development by"),
    "TENANT": ("tenant", "leased to", "occupant"),
    "OPERATOR": ("operator", "operated by", "operates"),
    "CONTRACTOR": ("contractor", "general contractor", "builder", "construction manager"),
    "ARCHITECT": ("architect", "architectural firm"),
    "APPLICANT": ("applicant", "applicant_company", '"applicant"'),
}
BUYER_FUNCTIONS = {
    "DEVELOPER_PROCUREMENT",
    "TENANT_FACILITIES",
    "GENERAL_CONTRACTOR_BUYOUT",
    "PROPERTY_MANAGER",
    "OWNER_PROJECT_TEAM",
    "UNKNOWN",
}
MAX_ROLE_PROPOSALS = 8


def clean(value, maximum=210):
    return " ".join(str(value or "").split())[:maximum]


def check_roles(proposals, sources):
    """Return (supported source claims, rejected count) from untrusted model data.

    Exact application ID in a page means identity linkage sufficient to
    investigate a ROLE, not source evidence that a business is purchasing.
    A page that mentions only the same address may describe another project.
    """
    if not isinstance(proposals, list):
        return [], 0
    accepted = []
    rejected = 0
    used = set()
    for item in proposals[:MAX_ROLE_PROPOSALS]:
        if not isinstance(item,dict):
            rejected += 1
            continue
        role = str(item.get("role") or "").strip().upper()
        name = clean(item.get("organization"), 120)
        quote = clean(item.get("quote"), 225)
        index = item.get("source_j")
        if (role not in ROLE_WORDS or type(index) is not int or
                index < 0 or index >= len(sources) or
                not name or not quote or "@" in name or
                name.casefold() in ("unknown","n/a","none","not identified")):
            rejected += 1
            continue
        src = sources[index]
        if not isinstance(src, dict):
            rejected += 1
            continue
        proof = clean(str(src.get("role_excerpt") or "")+" "+
                      str(src.get("excerpt") or ""), 2000)
        normalized_quote = quote.casefold()
        # Search across individual source passages, not a concatenation
        # that could manufacture a quote spanning unrelated parts of a page.
        phrases = (clean(src.get("role_excerpt"), 1000),
                   clean(src.get("excerpt"), 1000))
        if (name.casefold() not in normalized_quote
                or not any(normalized_quote in passage.casefold()
                           for passage in phrases)
                or not any(word in normalized_quote for word in ROLE_WORDS[role])):
            rejected += 1
            continue
        identity = str(src.get("identity") or "")
        if identity not in ("EXACT_APPLICATION_ID_IN_FETCHED_TEXT",
                            "EXACT_OFFICIAL_ARCGIS_APPLICATION",
                            "SAME_ADDRESS_PROJECT_CONTEXT_NOT_LINKED",
                            "SAME_ADDRESS_COMPANY_CONTEXT_NOT_LINKED"):
            rejected += 1
            continue
        key = (name.casefold(),role,str(src.get("url") or ""))
        if key in used:
            continue
        used.add(key)
        exact = identity.startswith("EXACT")
        accepted.append({
            "organization": name,
            "role": role,
            "source_url": str(src.get("url") or "")[:1600],
            "evidence_quote": quote,
            "source_identity": identity,
            "evidence_level": ("EXACT_APPLICATION_ROLE_SOURCE_REVIEW_ONLY"
                               if exact else
                               "SAME_ADDRESS_SITE_CONTEXT_NOT_PROJECT_ROLE"),
            "project_role_supported_for_review": exact,
            "buyer_verified": False,
            "legal_entity_verified": False,
            "procurement_verified": False,
            "contact_verified": False,
        })
    rejected += max(0, len(proposals)-MAX_ROLE_PROPOSALS)
    return accepted, rejected


def buyer_hypothesis(value):
    """AI picks a purchasing FUNCTION only, never a claimed buyer identity."""
    if not isinstance(value, dict):
        return {"function":"UNKNOWN", "reason":"No reliable purchasing authority evidence",
                "state":"AI_HYPOTHESIS_NOT_BUYER_VERIFICATION"}
    function = str(value.get("function") or "").upper()
    if function not in BUYER_FUNCTIONS:
        function = "UNKNOWN"
    reason = clean(value.get("reason"), 160)
    if re.search(r"@|\+?\d[\d\s().-]{8,}|verified|confirmed", reason,re.I):
        reason = "Purchasing authority requires direct original-source confirmation"
    return {
        "function": function,
        "reason": reason or "Purchasing authority requires direct-source verification",
        "state":"AI_HYPOTHESIS_NOT_BUYER_VERIFICATION",
        "buyer_verified": False,
        "contact_verified": False,
    }


def check_site_mentions(proposals, sources):
    """Keep source-backed co-location candidates without promoting project roles.

    A business at the same address is NOT necessarily the permit applicant,
    operator, owner, supplier, purchaser or contractor.
    """
    if not isinstance(proposals, list):
        return [], 0
    accepted, rejected, seen = [], 0, set()
    for item in proposals[:8]:
        if not isinstance(item, dict):
            rejected += 1
            continue
        name = clean(item.get("organization"), 120)
        quote = clean(item.get("quote"), 240)
        idx = item.get("source_j")
        if not name or not quote or type(idx) is not int or idx < 0 or idx >= len(sources):
            rejected += 1
            continue
        src = sources[idx]
        if not isinstance(src, dict) or src.get("identity") not in (
                "SAME_ADDRESS_PROJECT_CONTEXT_NOT_LINKED",
                "SAME_ADDRESS_COMPANY_CONTEXT_NOT_LINKED",
                "EXACT_APPLICATION_ID_IN_FETCHED_TEXT",
                "EXACT_OFFICIAL_ARCGIS_APPLICATION"):
            rejected += 1
            continue
        passages = [clean(src.get(field), 2000) for field in ("excerpt", "role_excerpt")]
        if name.casefold() not in quote.casefold() or not any(
                quote.casefold() in passage.casefold() for passage in passages):
            rejected += 1
            continue
        key = (name.casefold(), str(src.get("url") or ""))
        if key in seen:
            continue
        seen.add(key)
        accepted.append({
            "organization": name,
            "source_url": str(src.get("url") or "")[:1600],
            "evidence_quote": quote,
            "source_identity": src["identity"],
            "evidence_level": "SITE_ASSOCIATION_ONLY_NOT_PERMIT_ROLE",
            "project_role_supported_for_review": False,
            "buyer_verified": False,
            "procurement_verified": False,
            "contact_verified": False,
        })
    return accepted, rejected + max(0, len(proposals)-8)
