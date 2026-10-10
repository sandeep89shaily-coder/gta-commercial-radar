# Southern Ontario regional batch — technical readiness release

This release **does not change the existing architecture** (`main.py`, `radar.py`, collector handlers, source definitions and SQLite schema are retained).

## Implementation

- `regional_pipeline.py`: parallel live metadata, server-side filter/count, date-window and small-record-sample probes for all staged ArcGIS collectors.
- `CHECK_REGIONS_TOGETHER.bat`: double-click to inspect the batch, then opens a human-readable report.
- `SOUTHERN_ONTARIO_LIVE_AUDIT.csv` and `.html`: generated on the Windows machine with internet access.
- Source-specific failure does not stop checks for other municipalities.
- **No automatic source activation**: technical checks alone cannot establish commercial reuse permission or that live changes are being detected reliably.
- **No database migration or import**. Previous v0.6 remains the daily collector.

## Status

Existing 32 configured source definitions remain unchanged. Source configurations are not evidence of a successful live data import. Live acceptance requires running the batch audit on a connected desktop. No claim is made that additional staged collectors are production-ready.

## Run

Double-click `CHECK_REGIONS_TOGETHER.bat` and inspect the resulting HTML. This is the only action required to report readiness for all staged ArcGIS sources simultaneously. Do not run setup or adopt commands for this audit.
