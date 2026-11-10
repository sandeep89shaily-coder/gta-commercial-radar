# GTA Radar — Authorized application identity reconciliation (2026-11-10)

Owner-approved follow-up to Burlington PR #166 and Vaughan/Kitchener PR #167.

## Problem

The authorized official CSV importer retains municipal application IDs and
unverified applicant, property-owner, and planning reviewer names. The manual
facility graph already combines municipal and pilot signals on civic *sites*.
It would be unsafe to infer a buyer or same development from shared addresses
or company name similarity. There was no bounded comparison of the authorized
role rows against independent municipal application file identities.

## New manual-only research overlay

Run the normal **manual** `RUN_FACILITY_EVIDENCE_REVIEW.bat` using the existing
`GTA_RADAR_RESULTS` folder. Its offline orchestration now additionally calls
`gta_authorized_application_identity_join.py`, which:

- Reads existing `GTA_RADAR_OFFICIAL_CSV_IMPORT_APPLICATIONS.csv` (assisted,
  **not independently authenticated** publisher export).
- Reads whichever previously collected comparison snapshots are available:
  `GTA_RADAR_FIVE_CITY_OFFICIAL_APPLICATIONS.csv`,
  `GTA_RADAR_ADDITIONAL_CITY_GIS_APPLICATIONS.csv`,
  `GTA_RADAR_EARLY_APPLICATION_CANDIDATES.csv`, and
  `GTA_RADAR_COLLECTION_MASTER.csv` (planning applications only).
- Considers **only Vaughan and Kitchener**, conservatively matching exact
  municipality, full application number with case/spacing normalization only,
  and normalized civic address. Different cities, numbers, missing sites,
  differently numbered buildings, conflicts across city feeds, and different
  or unspecified suites are not accepted as exact-site matches.
- Exports separately into `FACILITY_DOSSIER_PILOT`:
  `GTA_RADAR_OFFICIAL_APPLICATION_EXACT_SITE_ROLE_REVIEW.csv`,
  `GTA_RADAR_OFFICIAL_APPLICATION_IDENTITY_HOLDS.csv`, and
  `GTA_RADAR_OFFICIAL_APPLICATION_IDENTITY_STATUS.json`.
- Each candidate is a **review-only potential link**, not an automatic project
  merge. Its organization roles, purchaser, sourcing authority, award status,
  procurement availability, posting date and public contact are all UNVERIFIED.
- Missing export produces a clear missing-source status and no fabricated rows.
  Corrupt columns are rejected rather than counted as zero. Counts and hold
  reasons are retained for an auditable 20-record sample.

## Evidence and boundaries

An application filing date or GIS create/update date is **not** an original
public posting date. A planning reviewer is **not** an industrial buyer.
Matching one site and file number does not independently authenticate either
export: project-specific primary records must be opened and checked by a
human before any use in a customer-facing report.

This change makes no new network requests, spends no AI budget, does not
alter `radar.sqlite` or `GTA_RADAR_RESULTS` source files, and does not change
the production daily runner or schedule.

## Acceptance tests / live handoff

1. Cross-platform GitHub tests show successful exact ID + civic site matches,
   and rejection of city, application number, address and suite conflicts.
2. Missing, invalid and ambiguous source evidence produces a hold rather
   than a verified link. Output CSVs sanitize spreadsheet formula prefixes.
3. Run the manual facility evidence review against a real Windows ZIP or
   local original results; inspect at least 20 applicant/owner/reviewer
   comparisons where source data is available, including rejections.
4. Check source URLs and documents for every shortlisted result. Reconcile
   owner/applicant/agent/tenant versus buyer separately, without inferred
   procurement or company contact claims.
5. Promote a verified candidate only after independent original-source
   confirmation. The commercial gate remains 10 defensible actionable
   dossiers and two paying pilot customers.

Geographic expansion (Pickering, Ajax, Niagara Falls, Barrie) remains
controlled pilot work. Do not imply a 20-city operational system based on
four additional registered indexes.
