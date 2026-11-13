# Phase 2 AI research spending — 2026-11-12

The owner approved increasing the DeepSeek daily research budget to enable extensive AI-assisted buyer, equipment and procurement analysis. This change raises the **main shared investigator ceiling from US$0.25/day to US$1.00/day** (a maximum of US$30 over 30 days if every daily ceiling is reached). This is an initial operational limit, not an estimate that the model will spend that much.

## What changes
- `radar_config.DEEPSEEK_DAILY_LIMIT_USD` is the main authoritative ceiling.
- V5, V6/V7/V8 native investigators, selective fresh-event review, AI planner/harness and read-only diagnostic use this limit.
- The selective pipeline's stage/status labels reflect the configured limit instead of the old 0.25 figure.
- All prior reservation/ledger locking, duplicate checks, project eligibility, human evidence gates and review-only output requirements remain.
- The default harness remains free unless its **explicit paid option** is used. No scheduled collection or paid investigation is activated by this change.

## Important limitation: multiple legacy budgets
This main shared cap is enforced by the `v5_ai_budget.sqlite` ledger across its integrated investigators. Some **older standalone DeepSeek scripts** (`deepseek_daily.py` and `deepseek_research_agent.py`) retain a separate US$1/day legacy ledger. The new US$1 value is **not a guaranteed account-wide/provider-side limit** if these are run separately; avoid launching both integrated and legacy paid workflows until a single combined ledger is implemented. API provider charges and rate changes require independent checking. This change does not move secrets, reset ledger history or give permission for automatic API use.

## Acceptance
- Check `python -m unittest discover -s tests -v` on Windows and Linux, including budget/ledger regression coverage.
- In a manual owner run, inspect `gta_deepseek_budget_diagnostic.py` and the exact output/usage costs.
- Continue sourcing buyer/company/equipment claims only with exact original references. Keep unknown buying authority and available supplier packages UNKNOWN until independently established.
- Evaluate value per sourced and independently verified opportunity before increasing this ceiling further.
