"""Public web tables and CSV widgets; no browser or JavaScript execution needed."""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup
from radar import Snapshot, canon_json, normalize_row, norm_field, parse_tabular_bytes, sha256_text


def discover_csv_url(page_url, html):
    """Resolve a real export or a literal URL in a CSV-rendering widget."""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if re.search(r"download\s*csv", a.get_text(" ", strip=True), re.I) or urlsplit(href).path.lower().endswith(".csv"):
            if not href.startswith(("javascript:", "blob:", "data:")):
                return urljoin(page_url, href)
    for tag in soup.select("[data-csv-url]"):
        return urljoin(page_url, tag["data-csv-url"])
    # Read literal data configuration only. Never eval arbitrary site code.
    for script in soup.find_all("script"):
        m = re.search(r"\b(?:const|let|var)\s+csvUrl\s*=\s*([\"'])(.*?)\1\s*;", script.get_text(), re.S)
        if m:
            return urljoin(page_url, m.group(2))
    return ""


def parse_html_table(html, required_columns, page_url):
    """Parse a matching table, image status labels, and row evidence links."""
    soup = BeautifulSoup(html, "html.parser")
    required = {norm_field(x) for x in required_columns}
    for table in soup.find_all("table"):
        header = next((tr for tr in table.find_all("tr") if tr.find_all("th")), None)
        if header is None:
            continue
        columns = [norm_field(x.get_text(" ", strip=True)) for x in header.find_all("th", recursive=False)]
        if not required.issubset(columns):
            continue
        rows = []
        for tr in table.find_all("tr"):
            if tr.find("th"):
                continue
            cells = tr.find_all("td", recursive=False)
            if not cells:
                continue
            if len(cells) != len(columns):
                raise RuntimeError("Web table row/header width changed; refusing an incomplete snapshot")
            row = {}
            for column, cell in zip(columns, cells):
                text = cell.get_text(" ", strip=True)
                if not text:
                    text = " ".join(i.get("alt", "") or i.get("title", "") for i in cell.find_all("img")).strip()
                row[column] = text
            link = tr.find("a", href=re.compile(r"/Facility/Details/", re.I))
            if link:
                row["DETAIL_URL"] = urljoin(page_url, link["href"])
                row["FACILITY_ID"] = urlsplit(row["DETAIL_URL"]).path.rstrip("/").split("/")[-1]
            rows.append(normalize_row(row))
        return rows, soup
    raise RuntimeError("Expected public table/schema missing; no data was changed")


def _validators(response):
    return {"etag": response.headers.get("ETag", ""),
            "last_modified": response.headers.get("Last-Modified", ""),
            "content_length": response.headers.get("Content-Length", "")}


def _canonicalize(rows, source):
    out = []
    for raw in rows:
        row = normalize_row(raw)
        for canonical, aliases in source.get("column_aliases", {}).items():
            row[canonical] = next((row.get(norm_field(k)) for k in [*aliases, canonical] if str(row.get(norm_field(k), "")).strip()), "")
        if source.get("identity_strategy") == "agco_application":
            # FileNumber survives licence issuance. Older entries have only a licence.
            file_number = row.get("FILE_NUMBER", "")
            licence = row.get("LICENCE_NUMBER", "")
            if file_number:
                row["APPLICATION_ID"] = "FILE:" + str(file_number)
            elif licence:
                row["APPLICATION_ID"] = "LIC:" + str(licence) + "|" + str(row.get("ADDRESS_ID") or row.get("ADDRESS", ""))
            else:
                raise RuntimeError("AGCO row has neither application file number nor licence number")
        out.append(row)
    required = source.get("required_columns", [])
    if not out or any(any(not str(r.get(c, "")).strip() for c in required) for r in out):
        raise RuntimeError("Empty export or required identity/address fields missing; refusing snapshot")
    keys = [tuple(str(r.get(k, "")) for k in source.get("key_fields", [])) for r in out]
    if len(keys) != len(set(keys)):
        raise RuntimeError("Duplicate source identities; refusing to silently collapse records")
    if source.get("gta_only"):
        # Restrict by municipality, never by an incidental substring in a name/address.
        from radar import GTA_CITIES
        out = [r for r in out if str(r.get("MUNICIPALITY_OR_FIRST_NATION", "")).strip().upper() in GTA_CITIES]
        if not out:
            raise RuntimeError("GTA filter produced an empty snapshot; verify source schema")
    return out


