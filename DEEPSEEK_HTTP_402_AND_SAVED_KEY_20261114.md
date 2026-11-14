# DeepSeek HTTP 402 response, saved API key check and ledger holds (Nov 14, 2026)

## Verified operator evidence
- DeepSeek platform screenshot, **Today**, **All API keys**: USD 1.95 topped-up balance, 0 requests, 0 tokens and $0.00 usage.
- Radar local guard diagnostic: 388 ERROR rows with USD 0.99425 **unresolved local reservations**, zero completed-cost estimate; no paid attempts in latest 17:08 collection.
- Saved AI-investigation records had HTTP 402 "Payment Required". DeepSeek documents HTTP 402 as **insufficient balance** at the time of the rejected request, but the current screenshot indicates there is money in this browser account. This could be a key/account mismatch or a previous balance condition. The screenshot alone does not determine which key Radar is using.

## Critical change
- `v8_deepseek_native.request` now explicitly classifies HTTP 402 from the provider as `DeepSeekAccountBalanceError`.
- Search/Fetch 402 responses are **known nonbillable**, with zero local reservation. The official guide says successful non-empty HTTP 200 Search and Fetch calls are billed, and rejected requests are not. A single HTTP 402 **stops that research run**. Other HTTP failures remain cautious unresolved holds if their billing is uncertain.
- The adaptive AI planner and AI project research executor now propagate that error, release the specific newly rejected claim, and stop future attempts in that run instead of repeating the same rejection for every project.
- The AI harness exposes `PROVIDER_HTTP_402_BALANCE_REJECTED` rather than a generic "no completed reviews" status. Existing seven-stage collector code, shared spending cap, saved research queue and source evidence remain intact.

**Previous 388 error entries are NOT automatically modified.** They predate this change and cannot be safely classified or released in bulk without matching error-level provenance and API-account billing evidence.

## Verify that Radar's key belongs to the funded DeepSeek account

Open PowerShell **in your Radar code folder** (after `git pull --ff-only`):

```powershell
py -3 .\gta_deepseek_check_saved_key_balance.py
```

This reads the same encrypted key as the collector (or `DEEPSEEK_API_KEY` environment variable if set), makes exactly one **GET** to DeepSeek's official `https://api.deepseek.com/user/balance`, and prints only the available balance, not the key. It makes no model/search/fetch calls, costs no tokens and never changes the ledger.

If the result reports `RADAR_KEY_BALANCE_READ` and USD 1.95, the key's live account balance matches the browser's USD amount, subject to any later transactions. If the key returns `NO_RADAR_API_KEY`, HTTP 401/402 or a different amount, identify and fix that configuration before the full AI run.

## Existing holds
Old `ERROR` ledger entries presently consume USD 0.99425 of the local USD 1.00 guard despite zero completed-call estimates. The new fix prevents the same issue **from new HTTP 402 requests** but does not retroactively reconcile these records. Keep the files; do not manually delete `v5_ai_budget.sqlite` or indiscriminately wipe every `ERROR` entry. Retained old holds are date-scoped: the next local calendar day starts a new ledger day, but the underlying provider-key problem must be fixed independently.

## Operator acceptance
- Full Windows/Linux Python 3.11/3.12 tests, including simulated HTTP 402 and zero-result accounting.
- Test the zero-paid-request balance script on the owner Windows installation and compare to browser.
- Do not infer actual provider charges from ledger holds; do not assert the user spent any money today.
