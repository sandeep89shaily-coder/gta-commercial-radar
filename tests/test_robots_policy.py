import unittest
import requests
import robots_policy as rp

AGENT = "GTA-Radar-Test"
URL = "https://secure.toronto.ca/council/report.do?meeting=2026.PH31"
ROBOTS = "https://secure.toronto.ca/robots.txt"


class R:
    def __init__(self, status=200, text="", headers=None):
        self.status_code = status
        self.text = text
        self.content = text.encode()
        self.headers = headers or {}


class S:
    """Fake session: maps URL -> response (or exception)."""
    def __init__(self, table):
        self.table = table
        self.calls = []

    def get(self, url, **kw):
        assert kw.get("allow_redirects") is False
        self.calls.append(url)
        out = self.table[url]
        if isinstance(out, Exception):
            raise out
        return out


class RobotsPolicyTests(unittest.TestCase):
    def ev(self, table):
        return rp.evaluate(S(table), URL, AGENT)

    def test_404_means_no_restrictions(self):
        self.assertEqual(self.ev({ROBOTS: R(404)}), (True, "ALLOWED_NO_ROBOTS_FILE"))

    def test_410_means_no_restrictions(self):
        self.assertEqual(self.ev({ROBOTS: R(410)}), (True, "ALLOWED_NO_ROBOTS_FILE"))

    def test_5xx_is_disallow_all_with_specific_reason(self):
        self.assertEqual(self.ev({ROBOTS: R(503)}), (False, "ROBOTS_SERVER_ERROR"))

    def test_403_and_429_are_access_denied(self):
        self.assertEqual(self.ev({ROBOTS: R(403)}), (False, "ROBOTS_ACCESS_DENIED"))
        self.assertEqual(self.ev({ROBOTS: R(429)}), (False, "ROBOTS_ACCESS_DENIED"))

    def test_network_error_is_distinct(self):
        self.assertEqual(self.ev({ROBOTS: requests.ConnectionError("x")}),
                         (False, "ROBOTS_NETWORK_ERROR"))

    def test_200_obeys_disallow(self):
        body = "User-agent: *\nDisallow: /council/\n"
        self.assertEqual(self.ev({ROBOTS: R(200, body)}), (False, "ROBOTS_DISALLOWED"))

    def test_200_allows_when_permitted(self):
        self.assertEqual(self.ev({ROBOTS: R(200, "User-agent: *\nAllow: /\n")}), (True, "ALLOWED"))

    def test_same_site_https_redirect_is_followed(self):
        table = {ROBOTS: R(301, headers={"Location": "https://www.toronto.ca/robots.txt"}),
                 "https://www.toronto.ca/robots.txt": R(200, "User-agent: *\nAllow: /\n")}
        self.assertEqual(self.ev(table), (True, "ALLOWED"))

    def test_cross_site_redirect_is_rejected(self):
        table = {ROBOTS: R(302, headers={"Location": "https://evil.example.net/robots.txt"})}
        self.assertEqual(self.ev(table), (False, "ROBOTS_REDIRECT_REJECTED"))

    def test_http_downgrade_redirect_is_rejected(self):
        table = {ROBOTS: R(302, headers={"Location": "http://www.toronto.ca/robots.txt"})}
        self.assertEqual(self.ev(table), (False, "ROBOTS_REDIRECT_REJECTED"))

    def test_redirect_loop_is_bounded(self):
        table = {ROBOTS: R(302, headers={"Location": ROBOTS})}
        self.assertEqual(self.ev(table), (False, "ROBOTS_REDIRECT_LOOP"))

    def test_oversized_file_is_truncated_not_refused(self):
        body = "User-agent: *\nAllow: /\n" + ("# pad\n" * 200000)
        self.assertEqual(self.ev({ROBOTS: R(200, body)}), (True, "ALLOWED"))

    def test_legacy_policy_reader_contract(self):
        self.assertEqual(rp.evaluate(None, URL, AGENT, policy_reader=lambda u: None),
                         (False, "ROBOTS_SERVER_ERROR"))
        self.assertEqual(rp.evaluate(None, URL, AGENT, policy_reader=lambda u: "User-agent: *\nAllow: /"),
                         (True, "ALLOWED"))
        self.assertEqual(rp.evaluate(None, URL, AGENT, policy_reader=lambda u: (404, "")),
                         (True, "ALLOWED_NO_ROBOTS_FILE"))

    def test_generic_unavailable_reason_is_gone(self):
        import pathlib
        for name in ("gta_verified_source_pipeline.py", "toronto_pdf_download.py",
                     "toronto_meeting_pdf_pipeline.py", "robots_policy.py"):
            src = (pathlib.Path(__file__).resolve().parent.parent / name).read_text(encoding="utf-8")
            self.assertNotIn('"ROBOTS_UNAVAILABLE"', src, name)


if __name__ == "__main__":
    unittest.main()
