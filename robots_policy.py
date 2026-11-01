"""One robots.txt decision function for every GTA Radar fetcher (RFC 9309).

Status handling
  2xx            parse the file (first 500 KiB) and obey it
  401/403/429    ROBOTS_ACCESS_DENIED   -> do not fetch (the site is refusing us)
  other 4xx      ALLOWED_NO_ROBOTS_FILE -> no robots file means no restrictions
  5xx            ROBOTS_SERVER_ERROR    -> do not fetch (RFC: assume disallow-all)
  network error  ROBOTS_NETWORK_ERROR   -> do not fetch
Redirects are followed (max 5) but only over https and within the same site.
The generic reason ROBOTS_UNAVAILABLE no longer exists: every refusal says why.
"""
from __future__ import annotations
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

MAX_BYTES = 500 * 1024
MAX_REDIRECTS = 5
REDIRECT_CODES = (301, 302, 303, 307, 308)
DENIED_CODES = (401, 403, 429)


def robots_url_for(url):
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}/robots.txt"


def _site(host):
    labels = (host or "").lower().split(".")
    return ".".join(labels[-2:]) if len(labels) >= 2 else (host or "").lower()


def _same_site(a, b):
    return _site(urlparse(a).hostname) == _site(urlparse(b).hostname)


def _body(response):
    raw = getattr(response, "content", None)
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw[:MAX_BYTES]).decode("utf-8", "replace")
    return (getattr(response, "text", "") or "")[:MAX_BYTES]


def fetch_robots(session, robots_url, timeout=12):
    """Return (status_code, text, note). Never raises for HTTP-level problems."""
    current = robots_url
    for _ in range(MAX_REDIRECTS + 1):
        try:
            r = session.get(current, timeout=timeout, allow_redirects=False)
        except requests.RequestException:
            return None, "", "NETWORK"
        status = int(getattr(r, "status_code", 0) or 0)
        if status in REDIRECT_CODES:
            location = (getattr(r, "headers", None) or {}).get("Location")
            if not location:
                return status, "", "REDIRECT_WITHOUT_LOCATION"
            nxt = urljoin(current, location)
            if urlparse(nxt).scheme != "https" or not _same_site(robots_url, nxt):
                return status, "", "REDIRECT_REJECTED"
            current = nxt
            continue
        return status, _body(r), ""
    return None, "", "REDIRECT_LOOP"


def decide(status, text, note, agent, url):
    """Pure decision: (allowed, reason). Unit-testable with no network."""
    if note == "NETWORK":
        return False, "ROBOTS_NETWORK_ERROR"
    if note in ("REDIRECT_WITHOUT_LOCATION", "REDIRECT_REJECTED", "REDIRECT_LOOP"):
        return False, "ROBOTS_" + note
    if status is None:
        return False, "ROBOTS_NETWORK_ERROR"
    if 200 <= status < 300:
        parser = RobotFileParser()
        parser.parse(text.splitlines())
        return (True, "ALLOWED") if parser.can_fetch(agent, url) else (False, "ROBOTS_DISALLOWED")
    if status in DENIED_CODES:
        return False, "ROBOTS_ACCESS_DENIED"
    if 400 <= status < 500:
        return True, "ALLOWED_NO_ROBOTS_FILE"
    if status >= 500:
        return False, "ROBOTS_SERVER_ERROR"
    return False, "ROBOTS_UNEXPECTED_STATUS"


def evaluate(session, url, agent, *, timeout=12, robots_url=None, policy_reader=None):
    """Decide whether `agent` may fetch `url`.

    policy_reader(robots_url) may return robots text (str), (status, text), or
    None (read failed -> treated as a server error). Used by tests and by the
    legacy `get_policy` hooks.
    """
    target = robots_url or robots_url_for(url)
    if policy_reader is not None:
        got = policy_reader(target)
        if got is None:
            return decide(503, "", "", agent, url)
        if isinstance(got, tuple):
            return decide(int(got[0]), got[1] or "", "", agent, url)
        return decide(200, str(got), "", agent, url)
    status, text, note = fetch_robots(session, target, timeout)
    return decide(status, text, note, agent, url)
