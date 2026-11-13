# Brampton GIS → saved Radar evidence reconciliation — November 13, 2026

## Problem addressed

PR #198 added a first-party, three-layer Brampton application source (OPA/ZBA/subdivision, pre-consultation and site-plan approvals), but the review-only GIS data did not appear in a cross-source shortlist audit against the existing private Radar investigation and source-master outputs. That meant additional records could be collected without demonstrating whether they supplied missing unique applications or simply duplicated old signals.

## Implemented conservative reconciliation

`gta_brampton_gis_radar_reconciliation.py` reads the existing manual-run official Brampton GIS source, the Brampton featured PDC cards and Radar's saved early-applications, master, private-investigation and private-top-ten CSVs.

- Requires the GIS collector's **current successful or partial-success source status**, matching per-layer completeness and every row's same-run `last_observed_utc`. Stale CSVs following blocked sources are refused. Every ID must have the correct exact City GIS layer URL.
- Matches **only an exact normalized municipal file number** (e.g. `OZS-2026-0038` equals `OZS 2026 0038`; `OZS-2026-00380` is a different file). No name/keyword/address-only fuzzy promotion.
- Distinguishes the number of unique official GIS application IDs already present in historical saved Radar evidence, saved private investigations and saved top ten from IDs missing from those outputs.
- The separate Brampton featured PDC source may cross-confirm an ID **only when its own current successful status and same-run observation are present**.
- Writes the **20 most recent City-received, commercial-keyword review cases**, with City planning stage, application number, site/proposal, applicant and agent text, file receipt date, local first-observed timestamp, exact saved-output matches, source provenance and explicit unresolved buyer/open-work flags.
- Exposes the per-source and case-count status in the existing seven-stage manual daily report and dated safe ZIP. No additional launcher or command is required.

## Review-only limitations

The saved private and master output CSVs can predate the new GIS collector. A match means **the same file ID occurs in a saved Radar output**, not that that output was independently verified as fresh today. City `DATE_RECEIVED` is the application receipt date, **not proof of first online publication or the earliest market intelligence**. City applicant and agent are source-text names, not verified contractor or procurement decision-makers.

This module makes no network calls, modifies no `radar.sqlite`, makes no paid DeepSeek calls and never inserts new leads into customer-facing top-ten lists without downstream source verification. It intentionally does not equate 20 review rows with 20 sale-ready buyer leads.

## Acceptance

Review the next owner-run dated ZIP for:
- `GTA_RADAR_RESULTS/COUNCIL_INTELLIGENCE_REVIEW/BRAMPTON_GIS_CROSS_SOURCE_REVIEW/BRAMPTON_GIS_20_FILE_CROSS_SOURCE_AUDIT.csv`
- `BRAMPTON_GIS_RECONCILIATION_STATUS.json`
- `COUNCIL_INTEGRATED_REVIEW_STATUS.json` and `MONDAY_FULL_RADAR_STATUS.json`

Confirm actual official-source Brampton GIS layer success, current rows, distinct file IDs, previously known IDs, historical overlaps, and commercially relevant proposals. Manually review 20 City originals for planning stage, first online posting, developer/GC/operator and actual supplier opportunity, without treating match counts as validated buyers.

No DeepSeek funding increase, schedule, outreach, original database reset, or source access-control bypass.