def collect_web_table(source, http, progress=True, *, smart=False, previous_metadata=None, force_full=False):
    page = http.get(source["url"], timeout=(15, 60))
    csv_url = discover_csv_url(source["url"], page.text)
    meta = {"page_url": source["url"], "resource_url": csv_url or source["url"]}
    if csv_url:
        # The widget's page date can be blank or day-only. Use exact resource validators.
        try:
            head = http.head(csv_url, timeout=(15, 60), retries=1)
            meta.update(_validators(head))
        except Exception:
            pass  # A server without HEAD still supports the small CSV snapshot.
        old = previous_metadata or {}
        validators = ("etag", "last_modified", "content_length")
        if (smart and not force_full and old.get("resource_url") == csv_url
                and (meta.get("etag") or meta.get("last_modified"))
                and all(meta.get(k, "") == old.get(k, "") for k in validators)):
            meta.update(snapshot_mode="metadata_unchanged", source_updated_at=meta.get("last_modified", ""))
            if progress:
                print(f"  {source['name']}: resource metadata unchanged; CSV download skipped", flush=True)
            return Snapshot(source, [], b"", csv_url, meta, is_complete=False, mode="metadata_unchanged")
        if progress:
            print(f"  {source['name']}: CSV widget/export resolved; downloading changed resource", flush=True)
        resource = http.get(csv_url, timeout=(20, 180))
        meta.update(_validators(resource))
        rows = _canonicalize(parse_tabular_bytes(resource.content, csv_url, "CSV"), source)
        meta.update(snapshot_mode="full", delivery="csv", source_updated_at=meta.get("last_modified", ""))
    else:
        # Reusable fallback for a normal server-rendered, paginated public table.
        rows, visited = [], set()
        url, html = source["url"], page.text
        for _ in range(int(source.get("max_pages", 500))):
            batch, soup = parse_html_table(html, source.get("table_columns", []), url)
            digest = sha256_text(canon_json(batch))
            if digest in visited:
                raise RuntimeError("Repeated web table page; pagination is incomplete")
            visited.add(digest)
            rows.extend(batch)
            nxt = soup.select_one('a[rel="next"], .pager__item--next a, a[aria-label="Next"]')
            if nxt is None:
                break
            url = urljoin(url, nxt["href"])
            if urlsplit(url).netloc != urlsplit(source["url"]).netloc:
                raise RuntimeError("Pagination left source host")
            html = http.get(url, timeout=(15, 60)).text
        else:
            raise RuntimeError("Web table pagination limit reached; no snapshot committed")
        rows = _canonicalize(rows, source)
        meta.update(snapshot_mode="full", delivery="html_table", pages=len(visited))
    if progress:
        print(f"  {source['name']}: {len(rows):,} filtered records", flush=True)
    return Snapshot(source, rows, b"", meta["resource_url"], meta, is_complete=True, mode="full")


def _peel_page(html, url):
    columns = ["FACILITY_NAME", "SITE_ADDRESS", "FACILITY_TYPE", "LAST_INSPECTION_DATE"]
    rows, soup = parse_html_table(html, columns, url)
    if not rows or any(not r.get("FACILITY_ID") or not r.get("FACILITY_NAME") or not r.get("SITE_ADDRESS") for r in rows):
        raise RuntimeError("Peel table empty or facility identity missing; refusing incomplete snapshot")
    pages = [1]
    current = soup.select_one(".selectedpage")
    if current and current.get_text(strip=True).isdigit():
        pages.append(int(current.get_text(strip=True)))
    for a in soup.select("a[href]"):
        target = urljoin(url, a["href"])
        if urlsplit(target).path != urlsplit(url).path:
            continue
        number = parse_qs(urlsplit(target).query).get("pageNumber", [""])[0]
        if number.isdigit():
            pages.append(int(number))
    return rows, max(pages), soup


