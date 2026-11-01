import csv, json, tempfile, unittest
from pathlib import Path

import gta_select_first_investigations as sel

URL = "https://www.toronto.ca/record"


def rec(pid, desc="", operator="", strength="IDENTIFIED_PROJECT_OPERATOR", **kw):
    return {"project_id": pid, "address": pid + " Test Rd", "city": "Toronto", "description": desc,
            "operator": operator, "developer": "", "opportunity_strength": strength,
            "source_id": "toronto_active_building_permits", "record_source_url": URL,
            "current_source_status": "Under Review", **kw}


ROWS = [
    rec("big", "Construct a new 120,000 sq ft cold storage warehouse with HVAC", "Big Foods Ltd"),
    rec("mid", "Construct a new 25,000 sq ft industrial addition", "Mid Corp"),
    rec("small", "Interior alterations and tenant fit-out of unit 4", "Small Co"),
    rec("house", "Minor variance for a detached dwelling", "Home Inc"),
    rec("school", "Construct a new 80,000 sq ft addition", "Toronto District School Board"),
    rec("nosrc1", "", "Mystery Industries"),
    rec("nosrc2", "", "Other Holdings"),
    rec("ai_only", "", "Hyped Corp", project_stage="Huge new 900,000 sq ft plant, $1 billion",
        buyer_fit="excellent"),
    rec("other_strength", "Construct a new warehouse", "X", strength="PROJECT_ONLY"),
]


class FirstInvestigationTests(unittest.TestCase):
    def test_strongest_scorable_records_come_first(self):
        top = sel.prioritize(ROWS, 10)["top"]
        order = [t["project_id"] for t in top]
        self.assertEqual(order[:2], ["big", "mid"])
        self.assertLess(order.index("mid"), order.index("small"))

    def test_operator_names_are_always_marked_unverified(self):
        for item in sel.prioritize(ROWS, 10)["top"]:
            self.assertEqual(item["operator_developer_status"], sel.UNVERIFIED)
        for item in sel.prioritize(ROWS, 10)["needs_source_refresh"]:
            self.assertEqual(item["operator_developer_status"], sel.UNVERIFIED)

    def test_public_bodies_are_excluded_everywhere(self):
        result = sel.prioritize(ROWS, 10)
        ids = [t["project_id"] for t in result["top"] + result["needs_source_refresh"]]
        self.assertNotIn("school", ids)

    def test_records_without_source_text_are_listed_not_ranked_or_buried(self):
        result = sel.prioritize(ROWS, 10)
        self.assertNotIn("nosrc1", [t["project_id"] for t in result["top"]])
        refresh = {t["project_id"]: t for t in result["needs_source_refresh"]}
        self.assertIn("nosrc1", refresh)
        self.assertEqual(refresh["nosrc1"]["selection_basis"], "SOURCE_RECORD_MISSING")

    def test_ai_written_hype_cannot_buy_a_rank(self):
        result = sel.prioritize(ROWS, 10)
        self.assertNotIn("ai_only", [t["project_id"] for t in result["top"]])
        self.assertIn("ai_only", [t["project_id"] for t in result["needs_source_refresh"]])

    def test_owner_pin_goes_first_and_is_labelled_a_human_decision(self):
        top = sel.prioritize(ROWS, 10, pinned=["nosrc1"])["top"]
        self.assertEqual(top[0]["project_id"], "nosrc1")
        self.assertEqual(top[0]["selection_basis"], "PINNED_BY_OWNER")
        self.assertEqual(top[0]["operator_developer_status"], sel.UNVERIFIED)
        self.assertNotIn("nosrc1", [t["project_id"] for t in sel.prioritize(ROWS, 10, pinned=["nosrc1"])["needs_source_refresh"]])

    def test_top_limit_is_respected(self):
        self.assertEqual(len(sel.prioritize(ROWS, 1)["top"]), 1)

    def test_load_records_filters_by_strength(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / sel.DEFAULT_FILE
            with path.open("w", newline="", encoding="utf-8") as h:
                w = csv.DictWriter(h, fieldnames=sorted({k for r in ROWS for k in r}))
                w.writeheader()
                w.writerows(ROWS)
            self.assertEqual(len(sel.load_records(path)), len(ROWS) - 1)
            self.assertEqual(len(sel.load_records(path, "")), len(ROWS))

    def test_worklist_never_overwrites_history(self):
        with tempfile.TemporaryDirectory() as t:
            result = sel.prioritize(ROWS, 10)
            first = sel.write_worklist(result, t, stamp="20261101")
            first.write_text("PRECIOUS", encoding="utf-8")
            second = sel.write_worklist(result, t, stamp="20261101")
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_text(), "PRECIOUS")
            data = json.loads(second.with_suffix(".json").read_text())
            self.assertIn("UNVERIFIED", data["note"])

    def test_cli_runs_without_network_or_ai(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / sel.DEFAULT_FILE
            with path.open("w", newline="", encoding="utf-8") as h:
                w = csv.DictWriter(h, fieldnames=sorted({k for r in ROWS for k in r}))
                w.writeheader()
                w.writerows(ROWS)
            self.assertEqual(sel.main(["--results", t, "--top", "3"]), 0)
            self.assertTrue(list(Path(t).glob("FIRST_INVESTIGATIONS_*.csv")))


if __name__ == "__main__":
    unittest.main()
