"""Freshness-first: preserve source truth and prioritize expensive investigation."""
from __future__ import annotations

import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import free_daily_report as free
import gta_freshness as freshness
import gta_manual_project_list as manual
import selective_daily_ai as selective
import v8_deepseek_native as deepseek

DAY = dt.date(2026, 11, 2)


def sample(pid, source_date, **other):
    row = {
        "project_id": pid,
        "source_id": "toronto_active_building_permits",
        "source_keys": pid.rsplit(":", 1)[-1],
        "city": "Toronto",
        "address": pid.rsplit(":", 1)[-1] + " Test Road",
        "description": "New industrial warehouse expansion with loading docks",
        "lane": "PERMIT_REVIEW",
        "source_group": "MUNICIPAL_CHANGE",
        "date_basis": "SOURCE RECORD UPDATE OBSERVED — NOT ISSUANCE/OPENING",
        "event_date": DAY.isoformat(),
        "source_record_date": source_date,
        "current_source_status": "Under Review",
        "review_priority": "85",
    }
    row.update(other)
    return row


def export(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r)) if rows else ["project_id"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class FreshnessPriorityTests(unittest.TestCase):
    def test_first_seen_old_source_is_historical_despite_today_detection(self):
        old = sample("toronto:old", "2025-04-01", observation="FIRST_OBSERVED")
        assessment = freshness.assess(old, DAY)
        self.assertEqual(assessment["freshness_band"], "HISTORICAL_SOURCE_DATE")
        self.assertFalse(assessment["paid_freshness_eligible"])
        self.assertEqual(assessment["freshness_date_basis"],
                         "SOURCE_RECORD_DATE_NOT_PUBLICATION_PROOF")
        self.assertGreater(assessment["source_age_days"], 365)

    def test_municipal_change_timestamp_cannot_rescue_undated_project(self):
        row = sample("toronto:undated", "", observation="FIRST_OBSERVED")
        assessment = freshness.assess(row, DAY)
        self.assertEqual(assessment["freshness_band"], "SOURCE_DATE_UNKNOWN")
        self.assertFalse(assessment["paid_freshness_eligible"])
        self.assertEqual(assessment["freshness_date_basis"],
                         "DETECTION_TIMESTAMP_IS_NOT_PUBLICATION")

    def test_documented_scope_change_reopens_old_project_without_claiming_new_announcement(self):
        row = sample("toronto:old", "2025-04-01",
                     observation="RECORD_CHANGED", changed_fields="description | company_name")
        assessment = freshness.assess(row, DAY)
        self.assertEqual(assessment["freshness_band"], "OLDER_PROJECT_SCOPE_CHANGED_REVIEW")
        self.assertTrue(assessment["paid_freshness_eligible"])
        status = dict(row, changed_fields="current_source_status")
        self.assertFalse(freshness.assess(status, DAY)["paid_freshness_eligible"])

    def test_recent_source_date_first_but_no_first_publication_claim(self):
        newest = freshness.assess(sample("toronto:a", "2026-11-01", observation="FIRST_OBSERVED"), DAY)
        week = freshness.assess(sample("toronto:b", "2026-10-15", observation="FIRST_OBSERVED"), DAY)
        older = freshness.assess(sample("toronto:c", "2026-08-22", observation="FIRST_OBSERVED"), DAY)
        self.assertEqual([v["freshness_sort_bucket"] for v in [newest,week,older]], [0,1,2])
        self.assertEqual(newest["freshness_date_basis"], "SOURCE_RECORD_DATE_NOT_PUBLICATION_PROOF")

    def test_future_date_does_not_qualify(self):
        x = freshness.assess(sample("toronto:future", "2026-11-06",
                                  observation="FIRST_OBSERVED"), DAY)
        self.assertEqual(x["freshness_band"], "SOURCE_DATE_UNKNOWN")
        self.assertFalse(x["paid_freshness_eligible"])

    def test_first_observed_historical_stays_in_manual_csv_but_not_paid(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "candidates.csv"
            baseline = sample("toronto:baseline", "2026-10-28")
            export(p, [baseline])
            free.build(p, root, today=DAY)
            historical = sample("toronto:historical", "2025-04-01", review_priority="99")
            recent = sample("toronto:recent", "2026-11-01", review_priority="35",
                            lane="PLANNING_WATCH",
                            description="New industrial facility site plan application")
            export(p, [historical, baseline, recent])
            free.build(p, root, today=DAY + dt.timedelta(days=1))
            review = free._read(root / free.CSV_NAME)
            self.assertEqual([x["project_id"] for x in review],
                             ["toronto:recent", "toronto:historical"])
            self.assertEqual(review[1]["paid_freshness_eligible"], "False")
            pending, new = selective.enqueue(p, root / free.CSV_NAME, root,
                                              today=DAY + dt.timedelta(days=1))
            self.assertEqual(new, ["toronto:recent"])
            self.assertEqual([x["project_id"] for x in pending], ["toronto:recent"])
            # The complete user-facing manual project list still exposes old
            # projects with explicit dates and manual-verification requirements.
            handoff = manual.build(root, today=DAY + dt.timedelta(days=1))
            handoff_rows = manual.rows_of(handoff["manual_review_csv"])
            self.assertEqual([x["project_id"] for x in handoff_rows],
                             ["toronto:recent", "toronto:historical"])
            self.assertEqual(handoff_rows[1]["freshness_band"], "HISTORICAL_SOURCE_DATE")

    def test_real_description_change_on_old_project_gets_one_paid_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "candidates.csv"
            orig = sample("toronto:original", "2025-04-01",
                          description="Industrial warehouse expansion proposed")
            export(p, [orig])
            free.build(p, root, today=DAY)
            changed = dict(orig, description="Industrial warehouse expansion with new cold storage phase")
            export(p, [changed])
            free.build(p, root, today=DAY + dt.timedelta(days=1))
            review = free._read(root / free.CSV_NAME)
            self.assertIn("description", review[0]["changed_fields"])
            self.assertEqual(review[0]["freshness_band"],
                             "OLDER_PROJECT_SCOPE_CHANGED_REVIEW")
            pending, new = selective.enqueue(p, root / free.CSV_NAME, root,
                                              today=DAY + dt.timedelta(days=1))
            self.assertEqual(new, ["toronto:original"])
            self.assertEqual(pending[0]["_radar_freshness_approved"], "YES")
            self.assertEqual(pending[0]["observation"], "RECORD_CHANGED")

    def test_status_only_change_is_not_paid(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "candidates.csv"
            old = sample("toronto:old", "2025-04-01")
            export(p, [old])
            free.build(p, root, today=DAY)
            export(p, [dict(old, current_source_status="Approved")])
            free.build(p, root, today=DAY + dt.timedelta(days=1))
            review = free._read(root / free.CSV_NAME)
            self.assertEqual(review[0]["changed_fields"], "current_source_status")
            pending, new = selective.enqueue(p, root / free.CSV_NAME, root,
                                              today=DAY + dt.timedelta(days=1))
            self.assertEqual((pending, new), ([], []))

    def test_selective_api_receives_freshness_priority_and_budget_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "candidates.csv"
            export(p, [sample("toronto:baseline", "2026-11-01")])
            free.build(p, root, today=DAY)
            export(p, [sample("toronto:baseline", "2026-11-01"),
                       sample("toronto:recent", "2026-11-02"),
                       sample("toronto:30d", "2026-10-15")])
            free.build(p, root, today=DAY+dt.timedelta(days=1))
            def fake_run(*args, **kwargs):
                self.assertEqual(kwargs["budget_cap_usd"], 0.25)
                self.assertEqual(kwargs["eligible_project_ids"],
                                 {"toronto:recent","toronto:30d"})
                self.assertEqual(kwargs["freshness_priority_buckets"],
                                 {"toronto:recent":0,"toronto:30d":1})
                return {"queue_stop_reason":"QUEUE_DRAINED","ai_calls_attempted":0,
                        "native_searches":0,"processed":0,"reserved_usd":0}
            with patch.object(deepseek,"run",side_effect=fake_run) as mocked:
                outcome=selective.run(p,root/free.CSV_NAME,root,root,
                                      today=DAY+dt.timedelta(days=1))
            mocked.assert_called_once()
            self.assertEqual(outcome["new_eligible"],2)


if __name__ == "__main__":
    unittest.main()