def collect_peel_health(source, http, progress=True, *, smart=False, since_date=None, previous_metadata=None, force_full=False):
    # This is a non-binding public accuracy notice, not an account or a licence.
    start = http.get(source["url"], timeout=(15, 60))
    soup = BeautifulSoup(start.text, "html.parser")
    accept = soup.find("input", attrs={"name": "AcceptDisclaimerButton"})
    if accept:
        form = accept.find_parent("form")
        action = urljoin(source["url"], form.get("action", ""))
        if urlsplit(action).netloc != urlsplit(source["url"]).netloc:
            raise RuntimeError("Peel disclaimer form changed host")
        http.post(action, data={"AcceptDisclaimerButton": "Accept"}, timeout=(15, 60), retries=1)
    table_url = source["table_url"]
    incremental = bool(smart and since_date and not force_full)
    params = {"FacilityCountLimit": 0, "ProgramAreaName": source["program_area"],
              "SortBy": "MostRecentlyInspected" if incremental else "FacilityName", "pageNumber": 1}
    rows, seen, pages, last_date = [], set(), 0, None
    max_pages = int(source.get("max_pages", 1000))
    total_pages = 1
    pending = {}
    def fetch_page(number):
        client = http
        # Independent read sessions retain only the public disclaimer cookie.
        if hasattr(http, "s"):
            from radar import Http
            client = Http()
            client.s.headers.update(http.s.headers)
            client.s.cookies.update(http.s.cookies)
        return number, client.get(table_url, params={**params, "pageNumber": number}, timeout=(15, 90))
    while pages < total_pages:
        if pages >= max_pages:
            raise RuntimeError("Peel pagination limit reached; no snapshot committed")
        params["pageNumber"] = pages + 1
        if not incremental and pages > 0 and not pending and int(source.get("baseline_workers", 3)) > 1:
            numbers = list(range(pages + 1, min(total_pages, pages + int(source.get("baseline_workers", 3)), max_pages) + 1))
            with ThreadPoolExecutor(max_workers=min(3, len(numbers))) as executor:
                pending.update(executor.map(fetch_page, numbers))
        response = pending.pop(pages + 1) if pending else http.get(table_url, params=params, timeout=(15, 90))
        expected_pages = total_pages if pages else None
        batch, total_pages, soup = _peel_page(response.text, table_url)
        current = soup.select_one(".selectedpage")
        if current and current.get_text(strip=True) != str(pages + 1):
            raise RuntimeError("Peel server returned a different page than requested")
        if expected_pages is not None and total_pages != expected_pages:
            raise RuntimeError("Peel directory page count changed during scan; retry before committing")
        pages += 1
        # Verify the sort actually took effect before using an early-stop window.
        selected = soup.select_one('select[name="SortBy"] option[selected]')
        if incremental and (selected is None or selected.get("value") != "MostRecentlyInspected"):
            raise RuntimeError("Peel recent-date sort was not honoured; refusing partial query")
        cutoff = False
        for row in batch:
            key = row["FACILITY_ID"]
            if key in seen:
                raise RuntimeError("Peel pagination repeated a facility; directory changed during scan; retry")
            seen.add(key)
            date = row.get("LAST_INSPECTION_DATE", "")
            if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                raise RuntimeError("Peel inspection date format changed")
            if incremental:
                if date and last_date and date > last_date:
                    raise RuntimeError("Peel recent-date order changed; refusing partial query")
                if not date or date < since_date:
                    cutoff = True
                    continue
                if cutoff:
                    raise RuntimeError("Peel dates are not consistently sorted")
            if date:
                last_date = date
            row["PROGRAM_AREA"] = source["program_area"]
            rows.append(row)
        if progress:
            print(f"  {source['name']}: {'recent window' if incremental else 'directory baseline/reconcile'} page {pages}/{total_pages}; kept={len(rows):,}", flush=True)
        if incremental and cutoff:
            break
        if pages < total_pages:
            time.sleep(float(source.get("request_pause_seconds", 0.1)))
    meta = {"snapshot_mode": "incremental" if incremental else "full", "pages": pages,
            "published_pages": total_pages, "since_date": since_date if incremental else "",
            "resource_url": table_url, "delivery": "public_html_table",
            "coverage_note": "Daily: most-recent inspection dates. Weekly full directory catches undated/new facilities and old edits."}
    return Snapshot(source, rows, b"", table_url, meta, is_complete=not incremental, mode=meta["snapshot_mode"])
