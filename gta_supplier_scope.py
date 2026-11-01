"""Zero-cost, deterministic supplier-sector suggestions for the manual Radar handoff.

A category is a possible *customer type for project intelligence*, NOT proof
that a procurement package is open or a supplier is required/available.
Only source-record descriptions are used, not model-generated company claims.
"""
from __future__ import annotations

import re

# family, category, match tier, stage, source-description regex
# The scope tier means the *type of work* is indicated in the source text,
# not that a purchase requirement or buying authority has been confirmed.
RULES = (
    ("Construction", "General contractors / construction management", "SCOPE_LINKED",
     "Planning / construction", r"\bnew\b.{0,28}\b(?:building|facility|warehouse|plant)\b|\b(?:expansion|addition|construction)\b"),
    ("Construction", "Industrial roofing / building envelope", "SCOPE_LINKED",
     "Construction", r"\b(?:roof replacement|roof repair|re.?roof|industrial roof|roof modifications?|roofing)\b"),
    ("Construction", "Commercial interior fit-out contractors", "SCOPE_LINKED",
     "Construction", r"\b(?:fit[ -]?out|interior (?:renovation|modification|alteration|improvement)|office addition)\b"),
    ("Construction", "Industrial flooring / concrete floor contractors", "SCOPE_LINKED",
     "Construction", r"\b(?:floor replacement|concrete floor|industrial floor|floor resurfacing|floor repair)\b"),
    ("Construction", "Heritage restoration / masonry contractors", "SCOPE_LINKED",
     "Planning / construction", r"\b(?:heritage|masonry restoration|heritage building)\b"),
    ("Construction", "Structural steel / metal fabrication", "SCOPE_LINKED",
     "Construction", r"\b(?:steel building|structural steel|metal fabrication|steel structure)\b"),
    ("Construction", "Shoring / underpinning contractors", "SCOPE_LINKED",
     "Construction", r"\b(?:shoring|underpinning|foundation support)\b"),
    ("Construction", "Demolition contractors", "SCOPE_LINKED",
     "Construction", r"\b(?:demolition|demolish|removal of structural)\b"),
    ("Mechanical & electrical", "Commercial HVAC / mechanical contractors", "SCOPE_LINKED",
     "Construction", r"\b(?:hvac|heating ventilation|air conditioning|air handling)\b"),
    ("Mechanical & electrical", "Commercial plumbing contractors", "SCOPE_LINKED",
     "Construction", r"\b(?:plumbing|sanitary piping|drainage installation)\b"),
    ("Mechanical & electrical", "Electrical contractors / switchgear", "SCOPE_LINKED",
     "Construction", r"\b(?:electrical installation|electrical work|switchgear|solar|photovoltaic|\bPV\b)\b"),
    ("Energy & solar", "Commercial solar PV installers / EPC", "SCOPE_LINKED",
     "Design / construction", r"\b(?:solar|photovoltaic|PV|rooftop PV)\b"),
    ("Industrial structures", "Fabric-covered industrial building suppliers", "SCOPE_LINKED",
     "Design / construction", r"\b(?:fabric.covered|fabric structure|tension(?:ed)? fabric)\b"),
    ("Industrial structures", "Industrial storage structure suppliers", "SCOPE_LINKED",
     "Design / construction", r"\b(?:industrial storage|storage structure|storage building)\b"),
    ("Warehouse equipment", "Overhead / industrial loading doors", "SCOPE_LINKED",
     "Construction", r"\b(?:loading doors?|overhead doors?|dock doors?)\b"),
    ("Warehouse equipment", "Loading dock / dock leveler suppliers", "SCOPE_LINKED",
     "Construction", r"\b(?:loading bays?|loading docks?|dock levelers?)\b"),
    ("Automotive equipment", "Automotive paint booth manufacturers / installers", "SCOPE_LINKED",
     "Construction", r"\b(?:spray booth|paint booth)\b"),
    ("Automotive equipment", "Industrial ventilation / paint filtration", "SCOPE_LINKED",
     "Construction", r"\b(?:spray booth|paint booth|industrial ventilation)\b"),
    ("Cold chain", "Industrial refrigeration contractors", "SCOPE_LINKED",
     "Design / construction", r"\b(?:cold storage|refrigerated warehouse|industrial refrigeration|freezer storage)\b"),
    ("Cold chain", "Cold-storage insulation / insulated panels", "SCOPE_LINKED",
     "Construction", r"\b(?:cold storage|freezer storage|insulated panels)\b"),
    # Secondary possibilities: relevant commercial service, not established scope.
    ("Mechanical & electrical", "Commercial HVAC / mechanical contractors", "POSSIBLE_PROJECT_SERVICE",
     "Design / construction", r"\b(?:new\b.{0,28}\b(?:building|facility|warehouse|plant)|industrial expansion|office addition)\b"),
    ("Mechanical & electrical", "Commercial plumbing contractors", "POSSIBLE_PROJECT_SERVICE",
     "Design / construction", r"\b(?:new\b.{0,28}\b(?:building|facility|warehouse|plant)|industrial expansion|office addition)\b"),
    ("Mechanical & electrical", "Electrical contractors / switchgear", "POSSIBLE_PROJECT_SERVICE",
     "Design / construction", r"\b(?:new\b.{0,28}\b(?:building|facility|warehouse|plant)|industrial expansion|office addition)\b"),
    ("Construction", "Temporary fencing / construction site security", "POSSIBLE_PROJECT_SERVICE",
     "Construction", r"\b(?:new\b.{0,28}\b(?:building|facility|warehouse|plant)|expansion|addition|demolition)\b"),
    ("Construction", "Construction materials / site logistics suppliers", "POSSIBLE_PROJECT_SERVICE",
     "Construction", r"\b(?:new\b.{0,28}\b(?:building|facility|warehouse|plant)|addition|expansion|storage structure)\b"),
    ("Facilities", "Landscaping / snow and grounds services", "POSSIBLE_OPERATIONS_SERVICE",
     "Handover / operations", r"\b(?:new\b.{0,28}\b(?:building|facility|warehouse|plant)|industrial storage|site expansion)\b"),
    ("Facilities", "Commercial property / facility management", "POSSIBLE_OPERATIONS_SERVICE",
     "Operations", r"\b(?:warehouse|industrial|office|gym|commercial|facility|plant|storage)\b"),
    ("Engineering", "Structural / building-envelope engineers", "POSSIBLE_PROJECT_SERVICE",
     "Planning / design", r"\b(?:addition|expansion|roof|rooftop|heritage|mezzanine|shoring|new facility)\b"),
    ("Engineering", "Civil / site-servicing engineering", "POSSIBLE_PROJECT_SERVICE",
     "Planning / design", r"\b(?:new\b.{0,28}\b(?:building|facility|warehouse|plant)|expansion|industrial storage)\b"),
    ("Construction", "Concrete foundations / site preparation", "POSSIBLE_PROJECT_SERVICE",
     "Construction", r"\b(?:new\b.{0,28}\b(?:building|facility|warehouse|plant)|addition|industrial storage|expansion)\b"),
    ("Construction", "Construction equipment / lift rental", "POSSIBLE_PROJECT_SERVICE",
     "Construction", r"\b(?:new\b.{0,28}\b(?:building|facility|warehouse|plant)|addition|expansion|roof|storage structure|spray booth|solar)\b"),
    ("Safety & security", "Fire protection / suppression installers", "POSSIBLE_PROJECT_SERVICE",
     "Design / construction", r"\b(?:warehouse|industrial|spray booth|paint booth|office|gym|commercial|cold storage)\b"),
    ("Safety & security", "Security / CCTV / access control installers", "POSSIBLE_PROJECT_SERVICE",
     "Construction / operations", r"\b(?:warehouse|industrial|office|commercial|gym|facility|cold storage|plant)\b"),
    ("Warehouse equipment", "Racking / material handling / forklift suppliers", "POSSIBLE_OPERATIONS_SERVICE",
     "Occupancy / operations", r"\b(?:warehouse|industrial storage|cold storage|loading bay)\b"),
    ("Office & retail", "IT / structured cabling / business telecom", "POSSIBLE_PROJECT_SERVICE",
     "Fit-out / occupancy", r"\b(?:office|gym|retail|commercial fit.out)\b"),
    ("Office & retail", "Office furniture / signage suppliers", "POSSIBLE_OPERATIONS_SERVICE",
     "Occupancy", r"\b(?:office|gym|retail|commercial fit.out)\b"),
    ("Facilities", "Industrial / commercial cleaning services", "POSSIBLE_OPERATIONS_SERVICE",
     "Handover / operations", r"\b(?:warehouse|industrial|office|gym|commercial|facility|plant|addition|fit.out)\b"),
    ("Facilities", "Facility maintenance / property services", "POSSIBLE_OPERATIONS_SERVICE",
     "Handover / operations", r"\b(?:warehouse|industrial|office|gym|commercial|facility|plant|storage)\b"),
    ("Facilities", "Pest control / hygiene services", "POSSIBLE_OPERATIONS_SERVICE",
     "Operations", r"\b(?:warehouse|cold storage|industrial storage|food|commercial gym)\b"),
    ("Facilities", "Waste hauling / disposal / recycling services", "POSSIBLE_PROJECT_SERVICE",
     "Construction / operations", r"\b(?:construction|renovation|demolition|addition|expansion|fit.out|industrial)\b"),
    ("Insurance & finance", "Commercial property / construction insurance brokers", "POSSIBLE_PROJECT_SERVICE",
     "Planning / construction / renewal", r"\b(?:warehouse|industrial|office|gym|commercial|facility|plant|storage|addition|expansion)\b"),
    ("Energy & solar", "Energy management / electrical maintenance", "POSSIBLE_OPERATIONS_SERVICE",
     "Operations", r"\b(?:solar|photovoltaic|warehouse|industrial|office|cold storage|plant)\b"),
    ("Energy & solar", "Solar monitoring / panel maintenance", "POSSIBLE_OPERATIONS_SERVICE",
     "Operations", r"\b(?:solar|photovoltaic|PV)\b"),
    ("Automotive equipment", "Paint booth servicing / filter replacement", "POSSIBLE_OPERATIONS_SERVICE",
     "Operations", r"\b(?:spray booth|paint booth)\b"),
    ("Cold chain", "Cold-chain monitoring / refrigeration servicing", "POSSIBLE_OPERATIONS_SERVICE",
     "Operations", r"\b(?:cold storage|refrigerated warehouse|industrial refrigeration)\b"),
    ("Fitness equipment", "Commercial gym equipment / sport flooring", "POSSIBLE_OPERATIONS_SERVICE",
     "Occupancy", r"\b(?:gym|fitness|exercise facility)\b"),
)

COMPILED = tuple((family, sector, tier, phase, re.compile(pattern, re.IGNORECASE))
                 for family, sector, tier, phase, pattern in RULES)
TIERS = ("SCOPE_LINKED", "POSSIBLE_PROJECT_SERVICE", "POSSIBLE_OPERATIONS_SERVICE")


def classify(description):
    """Return deterministic, deduplicated category suggestions in tier order.

    Source text is intentionally not inferred from the address, operator or AI
    model output. Empty/vague descriptions yield no matches rather than generic
    manufactured opportunities.
    """
    work = " ".join(str(description or "").split())[:5000]
    if not work:
        return []
    matches = []
    seen = set()
    for family, sector, tier, phase, pattern in COMPILED:
        evidence = pattern.search(work)
        if not evidence or sector in seen:
            continue
        seen.add(sector)
        matches.append({"supplier_family": family, "supplier_category": sector,
                        "match_tier": tier, "likely_service_phase": phase,
                        "scope_phrase": evidence.group(0),
                        "qualification": "SUGGESTION_ONLY_NO_AWARD_OR_BUYER_VERIFIED"})
    return sorted(matches, key=lambda x: (TIERS.index(x["match_tier"]), x["supplier_family"], x["supplier_category"]))
