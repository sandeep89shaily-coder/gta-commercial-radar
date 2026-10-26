# Safe V8 early-signal desktop trial

**Double-click `RUN_V8_EARLY_PREVIEW.bat` after extracting the ZIP.**

This is a complete source-code snapshot from the V8 integration development
branch. The batch file does **not** download `main` and does not call the legacy
`GTA_RADAR_V8_ONE_CLICK.bat`, which points at the older main branch.

The launcher locates the existing `Desktop/new data` workspace and its valid
`radar.sqlite`. It creates
`Desktop/new data/GTA_RADAR_V8_EARLY_PREVIEW` and makes a consistent SQLite
backup of the established Radar database and other pilot SQLite history in
that same original data directory. Subsequent preview runs keep using the
preview copies; initial records are not repeatedly rebased as newly detected.
Original database contents, the current output folder and installed Windows
scheduled tasks are not touched.

The preview uses the common V8 collection coordinator for the existing main
collectors and all nine pilot groups (21 feed definitions; 17 additional after
four V8 overlaps). It runs with `--no-ai --no-schedule`, so paid API calls
and unattended scheduling are disabled. It then opens the one V8 dashboard.

The useful preview outputs live under
`GTA_RADAR_V8_EARLY_PREVIEW/GTA_RADAR_RESULTS`:

* `GTA_RADAR_V6_DASHBOARD.html` — primary report
* `GTA_RADAR_ALL_SOURCE_STATUS.csv` — health per feed and decision on 14
  disabled sources
* `GTA_RADAR_EARLY_CUES_REVIEW.csv` — fresh early cues, evidence gaps and
  review-only signals
* `CANDIDATES_V4_ALL_REVIEW_ONLY.csv` — qualified potential research targets,
  **not** verified supplier opportunities
* `V6_LOGS` — failures to debug without rerunning the whole system

A first baseline is not a fresh commercial opportunity. A missing or failed
source is not an empty-success. A development application is not proof that
a purchasing package remains unawarded. User still needs a successful
Windows live run before adopting these changes for scheduled production.

Avoid `GTA_RADAR_V8_ONE_CLICK.bat` for this trial: it fetches `main` and
does not use the selective-free trial mode.
