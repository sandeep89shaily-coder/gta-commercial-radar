# GTA Radar — early planning signals pilot

**State: proposed pilot, not activated in the V8 daily schedule.**

This additive free-data watcher collects official pre-permit development signals for Toronto, Brampton, Mississauga, and York Region (including but not limited to Vaughan). It deliberately keeps its own `data/early_signals_review.sqlite` database and **does not** edit `radar.sqlite`, modify `config/sources.json`, or call DeepSeek. There is no automated sales outreach.

## Included GIS signals

- Brampton: pre-consultation (before formal application), OPA/rezoning/subdivision, site-plan approval (three official Brampton GIS layers)
- Mississauga: site-plan and rezoning applications (already staged in main Radar but not enabled)
- York Region: active development applications (region-wide; **not** a verified Vaughan-only feed)
- Toronto: development applications (separate observation history for comparison with the existing main collector)

This does **not** yet include corporate investment announcements, commercial leasing, or council-document PDF extraction. These require a separate source-quality and rights review.

## Usage

Once this branch is merged and present on the installed computer, double-click `RUN_EARLY_SIGNALS_PREVIEW.bat` in the repository folder.

Or, in a command prompt from the repository folder:

```
python early_signal_watch.py --data-dir data --output-dir GTA_RADAR_RESULTS
```

To test a single source without running the other six:

```
python early_signal_watch.py --data-dir data --source brampton_preconsultation
```

All seven feeds are **manual/opt-in**, and a failed feed does not wipe data or turn old records into new leads. No daily Task Scheduler changes have been made.

Outputs:
- `GTA_RADAR_RESULTS/EARLY_SIGNALS_CHANGES_REVIEW_ONLY.csv` — genuinely newly observed / materially updated public planning records **after** a successful first baseline
- `GTA_RADAR_RESULTS/EARLY_SIGNALS_SOURCES_STATUS.csv` — per-source success/failure and counts
- `data/early_signals_review.sqlite` — per-source history and immutable event log

**Important first-run behavior:** the first successful snapshot for each source creates a baseline and generates *zero* new-lead alerts. Source application dates and first-observed timestamps are distinct. Subsequent record changes are **changes in a published public dataset**, not proof of new construction, unawarded procurement, decision-maker authority, or insurance intent.

The review CSV includes `record_scope`. `APPLICATION_ID` means unique in that snapshot; `FEATURE_ONLY` means multiple public features share an application number or lack one, and the row uses GIS object ID as a *feature key*, not a new project identity. No project counts or sales-ready claims should be made directly from feature-only rows. Use the original source URL and application ID for human review.

## Reliability and acceptance gates

Before connecting any source to the unattended V8 daily run:

1. Run the offline tests: `python -m unittest tests.test_early_signal_watch`.
2. Test on a computer with internet connectivity; inspect each GIS source count, fields, date freshness, and source errors.
3. Verify the published application number, applicant role, and actual business use on original municipal pages.
4. Confirm dataset terms for automated commercial reuse and attribution, including York Region and Brampton.
5. Run on two different days and confirm second-day `NEW`/`UPDATED` only appears for actual source changes.
6. Measure lag between source application date, first public availability (when known), and Radar first observation. These are **not interchangeable**.
7. Investigate whether source GIS row/object IDs remain stable across republishing. Do not silently treat ID reassignments as new projects.
8. Prevent duplicate reporting alongside existing Toronto or Mississauga source events before connecting to the V8 queue.
9. Resolve V8's contradictory US$0.25 vs US$1 DeepSeek budget settings independently; the pilot makes no AI calls.

The collector fails closed on missing IDs, empty snapshots, duplicate features and incomplete GIS responses. It intentionally does not infer cancellation if a record disappears from a public layer.

## What this stage does not claim

This first stage establishes source collection and change-history plumbing, **not** ten verified commercial opportunities or automated sales leads. No live remote fetch or all-suite tests were executed when the code was authored; GitHub CI and the first Windows preview are the acceptance checks. Keep V8 unchanged until those checks pass.
