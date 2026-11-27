"""Daily official public procurement snapshots and a five-day review worklist."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import requests

from gta_freshness import _date
from toronto_current_open_ckan import API, DATASET

INVENTORY = "GTA_RADAR_PUBLIC_PROCUREMENT.csv"
FIVE_DAY = "GTA_RADAR_PUBLIC_PROCUREMENT_FIVE_DAY.csv"
STATUS = "GTA_RADAR_PUBLIC_PROCUREMENT_STATUS.json"
STATE = "GTA_RADAR_PUBLIC_PROCUREMENT_STATE.json"
CANADA_BASE = "https://canadabuys.canada.ca/opendata/pub/"
CANADA_OPEN = "openTenderNotice-ouvertAvisAppelOffres.csv"
CANADA_NEW = "newTenderNotice-nouvelAvisAppelOffres.csv"
TORONTO_AWARDS = "tobids-awarded-contracts"
TORONTO_ORG = "City of Toronto"
MAX_DOWNLOAD = 64_000_000
AGENT = "GTA-Radar-PublicSources/1.0"
EQUIPMENT = re.compile(
    r"\b(?:HVAC|ventilation|chillers?|compressors?|generators?|switchgear|transformers?|"
    r"motor control cent(?:re|er)s?|pumps?|pumping stations?|valves?|boilers?|"
    r"conveyors?|machinery|machine tools?|CNC|robotics?|industrial automation|"
    r"water treatment|wastewater|dust collect(?:or|ion)|scrubbers?|"
    r"industrial refrigeration|industrial equipment|lift stations?|forklifts?|"
    r"boom lifts?|scissor lifts?|cranes?|hoists?)\b", re.I)
FIELDS = (
    "source", "record_id", "solicitation_id", "buyer", "city", "delivery_region",
    "title", "scope", "category", "notice_type", "commodity_codes", "supplier",
    "amount", "currency", "publication_date", "amendment_number", "amendment_date", "closing_at",
    "award_date", "award_notice_date", "source_status", "source_url", "source_url_basis",
    "source_event_date", "source_event_type", "first_observed_on", "observed_on",
    "procurement_state", "in_new_notices_feed",
)


def _download(url, limit=MAX_DOWNLOAD):
    """Only the official endpoints constructed by these collectors are fetched."""
    with requests.get(url, headers={"User-Agent": AGENT}, timeout=(7, 20),
                      stream=True, allow_redirects=False) as response:
        if response.status_code != 200:
            raise ValueError(f"HTTP_{response.status_code}")
        body = bytearray()
        for chunk in response.iter_content(65536):
            body.extend(chunk)
            if len(body) > limit:
                raise ValueError("SOURCE_SIZE_LIMIT")
        return bytes(body)


def _text(value):
    return " ".join(str(value or "").split())


def _csv_rows(raw, required):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    if not set(required).issubset(reader.fieldnames or ()):
        raise ValueError("SOURCE_CSV_REQUIRED_COLUMNS_MISSING")
    return reader


def _write_csv(path, rows, fields=FIELDS):
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            values = {field: str(row.get(field, "") or "") for field in fields}
            writer.writerow({key: "'" + value if value.lstrip().startswith(
                ("=", "-", "+", "@")) else value for key, value in values.items()})
    temp.replace(path)


def _write_json(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _toronto_rows(dataset, download, required):
    package = json.loads(download(API + "package_show?" + urlencode({"id": dataset}), 1_000_000))
    if package.get("success") is not True or package["result"].get("name") != dataset:
        raise ValueError("TORONTO_DATASET_IDENTITY_NOT_VERIFIED")
    meta = package["result"]
    if meta.get("license_title") != "open-government-licence-toronto":
        raise ValueError("TORONTO_OPEN_LICENCE_METADATA_CHANGED")
    available = [item for item in meta["resources"] if item.get("datastore_active") is True]
    if len(available) != 1:
        raise ValueError("TORONTO_DATASTORE_NOT_UNIQUE")
    resource = available[0]
    identity = resource["id"]
    if not re.fullmatch(r"[0-9a-f-]{36}", identity):
        raise ValueError("TORONTO_DATASTORE_RESOURCE_ID_INVALID")
    url = API.split("/api/3/", 1)[0] + "/datastore/dump/" + identity
    snapshot = resource.get("metadata_modified") or meta.get("metadata_modified")
    return _csv_rows(download(url), required), identity, str(snapshot or "")


def _toronto(dataset, download, day):
    is_award = dataset == TORONTO_AWARDS
    required = {"Document Number", "Solicitation Document Description", "Division"}
    required.update({"Award"} if is_award else {"Issue Date", "Submission Deadline"})
    rows, resource, snapshot = _toronto_rows(dataset, download, required)
    results = []
    for row in rows:
        doc = _text(row["Document Number"]).removeprefix("Doc-")
        scope = _text(row["Solicitation Document Description"])
        if not re.fullmatch(r"\d{8,12}", doc) or not EQUIPMENT.search(scope):
            continue
        source_url = API + "datastore_search?" + urlencode({
            "resource_id": resource, "filters": json.dumps({"Document Number": row["Document Number"]}),
            "limit": 20,
        })
        base = dict(source="TORONTO_BIDS", solicitation_id=doc, buyer=TORONTO_ORG,
                    city="Toronto", delivery_region="Toronto", title=scope[:230], scope=scope[:1400],
                    category=_text(row.get("Division")), notice_type=_text(row.get("RFx (Solicitation) Type")),
                    source_url=source_url, source_url_basis="OFFICIAL_EXACT_DOCUMENT_NUMBER_LOOKUP")
        if is_award:
            try:
                awards = json.loads(row.get("Award") or "[]")
                # CKAN's CSV export JSON-encodes this string field one extra time.
                if isinstance(awards, str):
                    awards = json.loads(awards or "[]")
            except json.JSONDecodeError as exc:
                raise ValueError("TORONTO_AWARD_DETAIL_SCHEMA_CHANGED") from exc
            if not isinstance(awards, list) or any(not isinstance(a, dict) for a in awards):
                raise ValueError("TORONTO_AWARD_DETAIL_SCHEMA_CHANGED")
            for award in awards:
                who = _text(award.get("Successful_Bidder"))
                award_date = _date(award.get("AwardedDate") or award.get("Date_Awarded"))
                if not who or award.get("Cancellation_Date") or not award_date or award_date > day:
                    continue
                results.append(dict(base, record_id=f"{doc}:{who}:{award_date}", supplier=who,
                                    amount=_text(award.get("Award_Amount") or award.get("Initial_Contract_Val")),
                                    currency="CAD", award_date=award_date.isoformat(), source_status="AWARDED"))
        else:
            results.append(dict(base, record_id=doc, publication_date=_text(row["Issue Date"]),
                                closing_at=_text(row["Submission Deadline"]), source_status="OPEN_SNAPSHOT"))
    return results, snapshot


def _canada(filename, download, is_award=False):
    url = CANADA_BASE + filename
    required = {"referenceNumber-numeroReference", "title-titre-eng", "solicitationNumber-numeroSollicitation",
                "publicationDate-datePublication", "regionsOfDelivery-regionsLivraison-eng"}
    required.update({"awardStatus-attributionStatut-eng", "contractAwardDate-dateAttributionContrat"}
                    if is_award else {"tenderStatus-appelOffresStatut-eng", "tenderClosingDate-appelOffresDateCloture"})
    results = []
    for row in _csv_rows(download(url), required):
        region = _text(row["regionsOfDelivery-regionsLivraison-eng"])
        title = _text(row["title-titre-eng"])
        number = _text(row["referenceNumber-numeroReference"])
        if not number or not title or not re.search(r"\bOntario\b", region, re.I):
            continue
        description = _text(row.get("awardDescription-descriptionAttribution-eng" if is_award
                                    else "tenderDescription-descriptionAppelOffres-eng"))
        category = _text(row.get("unspscDescription-eng"))
        if not EQUIPMENT.search(" ".join((title, category, description[:1200]))):
            continue
        linked = urlsplit(_text(row.get("noticeURL-URLavis-eng")))
        native = (linked.scheme == "https" and linked.netloc == "canadabuys.canada.ca"
                  and linked.path.startswith("/en/tender-opportunities/tender-notice/"))
        results.append(dict(
            source="CANADABUYS", record_id=number,
            solicitation_id=_text(row["solicitationNumber-numeroSollicitation"]),
            buyer=_text(row.get("contractingEntityName-nomEntitContractante-eng")),
            city="Ontario (site unverified)", delivery_region=region, title=title[:230],
            scope=(description or title)[:1400], category=category[:300],
            notice_type=_text(row.get("noticeType-avisType-eng")),
            commodity_codes=_text(row.get("unspsc")), source_url=linked.geturl() if native else url,
            source_url_basis="PUBLISHER_NOTICE_URL" if native else "OFFICIAL_CSV_LOOK_UP_REFERENCE",
            publication_date="" if is_award else _text(row["publicationDate-datePublication"]),
            award_notice_date=_text(row["publicationDate-datePublication"]) if is_award else "",
            amendment_number=_text(row.get("amendmentNumber-numeroModification")),
            amendment_date=_text(row.get("amendmentDate-dateModification")),
            closing_at=_text(row.get("tenderClosingDate-appelOffresDateCloture")),
            award_date=_text(row.get("contractAwardDate-dateAttributionContrat")),
            supplier=_text(row.get("supplierLegalName-nomLegalFournisseur-eng")),
            amount=_text(row.get("totalContractValue-valeurTotaleContrat") or row.get("contractAmount-montantContrat")),
            currency=_text(row.get("contractCurrency-contratMonnaie")),
            source_status=_text(row.get("awardStatus-attributionStatut-eng" if is_award else
                                        "tenderStatus-appelOffresStatut-eng")).upper(),
        ))
    return results, ""


def _award_key(row):
    return row["source"], row["buyer"].strip().casefold(), row["solicitation_id"].strip().casefold()


def _recent(day, value):
    date = _date(value)
    return bool(date and 0 <= (day - date).days <= 4)


def run(results, *, today=None, download=_download):
    root = Path(results)
    root.mkdir(parents=True, exist_ok=True)
    day = today or dt.date.today()
    stamp = day.isoformat()
    year = day.year if day.month >= 4 else day.year - 1
    annual = [f"{y}-{y+1}-awardNotice-avisAttribution.csv"
              for y in range(year - (day.month == 4 and day.day <= 4), year + 1)]
    sources = {
        "TORONTO_OPEN": lambda: _toronto(DATASET, download, day),
        "TORONTO_AWARDS": lambda: _toronto(TORONTO_AWARDS, download, day),
        "CANADABUYS_NEW": lambda: _canada(CANADA_NEW, download),
        "CANADABUYS_OPEN": lambda: _canada(CANADA_OPEN, download),
        **{f"CANADABUYS_AWARDS_{name[:9]}": lambda name=name: _canada(name, download, True)
           for name in annual},
    }
    health, data = {}, {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = {name: pool.submit(fetch) for name, fetch in sources.items()}
        for name, future in pending.items():
            try:
                data[name], snapshot = future.result()
                health[name] = {"status": "COLLECTED", "industrial_rows": len(data[name]),
                                "publisher_snapshot_metadata": snapshot}
                if snapshot and not _recent(day, snapshot):
                    health[name]["status"] = "STALE_SNAPSHOT"
            except (requests.RequestException, OSError, ValueError, TypeError, KeyError, csv.Error) as exc:
                data[name] = []
                health[name] = {"status": "FAILED", "error": f"{type(exc).__name__}:{exc}"[:220]}

    state_path = root / STATE
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
    # Persist award identities across source outages; a later absence cannot reopen them.
    prior_awards = {tuple(key): date for key, date in state.get("awarded_identities", [])}
    award_rows = []
    for name, rows in data.items():
        if "AWARDS" not in name:
            continue
        for row in rows:
            date = _date(row.get("award_date"))
            if (not date or date > day or not row.get("supplier")
                    or row["source_status"] not in {"ACTIVE", "AWARDED", "COMPLETED", "EXPIRED"}):
                continue
            key = _award_key(row)
            if key[1] and key[2]:
                prior_awards[key] = max(prior_awards.get(key, ""), date.isoformat())
            if (day - date).days <= 45:
                award_rows.append(dict(row, observed_on=stamp, procurement_state="AWARD_RECORDED",
                                       source_event_date=date.isoformat(), source_event_type="AWARD_DATE"))

    new_ids = {r["record_id"] for r in data["CANADABUYS_NEW"]}
    open_ids = {r["record_id"] for r in data["CANADABUYS_OPEN"]}
    old = state.get("tenders", {})
    next_state = {k: v for k, v in old.items() if v.get("observed_on", "") >=
                  (day - dt.timedelta(days=45)).isoformat()}
    open_rows, fresh_rows = [], []
    used = set()
    for source in ("TORONTO_OPEN", "CANADABUYS_OPEN", "CANADABUYS_NEW"):
        for row in sorted(data[source], key=lambda item: item.get("amendment_date", ""), reverse=True):
            if source == "CANADABUYS_NEW" and row["record_id"] in open_ids:
                continue
            identity = row["source"] + ":" + row["record_id"]
            if identity in used:
                continue
            used.add(identity)
            issue, closes = _date(row["publication_date"]), _date(row["closing_at"])
            if not issue or issue > day or not closes or closes < day:
                continue
            if row["source_status"] not in {"OPEN", "OPEN_SNAPSHOT"}:
                continue
            if prior_awards.get(_award_key(row), "") >= issue.isoformat():
                continue
            observed = old.get(identity, {})
            material = [row["title"], row["scope"], row["closing_at"]]
            amendment_number = row.get("amendment_number", "")
            original_revision = bool(amendment_number) and set(amendment_number) == {"0"}
            amended = "" if original_revision else row.get("amendment_date", "")
            material_date = observed.get("material_amendment_date", "")
            if observed and observed.get("material") != material and _recent(day, amended):
                material_date = _date(amended).isoformat()
            if not _recent(day, material_date):
                material_date = ""
            original = observed.get("publication_date") or (
                issue.isoformat() if _date(amended) != issue else "")
            row["publication_date"] = original
            event_date, event_type = original, "ORIGINAL_SOLICITATION_POSTING" if original else "UNDATED_ORIGINAL_POSTING"
            if material_date and material_date > event_date:
                event_date, event_type = material_date, "PUBLISHER_DATED_MATERIAL_AMENDMENT"
            first = observed.get("first_observed_on") or stamp
            trusted = health[source]["status"] == "COLLECTED"
            row.update(first_observed_on=first, observed_on=stamp, source_event_date=event_date,
                       source_event_type=event_type, in_new_notices_feed=row["record_id"] in new_ids,
                       procurement_state=("STALE_SNAPSHOT_RECHECK_REQUIRED" if not trusted
                                          else "CLOSING_TODAY_VERIFY_TIME" if closes == day
                                          else "NEW_NOTICE_PENDING_OPEN_SNAPSHOT_RECHECK" if source == "CANADABUYS_NEW"
                                          else "OPEN_SNAPSHOT_REQUIRES_BUYER_RECHECK"))
            if trusted:
                next_state[identity] = dict(observed_on=stamp, first_observed_on=first, material=material,
                                           material_amendment_date=material_date, publication_date=original)
            open_rows.append(row)
            if trusted and closes > day and _recent(day, event_date):
                fresh_rows.append(row)
    _write_csv(root / INVENTORY, open_rows + award_rows)
    _write_csv(root / FIVE_DAY, sorted(fresh_rows, key=lambda row: row["source_event_date"], reverse=True))
    _write_json(state_path, {"tenders": next_state, "awarded_identities": sorted(prior_awards.items())})
    summary = {"status": "COLLECTED" if all(h["status"] == "COLLECTED" for h in health.values())
               else "PARTIAL_PUBLIC_PROCUREMENT_COLLECTION", "as_of": stamp, "sources": health,
               "open_snapshot_rows": len(open_rows), "recent_awards": len(award_rows),
               "five_day_review_rows": len(fresh_rows), "paid_calls": 0, "publication_approved": False}
    _write_json(root / STATUS, summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.results), indent=2))
