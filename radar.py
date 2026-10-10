from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import re
import sqlite3
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

UA = "GTACommercialRadar/0.5.0 (+local research prototype)"
GTA_CITIES = {
    "TORONTO","BRAMPTON","MISSISSAUGA","CALEDON","BURLINGTON","OAKVILLE","MILTON","HALTON HILLS",
    "VAUGHAN","MARKHAM","RICHMOND HILL","AURORA","NEWMARKET","WHITCHURCH-STOUFFVILLE",
    "WHITCHURCH STOUFFVILLE","EAST GWILLIMBURY","GEORGINA","KING","PICKERING","AJAX","WHITBY","OSHAWA",
    "CLARINGTON","UXBRIDGE","SCUGOG","BROCK",
    "SCARBOROUGH","NORTH YORK","ETOBICOKE","EAST YORK","YORK",
    "WOODBRIDGE","MAPLE","THORNHILL","KLEINBURG","ACTON","BOLTON"
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def norm_field(k: Any) -> str:
    s = str(k or "").strip().upper()
    s = re.sub(r"[^A-Z0-9]+", "_", s).strip("_")
    return s


def clean_value(v: Any) -> Any:
    if pd.isna(v) if not isinstance(v, (list, dict)) else False:
        return ""
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.isoformat()
    return v


def normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {norm_field(k): clean_value(v) for k, v in row.items()}


def canon_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()


def stable_key(row: Dict[str, Any], source: Dict[str, Any]) -> str:
    fields = [norm_field(x) for x in source.get("key_fields", [])]
    vals = [str(row.get(f, "")).strip() for f in fields]
    if fields and all(vals):
        return "|".join(vals)
    # fallbacks to common IDs
    for k in ("OBJECTID", "_ID", "ID", "LICENCE_NUMBER", "LICENSE_NUMBER", "PERMITNUMBER", "BP_NO"):
        if str(row.get(k, "")).strip():
            return str(row[k]).strip()
    # final fallback: stable composite from identity-ish columns; if the record changes
    # materially this becomes a NEW record, so sources should define key_fields whenever possible.
    parts = []
    for k in [*source.get("entity_fields", []), *source.get("address_fields", []), *source.get("date_fields", [])]:
        nk = norm_field(k)
        if str(row.get(nk, "")).strip():
            parts.append(f"{nk}={row.get(nk)}")
    return "HASH:" + sha256_text("|".join(parts) if parts else canon_json(row))[:24]


def first_nonempty(row: Dict[str, Any], fields: Iterable[str]) -> str:
    for f in fields:
        v = row.get(norm_field(f), "")
        if v is not None and str(v).strip() and str(v).lower() not in {"nan", "none", "nat"}:
            return str(v).strip()
    return ""


def combine_fields(row: Dict[str, Any], fields: Iterable[str]) -> str:
    vals = []
    for f in fields:
        v = row.get(norm_field(f), "")
        s = str(v).strip() if v is not None else ""
        if s and s.lower() not in {"nan", "none", "nat"}:
            vals.append(s)
    return " ".join(vals)


def parse_dateish(v: Any) -> str:
    if v in (None, ""):
        return ""
    if isinstance(v, (int, float)) and v > 10_000_000_000:
        try:
            return datetime.fromtimestamp(float(v)/1000, tz=timezone.utc).date().isoformat()
        except Exception:
            return ""
    s = str(v).strip()
    if not s:
        return ""
    # ISO first
    try:
        return pd.to_datetime(s, errors="raise", utc=True).date().isoformat()
    except Exception:
        return s[:10] if re.match(r"\d{4}-\d{2}-\d{2}", s) else ""


def source_date(row: Dict[str, Any], source: Dict[str, Any]) -> str:
    for f in source.get("date_fields", []):
        d = parse_dateish(row.get(norm_field(f)))
        if d:
            return d
    return ""


def gta_match(row: Dict[str, Any]) -> bool:
    text = " ".join(str(v) for v in row.values() if v not in (None, "")).upper()
    return any(city in text for city in GTA_CITIES)


def brampton_sector(row: Dict[str, Any]) -> Tuple[str, float]:
    sub = str(row.get("SUBDESC", "")).strip().lower()
    work = str(row.get("WORKDESC", "")).strip().lower()
    residential_terms = (
        "single detached", "semi-detached", "townhouse", "residential", "two unit dwelling",
        "apartment dwelling", "accessory residential", "deck", "basement finish", "garage"
    )
    if any(x in sub for x in residential_terms) or "creating second unit" in work:
        return "LOW", 0.99
    if str(row.get("SECOND_UNIT", "")).strip().upper() not in {"", "N", "NO", "0"}:
        return "LOW", 0.99
    if sub.startswith(("d:", "e:", "f1:", "f2:", "f3:", "a1:", "a2:", "b1:", "b2:", "b3:")):
        return "HIGH", 0.98
    if any(x in sub for x in ("restaurant", "car wash", "fire station")):
        return "HIGH", 0.97
    if any(x in work for x in ("non residential demolition", "interior/unit finish", "change of use")):
        return "HIGH", 0.90
    return "UNKNOWN", 0.30


def mississauga_sector(row: Dict[str, Any]) -> Tuple[str, float]:
    ft = str(row.get("FILE_TYPE", "")).strip().upper()
    bt = str(row.get("BLDG_TYPE", "")).strip().upper()
    if ft in {"COMMERCIAL", "INDUSTRIAL", "PUBLIC"}:
        return "HIGH", 0.99
    if ft == "RESIDENTIAL":
        return "LOW", 0.99
    if any(x in bt for x in ("COMMERCIAL", "INDUSTRIAL", "SCHOOL", "CHURCH", "PUBLIC", "GOVERNMENT")):
        return "HIGH", 0.92
    return "UNKNOWN", 0.30


def toronto_permit_sector(row: Dict[str, Any]) -> Tuple[str, float]:
    # Toronto publishes non-residential GFA columns. Prefer those over text.
    nonres_cols = [
        "ASSEMBLY", "INSTITUTIONAL", "BUSINESS_AND_PERSONAL_SERVICES", "MERCANTILE", "INDUSTRIAL"
    ]
    def num(k: str) -> float:
        try:
            return float(str(row.get(k, "0")).replace(",", "") or 0)
        except Exception:
            return 0.0
    nonres = sum(max(0.0, num(k)) for k in nonres_cols)
    residential = max(0.0, num("RESIDENTIAL"))
    if nonres > 0:
        return "HIGH", 0.98
    if residential > 0 and nonres == 0:
        return "LOW", 0.95
    text = " ".join(str(row.get(k, "")) for k in ("CURRENT_USE", "PROPOSED_USE", "STRUCTURE_TYPE", "WORK", "DESCRIPTION")).lower()
    if any(x in text for x in ("commercial", "retail", "office", "restaurant", "industrial", "warehouse", "clinic", "school", "institutional", "mercantile")):
        return "HIGH", 0.80
    if any(x in text for x in ("single family", "detached", "semi-detached", "townhouse", "residential")):
        return "LOW", 0.80
    return "UNKNOWN", 0.25


def relevance(row: Dict[str, Any], source: Dict[str, Any]) -> Tuple[str, float]:
    sid = source["id"]
    fam = source.get("family", "")
    if sid == "brampton_building_permits":
        return brampton_sector(row)
    if sid == "mississauga_issued_building_permits":
        return mississauga_sector(row)
    if sid.startswith("toronto_") and fam in {"permit", "permit_history"}:
        return toronto_permit_sector(row)
    if fam in {"business_licence", "health_inspection", "regulated_registry", "cannabis_application", "industrial_regulatory"}:
        return "HIGH", 0.95
    if fam == "planning_application":
        return "UNKNOWN", 0.50
    return "UNKNOWN", 0.30


def normalized_summary(row: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    entity = first_nonempty(row, source.get("entity_fields", []))
    address = combine_fields(row, source.get("address_fields", []))
    desc = combine_fields(row, source.get("description_fields", []))
    status = first_nonempty(row, source.get("status_fields", []))
    value = first_nonempty(row, source.get("value_fields", []))
    rel, rel_conf = relevance(row, source)
    event_type = {
        "permit": "PERMIT_RECORD",
        "permit_history": "PERMIT_HISTORY",
        "business_licence": "BUSINESS_LICENCE_RECORD",
        "health_inspection": "HEALTH_INSPECTION_RECORD",
        "regulated_registry": "REGULATED_REGISTRY_RECORD",
        "planning_application": "PLANNING_APPLICATION_RECORD",
        "cannabis_application": "CANNABIS_RETAIL_APPLICATION",
        "industrial_regulatory": "INDUSTRIAL_REGULATORY_NOTICE",
    }.get(source.get("family"), "SOURCE_RECORD")
    summary = {
        "source_id": source["id"],
        "source_name": source["name"],
        "jurisdiction": source.get("jurisdiction", ""),
        "region": source.get("region", ""),
        "event_type": event_type,
        "entity_name": entity,
        "address": address,
        "description": desc,
        "status": status,
        "source_date": source_date(row, source),
        "value": value,
        "commercial_relevance": rel,
        "relevance_confidence": rel_conf,
    }
    if source.get("evidence_fields"):
        summary["evidence_url"] = first_nonempty(row, source["evidence_fields"]) or source.get("official_page", "")
    return summary


@dataclass
class Snapshot:
    source: Dict[str, Any]
    rows: List[Dict[str, Any]]
    raw_bytes: bytes
    resource_url: str
    metadata: Dict[str, Any]
    is_complete: bool = True
    mode: str = "full"


class Http:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA})

    def get(self, url: str, *, params=None, timeout=(15, 120), retries=3) -> requests.Response:
        return self._request("GET", url, params=params, timeout=timeout, retries=retries)

    def head(self, url: str, *, timeout=(15, 60), retries=2) -> requests.Response:
        return self._request("HEAD", url, timeout=timeout, retries=retries, allow_redirects=True)

    def post(self, url: str, *, data=None, timeout=(15, 60), retries=1) -> requests.Response:
        return self._request("POST", url, data=data, timeout=timeout, retries=retries)

    def _request(self, method, url, *, timeout, retries, **kwargs):
        last = None
        for attempt in range(1, retries + 1):
            try:
                r = self.s.request(method, url, timeout=timeout, **kwargs)
                r.raise_for_status()
                return r
            except Exception as e:
                last = e
                if attempt == retries:
                    raise
                print(f"  HTTP {method} retry {attempt}/{retries}: {type(e).__name__}", flush=True)
                time.sleep(attempt * 1.5)
        raise RuntimeError(str(last))


