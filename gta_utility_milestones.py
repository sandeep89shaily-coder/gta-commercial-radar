"""Read official OEB facilities proceedings and IESO connection milestones."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from gta_public_procurement import AGENT, _download, _text, _write_csv, _write_json
from robots_policy import evaluate

OEB_APPLICATIONS = "https://oeb.ca/applications/applications-oeb"
OEB_DECISIONS = "https://www.oeb.ca/applications/major-decisions"
IESO_QUEUE = "https://www.ieso.ca/-/media/files/IESO/files/applicationstatusdata.json"
IESO_PAGE = "https://www.ieso.ca/en/Sector-Participants/Connection-Process/Application-Status"
OUTPUT = "GTA_RADAR_UTILITY_MILESTONES.csv"
STATUS = "GTA_RADAR_UTILITY_MILESTONES_STATUS.json"
STATE = "GTA_RADAR_UTILITY_MILESTONES_STATE.json"
FIELDS = ("source", "record_id", "company", "title", "scope", "stage", "location",
          "proposed_in_service", "source_event_date", "source_event_date_basis",
          "source_url", "observation", "observed_on", "procurement_status")
GRID = re.compile(r"\b(?:electricity|transmission|substations?|transformers?|switchgear|"
                  r"switching stations?|large load|reinforcement|distribution station)\b", re.I)


def _fetch(url):
    # Preserve the configured publisher's policy gate for webpage/queue collection.
    with requests.Session() as session:
        allowed, reason = evaluate(session, url, AGENT, timeout=7)
    if not allowed:
        raise ValueError(reason)
    return _download(url, 6_000_000)


def _table_date(value):
    for form in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return dt.datetime.strptime(value, form).date()
        except ValueError:
            pass
    return None


def _oeb(raw, url, day, *, decisions):
    page = BeautifulSoup(raw, "html.parser")
    items, matched_tables = [], 0
    needed = ({"Case No.", "Date", "Description and Documents"} if decisions else
              {"Case No.", "Date Filed", "Case Description", "Category"})
    for table in page.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        headers = [c.get_text(" ", strip=True) for c in rows[0].find_all("th", recursive=False)]
        if not needed.issubset(headers):
            continue
        matched_tables += 1
        for tr in rows[1:]:
            entries = tr.find_all("td", recursive=False)
            if len(entries) != len(headers):
                continue
            cells = dict(zip(headers, entries))
            values = {key: td.get_text(" ", strip=True) for key, td in cells.items()}
            case = values["Case No."]
            if not re.fullmatch(r"EB-20\d{2}-\d{4}", case):
                continue
            scope = values["Description and Documents" if decisions else "Case Description"]
            if not GRID.search(scope) or (not decisions and values["Category"] != "Facilities"):
                continue
            date = _table_date(values["Date" if decisions else "Date Filed"])
            if not date or not 0 <= (day - date).days <= 90:
                continue
            link = cells["Case No."].find("a", href=True)
            source_url = urljoin(url, link["href"]) if link else url
            parsed = urlsplit(source_url)
            if parsed.scheme != "https" or parsed.netloc not in {"www.rds.oeb.ca", "oeb.ca", "www.oeb.ca"}:
                source_url = url
            items.append(dict(
                source="OEB_DECISION" if decisions else "OEB_APPLICATION",
                record_id=case, company=values.get("Applicant/Issue" if decisions else "Applicant", ""),
                title=scope[:230], scope=scope[:1300],
                stage="DECISION_PUBLISHED" if decisions else "APPLICATION_FILED",
                source_event_date=date.isoformat(),
                source_event_date_basis="OEB_DECISION_LIST_DATE" if decisions else "OEB_FILED_DATE",
                source_url=source_url,
            ))
    if not matched_tables:
        raise ValueError("OEB_CASE_TABLE_SCHEMA_NOT_FOUND")
    return items


def _ieso(raw):
    feed = json.loads(raw)
    if not isinstance(feed, list) or not feed:
        raise ValueError("IESO_QUEUE_SCHEMA_CHANGED")
    items, seen, valid = [], set(), 0
    for row in feed:
        if not isinstance(row, dict):
            continue
        case = _text(row.get("CaaIdAndDate")).upper()
        title = _text(row.get("Name"))
        if not re.fullmatch(r"20\d{2}-[A-Z0-9-]{3,40}", case) or not title:
            continue
        if case in seen:
            raise ValueError("IESO_DUPLICATE_CAA_IDENTIFIER")
        seen.add(case)
        valid += 1
        kind, stage = _text(row.get("Type")), _text(row.get("SiaStatus"))
        if not re.search(r"load|transmission|protection|station", kind + " " + title, re.I):
            continue
        if re.search(r"withdrawn|cancelled|canceled|retired", stage, re.I):
            continue
        plain = lambda field: BeautifulSoup(str(row.get(field) or ""), "html.parser").get_text(" ", strip=True)
        items.append(dict(source="IESO_QUEUE", record_id=case, title=title, company=_text(row.get("Applicant")),
                          stage=stage, scope=f"{kind} · {plain('Size')}", location=_text(row.get("Location")),
                          proposed_in_service=plain("ProposedInServiceDate"),
                          source_event_date="", source_event_date_basis="IESO_PUBLIC_RECORD_DATE_NOT_STATED",
                          source_url=IESO_PAGE))
    if valid < len(feed) * 0.90:
        raise ValueError("IESO_IDENTITY_COVERAGE_DEGRADED")
    return items


def run(results, *, today=None, fetch=_fetch):
    root = Path(results)
    root.mkdir(parents=True, exist_ok=True)
    day = today or dt.date.today()
    stamp = day.isoformat()
    sources = {
        "OEB_APPLICATION": (OEB_APPLICATIONS, lambda raw: _oeb(raw, OEB_APPLICATIONS, day, decisions=False)),
        "OEB_DECISION": (OEB_DECISIONS, lambda raw: _oeb(raw, OEB_DECISIONS, day, decisions=True)),
        "IESO_QUEUE": (IESO_QUEUE, _ieso),
    }
    health, rows = {}, []
    state_path = root / STATE
    history = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
    prior = history.get("IESO_QUEUE", {})
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending = {name: pool.submit(fetch, url) for name, (url, _) in sources.items()}
        for name, future in pending.items():
            try:
                items = sources[name][1](future.result())
                health[name] = {"status": "COLLECTED", "records": len(items)}
                if name == "IESO_QUEUE":
                    current = {}
                    for item in items:
                        case = item["record_id"]
                        fields = [item[k] for k in ("title", "company", "scope", "stage",
                                                    "location", "proposed_in_service")]
                        current[case] = fields
                        item["observation"] = ("INITIAL_BASELINE" if not prior else
                            "FIRST_OBSERVED_UNDATED" if case not in prior else
                            "CHANGED_SINCE_LAST_SNAPSHOT" if prior[case] != fields else "UNCHANGED")
                    history[name] = {**prior, **current}
                for item in items:
                    item.update(observed_on=stamp, procurement_status="UNKNOWN")
                rows.extend(items)
            except (requests.RequestException, OSError, ValueError, TypeError, KeyError) as exc:
                health[name] = {"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"[:220]}
    _write_csv(root / OUTPUT, rows, FIELDS)
    _write_json(state_path, history)
    summary = {
        "status": "COLLECTED" if all(h["status"] == "COLLECTED" for h in health.values())
        else "PARTIAL_UTILITY_COLLECTION", "as_of": stamp, "sources": health,
        "five_day_dated_utility_milestones": sum(
            bool(r.get("source_event_date")) and
            0 <= (day-dt.date.fromisoformat(r["source_event_date"])).days <= 4 for r in rows),
        "ieso_first_observed_undated": sum(r.get("observation") == "FIRST_OBSERVED_UNDATED" for r in rows),
        "ieso_changed_rows": sum(r.get("observation") == "CHANGED_SINCE_LAST_SNAPSHOT" for r in rows),
        "paid_calls": 0, "publication_approved": False,
    }
    _write_json(root / STATUS, summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.results), indent=2))
