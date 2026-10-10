# v0.7 — Eleven-source collection-policy batch

This release updates **all 11 flagged configurations**, rather than installing another isolated feed. The original SQLite schema, source enablement, existing collectors and lead export architecture remain unchanged.

- **Incremental (2)**: Durham business sites (`Updated_Date`) and Durham capital projects (`DATEUPDATED`). Both require live modification-date tests before enabling.
- **Scheduled snapshots (9)**: York applications (7 days), Mississauga site plans (3), Mississauga rezoning (3), Richmond Hill applications (3), Hamilton development applications (7), Durham consents (7), Durham Official Plan (7), Hamilton building/demolition (30, historical caution), Kitchener planning (3 until live timestamp query is proved).
- Sources stay **disabled** in normal unattended polling until their live checks and commercial-use licence review are completed. They can be explicitly selected during acceptance runs.
- A scheduled snapshot with a valid previously stored baseline is deferred until its interval elapses. `reconcile` always forces a full comparison. No synthetic empty run is written on a deferred check.
- ArcGIS full or incremental imports now reject mismatched reported/received row counts rather than treating partial retrieval as complete.
- A recent *application* or *issue* date is not necessarily a modification timestamp: never use it alone to claim updates are captured.

## Run tests
`python -m unittest discover -s tests -v`

## Acceptance before enabling
Use existing `regional_pipeline.py` read-only batch probes, then targeted `doctor` and source-limited `poll` in a **copied database**. Confirm stable IDs, pagination, suitable dates, source freshness and licence rights. No automatic migration/setup of your production folder occurs in this release.

**No live remote-data verification was possible in this build environment.** This is a locally tested code package, not a declaration that 11 feeds have completed real-data imports.
