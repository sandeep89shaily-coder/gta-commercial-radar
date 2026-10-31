"""Deterministic commercial-significance scoring for project candidates.

Purpose: decide which source-backed projects deserve scarce research spend
(including paid AI) BEFORE any model is called. Pure function of the source row;
no network, no model, fully explainable (every point has a named reason).

Company names in source rows are treated as UNVERIFIED hints and add little.
Public bodies are excluded from the private-opportunity ranking.
"""
from __future__ import annotations
import re

MIN_SELECTION_SCORE = 20      # below this a project gets no paid AI
STRONG_SCORE = 50

PUBLIC_BODY = re.compile(
    r"\b(city of|town of|municipality|regional municipality|region of|school board|"
    r"district school|catholic district|tdsb|tcdsb|university|college of applied|metrolinx|"
    r"toronto community housing|ministry|government of|province of ontario|conservation authority|"
    r"public works)\b", re.I)
COMMERCIAL = re.compile(
    r"\b(industrial|manufactur\w*|warehouse|distribution|logistics|data cent(?:re|er)|cold storage|"
    r"food process\w*|plant|factory|commercial|retail|shopping|hotel|hospital|clinic|"
    r"long[- ]term care|office|laborator\w*|self[- ]storage|supermarket|grocery)\b", re.I)
NEW_BUILD = re.compile(
    r"\b(new (?:\d+[- ]?)?(?:storey|story|building|construction|facility|plant|warehouse|shell)|"
    r"construct|constructing|erect|erecting|addition|expansion|expand\w*|redevelop\w*|new (?:one|1|two|2)[- ]storey|"
    r"shell building|core and shell)\b", re.I)
TRADE = re.compile(
    r"\b(hvac|mechanical|sprinkler|fire (?:alarm|protection|suppression)|security|access control|"
    r"refrigerat\w*|chiller|ventilation|cooling|electrical service|generator)\b", re.I)
ALTERATION = re.compile(
    r"\b(interior alteration\w*|alteration|renovation|tenant fit[- ]?(?:up|out)|fit[- ]?out|"
    r"change of use|revision|rev \d+|interior demolition|minor variance|legalization)\b", re.I)
MINOR_SCOPE = re.compile(
    r"\b(drain\w*|backflow|plumbing only|sign\b|signage|ramp|canopy|fence|deck|porch|pool|garage|"
    r"basement|walk[- ]?out|underpinning|shoring|fire alarm only|temporary)\b", re.I)
RESIDENTIAL = re.compile(
    r"\b(detached|semi[- ]detached|single[- ]family|dwelling|house|duplex|triplex|secondary suite|"
    r"basement apartment|townhouse|laneway)\b", re.I)
INSTITUTIONAL = re.compile(r"\b(daycare|day care|child care|place of worship|church|temple|mosque|gurdwara|synagogue|private school)\b", re.I)
RESIDENTIAL_TOWER = re.compile(r"\b(residential|condominium|condo|apartment|rental building)\b", re.I)
PRE_ISSUANCE = ("applied", "under review", "examiner", "application acceptable", "not started",
                "draft", "in review", "application received", "pre-application", "complete application")
LATE_STAGE = ("inspection", "closed", "completed", "final", "occupancy", "cancelled", "revoked", "refused")
PLANNING_SOURCE = re.compile(r"(site_plan|development_application|rezoning|official_plan|planning)", re.I)
_SQFT = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(?:sq\.?\s?ft\.?|sf\b|square f(?:ee|oo)t)", re.I)
_SQM = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(?:sq\.?\s?m\b|m2|m²|square met(?:re|er)s?)", re.I)
_MONEY = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)\s*(million|m\b|billion|b\b)?", re.I)
_STOREY = re.compile(r"(\d{1,2})[- ]?(?:storey|story|floor)s?\b", re.I)


def _num(text):
    return float(text.replace(",", ""))


def floor_area_sqft(text):
    best = 0.0
    for m in _SQFT.finditer(text):
        best = max(best, _num(m.group(1)))
    for m in _SQM.finditer(text):
        best = max(best, _num(m.group(1)) * 10.764)
    return best


def stated_value_cad(text):
    best = 0.0
    for m in _MONEY.finditer(text):
        v = _num(m.group(1))
        unit = (m.group(2) or "").lower()
        if unit in ("million", "m"):
            v *= 1e6
        elif unit in ("billion", "b"):
            v *= 1e9
        best = max(best, v)
    return best


def _text(row):
    # Only SOURCE-RECORD text drives scope. AI-written fields (project_stage, buyer_fit,
    # next_verification) are unverified hints and must never raise or lower a score.
    keys = ("description", "official_description", "permit_types",
            "company_name", "official_company", "operator", "developer", "address")
    return " ".join(str(row.get(k) or "") for k in keys)


