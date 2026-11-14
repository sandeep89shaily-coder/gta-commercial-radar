"""Manual, zero-model-call balance check for the exact API key saved in Radar.

Never prints or stores the API key. Does NOT clear ledger reservations, write
workspaces, make a model/search/fetch call, or incur AI token/tool fees.
"""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from v5_investigator import key_from_windows

BALANCE_URL = "https://api.deepseek.com/user/balance"


def check(*, key=None, opener=None):
    token = key_from_windows() if key is None else key
    if not token:
        return {"status": "NO_RADAR_API_KEY", "balance_checked": False,
                "model_calls": 0}
    req = Request(BALANCE_URL, headers={
        "Authorization": "Bearer " + token, "Accept": "application/json"
    }, method="GET")
    try:
        opener = opener or urlopen
        with opener(req, timeout=20) as response:
            data = json.load(response)
        if not isinstance(data, dict) or not isinstance(data.get("balance_infos"), list):
            raise ValueError("UNEXPECTED_BALANCE_RESPONSE")
        amounts = []
        for item in data["balance_infos"]:
            if isinstance(item, dict) and item.get("currency") in ("USD", "CNY"):
                amounts.append({"currency": item["currency"],
                                "total_balance": str(item.get("total_balance", "")),
                                "topped_up_balance": str(item.get("topped_up_balance","")),
                                "granted_balance": str(item.get("granted_balance",""))})
        return {"status": "RADAR_KEY_BALANCE_READ",
                "is_available": data.get("is_available") is True,
                "balance_infos": amounts,
                "no_model_search_fetch_requests": True,
                "ledger_reservations_changed": False}
    except HTTPError as exc:
        return {"status": "BALANCE_ENDPOINT_HTTP_ERROR",
                "http_status": exc.code,
                "balance_checked": False, "model_calls": 0}
    except (OSError, ValueError, URLError) as exc:
        return {"status": "BALANCE_CHECK_FAILED",
                "error_type": type(exc).__name__,
                "balance_checked": False, "model_calls": 0}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
