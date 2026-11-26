# Brampton + Mississauga: official planning open-data recovery

Date: 2026-11-19. Source-specific supplement, **not** replacement of working official HTML/CKAN/municipal collectors.

## Official source systems

**Brampton**: `Planning_Land_Use_Development/FeatureServer` published by the City:
- layer **9**: OPA/ZBA/Subdivision: `FILE_NUMBER`, `LOCATION`, `DATE_RECEIVED`, `APPLICATION_TITLE`, `PROPOSAL_DESCRIPTION`, `STATUS`, `APPLICANT_COMPANY`, `AGENT_COMPANY`.
- layer **10**: Pre Consultation.
- layer **11**: Site Plan Approval.
- Main source: https://services3.arcgis.com/rl7ACuZkiFsmDA2g/arcgis/rest/services/Planning_Land_Use_Development/FeatureServer
- Official catalogue datasets for pre-consultation and site-plan are labelled CC BY 4.0, subject to attribution and terms. The OPA/ZBA dataset's exact reuse status is left unverified.
- A prior Brampton GIS path was robots-denied. This alternative must satisfy **its own** robots/usage gate and will be recorded as blocked if not authorized. It is not a proxy bypass.

**Mississauga**: City Site Plan Applications layer:
- https://services6.arcgis.com/hM5ymMLbxIyWTjn2/ArcGIS/rest/services/Site_Plan_Applications/FeatureServer/0
- Exact `APP_FILE_NO`, `SITE_ADDRESS`, `APPLICATION_DATE`, `APPLICANT`, `DESCRIPTION`, stage, and `TOTAL_NON_RES_GFA`, `ICI_INDUST`, `ICI_OFFICE`, `ICI_RETAIL`.
- The dataset includes approved applications since 2016 as well as active cases. It is NOT entirely fresh.
- Catalogue: https://data.mississauga.ca/datasets/85536f145719436ebde8d31f36d11d83_0/about
- **Custom dataset licence is not commercially cleared**. Rows are collected as source research, and this added dataset's new rows are excluded from AI commercial candidate eligibility until approval. A public endpoint is not blanket permission to sell data.

## Automatic daily execution

`RUN_GTA_RADAR_TODAY.bat` invokes `gta_monday_full_run.py`, which now runs `gta_brampton_mississauga_open_data.run()` before the 28-city join and one shared-budget DeepSeek review.

All four layers have independent status. The source uses paginated, bounded first-party ArcGIS queries, `objectIdField` supplied by the publisher, HTTPS and redirect restrictions, and robots checks on the actual request. Failure of any source does not erase the other source's records. API errors and truncation are explicit.

BramPlanOnline is a separate Brampton source. Radar submits the City's public
planning search for the last 14 calendar days and reads up to five result
pages. It keeps permanent Pre Consultation, Site Plan, and OPA/ZBA file IDs
with exact City record links. Results include the displayed file date and
status. The date is for tracking and does not certify first publication.
BramPlanOnline results stay research-only while commercial reuse is unverified.

The GeoHub CSV download API served older cached files during validation.
Use the authorized local export to retain a larger planning baseline.

## ZIP audit outputs

- `GTA_RADAR_BR_MISS_OPEN_PLANNING_APPLICATIONS.csv`: exact file-ID rows, published company/agent, application stage, **separate** floor area metrics where present, date basis, and source permissions.
- `GTA_RADAR_BR_MISS_OPEN_PLANNING_STATUS.json`: per-layer request failures, real feature IDs, valid planning file counts, paging completeness, limits, rights status.
- `GTA_RADAR_COMBINED_28_CITY_PROJECT_MASTER.csv`: official supplemental files reconciled by municipality + normalized file ID without dropping existing files.
- `GTA_RADAR_COMBINED_28_CITY_COVERAGE.csv`: alternative source rows reflected while prior blocked-source warnings remain.

## Acceptance

1. GitHub offline tests prove parsing, deduplication and failure isolation — **not** municipal live access.
2. Operator must validate output status and compare original source records. Do not advertise new live Brampton/Mississauga coverage unless nonzero exact IDs were retrieved during that run.
3. File receipt dates are not first-publication dates; planner/agent contacts are not buyers; published site-plan applications are not open procurement contracts.
4. Record source-specific licence and source rights before customer/commercial resale, attribution and AI qualification.
