"""Regression: transient Peel Health directory shifts retry once without data loss."""
import unittest
from main import collect_with_safe_peel_retry

PEEL = {"collector": "peel_health", "id": "peel_health_food"}
DUP = ("Peel pagination repeated a facility; "
       "directory changed during scan; retry")


class PeelPollRetryTests(unittest.TestCase):
    def test_single_retry_recovers_with_fresh_client_and_original_arguments(self):
        calls = []
        old_client = object()
        new_client = object()
        def collect(source, client, **kwargs):
            calls.append((client, kwargs))
            if len(calls) == 1:
                raise RuntimeError(DUP)
            return "complete_snapshot"
        sleeping = []
        snapshot = collect_with_safe_peel_retry(
            PEEL, old_client, collect=collect,
            client_factory=lambda: new_client, sleep=sleeping.append,
            progress=True, smart=True, since_date="2026-11-13")
        self.assertEqual(snapshot, "complete_snapshot")
        self.assertEqual(len(calls), 2)
        self.assertIs(calls[0][0], old_client)
        self.assertIs(calls[1][0], new_client)
        self.assertEqual(calls[0][1], calls[1][1])
        self.assertEqual(sleeping, [1.0])

    def test_persistent_duplicate_still_fails_closed(self):
        count = []
        def collect(*args, **kwargs):
            count.append(1)
            raise RuntimeError(DUP)
        with self.assertRaisesRegex(RuntimeError,
                                    "pagination repeated a facility"):
            collect_with_safe_peel_retry(
                PEEL, object(), collect=collect, sleep=lambda *_: None,
                client_factory=object)
        self.assertEqual(len(count), 2)

    def test_unrelated_collector_not_retried(self):
        count = []
        def collect(*args, **kwargs):
            count.append(1)
            raise RuntimeError(DUP)
        with self.assertRaises(RuntimeError):
            collect_with_safe_peel_retry(
                {"collector":"arcgis"}, object(), collect=collect,
                sleep=lambda *_: self.fail("no sleep"))
        self.assertEqual(len(count), 1)

    def test_unrelated_peel_error_not_hidden(self):
        count = []
        def collect(*args, **kwargs):
            count.append(1)
            raise RuntimeError("Peel inspection date format changed")
        with self.assertRaisesRegex(RuntimeError, "date format changed"):
            collect_with_safe_peel_retry(
                PEEL, object(), collect=collect,
                sleep=lambda *_: self.fail("no retry"))
        self.assertEqual(len(count), 1)


if __name__ == "__main__":
    unittest.main()
