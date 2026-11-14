"""Static website regression checks: accessible links and honest lead handoff."""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parent.parent / "website"


class SiteParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.anchors = []
        self.assets = []
        self.forms = []
        self.mailto = []
        self.inputs = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if data.get("id"):
            self.ids.add(data["id"])
        if tag == "a":
            href = data.get("href", "")
            if href.startswith("#"):
                self.anchors.append(href[1:])
            if href.startswith("mailto:"):
                self.mailto.append(href)
        if tag == "link" and data.get("rel") == "stylesheet":
            self.assets.append(data.get("href"))
        if tag == "script" and data.get("src"):
            self.assets.append(data["src"])
        if tag == "form":
            self.forms.append(data)
        if tag == "input":
            self.inputs.append(data)


class WebsiteTests(unittest.TestCase):
    def test_site_files_exist_and_anchor_navigation_is_valid(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        parser = SiteParser()
        parser.feed(html)
        self.assertIn("main", parser.ids)
        self.assertIn("sample", parser.ids)
        self.assertIn("sample-form", parser.ids)
        self.assertTrue(all(anchor in parser.ids for anchor in parser.anchors))
        self.assertTrue(all((ROOT / asset).is_file() for asset in parser.assets))
        self.assertTrue(parser.mailto)
        self.assertTrue(any(f.get("id") == "sample-form" for f in parser.forms))
        self.assertTrue(any(x.get("id") == "lead-email" and
                            x.get("type") == "email" and
                            "required" in x for x in parser.inputs))

    def test_no_fake_live_leads_or_success_claim(self):
        text = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("Not a depiction of verified live opportunities", text)
        self.assertIn("Source coverage is not uniform", text)
        self.assertIn("does not automatically store your address", text)
        js = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn("mailto:gtaradar18@gmail.com", js)
        self.assertIn("nothing has been submitted automatically", js)
        self.assertNotIn("fetch(", js)
        self.assertNotIn("localStorage", js)

    def test_responsive_and_accessibility_protections(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        css = (ROOT / "styles.css").read_text(encoding="utf-8")
        self.assertIn('name="viewport"', html)
        self.assertIn('class="skip-link"', html)
        self.assertIn('aria-live="polite"', html)
        self.assertIn("@media(max-width:760px)", css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn(":focus-visible", css)

    def test_mail_client_contact_uses_only_public_business_inbox(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn("gtaradar18@gmail.com", html)
        self.assertIn("gtaradar18@gmail.com", js)
        self.assertNotIn("<script src=\"https://", html)
        self.assertNotIn("@submit", html)


if __name__ == "__main__":
    unittest.main()
