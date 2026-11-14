"""The saved-key balance checker must be free, privacy-safe and side-effect free."""
import io
import json
import unittest
from urllib.error import HTTPError
from gta_deepseek_check_saved_key_balance import check, BALANCE_URL


class DeepSeekSavedKeyBalanceTests(unittest.TestCase):
    def test_missing_key_makes_no_request(self):
        result = check(key="", opener=lambda *_args, **_kwargs:
                       self.fail("Network must not be called"))
        self.assertEqual(result["status"], "NO_RADAR_API_KEY")
        self.assertEqual(result["model_calls"], 0)

    def test_same_saved_key_read_only_endpoint_does_not_print_secret(self):
        calls = []
        def opener(req, timeout=20):
            calls.append((req.full_url, req.get_method(), req.get_header("Authorization")))
            return io.BytesIO(json.dumps({
                "is_available": True,
                "balance_infos": [{
                    "currency": "USD",
                    "total_balance": "1.95",
                    "topped_up_balance": "1.95",
                    "granted_balance": "0.00",
                }]
            }).encode("utf-8"))
        result = check(key="test-secret-do-not-log", opener=opener)
        self.assertEqual(result["status"], "RADAR_KEY_BALANCE_READ")
        self.assertEqual(result["balance_infos"][0]["total_balance"], "1.95")
        self.assertEqual(calls[0][:2], (BALANCE_URL, "GET"))
        self.assertIn("test-secret-do-not-log",calls[0][2])
        self.assertNotIn("test-secret-do-not-log", json.dumps(result))
        self.assertTrue(result["no_model_search_fetch_requests"])
        self.assertFalse(result["ledger_reservations_changed"])

    def test_balance_error_does_not_leak_saved_key(self):
        def opener(req, timeout=20):
            raise HTTPError(BALANCE_URL, 401, "No access", None, None)
        result = check(key="test-secret", opener=opener)
        self.assertEqual(result["http_status"], 401)
        self.assertNotIn("test-secret",json.dumps(result))


if __name__ == "__main__":
    unittest.main()
