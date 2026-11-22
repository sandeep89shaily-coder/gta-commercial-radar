"""ComIntel public-brand regression tests; internal Radar pipeline stays intact."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/"website"

class ComIntelBrandTests(unittest.TestCase):
    def test_public_pages_use_comintel(self):
        for name in ("index.html","opportunities.html","publisher.html"):
            with self.subTest(page=name):
                html=(SITE/name).read_text(encoding="utf-8")
                self.assertIn("COMINTEL",html)
                self.assertIn("ComIntel",html)
                self.assertNotIn("GTA RADAR",html)
                self.assertNotIn("<strong>GTA Radar</strong>",html)

    def test_title_and_domain_present(self):
        home=(SITE/"index.html").read_text(encoding="utf-8")
        opportunities=(SITE/"opportunities.html").read_text(encoding="utf-8")
        self.assertIn("ComIntel | Commercial &amp; Industrial",home.replace("& Industrial","&amp; Industrial"))
        self.assertIn("ComIntel.ca",opportunities)
        self.assertIn("./opportunities.html",home)
        self.assertIn("No guaranteed open tenders",home)
        self.assertIn("rights_checked !== true",
                      (SITE/"opportunities.js").read_text(encoding="utf-8"))

    def test_no_unverified_domain_mailbox_or_unsafe_pages_dns(self):
        for page in ("index.html","opportunities.html","publisher.html","app.js"):
            s=(SITE/page).read_text(encoding="utf-8")
            self.assertNotIn("info@comintel.ca",s)
        js=(SITE/"app.js").read_text(encoding="utf-8")
        self.assertIn("gtaradar18@gmail.com",js)
        self.assertIn("nothing has been submitted automatically",js)
        self.assertFalse((SITE/"CNAME").exists())

    def test_domain_instructions_preserve_old_collection_ids(self):
        doc=(SITE/"COMINTEL_DOMAIN_SETUP.md").read_text(encoding="utf-8")
        self.assertIn("GitHub Actions",doc)
        self.assertIn("CIPO",doc)
        self.assertIn("GTA Radar",doc)
        self.assertIn("gtaradar18@gmail.com",doc)

if __name__=="__main__":
    unittest.main()
