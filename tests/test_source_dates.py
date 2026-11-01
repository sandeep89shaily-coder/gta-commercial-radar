import datetime as dt
import json
import unittest

import source_dates as sd
import v8_deepseek_native as native

# Real raw values from Mississauga FIRE 26-2716 (October 31 results).
APPLICATION_MS = 1784678400000   # 2026-07-22T00:00:00Z
ISSUE_MS = 1786665600000         # 2026-08-14T00:00:00Z
RAW_PAGE = json.dumps({"PERMIT": "FIRE 26-2716", "APPLICATION_DATE": str(APPLICATION_MS),
                       "ISSUE_DATE": ISSUE_MS, "OBJECTID": 1234})


class SourceDateTests(unittest.TestCase):
    def test_reported_dates_match_raw_timestamps(self):
        for ms in (APPLICATION_MS, ISSUE_MS, 1788998400000, 1774396800000,
                   1767225599999, 1767225600000, 1709164800000):  # incl. year boundary and a leap day
            expected = dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date().isoformat()
            self.assertEqual(sd.epoch_ms_to_date(ms), expected)

    def test_known_regression_values(self):
        self.assertEqual(sd.epoch_ms_to_date(APPLICATION_MS), "2026-07-22")
        self.assertEqual(sd.epoch_ms_to_date(ISSUE_MS), "2026-08-14")

    def test_extracted_fields_carry_the_raw_value(self):
        found = {f["field"]: f for f in sd.extract_dated_fields(RAW_PAGE)}
        self.assertEqual(found["APPLICATION_DATE"]["raw"], str(APPLICATION_MS))
        self.assertEqual(found["APPLICATION_DATE"]["date"], "2026-07-22")
        self.assertEqual(found["ISSUE_DATE"]["date"], "2026-08-14")
        self.assertNotIn("OBJECTID", found)          # 4-digit id is not a timestamp

    def test_implausible_epoch_is_rejected(self):
        self.assertIsNone(sd.epoch_ms_to_date(12345))
        self.assertIsNone(sd.epoch_ms_to_date("abc"))
        self.assertIsNone(sd.epoch_ms_to_date(99999999999999999))

    def test_model_dates_not_backed_by_source_are_removed(self):
        allowed = sd.allowed_date_set({"description": RAW_PAGE})
        text, removed = sd.sanitize_model_text(
            "Application 2026-04-21, issued 2026-08-14. Hearing April 21, 2026.", allowed)
        self.assertEqual(removed, 2)
        self.assertIn("2026-08-14", text)
        self.assertNotIn("2026-04-21", text)
        self.assertIn(sd.UNVERIFIED, text)

    def test_analyze_replaces_wrong_model_dates_and_attaches_source_dates(self):
        row = {"project_id": "mississauga:FIRE 26-2716", "address": "1 Test Rd", "description": RAW_PAGE,
               "source_keys": "FIRE 26-2716", "record_source_url": "https://example.ca/r"}
        evidence = [{"url": "https://example.ca/r", "text": RAW_PAGE + " FIRE 26-2716",
                     "page_identity": "EXACT_CURRENT_PERMIT_ID_IN_PAGE"}]
        wrong = {"operator": "", "developer": "", "contact": "",
                 "project_stage": "Application 2026-04-21; issued 2026-05-13 (from epoch)",
                 "buyer_fit": "f", "next_verification": "n", "caveats": "c"}

        def transport(path, payload):
            self.assertIn("verified_dates", payload["messages"][1]["content"])
            return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(wrong)}}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50}}
        out, _ = native.analyze(row, evidence, "k", transport)
        self.assertNotIn("2026-04-21", out["project_stage"])
        self.assertNotIn("2026-05-13", out["project_stage"])
        self.assertEqual(out["model_dates_removed"], 2)
        dates = {d["field"]: d["date"] for d in out["source_dates"]}
        self.assertEqual(dates["APPLICATION_DATE"], "2026-07-22")
        self.assertEqual(dates["ISSUE_DATE"], "2026-08-14")


class ModelFailureClassTests(unittest.TestCase):
    ROW = {"project_id": "P", "address": "1 Test Rd", "description": "x" * 50, "source_keys": "k",
           "record_source_url": "https://example.ca/r"}

    def call(self, content, finish="stop"):
        def transport(path, payload):
            return {"choices": [{"finish_reason": finish, "message": {"content": content}}],
                    "usage": {"prompt_tokens": 500, "completion_tokens": 100}}
        return native.analyze(self.ROW, [], "k", transport)

    def fails_with(self, content, failure_class, finish="stop"):
        with self.assertRaises(native.ModelResponseError) as ctx:
            self.call(content, finish)
        self.assertEqual(ctx.exception.failure_class, failure_class)
        self.assertIsInstance(ctx.exception, ValueError)         # callers catching ValueError still work
        self.assertIsNotNone(ctx.exception.cost)                 # real usage cost is carried
        return ctx.exception

    def test_empty_content(self):
        self.fails_with("", "EMPTY_CONTENT")
        self.fails_with("   \n", "EMPTY_CONTENT")

    def test_truncated(self):
        exc = self.fails_with('{"operator":"x"', "TRUNCATED", finish="length")
        self.assertIn("operator", exc.raw)                       # raw reply preserved

    def test_invalid_json_keeps_raw_reply(self):
        exc = self.fails_with("I could not find anything.", "INVALID_JSON")
        self.assertIn("could not find", exc.raw)

    def test_non_object(self):
        self.fails_with("[1,2,3]", "NOT_AN_OBJECT")

    def test_fenced_and_preamble_json_are_accepted(self):
        good = json.dumps({"operator": "", "project_stage": "s", "buyer_fit": "f",
                           "next_verification": "n", "caveats": "c"})
        self.assertIn("project_stage", self.call("```json\n" + good + "\n```")[0])
        self.assertIn("project_stage", self.call("Here you go: " + good)[0])

    def test_no_choices(self):
        def transport(path, payload):
            return {"choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 0}}
        with self.assertRaises(native.ModelResponseError) as ctx:
            native.analyze(self.ROW, [], "k", transport)
        self.assertEqual(ctx.exception.failure_class, "NO_CHOICES")


if __name__ == "__main__":
    unittest.main()
