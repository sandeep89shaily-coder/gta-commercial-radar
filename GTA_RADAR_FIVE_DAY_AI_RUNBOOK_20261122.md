# GTA Radar — 5-day / all-useful / AI investigation integration

Date: 2026-11-22. **Runbook for the normal Windows `RUN_GTA_RADAR_TODAY.bat` workflow.**

## Owner-approved operating decisions

- Include the source-event dates **today and the preceding four calendar days**. For 2026-11-22: November 18–22.
- Preserve **ALL** qualifying general-commercial and industrial-equipment research candidates; Top 10 is only a summary, not a restriction.
- Make a **separate older active / scope-change watchlist**. A first-Radar-observed date does not establish the publisher's first disclosure date.
- Run source-backed AI planning, search/fetch and evidence analysis for all qualified fresh candidates in descending commercial research value, subject to existing shared paid-budget control. Retain the full investigation queue even when budget is exhausted.
- Never send emails or initiate sales outreach without the owner's explicit approval. No model inference alone establishes buyer authority, open procurement or first publication.

## Changes

1. `gta_unified_municipal_daily.py` now reconciles 15 independent source-specific daily change lanes, plus V6 permit changes, where their actual collection files exist. Does **not** import the 31-city historical master as freshly published events or replay old Toronto CKAN changes.
2. `gta_freshness_first_daily_selection.py` writes:
   - `GTA_RADAR_FRESH_GENERAL_RESEARCH_ALL.csv`
   - `GTA_RADAR_FRESH_EQUIPMENT_RESEARCH_ALL.csv`
   - `GTA_RADAR_FRESH_GENERAL_RESEARCH_TOP10.csv` (compatibility)
   - `GTA_RADAR_FRESH_EQUIPMENT_RESEARCH_TOP10.csv` (compatibility)
   - `GTA_RADAR_OLDER_ACTIVE_OPPORTUNITY_WATCHLIST.csv`
3. `gta_five_day_all_ai_queue.py` creates:
   - `GTA_RADAR_FIVE_DAY_ALL_AI_CANDIDATES.csv` — all source-qualified, commercially scored candidates that are safe to investigate
   - `GTA_RADAR_FIVE_DAY_ALL_AI_CANDIDATE_AUDIT.csv` — all input research records with explicit inclusion/hold reasons
   - `GTA_RADAR_FIVE_DAY_ALL_AI_QUEUE_STATUS.json` — counts, source cities and evidence/eligibility warnings
4. In the full current live run (not historical or test mode), `gta_monday_full_run.py` now prepares the 5-day list **before** the adaptive DeepSeek harness, and calls the existing `gta_execute_ai_project_research.execute` for eligible records. Model work is stored under `FRESH_AI_INVESTIGATIONS/`, with source evidence and per-project explanations. The shared local US$1/day DeepSeek ledger remains in force; **this change does not increase spending permission**. Project count is not capped at 10, but a hard safety bound of 500 remains and insufficient available budget causes explicit deferral.
5. `gta_ai_top10_reranker.py` preserves raw responses and successful per-project checkpoints, attempts one separately tracked JSON reformat/reanalysis when a paid reply is invalid, and continues analyzing other projects if that fails. It still refuses to label an incomplete 24/28/31-city review as an approved AI Top 10.

## Live acceptance checklist

- Check `MONDAY_FULL_RADAR/MONDAY_FULL_RADAR_STATUS.json` for `all_five_day_ai_research`, `unified_municipal_daily_changes` and `freshness_first_daily_selection`. A budget hold should be reported, not silently dropped.
- Check `GTA_RADAR_UNIFIED_MUNICIPAL_DAILY_STATUS.json`: per-source input/accepted counts and **real** cities with changes. A municipality being configured does not prove live successful coverage.
- Check `GTA_RADAR_FIVE_DAY_ALL_AI_CANDIDATE_AUDIT.csv`: every excluded lead has an explicit reason. Zero eligible rows is not necessarily zero actual developments.
- Check `FRESH_AI_INVESTIGATIONS/AI_PROJECT_RESEARCH_MANIFEST.json`: actual paid attempts, completed research records, held budget, source-fetch failure/402, and model failure file. Files are included in the dated ZIP.
- Check `GTA_RADAR_COMBINED_28_CITY_AI_TOP10_ATTEMPT_STATUS.json` for `recovered_json_batches`, `failed_reviews`, and `reviewed_count`. An invalid answer should no longer erase all successful checkpoints.
- Verify at least one real non-Toronto file-ID record flows from an approved source to the five-day research output. Official source blocking and municipal feed permission gaps **remain**; code integration alone cannot assert a successful live city.
- Independently verify original publication, specific purchasing authority, supplier-award/open-package status, and business contact before any customer release.

## Operational constraints

The live desktop run and its saved API key/municipal data sources are unavailable to GitHub Actions tests. Passing offline Linux/Windows CI confirms code behavior against fixtures, not real collection or purchases. No messages have been sent to any municipality, company or supplier.
