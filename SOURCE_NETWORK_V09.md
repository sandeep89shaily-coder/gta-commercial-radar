# GTA Commercial Radar v0.9 — Source Network Audit (first milestone)

This is an incremental addition on top of the **complete v0.8 application**, not a claim to have 50 live collectors. All existing Radar and business-discovery functionality is preserved. Original data is **not included**; keep your working v0.8/v0.7 directory and databases.

## What is implemented
- A consolidated source registry from the existing municipal configurations, business-discovery sources and two prior research queues. Duplicate source names are collapsed.
- Explicit distinctions among configured, enabled, researched, endpoint reachable, and live imported. No untested feed gets a working status.
- One-click source registry creation and limited metadata probe, designed to avoid bulk downloads.
- Ontario Business Registry remains manual only.

## Windows usage
1. Extract this package alongside your current project. **Do not replace or delete your existing data folders.**
2. Double-click `AUDIT_SOURCE_NETWORK.bat`; view `data/source_network.csv`.
3. Optionally double-click `PROBE_10_SOURCE_ENDPOINTS.bat` to test up to ten public endpoint metadata URLs. An HTTP response is NOT a collector live-import test.
4. For actual business records run `START_BUSINESS_DISCOVERY.bat` only after verifying the existing v0.7 database backup setup; it remains the v0.8 program.

## Limits
This milestone does not add 50 live collectors or 100 externally verified sources. Existing candidate lists contain unverified hypotheses, and duplicate data sources may overlap. New source endpoints must be checked individually for fields, freshness, licensing, and idempotent collection before enabling. Source counts are not customer leads.
