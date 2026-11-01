import copy, datetime as dt, json, tempfile, unittest
from pathlib import Path

import auto_verify as av
import reviewed_evidence as gate
from gta_release_acceptance import acceptance

TODAY = dt.date.today()
D = lambda n=0: (TODAY - dt.timedelta(days=n)).isoformat()
ORG = "Example Foods Co-operative Limited"
NEWS = "https://www.newswire.ca/news-releases/example-foods-invests-200-million-1.html"
GOV = "https://www.toronto.ca/permit/EX100"
CONTACT = "https://www.examplefoods.ca/contact"
PID = "toronto_active_building_permits:EX 100"

PAGES = {
    NEWS: (f"meta-date: {D(10)}T08:57:00-04:00\nNews provided by\n\n[**{ORG}**](https://x)\n"
           f"TORONTO - {ORG} today announced an investment of more than $200 million to significantly "
           "expand its Clayson Road dairy manufacturing facility in Toronto. The expansion will introduce "
           "advanced processing technology and modern manufacturing capabilities. The expansion, to be "
           f"complete in 2028, will create up to 75 new positions.\nSOURCE {ORG}\nMedia Contact: A. Person"),
    GOV: "Toronto Building. Permit EX 100 for 100 Example Rd: plant addition and refrigeration upgrade.",
    CONTACT: f"{ORG} head office. Business enquiries 416-555-0100. Our plant is at Clayson Road.",
}


def fetcher_for(pages):
    def fetch(url):
        if url in pages:
            import hashlib
            return {"ok": True, "reason": "", "url": url, "text": pages[url],
                    "sha256": hashlib.sha256(pages[url].encode()).hexdigest(), "fetched_at": TODAY.isoformat()}
        return {"ok": False, "reason": "HTTP_404"}
    return fetch


def spec():
    return {"project_id": PID, "address": "100 Example Rd, Toronto", "project_name": "Example plant expansion",
            "organization": ORG, "supplier_status": "UPCOMING", "service_categories": ["HVAC / refrigeration"],
            "claims": {
        "project_source": {"official_url": NEWS, "excerpt": "announced an investment of more than $200 million to significantly expand its Clayson Road dairy manufacturing facility"},
        "project_identity": {"official_url": GOV, "excerpt": "Permit EX 100 for 100 Example Rd: plant addition", "identity_tokens": ["EX 100", "100 Example Rd"]},
        "scope_evidence": {"official_url": NEWS, "excerpt": "introduce advanced processing technology and modern manufacturing capabilities"},
        "buyer_org_evidence": {"official_url": NEWS, "excerpt": f"{ORG} today announced an investment"},
        "buying_authority_evidence": {"official_url": NEWS, "excerpt": f"{ORG} today announced an investment of more than $200 million to significantly expand its Clayson Road dairy manufacturing facility",
                                      "authority_basis": "OWNER_OPERATOR_OF_SITE"},
        "contact_route_evidence": {"official_url": CONTACT, "excerpt": "Business enquiries 416-555-0100", "contact_url": CONTACT,
                                   "contact_kind": "PUBLIC_BUSINESS_PHONE", "contact_purpose": "GENERAL_BUSINESS", "contact_value": "416-555-0100"},
        "procurement_evidence": {"official_url": NEWS, "excerpt": "The expansion, to be complete in 2028", "procurement_basis": "PLANNING_STAGE_PRE_PROCUREMENT", "checked_at": D(1)},
        "source_first_publication": {"official_url": NEWS, "excerpt": f"{ORG} today announced an investment", "published_at": D(10)},
    }}


class MatchingTests(unittest.TestCase):
    def test_excerpt_matching_tolerates_markup_but_not_changed_facts(self):
        page = "Gay **Lea** announced an investment of more than $200 million."
        self.assertTrue(av.excerpt_present(page, "gay lea announced an investment of more than $200 million"))
        self.assertFalse(av.excerpt_present(page, "Gay Lea announced an investment of more than $300 million"))
        self.assertFalse(av.excerpt_present(page, "invest"))                       # too short to prove anything

    def test_source_classification(self):
        c = av.classify_source
        self.assertEqual(c(NEWS, PAGES[NEWS], ORG), "PRESS_RELEASE_BY_PARTY")
        self.assertIsNone(c(NEWS, PAGES[NEWS].replace("SOURCE " + ORG, "SOURCE Someone Else").replace("News provided by", "Reprinted from"), ORG))
        self.assertEqual(c(GOV, PAGES[GOV], ORG), "OFFICIAL_GOVERNMENT")
        self.assertEqual(c(CONTACT, PAGES[CONTACT], ORG), "COMPANY_OWNED")
        self.assertIsNone(c("https://www.examplefoods-deals.ca/contact", PAGES[CONTACT], ORG))   # look-alike domain
        self.assertIsNone(c("https://www.agcanada.com/daily/story", f"{ORG} expands", ORG))     # media, not the party
        self.assertIsNone(c("https://www.yellowpages.ca/x", PAGES[CONTACT], ORG))

    def test_publication_date_is_read_from_page_markup(self):
        self.assertEqual(av.parse_published_date(PAGES[NEWS]), D(10))
        self.assertIsNone(av.parse_published_date("no date here"))


