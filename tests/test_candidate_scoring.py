import unittest
import candidate_scoring as cs

URL = "https://www.toronto.ca/record"


def r(desc, status="Under Review", source="toronto_active_building_permits", **kw):
    return {"description": desc, "current_source_status": status, "source_id": source,
            "record_source_url": URL, "address": "1 Test Rd", **kw}


# Descriptions modelled on real rows from the October 31 queue.
SIGNIFICANT = {
    "cold_storage": r("Proposal to construct an addition to the existing refrigerated warehouse, 85,000 sq ft, with new refrigeration and sprinkler", "Application Acceptable"),
    "industrial_shell": r("New Shell Building F2: Industrial", "Applied", "brampton_building_permits"),
    "industrial_addition": r("New Site Plan application for industrial addition", "Under Review", "mississauga_site_plan_applications"),
    "hotel": r("To construct a new 15-storey hotel with 279 parking spaces", "Under Review", "toronto_development_applications"),
    "plant_expansion": r("Plant expansion: new 60,000 sq ft food processing facility, HVAC and refrigeration, estimated value $200 million", "Applied", company_name="Gay Lea"),
}
MINOR = {
    "detached_variance": r("Minor variance for a three-storey detached dwelling with rear deck", "Under Review", "toronto_development_applications"),
    "basement_walkout": r("Other(BA) Proposal for a basement walk out and canopy at the rear", "Permit Issued"),
    "thin_alteration": r("Alteration (Renovation) F2: Industrial", "Applied", "brampton_building_permits"),
    "drain": r("Building Permit Related(PS) Plumbing - drain and backflow prevention", "Inspection"),
    "restaurant_hvac_retrofit": r("Other(MS) Proposal for hvac retrofit for restaurant. Restaurant Restaurant", "Permit Issued"),
    "interior_fitout": r("Interior alterations and tenant fit-out of unit 4 for a new dental office", "Inspection"),
    "laneway": r("Construct a laneway suite at the rear of an existing house", "Applied"),
}


class CandidateScoringTests(unittest.TestCase):
    def test_every_significant_project_outranks_every_minor_one(self):
        worst_big = min(cs.score(v)["score"] for v in SIGNIFICANT.values())
        best_small = max(cs.score(v)["score"] for v in MINOR.values())
        self.assertGreater(worst_big, best_small)

    def test_significant_projects_clear_the_paid_ai_threshold_minor_do_not(self):
        for name, v in SIGNIFICANT.items():
            self.assertGreaterEqual(cs.score(v)["score"], cs.MIN_SELECTION_SCORE, name)
        for name, v in MINOR.items():
            self.assertLess(cs.score(v)["score"], cs.MIN_SELECTION_SCORE, name)

    def test_ranking_puts_significant_first_regardless_of_input_order(self):
        rows = list(MINOR.values()) + list(SIGNIFICANT.values())
        ranked = cs.rank(rows)
        top = [x for x, _ in ranked[:len(SIGNIFICANT)]]
        for v in SIGNIFICANT.values():
            self.assertIn(v, top)

    def test_select_for_ai_drops_minor_and_keeps_order(self):
        rows = list(MINOR.values()) + list(SIGNIFICANT.values())
        chosen = cs.select_for_ai(rows)
        self.assertEqual(len(chosen), len(SIGNIFICANT))
        scores = [s["score"] for _, s in chosen]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_unsourced_project_is_penalised_heavily(self):
        good = r("Construct a new 60,000 sq ft warehouse", "Applied")
        unsourced = {**good, "record_source_url": "http://example.com/x", "source_id": "blog_post"}
        self.assertLess(cs.score(unsourced)["score"], cs.score(good)["score"] - 30)

    def test_official_dataset_record_without_direct_url_is_penalised_lightly(self):
        good = r("Construct a new 60,000 sq ft warehouse", "Applied")
        no_url = {**good, "record_source_url": ""}
        gap = cs.score(good)["score"] - cs.score(no_url)["score"]
        self.assertGreater(gap, 0)
        self.assertLess(gap, 30)

    def test_ai_written_fields_never_change_the_score(self):
        base = r("Building Permit Related(MS) HVAC - interior alterations", "Permit Issued")
        hyped = {**base, "project_stage": "Under construction: huge new 500,000 sq ft plant, $900 million",
                 "buyer_fit": "excellent opportunity for every trade"}
        self.assertEqual(cs.score(base)["score"], cs.score(hyped)["score"])

    def test_under_construction_is_not_new_construction(self):
        row = r("Interior work in a building that is under construction", "Permit Issued")
        self.assertNotIn("new construction", " ".join(cs.score(row)["reasons"]))

    def test_public_bodies_are_excluded_from_private_ranking(self):
        school = r(SIGNIFICANT["cold_storage"]["description"], company_name="Toronto District School Board")
        result = cs.score(school)
        self.assertTrue(result["excluded"])
        self.assertEqual(cs.select_for_ai([school]), [])

    def test_street_address_is_not_a_company_name(self):
        row = r("Construct a new 60,000 sq ft warehouse", "Applied", company_name="318 Orenda Rd")
        reasons = " ".join(cs.score(row)["reasons"])
        self.assertNotIn("named company", reasons)

    def test_company_name_helps_but_cannot_rescue_a_minor_project(self):
        row = r(MINOR["basement_walkout"]["description"], "Permit Issued", company_name="Big Corp Inc")
        self.assertLess(cs.score(row)["score"], cs.MIN_SELECTION_SCORE)

    def test_late_stage_ranks_below_same_project_pre_issuance(self):
        early = r("Construct a new 60,000 sq ft warehouse", "Applied")
        late = r("Construct a new 60,000 sq ft warehouse", "Inspection")
        self.assertGreater(cs.score(early)["score"], cs.score(late)["score"])

    def test_minor_scope_items_lower_an_otherwise_identical_project(self):
        base = r("Construct a new 60,000 sq ft warehouse", "Applied")
        minor = r("Construct a new 60,000 sq ft warehouse with new fence and signage", "Applied")
        self.assertLess(cs.score(minor)["score"], cs.score(base)["score"])

    def test_every_score_is_explained(self):
        for v in list(SIGNIFICANT.values()) + list(MINOR.values()):
            self.assertTrue(cs.score(v)["reasons"])

    def test_size_and_value_parsing(self):
        self.assertEqual(cs.floor_area_sqft("332,764 SQ.FT. and 2,500 m2"), max(332764.0, 2500 * 10.764))
        self.assertEqual(cs.stated_value_cad("estimated $12.5 million"), 12_500_000.0)


if __name__ == "__main__":
    unittest.main()
