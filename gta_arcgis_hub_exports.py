"""Bounded CSV downloads from the published municipal ArcGIS Hub items."""
from __future__ import annotations

import csv
import io
import time
from datetime import datetime
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

HUB = "https://hub.arcgis.com"
AGENT = "GTA-Radar-official-open-data/1.0"
MAX_BYTES = 12_000_000
KITCHENER_ITEM = "b7e2f8feda7340eaa5f4dd7b9c4d5ac0"
YORK_ITEM = "2ea061702aaa4d5fae39c1226525fd4e"
_last_request = None
_robots = None
MAX_ROBOTS_BYTES = 500 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def csv_date(value):
    """Normalize Hub's US date or year-first date, ignoring its time suffix."""
    day = (value or "").partition(" ")[0].partition("T")[0]
    for pattern in ("%Y/%m/%d", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(day, pattern).date().isoformat()
        except ValueError:
            continue
    return ""


def download_rows(item, required_fields):
    global _last_request, _robots
    if item not in (KITCHENER_ITEM, YORK_ITEM):
        raise ValueError("UNAPPROVED_HUB_EXPORT_ITEM")
    params = "format=csv&spatialRefId=4326" if item == KITCHENER_ITEM else "format=csv&spatialRefId=26917&where=1%3D1"
    url = f"{HUB}/api/v3/datasets/{item}_0/downloads/data?{params}"
    opener = build_opener(NoRedirect())
    headers = {"User-Agent": AGENT}
    if _robots is None or time.monotonic() - _robots[0] > 900:
        with opener.open(Request(HUB + "/robots.txt", headers=headers), timeout=12) as response:
            contents = response.read(MAX_ROBOTS_BYTES + 1)
            if response.status != 200 or len(contents) > MAX_ROBOTS_BYTES:
                raise PermissionError("HUB_ROBOTS_INVALID")
        parser = RobotFileParser()
        parser.parse(contents.decode("utf-8-sig").splitlines())
        _robots = (time.monotonic(), parser)
    parser = _robots[1]
    if not parser.can_fetch(AGENT, url):
        raise PermissionError("HUB_ROBOTS_DISALLOWED")
    delay = parser.crawl_delay(AGENT) or 0
    if _last_request is not None:
        time.sleep(max(0, delay - (time.monotonic() - _last_request)))
    _last_request = time.monotonic()
    with opener.open(Request(url, headers=headers), timeout=30) as response:
        if response.status != 200:
            raise OSError(f"HUB_CSV_HTTP_{response.status}")
        if response.headers.get_content_type() != "text/csv":
            raise ValueError("HUB_EXPORT_NOT_CSV")
        payload = response.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise ValueError("HUB_CSV_TOO_LARGE")
    try:
        with io.StringIO(payload.decode("utf-8-sig"), newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            if not set(required_fields).issubset(reader.fieldnames or []):
                raise ValueError("HUB_CSV_REQUIRED_FIELDS_MISSING")
            return list(reader)
    except csv.Error as exc:
        raise ValueError("HUB_CSV_MALFORMED") from exc
