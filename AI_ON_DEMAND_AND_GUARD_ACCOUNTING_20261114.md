# DeepSeek research routing and budget guard audit — 2026-11-14

## Corrected interpretation of November 14 export

The 17:08 local collection reports **zero paid research attempts, zero native searches and zero investigations** in its `GTA_RADAR_V6_RUN.json` selective-AI section. The `0.99425` USD figure appears under `reserved_usd` and `actual_daily_ledger_estimate_usd`, while status is `DAILY_USD_LIMIT`. **This proves the local software cap blocked calls; it does not prove any provider charge.** The shared `v5_ai_budget.sqlite` and historic `deepseek_budget.sqlite` ledgers were not included in the shared ZIP, and we cannot infer their underlying per-request statuses from the summary alone.

Previous assistant statements describing this as “US$0.99425 spent” were wrong. The user independently reports no actual DeepSeek spending; this audit is consistent with **zero calls in the evening collection**. Other persisted AI project outputs in the ZIP are not proof that the evening collector called DeepSeek.

## New read-only accounting diagnostic

`gta_ai_budget_guard_diagnostic.py` opens existing shared/legacy SQLite ledgers **read-only**, for the current local date, groups statuses and separates:

- completed API usage **cost estimates** (`DONE` rows with actual >= 0);
- unresolved or unknown requests held at the full **reservation**, regardless of whether the provider actually billed;
- total **local guard effective usage** and nominal reservations;
- what the current saved V6 run actually attempted;
- **provider_actual_billed_usd: null**, and `provider_billing_verified: false` always.

Output: `GTA_RADAR_RESULTS/GTA_RADAR_AI_BUDGET_GUARD_DIAGNOSTIC.json`, included in normal dated export. The diagnostic never requests DeepSeek, sends secrets, resets/overwrites the ledger, or claims actual invoices. On unreadable ledgers it returns HOLD, not zero billed.

## On-demand source-backed AI research in a manual full run

The seventh stage previously ran `gta_agent_harness.py` in **free-preflight mode only**—it planned buyer/procurement work but did not investigate it. In a *fresh operator-initiated manual collection* the stage now invokes:

`gta_agent_harness.py --results <existing-results> --paid --max-projects 2`

The harness uses the existing scored source-backed candidate queue, project input fingerprints, review checkpoints, existing original source search/fetch/model executor, cross-process run lock, and **shared software spending ledger** with the **existing configured cap**. It can propose source-backed research findings but cannot automatically promote them to verified buyers, procurement, or leads. A repeated project fingerprint is skipped; a source or model failure is auditable. If there is no supported source, no key, no eligible work, or the local ledger guard is full/held, no paid model call occurs and the status explains why.

Saved-data review (`--skip-collection`) always remains **free**, including the seventh preflight stage. The number of core stages stays seven. There is no new scheduled job, budget increase, account reset, external data-provider dependency, automatic outreach, or database mutation beyond the existing paid executor's intentionally shared ledger accounting.

**Important commercial gate:** Model analyses are provisional even if names match a search page. Original pages and legal company roles still need verification; an applicant is not necessarily the purchaser, and procurement availability requires direct evidence.

## What to do if the software guard blocks despite zero provider charges

First read `GTA_RADAR_AI_BUDGET_GUARD_DIAGNOSTIC.json` from a *new* owner-side collection. Compare `DONE` estimates and `RESERVED`/`UNKNOWN` holds with the DeepSeek provider's actual activity for the same day. Only after that reconciliation should stale holds be explicitly reviewed; no automatic resets or “spent” labels are permitted. Existing `radar_config.py` currently sets the local guard to **US$1.00/day**; other historical reporting hardcodes US$0.25/day. This PR **does not change either**; aligning the business policy is a separate deliberate decision, not a presumed account charge.

## Acceptance

- CI on Ubuntu/Windows Python 3.11/3.12.
- Validate actual owner-side ledger diagnostic values and source-backed research attempt/skip reasons.
- Model results, if any, remain `AI_REVIEW_ONLY`.
- Verify the run keeps the existing database and DeepSeek ledger history; do not infer provider charges from the guard.
