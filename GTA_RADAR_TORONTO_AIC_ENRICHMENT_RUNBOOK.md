# Toronto AIC Application Metadata & Documents — Daily Collector

**November 19, 2026.** The existing Toronto Open Data/CKAN development-applications feed remains the authoritative primary application collector and is not replaced by this project.

## Official additional source

The City of Toronto publishes the *IBMS Application Information Centre* as [ArcGIS FeatureServer layer 60](https://gis.toronto.ca/arcgis/rest/services/cot_geospatial11/FeatureServer/60). This official layer includes:

- `APPLICATION_NUMBER`, `FULL_ADDRESS`, `FOLDERDESCRIPTION`, `APPLICATION_TYPE`
- `STATUS_DESC`, `LATEST_MILESTONE`, `LATEST_MILESTONE_DATE`
- `SUBMIT_DATE`, `COMMUNITYMEETINGDATE`, `HEARING_DATE`
- `ASSIGNEDPLANNER`, `PLANNEREMAIL`, `OPENRELATEDFOLDERCOUNT`
- `LAST_MODIFIED_DATE`, `AIC_URL`

**Important:** The ArcGIS layer declares **Has Attachments: false**. The application page *may* contain publicly available supporting planning documents, but they are not accessible as standard ArcGIS attachments. Official AIC guide: https://www.toronto.ca/city-government/planning-development/application-information-centre/application-information-centre-user-guide/

## What actually runs

After the normal 24-city combined master is built, the manual daily launcher calls `gta_toronto_aic_enrichment.run()` against the **first 15 exact Toronto file identifiers** in that master. It queries only the official layer (matching both original and space-stripped versions of the same file number), and rejects ambiguous or unmatched results.

An independently permitted AIC application page is inspected for **explicit same-owner** PDF/Office document hyperlinks. If the HTML is JavaScript-only, robots denied, redirected or missing document links, the report clearly indicates **no verified downloadable link**. No hidden API, protected viewer or URL pattern is inferred.

No citywide AIC crawling, bulk PDF downloading, external model calls, billing, or commercial outreach is performed.

## Daily outputs in GTA_RADAR_RESULTS

1. `GTA_RADAR_TORONTO_AIC_ENRICHMENT.csv` — matched metadata, planner (explicitly NOT purchasing contact), application status, separate milestone/submission/update dates, exact AIC link
2. `GTA_RADAR_TORONTO_AIC_DOCUMENT_INDEX.csv` — links explicitly discovered from permitted official AIC HTML. These are **links only**, never claimed downloaded or validated.
3. `GTA_RADAR_TORONTO_AIC_ENRICHMENT_STATUS.json` — counts of source applications attempted, exact matches, documents indexed, policy blocks, failures, zero verified buyers/procurement opportunities

The standard ZIP archiver automatically includes `GTA_RADAR_*.csv/json` root files.

## Acceptance criteria and limitations

- Metadata success requires `exact_aic_matches > 0` on a **real Windows manual run**.
- Documents success requires `official_document_links_indexed_not_downloaded > 0`, independently retrieved from a permitted HTML page. The ArcGIS layer itself contains no document attachments.
- Before expanding past 15 records, confirm publisher policy for the actual AIC layer and any commercial reuse of the documents; publicly accessible materials are not automatically licensed for republication.
- Dates are never called original first disclosure; municipal planners are never asserted to be purchasers; published documents are not open supplier contracts.
- Source restrictions remain restrictions. To recover documents blocked by website policy, pursue an explicit authorized download feed or published meeting/report documents, not a bypass.