OFFICIAL_DATASETS = ("toronto_active_building_permits", "toronto_development_applications",
                     "brampton_building_permits", "mississauga_issued_building_permits",
                     "mississauga_site_plan_applications", "waterloo_city_building_permits",
                     "st_catharines_building_permits", "ero_gta_environmental_instruments")


def _has_official_url(row):
    return any(str(row.get(k) or "").startswith("https://")
               for k in ("record_source_url", "official_record_url"))


def _status_text(row):
    for key in ("current_source_status", "official_status", "lifecycle_status_used"):
        value = str(row.get(key) or "").strip()
        if value:
            return value.casefold()
    return ""


def _named_company(row):
    for key in ("official_company", "operator", "developer", "company_name"):
        value = str(row.get(key) or "").strip()
        if value and value.upper() not in ("UNKNOWN", "NONE", "N/A", "-"):
            if not re.match(r"^\d+\s+\w+", value):      # a street address is not a company
                return value
    return ""


def score(row):
    """Return {'score','tier','reasons','excluded'}; higher = more commercially significant."""
    text = _text(row)
    low = text.casefold()
    points, reasons = 0, []

    def add(n, why):
        nonlocal points
        points += n
        reasons.append(("+" if n >= 0 else "") + f"{n} {why}")

    owner_text = " ".join(str(row.get(k) or "") for k in
                          ("company_name", "official_company", "operator", "developer", "company_owner"))
    if PUBLIC_BODY.search(owner_text):
        return {"score": -100, "tier": "EXCLUDED_PUBLIC_BODY",
                "reasons": ["-100 public body (not a private opportunity)"], "excluded": True}

    if _has_official_url(row):
        add(5, "official https record present")
    elif str(row.get("source_id") or "") in OFFICIAL_DATASETS:
        add(-10, "official dataset record but no direct record URL")
    else:
        add(-40, "no official record URL or dataset")

    if COMMERCIAL.search(text):
        add(15, "commercial/industrial scope")
    if NEW_BUILD.search(text):
        add(25, "new construction or expansion")
    if TRADE.search(text):
        add(8, "trade relevance (HVAC/fire/security/refrigeration)")

    area = floor_area_sqft(text)
    if area >= 100_000: add(30, f"large floor area {int(area):,} sq ft")
    elif area >= 20_000: add(20, f"floor area {int(area):,} sq ft")
    elif area >= 5_000: add(10, f"floor area {int(area):,} sq ft")
    value = stated_value_cad(text)
    if value >= 10_000_000: add(30, f"stated value ${value:,.0f}")
    elif value >= 1_000_000: add(15, f"stated value ${value:,.0f}")
    storeys = [int(x) for x in _STOREY.findall(text)]
    if storeys and max(storeys) >= 4: add(10, f"{max(storeys)} storeys")

    status = _status_text(row)
    if any(s in status for s in PRE_ISSUANCE): add(15, "pre-issuance stage")
    elif any(s in status for s in LATE_STAGE): add(-15, "late stage (purchasing likely complete)")
    if PLANNING_SOURCE.search(str(row.get("source_id") or "")): add(10, "planning-stage source (earlier signal)")

    if _named_company(row): add(8, "named company (unverified hint)")

    if RESIDENTIAL.search(text):
        add(-60, "residential scope")
    elif RESIDENTIAL_TOWER.search(text) and not COMMERCIAL.search(text):
        add(-15, "residential building without commercial scope")
    if INSTITUTIONAL.search(text):
        add(-15, "institutional use (lower commercial purchasing priority)")
    if ALTERATION.search(text) and not NEW_BUILD.search(text):
        add(-25, "alteration / fit-out / variance only")
    if MINOR_SCOPE.search(text):
        add(-30, "minor scope item")
    if len(re.sub(r"[^A-Za-z]", "", str(row.get("description") or ""))) < 25:
        add(-15, "description too thin to show real scope")

    tier = "STRONG" if points >= STRONG_SCORE else "MODERATE" if points >= MIN_SELECTION_SCORE else "WEAK"
    return {"score": points, "tier": tier, "reasons": reasons, "excluded": False}


def rank(rows):
    """Stable ranking, best first. Excluded rows sort last and keep their reason."""
    scored = []
    for index, row in enumerate(rows):
        result = score(row)
        scored.append((-result["score"], index, row, result))
    scored.sort(key=lambda item: (item[0], item[1]))
    return [(row, result) for _, _, row, result in scored]


def select_for_ai(rows, limit=None):
    """Rows worth paid research: eligible, above threshold, best first."""
    chosen = [(r, s) for r, s in rank(rows) if not s["excluded"] and s["score"] >= MIN_SELECTION_SCORE]
    return chosen[:limit] if limit else chosen
