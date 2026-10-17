# GTA Commercial Radar V5 — autonomous research (single batch)

**Purpose:** take evidence-first V4 candidates, investigate them against live public pages, use DeepSeek for grounded synthesis if the user configured a key, then create one HTML report. This is **not** an automated lead-selling or messaging system. Records remain `REVIEW_ONLY`.

## Windows — one file, no copying program folders

Download `GTA_RADAR_V5_ONE_CLICK.bat` and double-click it from Downloads. This standalone launcher embeds the V4 selector and V5 investigator and finds your existing `new data` database (including nested `GTA_RADAR_DAILY_48H/data`). It does **not** modify `radar.sqlite`, existing collectors, raw records, or task schedules for older programs.

It writes everything under `new data/GTA_RADAR_RESULTS` and opens `GTA_RADAR_V5_DASHBOARD.html`. On its first interactive Windows run it attempts to register **its own** daily review task for 8:30 AM, only when the PC is running. If Windows Task Scheduler refuses, the console says so. It never installs a second collector or replaces the user's original collection task.

To enable AI, it uses `DEEPSEEK_API_KEY` in the environment or the **existing encrypted Windows per-user DPAPI key** at `%LOCALAPPDATA%/GTACommercialRadar/deepseek_key.dpapi`. If neither exists, the interactive launcher offers a one-time hidden key entry and saves it with DPAPI. Press Enter to skip; no DeepSeek calls are made without a key. Never send the key through ChatGPT or put it in the repository.

## Unattended repository pipeline

`daily_radar.py` now runs `v5_investigator.py` after V4, as an optional step. The V5 module reads `data/CANDIDATES_V4_ALL_REVIEW_ONLY.csv` and produces `GTA_RADAR_V5_INVESTIGATIONS.csv`, `GTA_RADAR_V5_RUN.json`, and `GTA_RADAR_V5_DASHBOARD.html`. It searches a public Bing RSS index (best effort), reads public HTML pages only if robots policy permits, and checks that page text matches an address/company/permit identifier. **Search snippets are not accepted as evidence.** An inaccessible or irrelevant result remains unverified.

For a free no-AI review, call `python v5_investigator.py --no-ai`. The standalone Windows launcher also supports `--offline` (no web/AI) for testing and `--no-schedule` if task creation should be skipped.

## Spending and safety

- DeepSeek only (`deepseek-chat`); no OpenAI model or paid search provider.
- V5 maximum **8 projects per run**, one bounded API call per project and a **USD $0.50/day conservative local reservation**. This is not a provider-enforced billing cap; actual charges depend on DeepSeek's prices. Padded rates are $5/million input and $10/million output tokens; check against provider rates if they change.
- Daily SQLite reservation is transactional and fails closed when the cap is exhausted or if an older DeepSeek ledger is unreadable; existing `data/deepseek_budget.sqlite` reservations are included in the cap when available. **Old, separately scheduled API clients can still incur their own costs**; disable them if you require a single global limit.
- One project is not repeated for a paid run within the same day, and candidates reviewed in the previous seven days are deprioritized in favor of unexplored records.
- Unknown companies, contacts and operators remain blank unless the exact text appears in a source page actually retrieved; even a supported name is **not a verified buyer or qualified lead**.
- No automated outreach, advertising, email, contact list selling, or database changes.
- Public web searching is best effort and may be blocked or unavailable; no false claims of discovery are generated in those cases. The launcher relies on the existing municipal poll schedule for new source data and does **not** independently refresh the collectors. Check the dashboard/data timestamp before using any lead.

## Tests

`python -m unittest discover -s tests -p 'test_v5_*.py' -v`

The tests use temporary SQLite data and mocked search/API responses; they never spend API money. Live access to the public search index, actual DeepSeek calls, and Windows Task Scheduler must be verified on the user's desktop. The existing production data remain in place.