"""ONE consolidated 16-core + 8-expansion municipal Radar research universe.

The legacy 16-city collector, GGH pilot, three-city detail collector and
northern major-city collector all already run inside the same BAT launcher;
their outputs were never JOINED. This offline reconciliation merges them
under city+exact application ID, preserving every source's role/date and
counting issued permits separately from applications and project signals.

This is not verification of first public announcement, named purchasing
authority, open work, or complete citywide coverage. No network or paid AI.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from gta_authorized_application_exports import load as load_authorized_exports

CORE_CITIES = (
    "Toronto", "Brampton", "Mississauga", "Hamilton", "Burlington",
    "Oakville", "Vaughan", "Kitchener", "Markham", "Oshawa", "Milton",
    "Halton Hills", "Caledon", "Cambridge", "Waterloo", "Guelph",
)
# Last two use already-operational GGH / next-four municipal pilot feeds;
# they are explicitly NOT new GIS promises or citywide-complete sources.
EXPANSION_CITIES = (
    "Niagara Falls", "St. Catharines", "Brantford", "Barrie",
    "Greater Sudbury", "North Bay", "Peterborough", "Whitby",
)
CITIES = CORE_CITIES + EXPANSION_CITIES
MASTER = "GTA_RADAR_COMBINED_24_CITY_PROJECT_MASTER.csv"
COVERAGE = "GTA_RADAR_COMBINED_24_CITY_COVERAGE.csv"
RESEARCH = "GTA_RADAR_COMBINED_24_CITY_RESEARCH_QUEUE.csv"
TOP10 = "GTA_RADAR_COMBINED_24_CITY_RESEARCH_TOP10.csv"
STATUS = "GTA_RADAR_COMBINED_24_CITY_STATUS.json"
COLS = (
    "canonical_id", "city", "cohort", "record_kind", "application_id",
    "address", "project_title", "scope", "current_status",
    "applicant_or_agent_source_claim", "published_contact_name",
    "published_contact_email", "contact_role", "source_date",
    "source_date_basis", "webpage_posted_date_not_first_disclosure",
    "source_observation", "first_seen_local", "official_evidence_urls",
    "source_lanes", "commercial_text_match", "source_event_age_band_not_publication",
    "original_publication_verified",
    "purchasing_contact_verified", "open_supplier_contract_verified",
    "commercial_research_priority", "verification_required",
)
COVERAGE_COLS = (
    "city", "cohort", "application_files", "building_permits_historical",
    "project_only_signals", "source_rows", "commercial_research_candidates",
    "published_contact_email_records", "failed_or_blocked_source_count",
    "source_health", "coverage_verified_citywide", "first_publications_verified",
    "verified_buyers", "open_supplier_contracts_verified", "source_limitations",
)
STRONG = re.compile(
    r"\b(?:industrial|manufactur\w*|warehouse|distribution|logistics|"
    r"data.cent(?:re|er)|retail|commercial|medical|hospital|hotel|"
    r"restaurant|office|business.park|storage|mixed.use|clinic|"
    r"institutional|factory|industrial.condo|construction)\b", re.I)
CLOSED = re.compile(
    r"\b(?:cancelled|canceled|withdrawn|refused|rejected|expired|closed)\b", re.I)
NOISY = ("active development applications", "development applications",
         "planning and development", "current development applications")


def _clean(v):
    return " ".join(str(v or "").split())


def _csv(path, *, required_fields=()):
    if not path.is_file():
        if required_fields:
            raise ValueError("CORE_16_COLLECTION_MISSING_OR_CONFIG_CHANGED")
        return []
    if path.is_symlink() or path.stat().st_size > 80_000_000:
        raise ValueError("UNSAFE_COMBINED_SOURCE_FILE:" + path.name)
    with path.open(encoding="utf-8-sig", newline="") as fp:
        rows = csv.DictReader(fp)
        if not set(required_fields).issubset(rows.fieldnames or ()):
            raise ValueError("CORE_16_COLLECTION_MISSING_OR_CONFIG_CHANGED")
        return list(rows)


def _json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def _id(city, ident, fallback):
    normalized = re.sub(r"[^A-Z0-9]", "", _clean(ident).upper())
    if normalized:
        return city.upper().replace(" ", "_") + ":FILE:" + normalized
    return city.upper().replace(" ", "_") + ":SIGNAL:" + hashlib.sha256(
        fallback.encode("utf-8")).hexdigest()[:20]


def _date(value):
    val = _clean(value)
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", val):
        return ""
    try:
        return dt.date.fromisoformat(val).isoformat()
    except ValueError:
        return ""


def _write(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            safe = {}
            for field in fields:
                raw = row.get(field)
                value = "" if raw is None else " ".join(str(raw).split())
                safe[field] = ("'" + value if value.lstrip().startswith(
                    ("=", "+", "-", "@", "\t", "\r")) else value)
            writer.writerow(safe)


def _record(city, lane, ident, *, record_kind="APPLICATION", address="",
            title="", scope="", stage="", applicant="", contact="", email="",
            contact_role="", date="", date_basis="", posted="", observation="",
            first_seen="", url="", stable="", core=False):
    ident = _clean(ident)
    fallback = _clean(stable or (url + "|" + title + "|" + address + "|" + scope))
    if not ident and not fallback:
        return None
    if city not in CITIES:
        return None
    if _clean(applicant).casefold() in NOISY:
        applicant = ""
    if record_kind == "APPLICATION" and not ident:
        record_kind = "PROJECT_ONLY_SIGNAL"
    if record_kind == "PERMIT" and not ident:
        return None
    if url and not url.startswith("https://"):
        url = ""
    canonical = _id(city, ident, fallback)
    if record_kind == "PERMIT" and ident:
        # Planning IDs and permit numbers are distinct official identifier
        # namespaces even if a city happens to reuse the same string.
        canonical = city.upper().replace(" ", "_") + ":PERMIT:" + re.sub(
            r"[^A-Z0-9]", "", ident.upper())
    return {
        "canonical_id": canonical,
        "city": city,
        "cohort": "CORE_16" if core else "EXPANSION_8",
        "record_kind": record_kind,
        "application_id": ident,
        "address": _clean(address)[:200],
        "project_title": _clean(title)[:220],
        "scope": _clean(scope)[:1300],
        "current_status": _clean(stage)[:160],
        "applicant_or_agent_source_claim": _clean(applicant)[:220],
        "published_contact_name": _clean(contact)[:150],
        "published_contact_email": _clean(email)[:180],
        "contact_role": _clean(contact_role)[:160],
        "source_date": _date(date),
        "source_date_basis": _clean(date_basis),
        "webpage_posted_date_not_first_disclosure": _date(posted),
        "source_observation": _clean(observation),
        "first_seen_local": _date(first_seen),
        "official_evidence_urls": _clean(url)[:1000],
        "source_lanes": lane,
        "commercial_text_match": str(bool(STRONG.search(_clean(scope) + " " + _clean(title)))),
        "original_publication_verified": "False",
        "purchasing_contact_verified": "False",
        "open_supplier_contract_verified": "False",
        "commercial_research_priority": "BASELINE_OR_UNVERIFIED",
        "verification_required": (
            "Confirm exact original project publication and source application "
            "identity; establish project developer/GC, public project buying "
            "contact, relevant supplier scope and unawarded procurement."),
    }


def _explicit_source_change(value):
    """Only actual source-change states qualify; UNCHANGED is never CHANGED.

    Nov 18 operator archive showed all 250 research queue rows labelled
    SOURCE_CHANGED_NEEDS_REVIEW because substring \"CHANG\" matched UNCHANGED.
    These are source-content changes, not original public project disclosures.
    """
    status = _clean(value).upper()
    return status in ("CHANGED", "UPDATED", "SOURCE_UPDATED", "NEW_OR_CHANGED") or \
        status.startswith(("SOURCE_CHANGED", "DETAIL_PAGE_CHANGED",
                           "APPLICATION_CHANGED", "CHANGED_"))


def _merge(records):
    buckets = defaultdict(list)
    for row in records:
        if row is not None:
            buckets[row["canonical_id"]].append(row)
    combined = []
    for key, members in sorted(buckets.items()):
        # A detailed, recent planning record beats a generic index or a
        # permit title, but dates/contact roles survive all the contributing
        # sources without being reinterpreted as first-publication evidence.
        ranked = sorted(members, key=lambda r: (
            r["record_kind"] == "APPLICATION",
            len(r["scope"]), bool(r["applicant_or_agent_source_claim"]),
            bool(r["published_contact_email"])), reverse=True)
        base = dict(ranked[0])
        for field in ("address", "project_title", "applicant_or_agent_source_claim",
                      "published_contact_name", "published_contact_email",
                      "contact_role", "webpage_posted_date_not_first_disclosure",
                      "current_status"):
            if not base[field]:
                base[field] = next((r[field] for r in ranked if r[field]), "")
        # Never silently replace an application receipt date with a web-page
        # posting or a locally first-seen timestamp.
        dated = [r for r in members if r["source_date"]]
        if dated:
            chosen = max(dated, key=lambda r: (r["source_date"],
                                  r["record_kind"] == "APPLICATION"))
            base["source_date"] = chosen["source_date"]
            base["source_date_basis"] = chosen["source_date_basis"]
        first = [r["first_seen_local"] for r in members if r["first_seen_local"]]
        base["first_seen_local"] = min(first) if first else ""
        base["source_lanes"] = " | ".join(sorted(set(
            r["source_lanes"] for r in members if r["source_lanes"])))
        base["official_evidence_urls"] = " | ".join(dict.fromkeys(
            r["official_evidence_urls"] for r in members if r["official_evidence_urls"]))[:2500]
        obs = [r["source_observation"] for r in members]
        base["source_observation"] = (
            "SOURCE_CHANGED_NEEDS_REVIEW" if any(
                _explicit_source_change(v) for v in obs)
            else "FIRST_OBSERVED_NOT_FIRST_PUBLICATION"
            if any(v == "FIRST_OBSERVED" for v in obs)
            else "HISTORICAL_OR_UNCHANGED_BASELINE")
        base["commercial_text_match"] = str(any(
            r["commercial_text_match"] == "True" for r in members))
        # Some collector input applications may use a generic "APPLICATION"
        # class: do not override the full legacy city's core record.
        combined.append(base)
    return combined


def _rank(row, day):
    if row["record_kind"] != "APPLICATION":
        return None
    if row["commercial_text_match"] != "True":
        return None
    if CLOSED.search(row["current_status"]):
        return None
    scope = row["scope"]
    # Official Toronto records can say INACTIVE in description while
    # a separate lifecycle field still says Under Review. Never let the
    # more optimistic field override explicit inactive-source evidence.
    if scope.lstrip().upper().startswith(("INACTIVE ", "CLOSED ",
                                          "WITHDRAWN ", "CANCELLED ",
                                          "CANCELED ")):
        return None
    if len(scope) < 42:
        return None
    stage = row["current_status"].casefold()
    score = 5 if row["cohort"] == "EXPANSION_8" else 0
    if any(term in stage for term in ("under review", "pending", "received",
                                     "circulation", "submitted")):
        score += 18
    if row["applicant_or_agent_source_claim"]:
        score += 14
    if row["published_contact_email"]:
        score += 8  # city planner contact, not a buyer
    if row["application_id"]:
        score += 12
    if "industrial" in scope.casefold() or "manufactur" in scope.casefold():
        score += 12
    if row["source_observation"] in (
            "FIRST_OBSERVED_NOT_FIRST_PUBLICATION",
            "SOURCE_CHANGED_NEEDS_REVIEW"):
        score += 7   # explicit source event; NOT first publication proof
    try:
        age = (day - dt.date.fromisoformat(row["source_date"])).days
        if 0 <= age <= 60:
            score += 20
        elif 0 <= age <= 365:
            score += 10
    except (ValueError, TypeError):
        pass
    return score


def run(results, *, today=None):
    root = Path(results)
    if not root.is_dir():
        raise FileNotFoundError("EXISTING_RESULTS_DIRECTORY_REQUIRED")
    day = today or dt.date.today()
    originals = _csv(
        root / "GTA_RADAR_COLLECTION_MASTER.csv",
        required_fields=("canonical_id", "city", "record_kind", "application_id"),
    )
    prior_health = _csv(root / "GTA_RADAR_COLLECTION_HEALTH.csv")
    if {x.get("city") for x in prior_health} != set(CORE_CITIES):
        raise ValueError("CORE_16_COLLECTION_MISSING_OR_CONFIG_CHANGED")
    records = []
    sources = Counter()
    for r in originals:
        city = r.get("city", "")
        if city not in CORE_CITIES:
            continue
        record = _record(city, "CORE_16:" + _clean(r.get("source_types")),
            r.get("application_id"),
            record_kind=("APPLICATION" if r.get("record_kind") == "APPLICATION_ID"
                        else "PROJECT_ONLY_SIGNAL"),
            address=r.get("address"), scope=r.get("description"),
            stage=r.get("current_status"), date=r.get("date"),
            date_basis=r.get("date_basis"), url=r.get("evidence_urls"),
            first_seen=r.get("first_seen_local"), observation=r.get("observation"),
            stable=r.get("canonical_id"), core=True)
        records.append(record)
        sources["CORE_16"] += 1

    # The 30 Mississauga detail pages enrich matching core application files;
    # they do not create duplicate "new" source records.
    for r in _csv(root / "GTA_RADAR_MISSISSAUGA_DETAIL_APPLICATIONS.csv"):
        records.append(_record("Mississauga", "MISSISSAUGA_DETAIL",
            r.get("application_id"), address=r.get("address"),
            title=r.get("project_title"), scope=r.get("description"),
            stage=r.get("current_status"),
            applicant=r.get("applicant_name_source_claim"),
            contact=r.get("city_planner_name"), email=r.get("city_planner_email"),
            contact_role="MUNICIPAL_PLANNER_NOT_BUYER",
            posted=r.get("publisher_page_posted_date"),
            observation=r.get("observation"),
            url=r.get("record_source_url"), core=True))
        sources["MISSISSAUGA_DETAIL"] += 1

    for r in _csv(root / "GTA_RADAR_GGH_EXPANSION_APPLICATIONS.csv"):
        city = r.get("city")
        if city not in EXPANSION_CITIES:
            continue
        records.append(_record(city, "GGH_APPLICATION", r.get("application_id"),
            address=r.get("address"), scope=r.get("description"),
            applicant=r.get("applicant"), date=r.get("source_date"),
            date_basis=r.get("source_date_basis"),
            first_seen=r.get("first_seen_local"), observation=r.get("observation"),
            url=r.get("official_record_url") or r.get("source_url"),
            stable=r.get("project_id")))
        sources["GGH_APPLICATION"] += 1

    for r in _csv(root / "GTA_RADAR_THREE_CITY_EVIDENCE_CANDIDATES.csv"):
        city = r.get("city")
        if city not in EXPANSION_CITIES:
            continue
        records.append(_record(city, r.get("source_lane"), r.get("application_id"),
            record_kind=("PROJECT_ONLY_SIGNAL" if
                         r.get("record_kind") == "OFFICIAL_NOTICE_NO_EXACT_FILE_ID"
                         else "APPLICATION"),
            address=r.get("address"), scope=r.get("scope"),
            stage=r.get("application_status"),
            applicant=r.get("applicant_name_source_claim"),
            contact=r.get("planner_name"), email=r.get("planner_email_public"),
            contact_role=r.get("contact_role") or "MUNICIPAL_PLANNER_NOT_BUYER",
            date=(r.get("source_date") or r.get("application_complete_date")),
            date_basis=(r.get("source_date_basis") or
                        "APPLICATION_COMPLETE_NOT_FIRST_PUBLICATION"),
            posted=r.get("notice_posted_date"),
            first_seen=r.get("first_seen_local"), observation=r.get("observation"),
            url=r.get("source_url"), stable=r.get("candidate_key")))
        sources["THREE_CITY_DETAIL"] += 1

    for r in _csv(root / "GTA_RADAR_NORTHERN_MAJOR_CITY_EVIDENCE.csv"):
        city = r.get("city")
        if city not in EXPANSION_CITIES:
            continue
        permit = r.get("record_kind") == "OFFICIAL_BARRIE_ISSUED_PERMIT"
        records.append(_record(city, r.get("source_lane"),
            r.get("application_id"), record_kind="PERMIT" if permit else
            "APPLICATION" if r.get("application_id") else "PROJECT_ONLY_SIGNAL",
            address=r.get("address"), title=r.get("project_title"),
            scope=r.get("scope"), stage=r.get("current_status"),
            applicant=r.get("applicant_name_source_claim"),
            contact=r.get("planning_contact_name"),
            email=r.get("planning_contact_email"),
            contact_role="MUNICIPAL_PLANNER_NOT_BUYER" if
                r.get("planning_contact_email") else "",
            date=r.get("source_date"), date_basis=r.get("source_date_basis"),
            first_seen=r.get("first_seen_local"), observation=r.get("observation"),
            url=r.get("original_record_url"), stable=r.get("candidate_id")))
        sources["NORTHERN_MAJOR_CITY"] += 1

    for r in _csv(root / "GTA_RADAR_NEXT_FOUR_MUNICIPALITIES_REVIEW.csv"):
        city = r.get("city")
        if city not in EXPANSION_CITIES:
            continue
        records.append(_record(city, "OFFICIAL_PLANNING_NOTICE",
            r.get("application_id"), record_kind="PROJECT_ONLY_SIGNAL",
            title=r.get("project_title"), scope=r.get("description"),
            first_seen=r.get("first_seen_local"),
            observation=r.get("observation"), url=r.get("official_notice_url"),
            stable=r.get("record_id")))
        sources["NEXT_FOUR_NOTICE"] += 1

    # Publisher-permitted manually supplied City CSV exports. This is a
    # separate LOCAL source: no GIS bypass, live collection claim, or inferred
    # first-publication date. Never count rows without exact official IDs.
    authorized_rows, authorized_status = load_authorized_exports(root)
    for item in authorized_rows:
        records.append(_record(item["city"], "AUTHORIZED_CITY_CSV_OFFLINE",
            item["application_id"], address=item["address"],
            scope=item["scope"], stage=item["status"],
            applicant=item["applicant"], date=item["date"],
            date_basis=item["source_date_basis"], url=item["url"], core=True))
        sources["AUTHORIZED_CITY_CSV_OFFLINE"] += 1

    rows = _merge(records)
    for row in rows:
        try:
            source_age = (day - dt.date.fromisoformat(row["source_date"])).days
        except (ValueError, TypeError):
            source_age = None
        row["source_event_age_band_not_publication"] = (
            "FUTURE_OR_INVALID_DATE_REVIEW" if source_age is not None and source_age < 0 else
            "SOURCE_EVENT_0_TO_7_DAYS" if source_age is not None and source_age <= 7 else
            "SOURCE_EVENT_8_TO_30_DAYS" if source_age is not None and source_age <= 30 else
            "SOURCE_EVENT_31_TO_90_DAYS" if source_age is not None and source_age <= 90 else
            "SOURCE_EVENT_91_TO_365_DAYS" if source_age is not None and source_age <= 365 else
            "HISTORICAL_SOURCE_EVENT_OVER_365_DAYS" if source_age is not None else
            "SOURCE_EVENT_DATE_UNKNOWN_NOT_FRESH")
    by_city = defaultdict(list)
    for row in rows:
        by_city[row["city"]].append(row)

    north = _json(root / "GTA_RADAR_NORTHERN_MAJOR_CITY_STATUS.json")
    three = _json(root / "GTA_RADAR_THREE_CITY_EVIDENCE_STATUS.json")
    ggh = _json(root / "GTA_RADAR_GGH_EXPANSION_SOURCE_STATUS.json")
    next4 = _json(root / "GTA_RADAR_NEXT_FOUR_MUNICIPALITIES_STATUS.json")
    old_health = {r["city"]:r for r in prior_health}
    blocked = Counter()
    issues = defaultdict(list)
    for r in north.get("source_details", []):
        city = r.get("city")
        if city not in EXPANSION_CITIES:
            continue
        status = _clean(r.get("status"))
        if status in ("SOURCE_HELD", "SOURCE_BLOCKED_OR_UNSUPPORTED",
                      "NO_PUBLISHED_PERMIT_NUMBER_HOLD"):
            blocked[city] += 1
            issues[city].append(r.get("lane", "") + ":" + status)
        if r.get("error"):
            issues[city].append(_clean(r["error"])[:180])
        if city == "Greater Sudbury" and r.get("supplemental_notice_document_links"):
            issues[city].append(str(r["supplemental_notice_document_links"]) +
               " notice-document links only; NOT extracted application projects")
    for r in three.get("sources", []):
        city = r.get("city")
        if city in EXPANSION_CITIES and r.get("failures"):
            blocked[city] += 1
            issues[city].append(_clean(r.get("status")) + ":" +
                                _clean(r.get("failures"))[:220])
    for r in ggh.get("source_status", []):
        city = r.get("city")
        if city in EXPANSION_CITIES and r.get("state") not in (
                 "COLLECTED", "NO_APPLICATION_ID_ROWS"):
            issues[city].append("GGH:" + _clean(r.get("state")))
    for r in next4.get("source_status", []):
        if r.get("city") in EXPANSION_CITIES and r.get("status") != "COLLECTED":
            issues[r["city"]].append("Notice:" + _clean(r.get("status")))

    rankings = []
    for r in rows:
        score = _rank(r, day)
        if score is not None:
            r["commercial_research_priority"] = "RESEARCH_ONLY_NOT_SALE_READY"
            rankings.append((score, r))
    # A known RECENT application event outranks an undated or historical
    # file regardless of how many generic company/planner fields it has.
    # This is not proof of first publication. Preserve old files in MASTER
    # and RESEARCH for background work, never silently rewrite their dates.
    def event_band(row):
        try:
            age = (day - dt.date.fromisoformat(row["source_date"])).days
        except (ValueError, TypeError):
            return 3  # missing actual source event, NOT a fresh disclosure
        if 0 <= age <= 30:
            return 0
        if 31 <= age <= 90:
            return 1
        if 91 <= age <= 365:
            return 2
        return 3

    rankings.sort(key=lambda pair: (
        event_band(pair[1]), -pair[0],
        pair[1]["city"], pair[1]["application_id"]))
    research = [row for _,row in rankings]
    # One research list over BOTH cohorts. Limit any single city to four
    # placements in the first ten to avoid ten Toronto or ten Barrie files.
    winners, city_slots = [], Counter()
    for row in research:
        if city_slots[row["city"]] >= 4:
            continue
        city_slots[row["city"]] += 1
        winners.append(row)
        if len(winners) == 10:
            break

    coverage = []
    for city in CITIES:
        group = by_city[city]
        counters = Counter(r["record_kind"] for r in group)
        is_core = city in CORE_CITIES
        base = old_health.get(city, {})
        errors = (int(base.get("source_failures") or 0) if is_core else blocked[city])
        if errors:
            health = "PARTIAL_SOURCE_FAILURE_OR_BLOCKED"
        elif counters["APPLICATION"]:
            health = "APPLICATION_FILES_COLLECTED_NOT_CITYWIDE_VERIFIED"
        elif counters["PROJECT_ONLY_SIGNAL"]:
            health = "PROJECT_SIGNALS_ONLY_NOT_APPLICATION_COVERAGE"
        else:
            health = "NO_EXTRACTED_PROJECT_FILES_COVERAGE_UNVERIFIED"
        coverage.append({
            "city": city, "cohort": "CORE_16" if is_core else "EXPANSION_8",
            "application_files": counters["APPLICATION"],
            "building_permits_historical": counters["PERMIT"],
            "project_only_signals": counters["PROJECT_ONLY_SIGNAL"],
            "source_rows": len(group),
            "commercial_research_candidates": sum(
                r["commercial_research_priority"] ==
                "RESEARCH_ONLY_NOT_SALE_READY" for r in group),
            "published_contact_email_records": sum(
                bool(r["published_contact_email"]) for r in group),
            "failed_or_blocked_source_count": errors,
            "source_health": health, "coverage_verified_citywide": "False",
            "first_publications_verified": 0, "verified_buyers": 0,
            "open_supplier_contracts_verified": 0,
            "source_limitations": (
                base.get("source_notes", "") if is_core else
                " | ".join(issues[city]))[:850],
        })
    _write(root / MASTER, COLS, rows)
    _write(root / COVERAGE, COVERAGE_COLS, coverage)
    _write(root / RESEARCH, COLS, research[:250])
    _write(root / TOP10, COLS, winners)
    result = {
        "status": "COMBINED_16_PLUS_8_RESEARCH_ONLY_NOT_CUSTOMER_RELEASE",
        "core_collection_input_rows": len(originals),
        "configured_core_cities": list(CORE_CITIES),
        "configured_expansion_cities": list(EXPANSION_CITIES),
        "configured_city_count": 24,
        "core_city_count": 16, "expansion_city_count": 8,
        "municipalities_with_application_files": sum(
            int(r["application_files"]) > 0 for r in coverage),
        "cities_without_application_files": [r["city"] for r in coverage
                              if not int(r["application_files"])],
        "unique_application_files_in_combined_master": sum(
            r["record_kind"] == "APPLICATION" for r in rows),
        "historical_permit_records_separate_from_applications": sum(
            r["record_kind"] == "PERMIT" for r in rows),
        "project_only_signals_not_applications": sum(
            r["record_kind"] == "PROJECT_ONLY_SIGNAL" for r in rows),
        "total_combined_master_records": len(rows),
        "combined_commercial_research_candidates": len(research),
        "combined_research_top10_count": len(winners),
        "top10_cities": dict(Counter(r["city"] for r in winners)),
        "core_16_source_rows": sources["CORE_16"],
        "source_rows_by_lane": dict(sources),
        "authorized_local_exports_not_live": authorized_status["rows"],
        "all_citywide_coverage_verified": False,
        "verified_new_publications": 0, "verified_buyers": 0,
        "verified_open_supplier_contracts": 0,
        "automated_outreach": False, "additional_paid_ai_calls": 0,
        "standard_paid_ai_top10_already_runs_in_upstream_daily_stage": True,
        "standard_paid_ai_top10_includes_expansion": False,
        "combined_research_top10_is_offline_not_deepseek_approved": True,
        "outputs": [MASTER, COVERAGE, RESEARCH, TOP10, STATUS],
        "warning": (
            "The original daily paid Top 10 still runs before expansion "
            "collectors. This is a genuinely unified 24-city collection, "
            "coverage and cross-region research selection, not a claim that "
            "upstream DeepSeek reviewed all eight expansion cities. Project "
            "applicants and city planner emails are not purchasing buyers; "
            "receipt dates, notice dates and first-seen times are not "
            "verified first construction disclosures. Failed sources and "
            "permit-only feeds are retained but not called current leads."),
    }
    (root / STATUS).write_text(json.dumps(result, indent=2),
                                encoding="utf-8")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", required=True)
    args = p.parse_args()
    print(json.dumps(run(args.results), indent=2))


if __name__ == "__main__":
    main()
