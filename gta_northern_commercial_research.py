"""Prioritize source-backed northern commercial research without new AI/web calls.

Barrie GIS's ~5k historical planning and issued-permit rows are NOT 5k new
business opportunities. Produce a bounded review list of pending commercial
applications with exact file numbers, source received dates, applicants and
real scope. Permits already issued are lifecycle evidence, NOT early buyers.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import re
from pathlib import Path

SOURCE = "GTA_RADAR_NORTHERN_MAJOR_CITY_EVIDENCE.csv"
OUTPUT = "GTA_RADAR_NORTHERN_PRIORITIZED_RESEARCH.csv"
STATUS = "GTA_RADAR_NORTHERN_RESEARCH_QUALITY_STATUS.json"
COLUMNS = (
    "priority", "city", "application_id", "address", "source_received_date",
    "source_date_basis", "source_status", "project_scope",
    "applicant_or_agent_source_claim", "contact_role_verified",
    "procurement_status", "original_publication_verified",
    "source_url", "evidence_source", "research_priority",
    "why_review", "required_next_verification",
)
INDUSTRIAL = re.compile(
    r"\b(?:industrial|manufactur\w*|crane.manufactur\w*|factory|warehouse|"
    r"distribution|logistics|data.cent(?:re|er)|self.storage|employment.area|"
    r"industrial.condo|storage.facilit\w*)\b", re.I)
COMMERCIAL = re.compile(
    r"\b(?:commercial|retail|mixed.use|hotel|office|medical|clinic|"
    r"institutional|restaurant|bank|shopping|business.park)\b", re.I)


def _read(root):
    path = root / SOURCE
    if not path.is_file():
        return []
    if path.is_symlink() or path.stat().st_size > 12_000_000:
        raise ValueError("UNSAFE_NORTHERN_RAW_EVIDENCE")
    with path.open(encoding="utf-8-sig", newline="") as fp:
        return list(csv.DictReader(fp))


def _write(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            safe = {}
            for field in COLUMNS:
                value = str(row.get(field, ""))
                safe[field] = "'" + value if value.lstrip().startswith(
                    ("=", "+", "-", "@", "\t", "\r")) else value
            writer.writerow(safe)


def run(results, *, today=None, limit=25):
    root = Path(results)
    if not root.is_dir():
        raise FileNotFoundError("EXISTING_RESULTS_DIRECTORY_REQUIRED")
    day = today or dt.date.today()
    allrows = _read(root)
    eligible = []
    source_lanes = {}
    for row in allrows:
        lane = row.get("source_lane", "")
        source_lanes[lane] = source_lanes.get(lane, 0) + 1
        # Preserve issued permits as historical lifecycle evidence. They do
        # NOT establish buying windows or active early development.
        if lane != "BARRIE_PLANNING":
            continue
        ident = (row.get("application_id") or "").strip()
        scope = (row.get("scope") or "").strip()
        stage = (row.get("current_status") or "").upper()
        if not ident or len(scope) < 24 or stage != "UNDER REVIEW":
            continue
        industrial = bool(INDUSTRIAL.search(scope))
        commercial = bool(COMMERCIAL.search(scope))
        if not (industrial or commercial):
            continue
        source_date = row.get("source_date") or ""
        age = None
        try:
            age = (day - dt.date.fromisoformat(source_date)).days if source_date else None
        except ValueError:
            age = None
        if age is not None and age < 0:
            continue
        if industrial:
            focus = "INDUSTRIAL_SCOPE_REVIEW"
        else:
            focus = "COMMERCIAL_OR_MIXED_SCOPE_REVIEW"
        score = 40 if industrial else 20
        if age is not None and age <= 90:
            score += 30
        elif age is not None and age <= 365:
            score += 15
        if row.get("applicant_name_source_claim"):
            score += 5
        evidence = {
            "city": row.get("city", ""),
            "application_id": ident,
            "address": row.get("address", ""),
            "source_received_date": source_date,
            "source_date_basis": row.get("source_date_basis", ""),
            "source_status": stage,
            "project_scope": scope,
            "applicant_or_agent_source_claim": row.get("applicant_name_source_claim", ""),
            "contact_role_verified": "False",
            "procurement_status": "UNKNOWN_NOT_VERIFIED_OPEN",
            "original_publication_verified": "False",
            "source_url": row.get("original_record_url") or row.get("source_index_url", ""),
            "evidence_source": lane,
            "research_priority": focus,
            "why_review": ("Under-review source-file with substantial industrial scope."
                           if industrial else "Under-review commercial/mixed development."),
            "required_next_verification":
                "Find primary project notice and original publication date; "
                "identify legal developer/GC, public project contact, actual "
                "unawarded supplier scope and purchasing authority.",
            "_score": score,
        }
        eligible.append(evidence)
    eligible.sort(key=lambda r: (-r["_score"], -(int(r["source_received_date"].replace("-", ""))
                    if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", r["source_received_date"])
                    else 0), r["application_id"]))
    output = []
    for i, row in enumerate(eligible[:max(0, min(limit, 50))], 1):
        row = dict(row)
        row.pop("_score")
        row["priority"] = i
        output.append(row)
    _write(root / OUTPUT, output)
    status = {
        "status": "HISTORICAL_SOURCE_DATED_COMMERCIAL_RESEARCH_ONLY",
        "source_rows": len(allrows),
        "source_lanes": source_lanes,
        "barrie_planning_under_review_commercial_candidates": len(eligible),
        "private_research_worklist_rows": len(output),
        "historical_issued_permits_excluded_from_early_research":
            source_lanes.get("BARRIE_ISSUED_PERMITS", 0),
        "verified_new_publications": 0, "verified_buyers": 0,
        "verified_unawarded_contracts": 0, "new_paid_ai_calls": 0,
        "warning": "A dated planning application is not an original public "
                   "announcement, and an issued permit is not proof of open "
                   "procurement. Applicant/agent names are source claims, not "
                   "verified buyer contacts. Do not pad or sell this worklist.",
        "outputs": [OUTPUT, STATUS],
    }
    (root / STATUS).write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status