def _arcgis_date_clause(fields: List[str], since_date: str) -> str:
    if not fields or not since_date:
        return ""
    lit = f"DATE '{since_date}'"
    return " OR ".join(f"{norm_field(f)} >= {lit}" for f in fields)


def collect_arcgis(source: Dict[str, Any], http: Http, progress=True, *, smart=False, since_date: Optional[str]=None, force_full=False) -> Snapshot:
    qurl = source["query_url"]
    page_size = int(source.get("page_size", 1000))
    base_where = str(source.get("server_where") or "1=1")
    incremental = bool(smart and since_date and not force_full)
    if incremental:
        fields = source.get("incremental_fields") or source.get("freshness_fields") or source.get("date_fields") or []
        recent = _arcgis_date_clause(fields, since_date)
        if not recent:
            raise RuntimeError(f"{source['id']} has no usable incremental date fields; run reconcile instead")
        where = f"({base_where}) AND ({recent})"
        mode = "incremental"
    else:
        where = base_where
        mode = "full"

    count_resp = http.get(qurl, params={"f":"json","where":where,"returnCountOnly":"true"}, timeout=(10,40)).json()
    if "error" in count_resp:
        raise RuntimeError(f"ArcGIS {mode} count query rejected filter: {count_resp['error']}")
    total = int(count_resp.get("count", 0))
    if progress:
        print(f"  {source['name']}: {mode} query matches {total:,} record(s)", flush=True)
    rows: List[Dict[str, Any]]=[]; offset=0
    while True:
        params={"f":"json","where":where,"outFields":"*","returnGeometry":"false",
                "resultOffset":offset,"resultRecordCount":page_size,"orderByFields":"OBJECTID ASC"}
        data=http.get(qurl,params=params,timeout=(15,120)).json()
        if "error" in data:
            params.pop("orderByFields",None)
            data=http.get(qurl,params=params,timeout=(15,120)).json()
        if "error" in data: raise RuntimeError(data["error"])
        feats=data.get("features",[])
        rows.extend(normalize_row(f.get("attributes") or {}) for f in feats)
        if progress and total:
            print(f"  {source['name']}: {len(rows):,}/{total:,} fetched", flush=True)
        exceeded=bool(data.get("exceededTransferLimit"))
        if not feats or (len(feats)<page_size and not exceeded): break
        offset += len(feats)
    if len(rows) != total:
        raise RuntimeError(f"ArcGIS {mode} pagination incomplete: expected {total:,}, fetched {len(rows):,}; refusing to persist partial data")
    raw="\n".join(canon_json(r) for r in rows).encode("utf-8")
    meta={"reported_count":total,"server_where":where,"snapshot_mode":mode,"since_date":since_date or ""}
    return Snapshot(source,rows,raw,source["url"],meta,is_complete=not incremental,mode=mode)

def _title_score(title: str, query: str) -> int:
    a = set(re.findall(r"[a-z0-9]+", title.lower()))
    b = set(re.findall(r"[a-z0-9]+", query.lower()))
    return len(a & b) * 10 - abs(len(a) - len(b))


