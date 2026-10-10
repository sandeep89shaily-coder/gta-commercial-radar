Brampton collection fixes (October 2026)

Run START_RADAR.bat as usual. This release is a full Radar folder; place it beside, not over, your older Radar installation. It never modifies the original radar.sqlite. Your existing PC's Brampton archive remains in the older folder unless you deliberately transfer its brampton_sources.sqlite into this release's data folder. Do not transfer while either application is running.

1) Permit activity history: keyset pagination on OBJECTID with per-page SQLite checkpoints. On a normal run, up to 10,000 rows are collected, and a subsequent run continues the historical backfill. Set BRAMPTON_ARCGIS_ROWS_PER_RUN to a higher number to increase the per-run budget. Completion and periodic refresh of older IDs use the same checkpoint system. The initial 2.5 million rows may take many runs. No deletion events are inferred.
2) Food licence collector: verifies five separate columns and rejects malformed combined-field pages. Corrected records use a new source identifier brampton_food_licences_structured so prior incorrectly parsed rows are preserved separately as unverified historical observations. HTML pagination/completeness remains unverified; reports remain PARTIAL.
3) Inspections: bounded network retries, shorter metadata timeouts, limited 200 rows/run, and smaller 100-row batches. A persistently unresponsive server still shows ERROR without blocking other feeds.

The first run against the live Brampton service is needed to validate the site's current HTML and query behavior. Offline tests do not prove site availability or full licensing-page coverage.
