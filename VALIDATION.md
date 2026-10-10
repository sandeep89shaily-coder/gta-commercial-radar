# v0.5 validation

## Automated checks

`python -m unittest discover -s tests -q` passes **38 tests**: the 21 inherited v0.4 tests plus 17 web-collection/upgrade tests.

Coverage includes CSV widget discovery, server-rendered HTML fallback, exact GTA municipality filtering, same-day resource changes, unchanged-resource download skipping, application identity through licence issuance, duplicate/schema failure protection, Peel result images and categories without a result column, pagination and last-page handling, date-sort verification, bounded scans, partial-window removal safety, freshness retention and upgrade safety.

The actual adoption command is exercised while a source SQLite connection holds committed data in WAL mode. Records, versions, runs, fingerprints and raw deltas survive; repeat adoption refuses to overwrite the target.

## Uploaded working database

The uploaded v0.4 database contains 564,103 current records and 564,103 record versions, 42 runs, zero emitted changes, and 10 source fingerprints. A separate adoption copy retained every one of those counts and all source-state rows. SQLite `quick_check` returned `ok`. All 10 existing fingerprints match v0.5; no existing permit, planning, ERO or registry source needs rebaseline. The source database was not polled or rebaselined during release validation.

## Live interfaces checked

- AGCO: actual CSV contains 2,658 Ontario rows; exact municipality filtering retains 869 GTA rows. Resource Last-Modified was 2026-10-08 11:25:17 GMT. An immediate repeat collection skipped the CSV body. These are observed counts, not hard-coded expectations.
- All seven Peel categories: first pages parse facility identity, name, address, type and latest inspection date. Food/personal-service result labels are retained; the other five category tables omit the result column.
- Full directories completed for tanning (27 facilities, 2 pages), recreational camps (3 facilities, 1 page), and small drinking water systems (66 facilities, 3 pages). Their recent-window checks return zero rows when no inspection falls in the tested window and remain incomplete snapshots, preserving existing records.
- Food daily window since 2026-10-01: 294 retained records from 12 pages, versus a published directory of 294 pages. The collector stops at older dates and does not infer removals.
- Food full-directory pagination verified across the first seven pages using facility-name sorting. The slow full scan was intentionally interrupted; no food current rows or change alerts were committed. **The entire food directory, personal-service, child-care and pool baselines were not completed in this release session.** Their first full runs must finish on the desktop. Do not treat first-page checks as validation of every remote row.

## Limits

There is no claim that every live public row or future source schema is validated. Portal latency and moving pagination can interrupt a full baseline; progress/retries are visible and a failed scan leaves that source unchanged. A directory scan is not an atomic municipal export, so page-count/duplicate guards may ask for a retry if the source moves during collection.

Daily Peel queries can miss undated new facilities and edits to old inspection rows; weekly reconciliation covers these. v0.5 records directory summaries and their observed changes, not complete historical inspection reports. A directory entry/inspection is a corroborating business signal, not a guaranteed new opening, closure or design lead.

PowerShell scripts were reviewed but not executed on Windows in this Linux environment. The SQLite upgrade command and Python CLI/status paths were exercised locally.