def resolve_ckan_package(source: Dict[str, Any], http: Http) -> Dict[str, Any]:
    """Resolve a CKAN package deterministically whenever we know its id/slug.

    Fuzzy package_search is retained only for research-stage sources. Production-ready
    sources should set package_id or package_slug so a similarly named dataset can
    never silently replace the intended feed.
    """
    base = source["api_base"].rstrip("/")
    exact = source.get("package_id") or source.get("package_slug")
    if exact:
        show = http.get(base + "/package_show", params={"id": exact}, timeout=(10,40)).json()
        if not show.get("success") or not show.get("result"):
            raise RuntimeError(f"CKAN exact dataset not found: {exact}")
        pkg = show["result"]
    else:
        query = source["package_query"]
        data = http.get(base + "/package_search", params={"q": query, "rows": 20}, timeout=(10,40)).json()
        if not data.get("success") or not data.get("result", {}).get("results"):
            raise RuntimeError(f"CKAN dataset not found for query: {query}")
        results = data["result"]["results"]
        best = max(results, key=lambda p: _title_score(p.get("title", ""), query))
        show = http.get(base + "/package_show", params={"id": best["id"]}, timeout=(10,40)).json()
        pkg = show["result"] if show.get("success") else best

    expected = str(source.get("expected_package_title") or "").strip().lower()
    if expected and expected not in str(pkg.get("title") or "").lower():
        raise RuntimeError(
            f"CKAN dataset identity mismatch: expected title containing {source['expected_package_title']!r}, "
            f"got {pkg.get('title')!r}"
        )
    return pkg


def choose_ckan_resource(pkg: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    resources = pkg.get("resources", [])
    pinned = source.get("resource_id")
    if pinned:
        match = None
        for r in resources:
            if str(r.get("id") or "") == str(pinned):
                match = r
                break
        if match is None:
            raise RuntimeError(
                f"Pinned CKAN resource {pinned} not present in package {pkg.get('title')!r}; "
                "source metadata may have changed"
            )
        # A stable resource ID is the strongest selector, but still validate any
        # supplied semantic constraints so a provider-side resource replacement
        # cannot silently point us at a different table.
        exact_name = source.get("expected_resource_name")
        if exact_name and str(match.get("name") or "").strip().lower() != str(exact_name).strip().lower():
            raise RuntimeError(
                f"Pinned CKAN resource {pinned} has unexpected name {match.get('name')!r}; "
                f"expected {exact_name!r}"
            )
        url = str(match.get("url") or "").lower()
        for token in source.get("resource_url_contains", []) or []:
            if str(token).lower() not in url:
                raise RuntimeError(
                    f"Pinned CKAN resource {pinned} URL failed identity check: missing {token!r}"
                )
        for token in source.get("resource_url_excludes", []) or []:
            if str(token).lower() in url:
                raise RuntimeError(
                    f"Pinned CKAN resource {pinned} URL failed identity check: contains forbidden {token!r}"
                )
        return match

    # Production feeds may specify an exact resource name when a CKAN package
    # contains several deceptively similar tables (e.g. Ontario private schools
    # vs International Private Schools). Never silently substitute another table.
    exact_names = source.get("resource_name_exact") or []
    if isinstance(exact_names, str):
        exact_names = [exact_names]
    exact_names = {str(x).strip().lower() for x in exact_names if str(x).strip()}
    if exact_names:
        exact_matches = [
            r for r in resources
            if str(r.get("name") or "").strip().lower() in exact_names
        ]
        if not exact_matches:
            raise RuntimeError(
                f"Required CKAN resource name not present in package {pkg.get('title')!r}: "
                + ", ".join(sorted(exact_names))
            )
        fmts = [x.upper() for x in source.get("preferred_formats", [])]
        def exact_score(r):
            fmt = str(r.get("format") or "").upper()
            score = 1000
            if fmt in fmts:
                score += max(1, 50 - fmts.index(fmt))
            url = str(r.get("url") or "").lower().split("?",1)[0]
            if url.endswith((".csv",".xlsx",".xls",".json",".geojson",".zip")):
                score += 20
            return (score, str(r.get("last_modified") or r.get("created") or ""))
        return max(exact_matches, key=exact_score)

    names = [x.lower() for x in source.get("preferred_resource_names", [])]
    fmts = [x.upper() for x in source.get("preferred_formats", [])]
    candidates = []
    must_end = [str(x).lower() for x in source.get("resource_url_must_end_with", [])]
    for r in resources:
        fmt = str(r.get("format") or "").upper()
        name = str(r.get("name") or "")
        rurl0 = str(r.get("url") or "").lower().split("?",1)[0]
        if must_end and not any(rurl0.endswith(x) for x in must_end):
            continue
        score = 0
        if any(n in name.lower() for n in names): score += 100
        if fmt in fmts: score += max(1, 20 - fmts.index(fmt))
        if r.get("url"): score += 1
        lname=name.lower()
        # English resources preferred; supporting dictionaries are not data tables.
        if "english" in lname: score += 5
        if any(x in lname for x in ("data dictionary", "supporting file", "metadata")): score -= 150
        if "french" in lname or "français" in lname: score -= 10
        rurl = str(r.get("url") or "").lower().split("?",1)[0]
        # Prefer actual downloadable tabular assets over catalogue/support pages.
        if rurl.endswith((".csv", ".xlsx", ".xls", ".json", ".geojson", ".zip")): score += 40
        elif fmt in {"CSV","XLSX","XLS","JSON","GEOJSON","ZIP"}: score -= 10
        candidates.append((score, r))
    if not candidates:
        raise RuntimeError(f"No resources in CKAN package {pkg.get('title')}")
    return max(candidates, key=lambda x: (x[0], str(x[1].get("last_modified") or x[1].get("created") or "")))[1]


def _read_excel_bytes(content: bytes, fmt: str) -> pd.DataFrame:
    fmt = (fmt or "").upper()
    # XLSX/XLSM are ZIP containers, so magic bytes alone must NOT route them through
    # the generic ZIP archive parser. Explicit engines make BytesIO reliable on Windows.
    if fmt in {"XLSX", "XLSM"} or content[:4] == b"PK\x03\x04":
        try:
            return pd.read_excel(io.BytesIO(content), dtype=str, keep_default_na=False, engine="openpyxl")
        except Exception as e:
            raise RuntimeError(f"XLSX parse failed: {e}") from e
    if fmt == "XLS":
        try:
            return pd.read_excel(io.BytesIO(content), dtype=str, keep_default_na=False)
        except Exception as e:
            raise RuntimeError(f"XLS parse failed: {e}") from e
    raise RuntimeError(f"Unsupported Excel payload format: {fmt or 'unknown'}")


def parse_tabular_bytes(content: bytes, url: str, fmt: str) -> List[Dict[str, Any]]:
    fmt = (fmt or "").upper()
    lower = url.lower().split("?",1)[0]
    dfs = []

    # IMPORTANT: test Excel before generic ZIP because .xlsx itself is a ZIP container.
    if fmt in {"XLSX", "XLS", "XLSM"} or lower.endswith((".xlsx", ".xls", ".xlsm")):
        dfs = [_read_excel_bytes(content, fmt or ("XLSX" if lower.endswith((".xlsx", ".xlsm")) else "XLS"))]
    elif fmt == "ZIP" or lower.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            names = [n for n in z.namelist() if not n.endswith("/")]
            tab = [n for n in names if n.lower().endswith((".csv", ".xlsx", ".xls", ".json", ".geojson"))]
            if not tab:
                raise RuntimeError("ZIP contained no supported tabular file")
            for n in tab:
                b = z.read(n)
                if n.lower().endswith(".csv"):
                    try: df = pd.read_csv(io.BytesIO(b), dtype=str, keep_default_na=False, low_memory=False)
                    except UnicodeDecodeError: df = pd.read_csv(io.BytesIO(b), dtype=str, keep_default_na=False, encoding="latin-1", low_memory=False)
                    dfs.append(df)
                elif n.lower().endswith((".xlsx", ".xls")):
                    dfs.append(_read_excel_bytes(b, "XLSX" if n.lower().endswith(".xlsx") else "XLS"))
                else:
                    obj = json.loads(b.decode("utf-8-sig"))
                    if isinstance(obj, dict) and "features" in obj:
                        return [normalize_row(x.get("properties") or x.get("attributes") or {}) for x in obj["features"]]
                    if isinstance(obj, list): return [normalize_row(x) for x in obj]
    elif fmt in {"JSON", "GEOJSON"} or lower.endswith((".json", ".geojson")):
        obj = json.loads(content.decode("utf-8-sig"))
        if isinstance(obj, dict) and "features" in obj:
            return [normalize_row(x.get("properties") or x.get("attributes") or {}) for x in obj["features"]]
        if isinstance(obj, dict) and "result" in obj and isinstance(obj["result"], dict) and "records" in obj["result"]:
            return [normalize_row(x) for x in obj["result"]["records"]]
        if isinstance(obj, list): return [normalize_row(x) for x in obj]
        raise RuntimeError("Unsupported JSON structure")
    else:
        try:
            dfs = [pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False, low_memory=False)]
        except UnicodeDecodeError:
            dfs = [pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False, encoding="latin-1", low_memory=False)]
    if not dfs:
        return []
    df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
    df.columns = [norm_field(c) for c in df.columns]
    return [{k: clean_value(v) for k, v in rec.items()} for rec in df.to_dict(orient="records")]

