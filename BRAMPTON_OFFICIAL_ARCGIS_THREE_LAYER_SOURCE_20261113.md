# Brampton official GIS planning application collection — November 13, 2026

## Public source independently verified

The [City of Brampton's official Planning Land Use Development FeatureServer](https://services3.arcgis.com/rl7ACuZkiFsmDA2g/ArcGIS/rest/services/Planning_Land_Use_Development/FeatureServer) is a City of Brampton-owned, publicly documented ArcGIS service, advertised as **updated daily**. It publishes individual planning-application features rather than merely an index webpage. The three layers used are:

| Layer | Official exact URL | Application stage |
|---|---|---|
| 9 | [OPA ZBA Subdivision](https://services3.arcgis.com/rl7ACuZkiFsmDA2g/ArcGIS/rest/services/Planning_Land_Use_Development/FeatureServer/9) | Official Plan Amendment / zoning amendment / subdivision |
| 10 | [Pre Consultation](https://services3.arcgis.com/rl7ACuZkiFsmDA2g/ArcGIS/rest/services/Planning_Land_Use_Development/FeatureServer/10) | Early feasibility/pre-consultation |
| 11 | [Site Plan Approval](https://services3.arcgis.com/rl7ACuZkiFsmDA2g/ArcGIS/rest/services/Planning_Land_Use_Development/FeatureServer/11) | Site-plan approval |

The original City data schema includes `FILE_NUMBER`, `LOCATION`, `DATE_RECEIVED`, `APPLICATION_TITLE`, `APPLICATION_TYPE`, `DESCRIPTION`, `PROPOSAL_DESCRIPTION`, `STATUS`, `CITY_PLANNER`, `AGENT_COMPANY` and `APPLICANT_COMPANY`. Its system OID is `POLY_ID`, which must **never** be presented as an application file number.

## Implemented first-party collector

`gta_brampton_official_gis_planning.py` now runs as part of `gta_council_integrated_manual.py` within the existing `RUN_GTA_RADAR_TODAY.bat` fresh manual collection. On each layer it:

1. Fetches source metadata and confirms exact City layer number, name and required official field schema, including stable `POLY_ID`
2. Requests the entire bounded ArcGIS `returnIdsOnly` ID list (up to 12,000 polygon IDs per layer) and verifies every original returned ID once through batches of at most 250 exact IDs
3. Rejects partial, duplicate, missing or unexpected GIS features *without creating a new baseline or overwriting that layer's previous history*
4. Records exact municipal `FILE_NUMBER`, planning stage, civic location, proposal text, status, applicant/agent-company source text and City's `DATE_RECEIVED` field
5. Keeps a file-number-keyed, layer-specific first-observed and source-content-hash ledger; a changed record is a **review-only update**, not proof of a new published project
6. Tracks the source edit timestamp separately from the file's date received and Radar's first observation

All API reads use exact publicly documented host/layer endpoints, public DNS and robots checks, no redirects, bounded source responses and limited batch counts. A city-level partial failure is visible per layer rather than folded into `7/7 stages passed`. The isolated reports and prior files are preserved in the existing `GTA_RADAR_RESULTS/COUNCIL_INTELLIGENCE_REVIEW/BRAMPTON_OFFICIAL_GIS_PLANNING` output directory and safe dated ZIP; **no original user `radar.sqlite` file is modified**.

## Evidence levels

- `DATE_RECEIVED` = City-reported application receipt date, **not first publication or offer to bid**.
- `first_observed_utc` = first local Radar evidence, not the project's inception or initial publication.
- `APPLICANT_COMPANY` and `AGENT_COMPANY` = City source fields, **not verified purchasing authority**.
- Keyword-only commercial classification = private review candidate, **not a sales-ready project**.
- Multiple geometry polygons for the same application are deduplicated by exact file number only when source facts agree; otherwise held for audit.
- The source is City of Brampton public open data, **not a guarantee of completeness or a comprehensive citywide project list**.

## Acceptance gate

All four cross-platform CI suites must pass. The next real owner-side Windows manual run should show three independently successful Brampton layers, official application IDs and suitable multi-region signal quality in `BRAMPTON_OFFICIAL_GIS_APPLICATIONS_REVIEW.csv`. Existing V6 legacy collectors may still have blocked source paths, which need *separate* repair. The new GIS collector is an additive source recovery and does not immediately promote records to top-ten or verified buyer lists. Follow with a 20-file original-source audit of company, site, status and publication vs receipt/observed dates.

DeepSeek spending remains at the user's existing limit; no new paid AI call, schedule, outreach or original database reset is introduced.
