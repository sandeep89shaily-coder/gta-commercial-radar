import copy, csv, datetime as dt, json, sqlite3, tempfile, unittest
from pathlib import Path

import gta_integrated_run_gates as gates
import reviewed_evidence as re_
from gta_commercial_qualification import qualify_private
from gta_commercial_review_html import build
from gta_release_acceptance import acceptance

TODAY = dt.date.today()
D = lambda days=0: (TODAY - dt.timedelta(days=days)).isoformat()
PID = "toronto_active_building_permits:EX 100"


def ev(url, excerpt, **extra):
    return {"source_class": "COMPANY_OWNED", "official_url": url, "excerpt": excerpt,
            "retrieved_at": D(1), "reviewer_confirmed": True, **extra}


def good_review(pid=PID):
    news = "https://www.examplefoods.ca/news/plant-expansion"
    return {
        "project_id": pid, "address": "100 Example Rd, Toronto", "project_name": "Example Foods plant expansion",
        "reviewed_by": "Jordan Reviewer", "reviewed_at": D(1), "supplier_status": "UPCOMING",
        "service_categories": ["HVAC / refrigeration"],
        "evidence": {
            "project_source": ev(news, "Example Foods will invest in an expansion of its Example Road plant."),
            "project_identity": ev("https://www.toronto.ca/permit/EX100",
                                   "Permit EX 100 at 100 Example Rd: plant addition and refrigeration upgrade.",
                                   source_class="OFFICIAL_GOVERNMENT"),
            "scope_evidence": ev(news, "The expansion adds refrigerated processing space and new mechanical systems."),
            "buyer_org_evidence": ev(news, "Example Foods Co-operative Limited owns and operates the Example Road plant.",
                                     organization="Example Foods Co-operative Limited"),
            "buying_authority_evidence": ev(news, "Example Foods Co-operative Limited is funding and managing the expansion.",
                                            organization="Example Foods Co-operative Limited",
                                            authority_basis="OWNER_OPERATOR_OF_SITE"),
            "contact_route_evidence": ev("https://www.examplefoods.ca/contact",
                                         "Business enquiries: Example Foods head office, 416-555-0100.",
                                         contact_url="https://www.examplefoods.ca/contact",
                                         contact_kind="PUBLIC_BUSINESS_PHONE", contact_purpose="GENERAL_BUSINESS"),
            "procurement_evidence": ev(news, "Design is under way; trade packages have not yet been issued to the market.",
                                       procurement_basis="PLANNING_STAGE_PRE_PROCUREMENT", checked_at=D(2)),
            "source_first_publication": ev(news, "Example Foods announces plant expansion. Published " + D(10),
                                           published_at=D(10)),
        }}


def ai_dossier(pid=PID, **claims):
    """An AI dossier that boldly claims everything is verified."""
    return {"project_id": pid, "address": "100 Example Rd", "research_status": "AI_REVIEW_ONLY",
            "sources": [{"url": "https://www.toronto.ca/x", "text": "x", "page_identity": "EXACT_CURRENT_PERMIT_ID_IN_PAGE"}],
            "model_suggestions": {"operator": "Example Foods", "developer": "Build Co", "buyer_fit": "great",
                                  "project_stage": "pre-award", "next_verification": ""},
            "verified_buying_authority": True, "verified_supplier_unselected": True, "sale_ready": True,
            "qualification_status": "SALE_READY_VERIFIED", **claims}