def _ckan_meta(pkg: Dict[str, Any], res: Dict[str, Any]) -> Dict[str, Any]:
    material={
        "resource_id":res.get("id"), "resource_url":res.get("url"),
        "resource_modified":res.get("last_modified") or res.get("created"),
        "resource_hash":res.get("hash"), "resource_size":res.get("size"),
        "package_modified":pkg.get("metadata_modified"),
    }
    material["resource_fingerprint"] = sha256_text(canon_json(material))
    return material


def _ckan_unchanged(previous: Optional[Dict[str, Any]], current: Dict[str, Any]) -> bool:
    if not previous: return False
    if str(previous.get("resource_id") or "") != str(current.get("resource_id") or ""):
        return False
    # Resource timestamps are preferable to package timestamps; package descriptions
    # can change without the data changing.
    pm=str(previous.get("resource_modified") or "")
    cm=str(current.get("resource_modified") or "")
    if pm and cm:
        return pm == cm
    pf=str(previous.get("resource_fingerprint") or "")
    cf=str(current.get("resource_fingerprint") or "")
    return bool(pf and cf and pf==cf)


def _ckan_datastore_incremental(source: Dict[str, Any], http: Http, res: Dict[str, Any], since_date: str, progress=True) -> Optional[List[Dict[str, Any]]]:
    if not res.get("datastore_active"):
        return None
    base=source["api_base"].rstrip("/")
    rid=str(res.get("id") or "")
    probe=http.get(base+"/datastore_search",params={"id":rid,"limit":0},timeout=(10,40)).json()
    if not probe.get("success"):
        return None
    fields=probe.get("result",{}).get("fields",[])
    by_norm={norm_field(f.get("id")):f for f in fields}
    candidates=source.get("incremental_fields") or source.get("freshness_fields") or source.get("date_fields") or []
    usable=[]
    for name in candidates:
        f=by_norm.get(norm_field(name))
        if not f: continue
        typ=str(f.get("type") or "").lower()
        # Only use fields whose datastore type supports an ordered date comparison.
        if any(x in typ for x in ("date","time","timestamp")):
            usable.append(str(f.get("id")))
    if not usable:
        return None
    esc=lambda x: x.replace('"','""')
    clauses=[f'"{esc(f)}" >= \'{since_date}\'' for f in usable]
    where=" OR ".join(clauses)
    rows=[]; limit=10000; offset=0
    while True:
        sql=f'SELECT * FROM "{esc(rid)}" WHERE ({where}) LIMIT {limit} OFFSET {offset}'
        data=http.get(base+"/datastore_search_sql",params={"sql":sql},timeout=(15,120)).json()
        if not data.get("success"):
            return None
        batch=data.get("result",{}).get("records",[])
        rows.extend(normalize_row(x) for x in batch)
        if progress:
            print(f"  {source['name']}: datastore incremental fetched {len(rows):,}",flush=True)
        if len(batch)<limit: break
        offset += len(batch)
    return rows


def collect_ckan(source: Dict[str, Any], http: Http, progress=True, *, smart=False, since_date: Optional[str]=None, previous_metadata: Optional[Dict[str, Any]]=None, force_full=False) -> Snapshot:
    pkg=resolve_ckan_package(source,http)
    res=choose_ckan_resource(pkg,source)
    url=res.get("url")
    if not url: raise RuntimeError("CKAN resource has no URL")
    meta={
        "package_id":pkg.get("id"),"package_title":pkg.get("title"),
        "resource_id":res.get("id"),"resource_name":res.get("name"),"resource_format":res.get("format"),
        **_ckan_meta(pkg,res),
    }

    if smart and not force_full and _ckan_unchanged(previous_metadata,meta):
        if progress: print(f"  {source['name']}: resource metadata unchanged; download skipped",flush=True)
        meta["snapshot_mode"]="metadata_unchanged"
        return Snapshot(source,[],b"",url,meta,is_complete=False,mode="metadata_unchanged")

    if smart and since_date and not force_full:
        inc=_ckan_datastore_incremental(source,http,res,since_date,progress=progress)
        if inc is not None:
            if source.get("gta_only"):
                before=len(inc); inc=[x for x in inc if gta_match(x)]
                if progress: print(f"  {source['name']}: GTA filter kept {len(inc):,}/{before:,}",flush=True)
            meta["snapshot_mode"]="incremental_datastore"; meta["since_date"]=since_date
            raw="\n".join(canon_json(r) for r in inc).encode("utf-8")
            return Snapshot(source,inc,raw,url,meta,is_complete=False,mode="incremental_datastore")

    if progress:
        why="resource changed; full file required" if smart and not force_full else "full snapshot"
        print(f"  {source['name']}: {why}; downloading {res.get('name','resource')} [{res.get('format','?')}]",flush=True)
    r=http.get(url,timeout=(20,240),retries=3)
    rows=parse_tabular_bytes(r.content,url,str(res.get("format") or ""))
    if source.get("gta_only"):
        before=len(rows); rows=[x for x in rows if gta_match(x)]
        if progress: print(f"  {source['name']}: GTA filter kept {len(rows):,}/{before:,}",flush=True)
    raw="\n".join(canon_json(x) for x in rows).encode("utf-8")
    meta["snapshot_mode"]="full"
    return Snapshot(source,rows,raw,url,meta,is_complete=True,mode="full")


def _extract_page_last_updated(text: str) -> str:
    m=re.search(r"Last\s+updated\s+([A-Za-z]+\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2})", text, re.I)
    if not m:
        return ""
    try:
        return pd.to_datetime(m.group(1), errors="raise").date().isoformat()
    except Exception:
        return ""

