# Alternative-feed root-cause recovery — November 19, 2026

## What changed
The previous baseline had many blocked *municipal* collectors. Rather than repeatedly retry restricted site routes, this change adds independent **publisher-listed official open-data** source lanes.

| Recovery target | Official replacement | Actual ID field | Coverage caveat |
| --- | --- | --- | --- |
| Vaughan | York Region *Active Development Application Boundaries* layer 0 | REG_FILE_NUM | Only applications reviewed by York Region |
| Markham | Same York Region layer | REG_FILE_NUM | Not all local municipal applications |
| Richmond Hill | Same York Region layer | REG_FILE_NUM | Not all local municipal applications |
| Hamilton | Hamilton Open Data, Development Applications layer 2 | FILE_NUM | Submitted in past five years; does not prove active projects |
| Kitchener | Existing merged PR #260 city open-data layer 0 | APPLICATION_NO | Requires actual live run acceptance |
| Caledon | Existing merged PR #260 current application index | RZ / SPA / POPA reference | Research-only until publisher-reuse check |

## Primary public source evidence
- York Region publishes this dataset as an official public open-data feature layer: https://insights-york.opendata.arcgis.com/datasets/york::active-development-application-boundaries and https://www.york.ca/newsroom/campaigns-projects/track-status-development-applications
- York Region open-data licence: https://insights-york.opendata.arcgis.com/documents/york-region-open-data-licence/explore
- Actual York source: https://services1.arcgis.com/GzvOwaQBbX7KLiuG/ArcGIS/rest/services/Hosted_Active_Development_Application/FeatureServer/0
- York Region website map terms differ from the special Open Data Licence. This implementation uses only the published open-data dataset, conditional on robots permitting the source query. Terms for non-open-data mapping routes remain restrictive.
- Hamilton official open dataset: https://data-SpatialSolutions.opendata.arcgis.com/datasets/SpatialSolutions::development-applications-1
- Hamilton REST feature layer 2: https://services.arcgis.com/rYz782eMbySr2srL/arcgis/rest/services/Development_Applications/FeatureServer/2
- Hamilton Open Data Licence explicitly permits commercial data reuse, subject to its conditions: https://www.hamilton.ca/city-council/data-maps/open-data/open-data-licence-terms-and-conditions

## Live-stage behaviour
The normal `RUN_GTA_RADAR_TODAY.bat` invokes the collector from `gta_monday_full_run.py`. If a host's robots policy disallows querying, or the official source returns HTTP/TLS/schema errors, the lane is marked **BLOCKED_OR_FAILED** and no prior rows are relabelled as collected today. Paged ArcGIS requests have a 5-page (1,000 row) cap and require stable ObjectIDs. The original 24 cities remain present. New validated rows are independently reconciled into the 28-city research master, queue and DeepSeek input.

The output ZIP contains:
- `GTA_RADAR_ADDITIONAL_OFFICIAL_OPEN_DATA.csv`
- `GTA_RADAR_ADDITIONAL_OFFICIAL_OPEN_DATA_STATUS.json`
- `GTA_RADAR_COMBINED_28_CITY_PROJECT_MASTER.csv`

## Outstanding caveats
- The regional publisher covers a **subset** of Vaughan, Markham, Richmond Hill planning applications. Neither 28-city configuration nor four-city fallback means verified full coverage.
- An application date, regional receipt date or a Hamilton FILE_YEAR does **not** establish original public notice, current availability or supplier opportunity.
- No named buyer, open contract or paid customer ready lead is asserted by this collector.
- Complete operational acceptance requires actual machine live output and comparison against official publisher records.
- Brampton, Mississauga, Toronto, Brantford and other municipalities still need source-specific interventions and tested permissions; do not count these as repaired.