class Workspace:
    def __init__(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.review = self.root / "TOTAL_INTELLIGENCE_REVIEW"
        self.review.mkdir()

    def write_reviews(self, reviews):
        (self.root / "REVIEWED_EVIDENCE.json").write_text(json.dumps({"reviews": reviews}), encoding="utf-8")

    def write_ai(self, dossier, name="AI_PROJECT_0123456789abcdef.json"):
        (self.review / name).write_text(json.dumps(dossier), encoding="utf-8")


class GatePassesLegitimateReviewTests(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()
        self.addCleanup(self.ws.td.cleanup)

    def test_reviewed_opportunity_passes_the_whole_acceptance_chain(self):
        self.ws.write_ai(ai_dossier())
        self.ws.write_reviews([good_review()])
        report = acceptance(self.ws.review)
        self.assertEqual(report["sale_ready"], 1)
        self.assertEqual(report["verified_buying_authorities"], 1)
        self.assertEqual(report["verified_unawarded_packages"], 1)
        self.assertEqual(report["failures"], [])
        self.assertTrue(report["production_acceptance"])
        data = json.loads((self.ws.review / "COMMERCIAL_REVIEW.json").read_text())
        self.assertEqual(data["verified_private_opportunities"], 1)
        self.assertIn("VERIFIED OPPORTUNITY", (self.ws.review / "COMMERCIAL_REVIEW.html").read_text())
        # downstream run gate reads the computed count, so the verified-buyer check now passes
        gate = gates.evaluate(self.ws.review, self.ws.root)
        self.assertTrue(gate["checks"]["verified_buyer_authorities"])
        self.assertTrue(gate["checks"]["unawarded_private_work_packages_verified"])

    def test_human_reviewed_project_needs_no_ai_dossier(self):
        self.ws.write_reviews([good_review("manual:EX 200")])
        report = acceptance(self.ws.review)
        self.assertEqual(report["sale_ready"], 1)
        self.assertEqual(report["official_exact_id_projects"], 1)

    def test_legacy_entry_point_also_accepts_only_proof(self):
        review = good_review()
        legacy = {"project_id": PID, "reviewed_by": review["reviewed_by"], "reviewed_at": review["reviewed_at"],
                  "supplier_status": "UPCOMING",
                  "evidence_ids": {f: f for f in review["evidence"]}, "source_evidence": review["evidence"]}
        self.assertEqual(qualify_private(legacy)["status"], "SALE_READY_VERIFIED")

    def test_radar_first_seen_is_reported_separately_and_never_gates(self):
        self.ws.write_reviews([good_review()])
        self.assertEqual(acceptance(self.ws.review)["sale_ready"], 1)     # no ledger at all
        db = self.ws.root / "RADAR_DISCOVERY_LEDGER.sqlite"
        con = sqlite3.connect(db)
        try:
            con.execute("CREATE TABLE discovery(project_id TEXT, first_seen_at TEXT, source_url TEXT)")
            con.execute("INSERT INTO discovery VALUES(?,?,?)", (PID, D(3) + "T12:00:00+00:00", "u"))
            con.commit()
        finally:
            con.close()
        build(self.ws.review)
        row = json.loads((self.ws.review / "COMMERCIAL_REVIEW.json").read_text())["projects"][0]
        self.assertEqual(row["radar_first_seen_at"][:10], D(3))
        self.assertEqual(row["radar_vs_publication_days"], 7)            # Radar noticed 7 days after publication

    def test_review_file_is_never_modified(self):
        self.ws.write_reviews([good_review()])
        path = self.ws.root / "REVIEWED_EVIDENCE.json"
        before = path.read_bytes()
        acceptance(self.ws.review)
        self.assertEqual(path.read_bytes(), before)


class UnsupportedClaimsCannotPassTests(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()
        self.addCleanup(self.ws.td.cleanup)

    def run_with(self, review):
        self.ws.write_reviews([review])
        gate = re_.evaluate_folder(self.ws.review)["results"][PID]
        return gate

    def test_ai_dossier_claiming_everything_is_verified_stays_unverified(self):
        self.ws.write_ai(ai_dossier())
        report = acceptance(self.ws.review)
        self.assertEqual(report["sale_ready"], 0)
        self.assertEqual(report["verified_buying_authorities"], 0)
        self.assertEqual(report["verified_unawarded_packages"], 0)
        self.assertFalse(report["production_acceptance"])
        self.assertIn("NO_VERIFIED_PRIVATE_BUYERS", report["failures"])

    def test_legacy_verified_booleans_are_assertions_not_proof(self):
        dossier = {"verified": {f: True for f in re_.MILESTONE_FIELDS + ("radar_first_observed",)},
                   "supplier_status": "INDEPENDENTLY_CHECKED_UNSELECTED"}
        result = qualify_private(dossier)
        self.assertFalse(result["sale_ready"])
        self.assertEqual(set(result["missing"]), set(re_.MILESTONE_FIELDS))

    def test_every_single_defect_blocks_sale_ready(self):
        def mutate(fn):
            r = copy.deepcopy(good_review()); fn(r); return r
        e = lambda r, f: r["evidence"][f]
        cases = {
            "reviewer_confirmed false": lambda r: e(r, "buying_authority_evidence").update(reviewer_confirmed=False),
            "reviewer_confirmed missing": lambda r: e(r, "buyer_org_evidence").pop("reviewer_confirmed"),
            "AI named as reviewer": lambda r: r.update(reviewed_by="DeepSeek AI"),
            "automated reviewer": lambda r: r.update(reviewed_by="automated pipeline"),
            "blank reviewer": lambda r: r.update(reviewed_by=""),
            "AI source class": lambda r: e(r, "buying_authority_evidence").update(source_class="AI_MODEL"),
            "news media only": lambda r: e(r, "buyer_org_evidence").update(source_class="NEWS_MEDIA"),
            "http not https": lambda r: e(r, "project_source").update(official_url="http://www.examplefoods.ca/n"),
            "directory site": lambda r: e(r, "buyer_org_evidence").update(official_url="https://www.yellowpages.ca/x"),
            "ip address host": lambda r: e(r, "project_source").update(official_url="https://10.0.0.5/x"),
            "empty excerpt": lambda r: e(r, "scope_evidence").update(excerpt=""),
            "short excerpt": lambda r: e(r, "scope_evidence").update(excerpt="plant"),
            "address as organization": lambda r: (e(r, "buyer_org_evidence").update(organization="318 Orenda Rd"),
                                                  e(r, "buyer_org_evidence").update(excerpt="Site 318 Orenda Rd was permitted.")),
            "organization not in excerpt": lambda r: e(r, "buyer_org_evidence").update(organization="Other Corp"),
            "no authority basis": lambda r: e(r, "buying_authority_evidence").pop("authority_basis"),
            "person not in excerpt": lambda r: e(r, "buying_authority_evidence").update(person_or_role="Chief Procurement Officer"),
            "media contact only": lambda r: e(r, "contact_route_evidence").update(contact_purpose="MEDIA"),
            "contact not https": lambda r: e(r, "contact_route_evidence").update(contact_url="mailto:a@b.ca"),
            "unknown contact kind": lambda r: e(r, "contact_route_evidence").update(contact_kind="PERSONAL_CELL"),
            "supplier awarded": lambda r: r.update(supplier_status="AWARDED"),
            "supplier already contracted": lambda r: r.update(supplier_status="ALREADY_CONTRACTED"),
            "supplier unknown": lambda r: r.update(supplier_status="UNKNOWN"),
            "supplier status absent": lambda r: r.pop("supplier_status"),
            "no procurement basis (absence of award notice)": lambda r: e(r, "procurement_evidence").pop("procurement_basis"),
            "stale procurement check": lambda r: e(r, "procurement_evidence").update(checked_at=D(200)),
            "future publication": lambda r: e(r, "source_first_publication").update(published_at=(TODAY + dt.timedelta(days=5)).isoformat()),
            "bad publication date": lambda r: e(r, "source_first_publication").update(published_at="soon"),
            "retrieved in future": lambda r: e(r, "project_identity").update(retrieved_at=(TODAY + dt.timedelta(days=2)).isoformat()),
            "reviewed in future": lambda r: r.update(reviewed_at=(TODAY + dt.timedelta(days=2)).isoformat()),
        }
        for name, fn in cases.items():
            with self.subTest(defect=name):
                result = self.run_with(mutate(fn))
                self.assertFalse(result["sale_ready"], name)
                self.assertNotEqual(result["status"], "SALE_READY_VERIFIED")
                self.assertTrue(result["reasons"], "a plain-English reason must be given")

    def test_each_missing_milestone_field_blocks_sale_ready(self):
        for field in re_.MILESTONE_FIELDS:
            with self.subTest(missing=field):
                r = good_review()
                del r["evidence"][field]
                result = self.run_with(r)
                self.assertFalse(result["sale_ready"])
                self.assertIn(field, result["missing"])

    def test_buyer_and_supplier_flags_follow_their_own_evidence(self):
        r = good_review()
        r["evidence"]["buying_authority_evidence"]["reviewer_confirmed"] = False
        result = self.run_with(r)
        self.assertFalse(result["buyer_authority_verified"])
        self.assertTrue(result["supplier_selection_verified"])

    def test_malformed_review_file_verifies_nothing_and_does_not_crash(self):
        (self.ws.root / "REVIEWED_EVIDENCE.json").write_text("{not json", encoding="utf-8")
        self.ws.write_ai(ai_dossier())
        report = acceptance(self.ws.review)
        self.assertEqual(report["sale_ready"], 0)
        data = json.loads((self.ws.review / "COMMERCIAL_REVIEW.json").read_text())
        self.assertTrue(data["review_file_problems"])

    def test_review_without_project_id_is_ignored(self):
        self.ws.write_reviews([{"reviewed_by": "A Person", "evidence": {}}])
        self.assertEqual(acceptance(self.ws.review)["sale_ready"], 0)


class NoHardCodedVerificationTests(unittest.TestCase):
    def test_flags_are_computed_from_evidence_not_constants(self):
        """Same AI dossier, with and without a reviewed record: flags must differ."""
        ws = Workspace()
        self.addCleanup(ws.td.cleanup)
        ws.write_ai(ai_dossier())
        build(ws.review)
        before = json.loads((ws.review / "COMMERCIAL_REVIEW.json").read_text())["projects"][0]
        self.assertFalse(before["sale_ready"])
        ws.write_reviews([good_review()])
        build(ws.review)
        after = json.loads((ws.review / "COMMERCIAL_REVIEW.json").read_text())["projects"][0]
        self.assertTrue(after["sale_ready"])
        self.assertTrue(after["buyer_authority_verified"])
        self.assertTrue(after["supplier_selection_verified"])
        self.assertTrue(after["contact_route_verified"])

    def test_worklist_and_unified_status_counts_follow_the_gate(self):
        import gta_buyer_verification_worklist as wl
        import gta_unified_intelligence as ui
        ws = Workspace()
        self.addCleanup(ws.td.cleanup)
        ws.write_ai(ai_dossier())
        self.assertEqual(wl.build(ws.review)["verified_buyers"], 0)
        ws.write_reviews([good_review()])
        self.assertEqual(wl.build(ws.review)["verified_buyers"], 1)
        acceptance(ws.review)
        out = ui.build(ws.root, ws.review)
        summary = out["summary"] if isinstance(out, dict) and "summary" in out else out
        self.assertEqual(summary["verified_private_leads"], 1)

    def test_acceptance_counts_change_with_evidence(self):
        ws = Workspace()
        self.addCleanup(ws.td.cleanup)
        self.assertFalse(acceptance(ws.review)["production_acceptance"])
        ws.write_reviews([good_review()])
        self.assertTrue(acceptance(ws.review)["production_acceptance"])
        ws.write_reviews([])
        self.assertFalse(acceptance(ws.review)["production_acceptance"])


if __name__ == "__main__":
    unittest.main()