def _agco_resolve_download(page_url: str, html: str) -> Tuple[str, str]:
    soup=BeautifulSoup(html,"html.parser")
    updated=_extract_page_last_updated(soup.get_text(" ",strip=True))
    for a in soup.find_all("a", href=True):
        label=" ".join(a.stripped_strings)
        href=str(a.get("href") or "")
        if re.search(r"download\s*csv", label, re.I) or ("csv" in href.lower() and "export" in href.lower()):
            return urljoin(page_url,href), updated
    raise RuntimeError("AGCO page did not expose a Download CSV link")

def _agco_row_is_gta(row: Dict[str, Any]) -> bool:
    for k in ("MUNICIPALITY_OR_FIRST_NATION","MUNICIPALITY","CITY"):
        v=str(row.get(k,"") or "").strip().upper()
        if v and any(place == v or place in v for place in GTA_CITIES):
            return True
    return gta_match(row)

def collect_html_csv_link(source: Dict[str, Any], http: Http, progress=True, *, smart=False, previous_metadata=None, force_full=False) -> Snapshot:
    page_url=source["url"]
    page=http.get(page_url,timeout=(15,60),retries=3)
    csv_url, last_updated=_agco_resolve_download(page_url,page.text)
    page_meta={"page_url":page_url,"resource_url":csv_url,"page_last_updated":last_updated,
               "page_etag":page.headers.get("ETag") or "","page_last_modified":page.headers.get("Last-Modified") or ""}
    page_meta["resource_fingerprint"]=sha256_text(canon_json(page_meta))
    if smart and not force_full and previous_metadata:
        same=(str(previous_metadata.get("resource_url") or "")==csv_url and
              str(previous_metadata.get("page_last_updated") or "")==last_updated and bool(last_updated))
        if same:
            if progress: print(f"  {source['name']}: page last-updated unchanged ({last_updated}); CSV download skipped",flush=True)
            page_meta["snapshot_mode"]="metadata_unchanged"
            return Snapshot(source,[],b"",csv_url,page_meta,is_complete=False,mode="metadata_unchanged")
    if progress: print(f"  {source['name']}: downloading regulator CSV" + (f" (page updated {last_updated})" if last_updated else ""),flush=True)
    r=http.get(csv_url,timeout=(20,180),retries=3)
    rows=parse_tabular_bytes(r.content,csv_url,"CSV")
    for row in rows:
        if last_updated and not row.get("SOURCE_LAST_UPDATED"):
            row["SOURCE_LAST_UPDATED"]=last_updated
    if source.get("gta_only"):
        before=len(rows); rows=[x for x in rows if _agco_row_is_gta(x)]
        if progress: print(f"  {source['name']}: GTA filter kept {len(rows):,}/{before:,}",flush=True)
    page_meta["snapshot_mode"]="full"
    raw="\n".join(canon_json(x) for x in rows).encode("utf-8")
    return Snapshot(source,rows,raw,csv_url,page_meta,is_complete=True,mode="full")

def _ero_text_value(text: str, label: str) -> str:
    labels=("Instrument type","ERO (Environmental Registry of Ontario) number","Notice type","Notice stage",
            "Decision posted","Proposal posted","Comment period","Last updated")
    stop="|".join(re.escape(x) for x in labels if x.lower()!=label.lower())
    m=re.search(re.escape(label)+r"\s*[:\n]?\s*(.+?)(?=\s+(?:"+stop+r")\b|$)",text,re.I|re.S)
    return re.sub(r"\s+"," ",m.group(1)).strip(" :-") if m else ""

def _parse_ero_search_cards(html: str) -> List[Dict[str, Any]]:
    soup=BeautifulSoup(html,"html.parser")
    out=[]; seen=set()
    for a in soup.find_all("a",href=True):
        href=str(a.get("href") or "")
        m=re.search(r"/notice/([0-9-]+)",href)
        if not m: continue
        eno=m.group(1)
        if eno in seen: continue
        node=a; card=None
        for _ in range(8):
            node=node.parent
            if node is None: break
            txt=" ".join(node.stripped_strings)
            if "Notice stage" in txt and ("Proposal posted" in txt or "Decision posted" in txt):
                card=node; break
        if card is None: continue
        text=" ".join(card.stripped_strings)
        title=" ".join(a.stripped_strings).strip()
        if not title: continue
        row={"ERO_NUMBER":eno,"TITLE":title,
             "INSTRUMENT_TYPE":_ero_text_value(text,"Instrument type"),
             "NOTICE_TYPE":_ero_text_value(text,"Notice type"),
             "NOTICE_STAGE":_ero_text_value(text,"Notice stage"),
             "DECISION_POSTED":_ero_text_value(text,"Decision posted"),
             "PROPOSAL_POSTED":_ero_text_value(text,"Proposal posted"),
             "LAST_UPDATED":_ero_text_value(text,"Last updated"),
             "SUMMARY":text,"NOTICE_URL":urljoin("https://ero.ontario.ca",href)}
        row["ENTITY_NAME"]=title.split(" - ",1)[0].strip()
        for k in ("DECISION_POSTED","PROPOSAL_POSTED","LAST_UPDATED"):
            if row[k]: row[k]=parse_dateish(row[k]) or row[k]
        seen.add(eno); out.append(row)
    return out

def _ero_business_relevant(row: Dict[str, Any], source: Dict[str, Any]) -> bool:
    text=" ".join(str(v) for v in row.values() if v not in (None,"")).upper()
    if source.get("gta_only") and not any(city in text for city in GTA_CITIES):
        return False
    kws=[str(x).upper() for x in source.get("include_keywords",[]) or []]
    return (not kws) or any(k in text for k in kws)

def collect_ero_search(source: Dict[str, Any], http: Http, progress=True, *, smart=False, since_date=None, force_full=False) -> Snapshot:
    from datetime import datetime, timezone, timedelta
    today=datetime.now(timezone.utc).date()
    if smart and since_date and not force_full:
        start=since_date; mode="incremental"
    else:
        start=(today-timedelta(days=int(source.get("baseline_days",90)))).isoformat(); mode="recent_baseline"
    end=today.isoformat()
    rows=[]; seen=set(); page=0; max_pages=int(source.get("max_pages",40))
    while page < max_pages:
        params={"date[min]":start,"date[max]":end,"search":"","page":page}
        r=http.get(source["url"],params=params,timeout=(15,90),retries=3)
        batch=_parse_ero_search_cards(r.text)
        fresh=[]
        for x in batch:
            key=x.get("ERO_NUMBER")
            if key and key not in seen:
                seen.add(key); fresh.append(x)
        if not batch or not fresh: break
        rows.extend(fresh)
        if progress: print(f"  {source['name']}: page {page+1}, {len(rows):,} notices parsed",flush=True)
        if len(batch) < 20: break
        page += 1
    before=len(rows); rows=[r for r in rows if _ero_business_relevant(r,source)]
    if progress: print(f"  {source['name']}: GTA/business filter kept {len(rows):,}/{before:,} recent notices",flush=True)
    meta={"snapshot_mode":mode,"date_min":start,"date_max":end,"pages":page+1,"parsed_before_filter":before}
    raw="\n".join(canon_json(x) for x in rows).encode("utf-8")
    return Snapshot(source,rows,raw,source["url"],meta,is_complete=(not smart or force_full or not since_date),mode=mode)

