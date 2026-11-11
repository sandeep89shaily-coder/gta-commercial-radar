# GTA Radar — Priority 3 + 4 evidence-gate checkpoint (2026-11-10)

**Scope:** preserve the 16-city manual Radar runner, finish source-integrity work for the **Burlington/Vaughan/Kitchener** repair lane, and keep **industrial equipment** and **commercial activation** as isolated manual pilots. The code changes in this checkpoint prevent unsupported source-evidence promotion; they do **not** establish new live site access, production geographic coverage, buyers or open contracts.

## Priority 3: existing three-city collector reliability

**Burlington:** The canonical official development-project index was repaired earlier on main, but its post-fix Windows run has not been checked. A strict new identity gate in `gta_five_city_application_recovery.py` now rejects *every* conflicting candidate when two official pages share an application ID but differ in source page, address, scope or status. The prior first-seen ledger stays untouched for held IDs; no false FIRST_OBSERVED / RECORD_CHANGED event or recovered-file count can be emitted for such conflicts. The status exposes `identity_conflicts_held_count`, `identity_conflicts_held_ids`, and city-level `identity_conflicts_held`, alongside separate link-fetch failures.

**Vaughan:** The latest user Windows results returned HTTP 403 on the official source. No scraper retry, browser impersonation or anti-bot workaround is authorized. Use the already implemented, unsent official-access request packet and only permitted City/Regional public export evidence. A York Region file ID is regional context, not proof the exact Vaughan PLANit project was recovered.

**Kitchener:** The prior official GeoHub automated query returned a robots-policy denial. Continue the already implemented authorized CSV import and original-ID/site validation, preserving provisional applicant/owner roles. Do not classify `CREATE_DATE` or `UPDATE_DATE` as the date an application first became public.

**Live acceptance, still required:** two separate permission-compliant Windows collections; archive each output before the next run overwrites daily CSVs. Compare exact IDs, current official post links, source failure/robots diagnostics, accepted vs held identities, commercial relevance and source/Radar dates. A successful one-time first baseline must not be reported as newly published projects. No citywide completeness or increased advertised coverage is approved yet.

## Priority 4a: industrial equipment evidence pilot

Use existing `RUN_INDUSTRIAL_EQUIPMENT_PILOT.bat` (bounded at 10 distinct unreviewed or source-changed official ERO notices, robots check first). The third historical user ZIP demonstrated 5/5 successful official notice parsing and 2 equipment-change findings; it did **not** demonstrate open purchases or buyers.

A new evidence rule gives a current, exact official notice payload precedence over an older user-provided excerpt with the same ERO number. If its official recheck fails or the ERO card changed without a successfully accepted refreshed payload, a stale manual excerpt cannot silently regenerate an apparently fresh equipment signal. Existing evidence remains in the isolated CSV as `SOURCE_CHANGED_OR_RECHECK_FAILED_HOLD`, with procurement `UNKNOWN` and buyer `NO`. The status now exposes `unverified_manual_excerpt_ids_held_on_official_recheck`.

**Live acceptance:** continue the persistent cursor, preserve previous output folder, manually cross-check original ERO site, stage, changes and prior notice history, and measure distinct supplier-relevant signals. Do not claim an open supplier package, purchasing authority or sale-ready lead from a notice.

## Priority 4b: commercial opening / facility activation pilot

Use existing `RUN_COMMERCIAL_ACTIVATION_PILOT.bat`, offline, with the user's current local `radar.sqlite` read-only. No new collector, API, AI spend or schedule is enabled.

An activation source record may provide an inline `Suite 101` address plus a separate `UNIT=202`. The pilot now rejects such contradictory site evidence as `MISSING_PHYSICAL_ADDRESS` rather than removing the inline suite and accepting a false cross-source same-site link. A consistent inline and structured suite is still eligible for *research-only* source activity.

**Live acceptance:** audit at least 20 individual original records with dates, stage, exact site/unit, company/tenant roles, exclusion counts and false positives; then 10 human-reviewed source-backed dossiers. Licence issue, construction permit, inspection, occupancy and actual business opening are distinct milestones. No opening is confirmed without independent evidence.

## Manual handoff, no automatic outreach

On the owner's Windows desktop use the latest tested main branch and run in this order:

1. `RUN_GTA_RADAR_DISCOVERY.bat` — normal manual collection. Check `GTA_RADAR_FIVE_CITY_RECOVERY_STATUS.json`, `GTA_RADAR_THREE_CITY_EARLY_PLANNING_GAPS.json`, `GTA_RADAR_OFFICIAL_CSV_IMPORT_STATUS.json`, and municipality source audit files. Preserve a dated ZIP for the next two-run comparison.
2. `RUN_INDUSTRIAL_EQUIPMENT_PILOT.bat` — bounded opt-in ERO review; keep the existing `INDUSTRIAL_PILOT` cursor and reports. Inspect `GTA_RADAR_INDUSTRIAL_EQUIPMENT_STATUS.json` and review CSV.
3. `RUN_COMMERCIAL_ACTIVATION_PILOT.bat` — local offline read-only source snapshots. Inspect `GTA_RADAR_COMMERCIAL_ACTIVATION_STATUS.json` and review CSV.

The user's original SQLite database, paid AI key, source exports and historical human annotations should not be replaced by test fixtures. Upload only the needed reports (and any allowable official evidence) for manual review. Preserve the shared US$0.25/day AI ceiling and owner-controlled daily operation.

**Release conditions:** passing Windows/Linux CI for these fixes, then separately actual authorized live source samples, original evidence audit, unverified/held source reconciliation and actual market-value verification. None of these three lanes is promoted to automatic outreach or a verified paying lead.
