# Operator-attested DeepSeek local hold reconciliation — 2026-11-14

The official DeepSeek screenshot shows Today / All API keys / zero API requests, zero tokens, and $0.00 cost, with $1.95 available. The saved Radar API key independently authenticated to the official balance endpoint and saw $1.95. Radar's own read-only diagnostic showed 388 ERROR entries and USD 0.99425 of unresolved internal reservations. Those are **not established provider charges**.

The ledger itself does not store per-request HTTP error codes, so the 388 ERROR entries cannot automatically be matched to HTTP 402. This tool therefore refuses to change anything without the operator's explicit same-day zero-usage confirmation.

## No-change preview

From the existing Radar installation, with updated main code:

    py -3 .\gta_reconcile_deepseek_local_holds.py --results "C:\Users\sande\Desktop\new data\GTA_RADAR_RESULTS"

## Explicit optional same-day reconciliation

Only if the preview matches 388 entries and $0.99425, the provider dashboard still shows zero usage for the same date across all API keys, and the owner deliberately authorizes release:

    py -3 .\gta_reconcile_deepseek_local_holds.py --results "C:\Users\sande\Desktop\new data\GTA_RADAR_RESULTS" --date 2026-11-14 --apply --confirm-provider-zero-usage --expected-errors 388 --expected-usd 0.99425

The program refuses if the expected count/total, date or funded key status differs. It acquires Radar's normal process lock, makes a unique complete SQLite backup, and changes only same-day ERROR entries with NULL actual and positive reservation. The original error rows are **not deleted**: their status becomes RECONCILED_OPERATOR_CONFIRMED_ZERO_USAGE and their local reservations become zero. Old records remain fully available in the backup; completed/unknown/pending/other-day entries are not changed. An audit JSON is written. There are no model/Search/Fetch requests.

## After a successful explicit reconciliation

Run only the existing AI research harness; do not repeat the seven-stage collection:

    py -3 .\gta_agent_harness.py --results "C:\Users\sande\Desktop\new data\GTA_RADAR_RESULTS" --paid --max-projects 2

The pre-existing US$1/day shared ledger cap still applies, and all model output remains review-only. Check the harness manifest and the official provider usage after the run.

Never reset/delete the ledger, arbitrarily increase the budget, or apply reconciliation to old dates. If expected totals fail, investigate rather than adjusting the inputs blindly. Merging this optional tool alone does not change the user's database.