def collect_source(source: Dict[str, Any], http: Optional[Http]=None, progress=True, *, smart=False, since_date: Optional[str]=None, previous_metadata: Optional[Dict[str, Any]]=None, force_full=False) -> Snapshot:
    http=http or Http()
    if source["collector"] == "web_table":
        from web_collectors import collect_web_table
        return collect_web_table(source,http,progress,smart=smart,previous_metadata=previous_metadata,force_full=force_full)
    if source["collector"] == "peel_health":
        from web_collectors import collect_peel_health
        return collect_peel_health(source,http,progress,smart=smart,since_date=since_date,previous_metadata=previous_metadata,force_full=force_full)
    if source["collector"]=="arcgis":
        return collect_arcgis(source,http,progress,smart=smart,since_date=since_date,force_full=force_full)
    if source["collector"]=="ckan":
        return collect_ckan(source,http,progress,smart=smart,since_date=since_date,previous_metadata=previous_metadata,force_full=force_full)
    if source["collector"]=="html_csv_link":
        return collect_html_csv_link(source,http,progress,smart=smart,previous_metadata=previous_metadata,force_full=force_full)
    if source["collector"]=="ero_search":
        return collect_ero_search(source,http,progress,smart=smart,since_date=since_date,force_full=force_full)
    raise ValueError(f"Unknown collector {source['collector']}")



def source_universe_hash(source: Dict[str, Any]) -> str:
    """Fingerprint the part of source configuration that defines which records exist.

    If this changes, comparing the new snapshot with the old source universe can
    create fake NEW/REMOVED events. The engine therefore refuses to diff until
    that source is explicitly rebaselined.
    """
    keys = (
        "collector","url","query_url","server_where",
        "api_base","package_id","package_slug","resource_id","resource_name_exact",
        "include_keywords","baseline_days","download_link_text",
        "expected_resource_name","resource_url_contains","resource_url_excludes",
        "resource_url_must_end_with","gta_only","key_fields","complete_snapshot",
        "table_url","program_area","column_aliases","identity_strategy","required_columns","table_columns","evidence_fields"
    )
    obj = {k: source.get(k) for k in keys if k in source}
    return sha256_text(canon_json(obj))


def get_source_state(con: sqlite3.Connection, source_id: str):
    return con.execute(
        "SELECT source_id,universe_hash,updated_at FROM source_state WHERE source_id=?",
        (source_id,)
    ).fetchone()


def set_source_state(con: sqlite3.Connection, source: Dict[str, Any]) -> None:
    con.execute(
        """INSERT INTO source_state(source_id,universe_hash,updated_at)
           VALUES(?,?,?)
           ON CONFLICT(source_id) DO UPDATE SET
             universe_hash=excluded.universe_hash,
             updated_at=excluded.updated_at""",
        (source["id"], source_universe_hash(source), utc_now())
    )


def last_successful_run(con: sqlite3.Connection, source_id: str):
    return con.execute(
        "SELECT * FROM runs WHERE source_id=? AND success=1 ORDER BY run_id DESC LIMIT 1",
        (source_id,)
    ).fetchone()


def previous_run_metadata(con: sqlite3.Connection, source_id: str) -> Dict[str, Any]:
    r=last_successful_run(con,source_id)
    if not r or not r["metadata_json"]: return {}
    try: return json.loads(r["metadata_json"])
    except Exception: return {}


def current_active_count(con: sqlite3.Connection, source_id: str) -> int:
    return int(con.execute("SELECT COUNT(*) FROM records_current WHERE source_id=? AND active=1",(source_id,)).fetchone()[0])


