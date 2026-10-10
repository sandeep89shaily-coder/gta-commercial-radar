# GTA Commercial Radar v0.5

Adds Peel Health and repairs AGCO from the exact working v0.4 package. Toronto planning, ERO, permits and registry collectors retain their v0.4 definitions. No buyer-specific scoring is added.

## Upgrade from your existing v0.4 folder

This is a **code release**, not another copy of your 1 GB database. Extract `gta_commercial_radar_v05` **beside** `gta_commercial_radar_v04`. Keep v0.4 and its data until the upgrade is verified. Stop any running old poll and temporarily disable its daily task before switching.

Open PowerShell in the extracted v0.5 folder:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python main.py adopt --from-data "..\gta_commercial_radar_v04\data"
python main.py doctor --source agco_cannabis_retail_applications --source peel_health_food
python main.py poll
python main.py status
```

`adopt` copies a consistent SQLite backup and the existing history/raw deltas. It refuses to overwrite a destination that already contains a database. **Run adoption only once.** Adjust the `--from-data` path if your folders are arranged differently. The original v0.4 folder is retained.

If you prefer to avoid copying the database, every command supports `--data-dir "..\gta_commercial_radar_v04\data"`. Use the same data directory consistently and run only the v0.5 poller against it.

The first v0.5 poll:

- Existing v0.4 feeds continue with incremental windows or metadata checks; no rebaseline is required for them.
- AGCO establishes its first baseline. If your local AGCO already has records, its changed schema/identity will trigger a request to `python main.py rebaseline --source agco_cannabis_retail_applications`. This applies only to AGCO. The uploaded v0.4 database had no AGCO baseline.
- Each Peel category builds its directory baseline once. Food has hundreds of pages, so this can take tens of minutes depending on portal latency. Progress prints every page. This is **not** a redownload of the Toronto/Ontario baseline.
- Baselines do not fill `feed.csv` with historical NEW alerts. The console's baseline `new` count means rows added to storage, not alerts emitted.

Run a second `python main.py poll` acceptance check. AGCO should report `resource metadata unchanged; CSV download skipped` when unchanged. Peel should report `recent window`, rather than traverse its entire directory. Existing unchanged CKAN feeds should continue skipping downloads.

## Daily and weekly

```powershell
python main.py poll
python main.py reconcile
```

Daily uses metadata checks and recent windows. Run reconciliation roughly weekly to discover removals, undated facilities and changes to old inspection records. Toronto cleared permits remain backfill-only.

The PowerShell runners now change into their own folder, so Windows Task Scheduler works regardless of its working directory. If using the existing task name, reinstall from v0.5 with the **same time you previously chose**:

```powershell
.\install_daily_task.ps1 -Time "06:30"
```

The time is an example; the script replaces the old daily task's path. Weekly reconciliation remains separate, using `run_weekly_reconcile.ps1`.

## AGCO cannabis applications

The current page renders its table from a JavaScript-configured CSV. v0.5 reads the literal URL without executing JavaScript. Resource ETag/Last-Modified/size skip an unchanged export and detect changes within a day. If HEAD is unavailable, it fetches the small CSV instead of claiming it was unchanged.

Actual export columns are mapped to canonical fields. Application file identity survives licence issuance; legacy licence-only rows use licence and address identity. GTA filtering checks exact municipalities. Public notice dates remain event dates; publication timestamps do not manufacture UPDATED events for every store.

The reusable collector also supports paginated HTML tables and real CSV links. Unknown schemas, duplicate identities, repeated pages and empty filtered snapshots fail visibly rather than remove records.

## Peel Health

Seven independently tracked categories cover Brampton, Mississauga and Caledon:

| Source ID | Public category |
| --- | --- |
| `peel_health_food` | Food premises |
| `peel_health_personal_services` | Personal service settings |
| `peel_health_child_care` | Child care |
| `peel_health_pools` | Pools, hot tubs and splash pads |
| `peel_health_tanning` | Tanning beds |
| `peel_health_camps` | Recreational camps |
| `peel_health_drinking_water` | Small drinking water systems |

The collector reads the public disclaimer form and tables, retains facility IDs and detail-page evidence links, and tracks names, addresses, facility types, latest inspection dates and results where published. Some categories omit a result column; no result is invented. v0.5 tracks latest directory summaries and changes over time, not every violation or historical report.

After baseline, daily polling scans descending inspection dates with a seven-day overlap and stops at older dates. Missing facilities in a partial query can **never** be marked REMOVED. Full baseline/reconciliation traverses all pages with at most three read requests concurrently. Malformed or interrupted scans cannot commit partial removals.

New facilities without inspection dates and edits to older rows may first appear during weekly reconciliation. First observed does not prove newly opened. Removal is absence from the directory, not proof of closure. Inspection results describe the inspected date, not guaranteed current conditions.

## Source health and evidence

`data/dashboard.html` and `data/source_status.csv` separate the latest check, last successful check, last non-empty fetch, latest known record date and reported publication timestamp. Unchanged checks retain known record dates. Polling older than 48 hours is OVERDUE; errors remain visible. AGCO publication is flagged STALE after 30 days. Publication freshness is UNKNOWN without a verified timestamp; old inspection dates alone do not indicate a stale source.

New Peel/AGCO records retain evidence URLs; linked entity names open the source. Buyer scoring and cross-source project linking remain later work.

## Troubleshooting

- Target already has a database: do not adopt again; continue with `poll` and `status`.
- Interrupted adoption leaves `radar.sqlite.adopting`: move that staging file aside and retry. The original v0.4 data is retained.
- One source fails: others continue and its previous records remain intact. Retry with `--source SOURCE_ID` after checking the error.
- Peel page count/repeated facility error: the directory moved during pagination; no snapshot was committed. Retry that source. Do not rebaseline to bypass collection errors.
- Source definition changed: only rebaseline the named source if you intentionally changed its collector/filter/key. Historical runs and versions are retained.

See `SOURCES.md`, `VALIDATION.md` and `EXPANSION_ROADMAP.md` for evidence, test scope and next coverage work.
