"""Checks for the image-reference-inspired premium site redesign.

Site design must preserve source controls, responsive behavior, and the
manual, review-gated five-day opportunity feed.
"""
import json
from pathlib import Path
import unittest
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "website"

class Capture(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.assets = []
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if d.get("id"):
            self.ids.add(d["id"])
        if tag in ("link", "script"):
            src = d.get("src") or d.get("href") or ""
            if src.startswith("./"):
                self.assets.append(src)

class PremiumSiteTests(unittest.TestCase):
    def test_home_uses_actual_premium_theme_and_source_dossier(self):
        text = (SITE / "index.html").read_text(encoding="utf-8")
        parsed = Capture()
        parsed.feed(text)
        self.assertIn("./premium.css", parsed.assets)
        self.assertIn("radar-console-map", text)
        self.assertIn("SIMULATED VIEW", text)
        self.assertIn("NOT A REAL PROJECT", text)
        self.assertIn("Not a depiction of verified live opportunities", text)
        self.assertIn("./opportunities.html", text)
        self.assertTrue(all((SITE / x).is_file() for x in parsed.assets))

    def test_opportunity_board_keeps_filters_and_no_fabricated_feed(self):
        text = (SITE / "opportunities.html").read_text(encoding="utf-8")
        parsed = Capture()
        parsed.feed(text)
        self.assertIn("./premium-opportunities.css", parsed.assets)
        self.assertIn("./premium.css", parsed.assets)
        for key in ("op-results", "op-empty", "op-search-input", "op-city",
                    "op-sort", "op-clear", "metric-total", "window-label"):
            self.assertIn(key, parsed.ids)
        self.assertIn("op-filter-sidebar", text)
        self.assertIn("op-demo-dossier", text)
        self.assertIn("NOT A LIVE LEAD", text)
        self.assertIn("ILLUSTRATIVE", text)
        self.assertTrue(all((SITE / x).is_file() for x in parsed.assets))
        feed = json.loads((SITE / "data" / "opportunities.json").read_text())
        self.assertEqual(feed["records"], [])

    def test_premium_css_responsive_and_no_external_assets(self):
        for name in ("premium.css", "premium-opportunities.css"):
            css = (SITE / name).read_text(encoding="utf-8")
            self.assertIn("@media(max-width:760px)", css)
            self.assertNotIn("@import", css)
            self.assertNotIn("url(http", css)
        js = (SITE / "opportunities.js").read_text(encoding="utf-8")
        self.assertIn('"op-card " + rec.lane', js)
        self.assertIn("source_checked !== true", js)
        self.assertIn("rights_checked !== true", js)
        self.assertIn("textContent", js)

    def test_manual_pages_deploy_includes_new_stylesheets(self):
        workflow = (ROOT / ".github" / "workflows" /
                    "deploy-marketing-site.yml").read_text()
        self.assertIn("website/premium.css", workflow)
        self.assertIn("website/premium-opportunities.css", workflow)
        self.assertIn("python3 website/validate_public_feed.py", workflow)
        self.assertNotIn("cp website/publisher.html", workflow)

if __name__ == "__main__":
    unittest.main()
