"""Read recent exact planning files from the City's public BramPlanOnline search."""
from datetime import date, timedelta
import re
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup
import requests

from robots_policy import evaluate

SEARCH = "https://planning.brampton.ca/CitizenAccess/Cap/CapHome.aspx?TabName=Planning&module=Planning"
DETAIL_PATH = "/CitizenAccess/Cap/CapDetail.aspx"
AGENT = "GTA-Radar-public-planning/1.0"
FORM_PREFIX = "ctl00$PlaceHolderMain$"
GRID = "ctl00_PlaceHolderMain_dgvPermitList_gdvPermitList"
FILE_ID = re.compile(r"(?:PRE|SPA?|OZS)-20\d{2}-\d{4,6}", re.I)
PAGE_TARGET = re.compile(r"javascript:__doPostBack\('(ctl00\$PlaceHolderMain\$dgvPermitList\$gdvPermitList\$[\w$]+)',''\)")
MAX_HTML_BYTES = 2_000_000
MAX_PAGES = 5
WINDOW_DAYS = 14
LANE = "Brampton_Public_Planning_Search"
LICENCE = "PUBLIC_PORTAL_COMMERCIAL_REUSE_NOT_VERIFIED"


def _page(session, method, data=None):
    with session.request(method, SEARCH, data=data, timeout=(8, 20),
                         stream=True, allow_redirects=False) as response:
        if response.status_code != 200 or response.url != SEARCH:
            raise ValueError(f"BRAMPTON_PLANNING_HTTP_{response.status_code}_OR_REDIRECT")
        if "html" not in response.headers.get("Content-Type", "").lower():
            raise ValueError("BRAMPTON_PLANNING_NOT_HTML")
        body = bytearray()
        for chunk in response.iter_content(65536):
            body.extend(chunk)
            if len(body) > MAX_HTML_BYTES:
                raise ValueError("BRAMPTON_PLANNING_RESPONSE_TOO_LARGE")
    return BeautifulSoup(bytes(body), "html.parser")


def _form(soup, event_target):
    form = soup.find("form", action=True)
    if form is None or urljoin(SEARCH, form["action"]) != SEARCH:
        raise ValueError("BRAMPTON_PLANNING_FORM_CHANGED")
    fields = {}
    for control in form.select("input[name],select[name]"):
        if control.has_attr("disabled"):
            continue
        if control.name == "select":
            option = control.select_one("option[selected]") or control.select_one("option")
            if option is not None:
                fields[control["name"]] = option.get("value", option.get_text())
        elif control.get("type") in ("hidden", "text"):
            fields[control["name"]] = control.get("value", "")
    if not fields.get("__VIEWSTATE"):
        raise ValueError("BRAMPTON_PLANNING_FORM_STATE_MISSING")
    fields.update(__EVENTTARGET=event_target, __EVENTARGUMENT="")
    return fields


def _records(grid, start, end):
    headings = [th.get_text(" ", strip=True) for th in grid.find_all("th")]
    wanted = ("Date", "File Number", "File Type", "Address", "Status")
    if not set(wanted).issubset(headings):
        raise ValueError("BRAMPTON_PLANNING_GRID_CHANGED")
    for row in grid.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != len(headings):
            continue
        filed, file_cell, category, address, status = (cells[headings.index(key)] for key in wanted)
        link = file_cell.find("a", href=True)
        ident = file_cell.get_text(" ", strip=True).upper()
        if link is None or not FILE_ID.fullmatch(ident):
            continue
        url = urljoin(SEARCH, link["href"])
        parts = urlsplit(url)
        if (parts.scheme != "https" or parts.netloc != "planning.brampton.ca"
                or parts.path != DETAIL_PATH or parts.fragment
                or parse_qs(parts.query).get("agencyCode") != ["BRAMPTON"]):
            continue
        match = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", filed.get_text(" ", strip=True))
        if match is None:
            continue
        month, day, year = map(int, match.groups())
        filing_date = date(year, month, day)
        location = address.get_text(" ", strip=True)
        application_type = category.get_text(" ", strip=True)
        if not (start <= filing_date <= end and location and application_type):
            continue
        yield {
            "city": "Brampton", "application_id": ident, "address": location,
            "scope": application_type, "category": application_type,
            "stage": status.get_text(" ", strip=True),
            "source_date": filing_date.isoformat(),
            "source_date_basis": "PUBLIC_PORTAL_RECORD_DATE_NOT_FIRST_PUBLICATION",
            "source_url": url, "source_lane": LANE, "licence_status": LICENCE,
            "first_publication_verified": "False", "buyer_verified": "False",
            "procurement_verified": "False",
        }


def collect(*, today=None):
    end = today or date.today()
    start = end - timedelta(days=WINDOW_DAYS - 1)
    with requests.Session() as session:
        session.headers.update({"User-Agent": AGENT, "Referer": SEARCH})
        allowed, reason = evaluate(session, SEARCH, AGENT)
        if not allowed:
            raise PermissionError(reason)
        initial = _page(session, "GET")
        fields = _form(initial, FORM_PREFIX + "btnNewSearch")
        start_key = FORM_PREFIX + "generalSearchForm$txtGSStartDate"
        end_key = FORM_PREFIX + "generalSearchForm$txtGSEndDate"
        if start_key not in fields or end_key not in fields:
            raise ValueError("BRAMPTON_PLANNING_DATE_FILTER_CHANGED")
        fields.update({start_key: start.strftime("%m/%d/%Y"), end_key: end.strftime("%m/%d/%Y")})
        records = {}
        for page in range(1, MAX_PAGES + 1):
            soup = _page(session, "POST", fields)
            grid = soup.find("table", id=GRID)
            if grid is None:
                if page == 1 and re.search(
                    r"\b(?:0 records? (?:results|found)|no records? (?:results|found))\b",
                    soup.get_text(" ", strip=True), flags=re.I,
                ):
                    return [], {"pages_fetched": 1, "pagination_complete": True}
                raise ValueError("BRAMPTON_PLANNING_RESULT_GRID_MISSING")
            for record in _records(grid, start, end):
                records[record["application_id"]] = record
            next_link = next((link for link in grid.find_all("a", href=True)
                              if link.get_text(strip=True) == str(page + 1)
                              and PAGE_TARGET.fullmatch(link["href"])), None)
            if next_link is None or page == MAX_PAGES:
                return list(records.values()), {
                    "pages_fetched": page, "pagination_complete": next_link is None,
                }
            fields = _form(soup, PAGE_TARGET.fullmatch(next_link["href"]).group(1))
