# GTA Commercial Radar V6 — collection + investigation, one daily workflow

This release connects the **existing** municipal and business collectors to the opportunity engine, V4 commercial selector, V5 DeepSeek evidence analyst and a new V6 HTML dashboard. The project remains a local Windows desktop workflow using Southern Ontario public sources.

## Workflow

1. Locate the `Desktop/new data` workspace. Prefer the database previously selected by the V5 launcher (recorded in `GTA_RADAR_RESULTS/RUN_DETAILS.json`), or use the largest valid existing collector SQLite database. Do not create a new empty collector database.
2. Run `main.py poll --data-dir <existing data>` against existing enabled municipal source definitions. This updates existing collection history using the collector's incremental/snapshot policy.
3. Run `business_discovery.py run --data-dir <existing data>` against enabled business discovery sources.
4. If **both collectors fail**, stop, report `FAILED`, and **do not reuse an old opportunities CSV** or launch AI. If one fails, mark `PARTIAL` visibly and continue only with available data.
5. Rebuild opportunities with a 2-day source-event window (`opportunity_engine.py --days 2`) and run V4 selector with the *current* collector database metadata. Municipality detection dates remain distinguished from permit issuance/opening.
6. Investigate up to 25 previously unreviewed candidates per run, prioritizing the existing five pilot projects. Recheck after seven days; daily reruns use cached same-day results. Discover potential source URLs using up to four public indexed RSS queries, read at most five corroborated pages, and invoke DeepSeek only when a page matches the project, operator or source identifier.
7. Save all resulting source links and caveats to `GTA_RADAR_RESULTS/GTA_RADAR_V6_DASHBOARD.html`, with `GTA_RADAR_V6_RUN.json`, per-step logs in `V6_LOGS`, and non-sale-ready research CSVs.
8. After a successful or partial interactive run, schedule **GTA Commercial Radar V6** daily at 8:30 AM and attempt to replace the previous V5-only scheduled task.

## Cost and safety

- Retains the existing V5 local DeepSeek budget ledger and checks earlier DeepSeek reservations in the existing collection data directory. Local reservation limit: **US$0.50/day**. This is **not** a provider-enforced billing cap; other external clients can spend separately.
- `DEEPSEEK_API_KEY` is read from the existing Windows DPAPI credential (or environment variable); no secrets in source files or reports. If no key, research proceeds without paid AI.
- The coordinator never deletes or replaces original collector DBs. **Successful polling updates the original databases** as intended; do not interpret it as a read-only process. A V6 lock prevents concurrent V6 writers.
- Existing V4 and V5 results remain in `GTA_RADAR_RESULTS`. An investigation is **REVIEW ONLY**, not a promise that a company is buying, that a permit is issued, or that contact information is cleared for outreach.
- Source robots/security checks, HTTP-only official collector configuration, and all existing source-license gates remain in the underlying collectors.
- When the computer is switched off or sleeping, the scheduled task cannot collect. Missing or failing sources are shown in the dashboard and logs.

## Running

Once the complete GitHub repository is installed locally, double-click `RUN_GTA_RADAR_V6.bat` in the installation folder. For direct CLI debugging:

```
python v6_daily_pipeline.py --workspace "C:\Users\<you>\Desktop\new data" --no-schedule
```

A separate one-click bootstrapper is provided for nontechnical Windows users. It downloads a pinned GitHub commit into a versioned **program-only** folder under `%LOCALAPPDATA%\GTACommercialRadar` and runs the above file. It does not download or copy your large database. The bootstrapper is never itself registered as the daily scheduled task.

## Acceptance

Run `python -m unittest discover -s tests -p 'test_v6_daily_pipeline.py' -v` plus the repository's existing test suite. Tests use simulated source calls; an actual first desktop run with live municipal feeds and the configured DeepSeek account must still be checked for source/network failures, terms, and spending.