def clear_source_current(con: sqlite3.Connection, source_id: str) -> int:
    """Clear only the current comparison universe for a source.

    Historical runs, record_versions, and past changes remain intact. The next
    successful poll for the source becomes a fresh baseline and emits no false
    NEW/REMOVED events.
    """
    n = con.execute(
        "SELECT COUNT(*) FROM records_current WHERE source_id=?", (source_id,)
    ).fetchone()[0]
    con.execute("DELETE FROM records_current WHERE source_id=?", (source_id,))
    con.execute("DELETE FROM source_state WHERE source_id=?", (source_id,))
    con.commit()
    return int(n)


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
CREATE TABLE IF NOT EXISTS sources(
  source_id TEXT PRIMARY KEY, name TEXT, jurisdiction TEXT, region TEXT, family TEXT,
  collector TEXT, mode TEXT, enabled INTEGER, official_page TEXT, licence_note TEXT,
  created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS source_state(
  source_id TEXT PRIMARY KEY,
  universe_hash TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs(
  run_id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT, started_at TEXT, finished_at TEXT,
  success INTEGER, baseline INTEGER, record_count INTEGER, new_count INTEGER, updated_count INTEGER,
  removed_count INTEGER, latest_source_date TEXT, resource_url TEXT, error TEXT, metadata_json TEXT
);
CREATE TABLE IF NOT EXISTS records_current(
  source_id TEXT NOT NULL, record_key TEXT NOT NULL, content_hash TEXT NOT NULL,
  first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, source_date TEXT,
  active INTEGER NOT NULL DEFAULT 1, normalized_json TEXT NOT NULL,
  PRIMARY KEY(source_id, record_key)
);
CREATE TABLE IF NOT EXISTS record_versions(
  version_id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT NOT NULL, record_key TEXT NOT NULL,
  content_hash TEXT NOT NULL, observed_at TEXT NOT NULL, payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_versions_source_key ON record_versions(source_id, record_key);
CREATE TABLE IF NOT EXISTS changes(
  change_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL, source_id TEXT NOT NULL,
  record_key TEXT NOT NULL, change_type TEXT NOT NULL, observed_at TEXT NOT NULL,
  old_hash TEXT, new_hash TEXT, normalized_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_changes_time ON changes(observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_changes_source ON changes(source_id, observed_at DESC);
"""


def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.row_factory = sqlite3.Row
    return con


def register_sources(con: sqlite3.Connection, sources: List[Dict[str, Any]]) -> None:
    now = utc_now()
    for s in sources:
        con.execute("""INSERT INTO sources(source_id,name,jurisdiction,region,family,collector,mode,enabled,official_page,licence_note,created_at,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(source_id) DO UPDATE SET name=excluded.name,jurisdiction=excluded.jurisdiction,
                       region=excluded.region,family=excluded.family,collector=excluded.collector,mode=excluded.mode,
                       enabled=excluded.enabled,official_page=excluded.official_page,licence_note=excluded.licence_note,updated_at=excluded.updated_at""",
                    (s["id"],s["name"],s.get("jurisdiction",""),s.get("region",""),s.get("family",""),s.get("collector",""),
                     s.get("mode",""),1 if s.get("enabled") else 0,s.get("official_page",""),s.get("licence_note",""),now,now))
    con.commit()


def save_raw_delta(raw_dir: Path, source_id: str, run_id: int, rows: List[Dict[str, Any]]) -> Optional[Path]:
    if not rows:
        return None
    d = raw_dir / source_id
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"run_{run_id:08d}.jsonl.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        for row in rows:
            f.write(canon_json(row) + "\n")
    return p


def process_snapshot(con: sqlite3.Connection, snap: Snapshot, raw_dir: Path, emit_baseline=False) -> Dict[str, Any]:
    s = snap.source
    sid = s["id"]
    started = utc_now()
    existing = {r["record_key"]: (r["content_hash"], r["normalized_json"], r["active"]) for r in con.execute(
        "SELECT record_key,content_hash,normalized_json,active FROM records_current WHERE source_id=?", (sid,)
    )}

    state = get_source_state(con, sid)
    current_universe = source_universe_hash(s)
    if existing and state is not None and state["universe_hash"] != current_universe:
        raise RuntimeError(
            f"Source definition changed for {sid}; refusing to create false diffs. "
            f"Run: python main.py rebaseline --source {sid}"
        )
    baseline = len(existing) == 0
    if baseline and not snap.is_complete:
        raise RuntimeError(f"{sid} has no full baseline; run: python main.py reconcile --source {sid}")
    cur: Dict[str, Tuple[str, Dict[str, Any], Dict[str, Any]]] = {}
    latest = ""
    normalized_rows = []
    for raw in snap.rows:
        row = normalize_row(raw)
        normalized_rows.append(row)
        key = stable_key(row, s)
        h = sha256_text(canon_json(row))
        summ = normalized_summary(row, s)
        cur[key] = (h, summ, row)
    # Freshness is intentionally separate from an event's own date. Some permit
    # systems contain future scheduled/issue dates, so use the first configured
    # freshness field that actually has values across the snapshot.
    for ff in s.get("freshness_fields", s.get("date_fields", [])):
        vals=[parse_dateish(r.get(norm_field(ff))) for r in normalized_rows]
        vals=[d for d in vals if d]
        if vals:
            latest=max(vals); break

    run_cur = con.execute("INSERT INTO runs(source_id,started_at,success,baseline,record_count,new_count,updated_count,removed_count,resource_url,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
                          (sid,started,0,1 if baseline else 0,len(cur),0,0,0,snap.resource_url,canon_json(snap.metadata)))
    run_id = int(run_cur.lastrowid)
    now = utc_now()
    new_rows=[]; changed_payloads=[]
    new_count=updated_count=removed_count=0

    for key,(h,summ,row) in cur.items():
        old = existing.get(key)
        if old is None:
            new_count += 1
            if not baseline or emit_baseline:
                con.execute("INSERT INTO changes(run_id,source_id,record_key,change_type,observed_at,old_hash,new_hash,normalized_json) VALUES(?,?,?,?,?,?,?,?)",
                            (run_id,sid,key,"NEW",now,None,h,canon_json(summ)))
            con.execute("INSERT OR REPLACE INTO records_current(source_id,record_key,content_hash,first_seen_at,last_seen_at,source_date,active,normalized_json) VALUES(?,?,?,?,?,?,1,?)",
                        (sid,key,h,now,now,summ.get("source_date",""),canon_json(summ)))
            changed_payloads.append(row)
        elif old[1] != canon_json(summ) or old[2] == 0:
            # Feed changes are based on the normalized commercially relevant summary,
            # not harmless serialization/internal-ID differences between delivery methods.
            updated_count += 1
            con.execute("INSERT INTO changes(run_id,source_id,record_key,change_type,observed_at,old_hash,new_hash,normalized_json) VALUES(?,?,?,?,?,?,?,?)",
                        (run_id,sid,key,"UPDATED",now,old[0],h,canon_json(summ)))
            first = con.execute("SELECT first_seen_at FROM records_current WHERE source_id=? AND record_key=?",(sid,key)).fetchone()[0]
            con.execute("UPDATE records_current SET content_hash=?,last_seen_at=?,source_date=?,active=1,normalized_json=? WHERE source_id=? AND record_key=?",
                        (h,now,summ.get("source_date",""),canon_json(summ),sid,key))
            changed_payloads.append(row)
        else:
            # Keep the newest payload hash silently even when the customer-facing summary
            # did not materially change. This avoids noisy UPDATED events.
            con.execute("UPDATE records_current SET content_hash=?,last_seen_at=?,source_date=?,active=1,normalized_json=? WHERE source_id=? AND record_key=?",
                        (h,now,summ.get("source_date",""),canon_json(summ),sid,key))

    if s.get("complete_snapshot", False) and snap.is_complete and not baseline:
        current_keys = set(cur)
        for key,(old_hash, old_norm, old_active) in existing.items():
            if old_active and key not in current_keys:
                removed_count += 1
                con.execute("UPDATE records_current SET active=0,last_seen_at=? WHERE source_id=? AND record_key=?",(now,sid,key))
                con.execute("INSERT INTO changes(run_id,source_id,record_key,change_type,observed_at,old_hash,new_hash,normalized_json) VALUES(?,?,?,?,?,?,?,?)",
                            (run_id,sid,key,"REMOVED",now,old_hash,None,old_norm))

    # Version payloads are stored only for rows first observed or materially changed.
    for row in changed_payloads:
        key = stable_key(row,s); h=sha256_text(canon_json(row))
        con.execute("INSERT INTO record_versions(source_id,record_key,content_hash,observed_at,payload_json) VALUES(?,?,?,?,?)",
                    (sid,key,h,now,canon_json(row)))
    con.execute("UPDATE runs SET finished_at=?,success=1,new_count=?,updated_count=?,removed_count=?,latest_source_date=? WHERE run_id=?",
                (utc_now(),new_count,updated_count,removed_count,latest,run_id))
    set_source_state(con, s)
    con.commit()
    save_raw_delta(raw_dir, sid, run_id, changed_payloads)
    return {"run_id":run_id,"source_id":sid,"baseline":baseline,"records":len(cur),"current":current_active_count(con,sid),"new":new_count,"updated":updated_count,"removed":removed_count,"latest_source_date":latest,"mode":snap.mode}


def record_failed_run(con: sqlite3.Connection, source: Dict[str, Any], error: Exception) -> None:
    con.rollback()  # A processing error must never commit half-applied record diffs.
    now=utc_now()
    con.execute("INSERT INTO runs(source_id,started_at,finished_at,success,baseline,record_count,new_count,updated_count,removed_count,error) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (source["id"],now,now,0,0,0,0,0,0,str(error)[:2000]))
    con.commit()


def latest_changes(con: sqlite3.Connection, hours: int=48, only_commercial=True) -> List[Dict[str, Any]]:
    rows = con.execute("""SELECT c.*, s.name AS source_name, s.jurisdiction, s.region, s.family
                          FROM changes c JOIN sources s ON s.source_id=c.source_id
                          WHERE datetime(c.observed_at) >= datetime('now', ?)
                          ORDER BY c.observed_at DESC, c.change_id DESC""", (f"-{hours} hours",)).fetchall()
    out=[]
    for r in rows:
        d=dict(r); n=json.loads(d.pop("normalized_json"))
        d.update(n)
        if only_commercial and d.get("commercial_relevance") == "LOW":
            continue
        out.append(d)
    return out


def source_status(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    sources = con.execute("SELECT * FROM sources ORDER BY region,jurisdiction,name").fetchall()
    out=[]
    for s in sources:
        r=con.execute("SELECT * FROM runs WHERE source_id=? ORDER BY run_id DESC LIMIT 1",(s["source_id"],)).fetchone()
        d={"source_id":s["source_id"],"name":s["name"],"jurisdiction":s["jurisdiction"],"mode":s["mode"],"enabled":s["enabled"]}
        if r:
            try: md=json.loads(r["metadata_json"] or "{}")
            except Exception: md={}
            d.update({"last_run":r["finished_at"] or r["started_at"],"success":r["success"],"record_count":r["record_count"],
                      "current_count":current_active_count(con,s["source_id"]),"snapshot_mode":md.get("snapshot_mode","full"),
                      "new":r["new_count"],"updated":r["updated_count"],"removed":r["removed_count"],
                      "latest_source_date":r["latest_source_date"],"error":r["error"] or ""})
        else:
            d.update({"last_run":"","success":"","record_count":"","current_count":"","snapshot_mode":"","new":"","updated":"","removed":"","latest_source_date":"","error":"NEVER_RUN"})
        successful = last_successful_run(con, s["source_id"])
        fetched = con.execute("SELECT finished_at FROM runs WHERE source_id=? AND success=1 AND record_count>0 ORDER BY run_id DESC LIMIT 1", (s["source_id"],)).fetchone()
        latest = con.execute("SELECT MAX(latest_source_date) FROM runs WHERE source_id=? AND success=1 AND latest_source_date<>''", (s["source_id"],)).fetchone()[0] or ""
        if not latest:
            latest = con.execute("SELECT MAX(source_date) FROM records_current WHERE source_id=? AND active=1", (s["source_id"],)).fetchone()[0] or ""
        md = previous_run_metadata(con, s["source_id"])
        updated = md.get("source_updated_at") or md.get("resource_modified") or md.get("package_modified") or ""
        d.update(last_successful_check=successful["finished_at"] if successful else "",
                 last_data_fetch=fetched["finished_at"] if fetched else "",
                 latest_source_date=latest, source_updated_at=updated,
                 poll_health="NEVER_RUN", source_freshness="UNKNOWN", source_age_days="")
        if successful:
            age_hours = (datetime.now(timezone.utc) - datetime.fromisoformat(successful["finished_at"])).total_seconds() / 3600
            d["poll_health"] = "ERROR" if d.get("success") == 0 else ("OVERDUE" if age_hours > 48 else "OK")
        elif r:
            d["poll_health"] = "ERROR"
        if updated:
            date = parse_dateish(updated)
            if date:
                age_days = (datetime.now(timezone.utc).date() - datetime.fromisoformat(date).date()).days
                d["source_age_days"] = age_days
                # Only AGCO has a verified daily-published timestamp contract here.
                # Old inspection/event dates are never treated as stale publication.
                d["source_freshness"] = ("STALE" if age_days > 30 else "CURRENT") if s["source_id"].startswith("agco_") else "REPORTED"
        out.append(d)
    return out


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("",encoding="utf-8"); return
    fields=[]
    for r in rows:
        for k in r:
            if k not in fields: fields.append(k)
    with path.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        w.writeheader(); w.writerows(rows)


def html_escape(s: Any) -> str:
    import html
    return html.escape(str(s if s is not None else ""))


def _evidence_entity(change):
    label = html_escape(change.get("entity_name"))
    url = str(change.get("evidence_url") or "")
    if url.startswith(("https://", "http://")):
        return f'<a href="{html_escape(url)}" target="_blank" rel="noopener noreferrer">{label}</a>'
    return label


def write_dashboard(path: Path, changes: List[Dict[str, Any]], status: List[Dict[str, Any]]) -> None:
    status_rows="".join(
        f"<tr><td>{html_escape(x['name'])}</td><td>{html_escape(x['jurisdiction'])}</td><td>{html_escape(x['last_run'])}</td>"
        f"<td>{'OK' if x.get('success')==1 else ('NEVER' if x.get('success')=='' else 'FAIL')}</td>"
        f"<td>{html_escape(x.get('snapshot_mode',''))}</td><td>{html_escape(x.get('current_count',''))}</td><td>{html_escape(x.get('record_count',''))}</td><td>{html_escape(x.get('new',''))}</td><td>{html_escape(x.get('updated',''))}</td>"
        f"<td>{html_escape(x.get('removed',''))}</td><td>{html_escape(x.get('latest_source_date',''))}</td>"
        f"<td>{html_escape(x.get('last_data_fetch',''))}</td><td>{html_escape(x.get('poll_health',''))}</td>"
        f"<td>{html_escape(x.get('source_updated_at',''))} {html_escape(x.get('source_freshness',''))}</td>"
        f"<td>{html_escape(x.get('error',''))}</td></tr>" for x in status)
    change_rows="".join(
        f"<tr><td>{html_escape(x.get('observed_at'))}</td><td><b>{html_escape(x.get('change_type'))}</b></td>"
        f"<td>{html_escape(x.get('source_name'))}</td><td>{_evidence_entity(x)}</td>"
        f"<td>{html_escape(x.get('address'))}</td><td>{html_escape(x.get('description'))}</td>"
        f"<td>{html_escape(x.get('status'))}</td><td>{html_escape(x.get('commercial_relevance'))}</td></tr>" for x in changes[:1000])
    body=f"""<!doctype html><html><head><meta charset='utf-8'><title>GTA Commercial Radar</title>
<style>body{{font-family:Arial,sans-serif;margin:24px;color:#222}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{border:1px solid #ddd;padding:7px;vertical-align:top}}th{{background:#f3f3f3;position:sticky;top:0}}.note{{background:#f5f5f5;padding:12px;border-radius:8px}}.ok{{font-weight:bold}}</style></head><body>
<h1>GTA Commercial Radar — local feed</h1>
<p class='note'>This dashboard shows observed source changes, not AI predictions. The first successful run of a source is treated as a baseline and does not flood the feed with historical rows. A source can fail without stopping the others.</p>
<h2>Source health</h2><p>Last check, last non-empty fetch, publication timestamp and latest event date are separate. UNKNOWN publication freshness means the source does not provide a verified timestamp. A removed directory record does not prove a business closed.</p><div style="overflow:auto"><table><tr><th>Source</th><th>Jurisdiction</th><th>Last run</th><th>Health</th><th>Mode</th><th>Current</th><th>Fetched</th><th>New</th><th>Updated</th><th>Removed</th><th>Latest event date</th><th>Last non-empty fetch</th><th>Polling</th><th>Source publication</th><th>Error</th></tr>{status_rows}</table></div>
<h2>Recent commercial/unknown changes</h2><p>{len(changes):,} changes in the selected window.</p><table><tr><th>Observed</th><th>Change</th><th>Source</th><th>Entity</th><th>Address</th><th>Description</th><th>Status</th><th>Commercial relevance</th></tr>{change_rows}</table>
</body></html>"""
    path.write_text(body,encoding="utf-8")
