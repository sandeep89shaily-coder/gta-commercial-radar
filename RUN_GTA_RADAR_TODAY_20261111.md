# GTA Radar — one-click manual full run for November 11, 2026

**Owner directive:** integrate the existing manual discovery, the revised Burlington/Vaughan/Kitchener evidence gates, industrial equipment intelligence, commercial facility activation, facility evidence graph, Toronto 20 source-review package, free AI harness, and dated results export.

## On the installed Windows PC

From the current local clone of `sandeep89shaily-coder/gta-commercial-radar`, double-click **`RUN_GTA_RADAR_TODAY.bat`**. Legacy desktop shortcuts `RUN_TOTAL_INTELLIGENCE_TODAY.bat` and `RUN_ALL_GTA_RADAR_MONDAY.bat` also direct to this canonical one-click launcher.

1. The launcher first invokes `desktop_update.py` in a distinct Python process. It checks the origin, refuses dirty/diverged/unverified code, fast-forwards **only the Git code** to `origin/main` and compile-checks it. The original `radar.sqlite`, previous results, source CSVs, ledger snapshots, pilot cursor and paid-AI state are never deleted or reset. If Git is unavailable or the code cannot be safely verified, collection is **not** started. No `git reset --hard` is used on a dirty workspace.
2. It then launches **one** integrated manual `gta_monday_full_run.py` execution, regardless of weekday. It runs the existing normal daily collector once (including eligible source-aware DeepSeek investigation under the **existing shared US$0.25/day budget**) and then the industrial ERO pilot (max **10** policy-permitted source requests), commercial activation, facility evidence review, Toronto 20 research and **free-only AI harness preflight**. No second paid AI run or automatic outreach is introduced.
3. Each stage writes its own log and passed/failed status in `<existing new data>/GTA_RADAR_RESULTS/MONDAY_FULL_RADAR/`. Each original source and buyer-stage gate continues to apply. A stage returning 0 means execution health, not ten commercial buyer leads.
4. After the final stage, `gta_daily_result_archive.py` creates a new timestamped `<existing new data>/GTA_RADAR_EXPORTS/GTA_RADAR_RESULTS_YYYY-MM-DD_HHMMSS.zip` containing the current integration status, source/ID/ledger CSV/JSON, independent pilot review CSVs, and source-checked PDF/HTML reports. The ZIP has a per-file SHA-256 inventory and a conservatively labelled fresh/saved-evidence status. It never includes `radar.sqlite`, raw API keys, auth files, previous exports, or per-stage logs. If the export fails, the main launcher reports an error rather than telling the operator everything finished.
5. The owner can attach the new dated ZIP to the conversation for independent 20-source-record and 10-facility verification and for follow-up on Burlington's two successful Windows runs. The ZIP and manifest do **not** itself certify original posting dates, tenants, purchasing authority, a new business opening, or a viable unawarded equipment purchase.

**Critical release limits:** Vaughan and Kitchener public GIS source access remain restricted pending the municipal data-access replies; the runner will not circumvent robots/403. Burlington live GitHub source acceptance previously showed 10/10 selected current City pages, 16 application IDs, but **two independently dated post-fix owner-side Windows runs have not been executed and compared here**. Current ERO research identifies 4 equipment changes from 3 original notices; buyer and supplier purchase packages are unverified. Pilot CSVs stay review-only.

## When collection cannot be run here

The original live Windows `radar.sqlite`, source exports and paid-AI credentials are on the owner's PC and **are not available inside GitHub Actions or this assistant session**. A passing remote GitHub test run is code validation, not today's local daily Radar run. Do not call an Actions smoke test a successful manual collection or create a replacement empty database. A real daily output ZIP must come from the authenticated owner-side manual launcher.

## Checked in CI

The existing six-stage ordering is preserved. New tests check the safe-update launcher ordering, legacy shortcut compatibility, dated ZIP manifest and SHA inventory, exclusion of credentials and SQLite, archive tamper/double-write refusal, and failure reporting. CI must pass Windows and Linux Python 3.11/3.12 before release.
