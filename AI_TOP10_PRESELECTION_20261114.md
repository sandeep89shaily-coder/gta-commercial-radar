# DeepSeek pre-selection for the commercial top ten (Nov 14, 2026)

## Problem

The deterministic top-ten analyst shortlist is useful for source-first filtering but can select duplicate application IDs presented with different spaces, older/superseded industrial projects, or large residential work that is less relevant to buyers of industrial equipment, HVAC, electrical, security and facility services. Post-selection DeepSeek research cannot correct the selection itself.

## Architecture / deployment

### 1. No-cost candidate preparation
`gta_commercial_qualification_review.py` continues to combine client freshness, private development and source-backed V8 pending project data with the existing exact-ID source-evidence company graph and lifecycle conflict flags. The prior source/first-seen date distinction remains. It now removes duplicate *presentation records* where single unambiguous application IDs differ in spaces (e.g. `25 249692 ESC 21 CD` vs `25249692ESC21CD`). Two different official IDs at the same address are **not** merged.

### 2. Conditional DeepSeek pre-selection review
`gta_ai_top10_reranker.py` selects up to 24 plausible industrial/commercial projects, trying to represent different municipalities. DeepSeek reviews them in up to three batches of eight with no additional Search/Fetch. It receives bounded **existing source snapshots only**: official reference, original source dates, filing status, relevant description, exact-ID role evidence, unresolved contradictions and prior-report status.

The model returns exactly one of `PREFER`, `NEUTRAL`, `CHECK_CONFLICT`, `DEPRIORITIZE` for each candidate, with a short rationale and **next verification step**. This review is not an independent live fact-check; stale source snapshots remain stale until independently rechecked.

- `PREFER` adds **8** points, `CHECK_CONFLICT` subtracts **8**, `DEPRIORITIZE` subtracts **12**, `NEUTRAL` changes nothing. These are internal queue nudges, *not* investment/contract probabilities.
- Model-suggested roles, dates, contacts, procurement or factual claims are **never written as verified fields**. Unknown buyer and supplier contract fields remain unknown.
- A model decision is applied **only if all selected candidates were reviewed**, each output is valid, unique and matches the current source fingerprint. Missing, partially truncated, invalid, unpriced or blocked batches fall back to the deterministic rank.
- Every completed batch is saved under an immutable input-fingerprint key, preventing repeated charges on an identical batch. Existing shared DeepSeek ledger, daily cap **US$1**, process lock and HTTP 402 stop are reused. No new secrets or provider accounts.
- Independent API charges are not proven by local spend estimates.
- Existing full manual workflow invokes this assessment **after source collection and before the project research harness**. It does not add an eighth collection stage or bypass the ledger; paid calls run only during the owner-initiated manual full run.

### 3. Transparent outputs
- `GTA_RADAR_AI_TOP10_REVIEW_STATUS.json` — complete, input-matched AI decisions, source-only disclaimer and counter.
- `GTA_RADAR_AI_TOP10_ATTEMPT_STATUS.json` — whether the attempt was complete, partial, skipped or blocked.
- `AI_TOP10_REVIEW_BATCHES/` — immutable per-batch result/cost-estimate checkpoints.
- `GTA_RADAR_COMMERCIAL_TOP10_ANALYST_REVIEW.csv` — final internal top ten with model decision, reason, next check and score adjustment.
- `GTA_RADAR_COMMERCIAL_QUALIFICATION_STATUS.json` — records whether AI was applied or ignored.

This is **not a report of ten verified, purchasable packages**. Any actual quotation/contract recommendation still requires original source checks, company legal entity, purchasing authority, unawarded package evidence and legitimate public contact route.

## Owner commands

No paid requests: run the normal offline refresh. This reuses only complete, matching saved AI assessment artifacts.

    py -3 .\gta_ai_project_intelligence_refresh.py --results "C:\Users\sande\Desktop\new data\GTA_RADAR_RESULTS"

Optional one-time paid AI assessment *of the existing records only*, without rerunning collectors:

    py -3 .\gta_ai_top10_reranker.py --results "C:\Users\sande\Desktop\new data\GTA_RADAR_RESULTS" --paid

The second command requires the saved, working key and the established shared software guard. It can make up to three batch-model requests. The full seven-stage manual launcher will run this step automatically after its source work, if fresh collection succeeds.

Never send a client report claiming these AI-nudged entries are currently unawarded projects solely because they appear in the top ten.

## Testing

Offline regression tests mock the DeepSeek API, covering no-paid default, valid bounded score impact, source-input change invalidation, partial/model-invalid fallback, exact-spaced-ID duplicates, immutable batch reuse, account HTTP 402 release and strict nonpromotion of buyers/contracts. Windows and Linux Python 3.11/3.12 CI required before merge.