class ClaimVerificationTests(unittest.TestCase):
    def verify(self, field, claim, pages=None):
        return av.verify_claim(field, claim, ORG, fetcher_for(pages or PAGES), TODAY)

    def test_real_quote_on_party_page_is_auto_verified_with_fingerprint(self):
        entry, problems, auto = self.verify("project_source", spec()["claims"]["project_source"])
        self.assertTrue(auto)
        self.assertEqual(problems, [])
        self.assertEqual(entry["verification_method"], gate.AUTOMATED_METHOD)
        self.assertEqual(len(entry["content_sha256"]), 64)
        self.assertEqual(entry["source_class"], "PRESS_RELEASE_BY_PARTY")

    def test_fabricated_or_ai_invented_quote_cannot_pass(self):
        claim = {**spec()["claims"]["project_source"], "excerpt": "Example Foods will spend $900 million on a new plant in Brampton"}
        entry, problems, auto = self.verify("project_source", claim)
        self.assertFalse(auto)
        self.assertIn("the quoted excerpt is not on the page", problems)
        self.assertNotIn("verification_method", entry)

    def test_unfetchable_page_cannot_pass(self):
        entry, problems, auto = self.verify("project_source", {**spec()["claims"]["project_source"], "official_url": "https://www.newswire.ca/gone"})
        self.assertFalse(auto)
        self.assertIsNone(entry)

    def test_publication_date_must_match_the_page(self):
        claim = {**spec()["claims"]["source_first_publication"], "published_at": D(40)}
        _, problems, auto = self.verify("source_first_publication", claim)
        self.assertFalse(auto)
        self.assertTrue(any("does not match" in p for p in problems))

    def test_project_identity_only_from_official_government_with_tokens(self):
        _, _, ok = self.verify("project_identity", spec()["claims"]["project_identity"])
        self.assertTrue(ok)
        news_claim = {**spec()["claims"]["project_identity"], "official_url": NEWS, "excerpt": "announced an investment of more than $200 million", "identity_tokens": ["EX 100"]}
        _, problems, ok2 = self.verify("project_identity", news_claim)
        self.assertFalse(ok2)

    def test_contact_value_must_be_on_the_page(self):
        claim = {**spec()["claims"]["contact_route_evidence"], "contact_value": "416-999-9999"}
        _, problems, ok = self.verify("contact_route_evidence", claim)
        self.assertFalse(ok)

    def test_judgment_fields_are_never_automated(self):
        for field in gate.HUMAN_ONLY_FIELDS:
            entry, problems, auto = self.verify(field, spec()["claims"][field])
            self.assertFalse(auto, field)
            self.assertIs(entry["reviewer_confirmed"], False)
            self.assertNotIn("verification_method", entry)


class FetchPageTests(unittest.TestCase):
    class Resp:
        def __init__(self, status=200, text="", url=None, headers=None):
            self.status_code, self.text, self.content, self.url, self.headers = status, text, text.encode(), url, headers or {}

    class Sess:
        def __init__(self, table): self.table = table
        def get(self, url, **kw):
            r = self.table[url]
            if r.url is None: r.url = url
            return r

    def test_robots_disallow_blocks_the_fetch(self):
        s = self.Sess({"https://www.toronto.ca/robots.txt": self.Resp(200, "User-agent: *\nDisallow: /\n")})
        out = av.fetch_page("https://www.toronto.ca/permit/EX100", s, TODAY)
        self.assertFalse(out["ok"]); self.assertEqual(out["reason"], "ROBOTS_DISALLOWED")

    def test_cross_site_redirect_is_rejected(self):
        s = self.Sess({"https://www.toronto.ca/robots.txt": self.Resp(404),
                       "https://www.toronto.ca/p": self.Resp(200, "x", url="https://evil.example.net/p")})
        self.assertEqual(av.fetch_page("https://www.toronto.ca/p", s, TODAY)["reason"], "REDIRECTED_TO_OTHER_SITE")

    def test_http_is_refused_and_good_fetch_is_fingerprinted(self):
        self.assertEqual(av.fetch_page("http://www.toronto.ca/p", None, TODAY)["reason"], "NOT_HTTPS")
        s = self.Sess({"https://www.toronto.ca/robots.txt": self.Resp(404), "https://www.toronto.ca/p": self.Resp(200, "hello")})
        out = av.fetch_page("https://www.toronto.ca/p", s, TODAY)
        self.assertTrue(out["ok"]); self.assertEqual(len(out["sha256"]), 64)


class GateIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); self.addCleanup(self.td.cleanup)
        self.root = Path(self.td.name); self.review = self.root / "TOTAL_INTELLIGENCE_REVIEW"; self.review.mkdir()

    def automated(self):
        review, report = av.build_review(spec(), fetcher_for(PAGES), TODAY)
        av.write_auto_file(self.root, [review])
        return review, report

    def test_machine_completes_everything_checkable_and_flags_only_the_judgment_items(self):
        _, report = self.automated()
        auto = [f for f, i in report.items() if i["status"] == "AUTO_VERIFIED"]
        self.assertEqual(set(auto), set(gate.AUTOMATABLE_FIELDS))
        self.assertEqual({f for f, i in report.items() if i["status"] == "NEEDS_HUMAN"}, set(gate.HUMAN_ONLY_FIELDS))
        result = gate.evaluate_folder(self.review)["results"][PID]
        self.assertEqual(result["status"], "NEEDS_HUMAN_CONFIRMATION")
        self.assertFalse(result["sale_ready"])
        self.assertTrue(result["automated_proofs_complete"])
        self.assertEqual(set(result["needs_human"]), set(gate.HUMAN_ONLY_FIELDS))

    def test_human_confirmation_of_the_two_judgment_items_completes_the_lead(self):
        review, _ = self.automated()
        human = {"project_id": PID, "reviewed_by": "Jordan Reviewer", "reviewed_at": D(0), "supplier_status": "UPCOMING",
                 "evidence": {f: {**review["evidence"][f], "reviewer_confirmed": True} for f in gate.HUMAN_ONLY_FIELDS}}
        (self.root / "REVIEWED_EVIDENCE.json").write_text(json.dumps({"reviews": [human]}), encoding="utf-8")
        before = (self.root / "REVIEWED_EVIDENCE.json").read_bytes()
        report = acceptance(self.review)
        self.assertEqual(report["sale_ready"], 1)
        self.assertTrue(report["production_acceptance"])
        av.write_auto_file(self.root, [review])                         # machine re-run must not touch the human file
        self.assertEqual((self.root / "REVIEWED_EVIDENCE.json").read_bytes(), before)

    def test_machine_evidence_alone_can_never_make_a_lead_sale_ready(self):
        self.automated()
        self.assertEqual(acceptance(self.review)["sale_ready"], 0)

    def test_forged_automated_entry_on_a_judgment_field_is_rejected(self):
        review, _ = self.automated()
        forged = copy.deepcopy(review)
        forged["evidence"]["buying_authority_evidence"].update(
            verification_method=gate.AUTOMATED_METHOD, match_confirmed=True, verifier_version="auto_verify/1",
            content_sha256="a" * 64, fetched_at=D(0))
        forged["reviewed_by"], forged["reviewed_at"] = "Jordan Reviewer", D(0)
        forged["evidence"]["procurement_evidence"]["reviewer_confirmed"] = True
        result = gate.evaluate_review(forged)
        self.assertFalse(result["sale_ready"])
        self.assertIn("needs a human", " ".join(result["reasons"]["buying_authority_evidence"]))

    def test_automated_entries_without_fingerprint_or_with_stale_fetch_fail(self):
        review, _ = self.automated()
        for label, mutate in {"no hash": lambda e: e.pop("content_sha256"),
                              "bad hash": lambda e: e.update(content_sha256="zz"),
                              "no match flag": lambda e: e.pop("match_confirmed"),
                              "stale": lambda e: e.update(fetched_at=D(200))}.items():
            with self.subTest(label):
                r = copy.deepcopy(review)
                mutate(r["evidence"]["scope_evidence"])
                self.assertIn("scope_evidence", gate.evaluate_review(r)["missing"])

    def test_media_contact_is_rejected_even_when_machine_verified(self):
        s = spec(); s["claims"]["contact_route_evidence"]["contact_purpose"] = "MEDIA"
        review, _ = av.build_review(s, fetcher_for(PAGES), TODAY)
        result = gate.evaluate_review(review)
        self.assertFalse(result["contact_route_verified"])

    def test_auto_file_merges_by_project_and_never_loses_other_projects(self):
        av.write_auto_file(self.root, [{"project_id": "other", "evidence": {}}])
        self.automated()
        ids = {r["project_id"] for r in json.loads((self.root / av.AUTO_FILE).read_text())["reviews"]}
        self.assertEqual(ids, {"other", PID})


if __name__ == "__main__":
    unittest.main()
