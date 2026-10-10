# Southern Ontario free-source comprehensive inventory — v0.7 broad batch

This is a tracked feasibility inventory, NOT a claim every municipality offers an automated free licensed feed. All new feeds are disabled pending live doctor, baseline, date, and licence checks. No existing database is bundled or altered.

| Region | Candidate | Evidence/status | URL |
|---|---|---|---|
| Hamilton | development | Hamilton development applications | endpoint verified; schema and incremental field pending | https://services.arcgis.com/rYz782eMbySr2srL/arcgis/rest/services/Development_Applications/FeatureServer/2 |
| Waterloo | permits | City of Waterloo issued building permits | endpoint and schema verified; live poll pending | https://services.arcgis.com/ZpeBVw5o1kjit7LT/arcgis/rest/services/City_of_Waterloo_Building_Permits/FeatureServer/0 |
| Niagara | permits | St. Catharines building permits | endpoint and schema verified; live poll pending | https://services6.arcgis.com/Yx1h0qHJ9wIpQWuU/arcgis/rest/services/Building_Permits_Public/FeatureServer/0 |
| Hamilton | research | Hamilton business licences | research only—not an implemented collector |  |
| Hamilton | research | Hamilton building permits | research only—not an implemented collector |  |
| Halton | research | Oakville planning | research only—not an implemented collector |  |
| Halton | research | Burlington permits | research only—not an implemented collector |  |
| Halton | research | Milton permits | research only—not an implemented collector |  |
| Halton | research | Halton inspections | research only—not an implemented collector |  |
| Durham | research | Oshawa permits | research only—not an implemented collector |  |
| Durham | research | Whitby planning | research only—not an implemented collector |  |
| Durham | research | Ajax permits | research only—not an implemented collector |  |
| Durham | research | Pickering planning | research only—not an implemented collector |  |
| Durham | research | Durham public health | research only—not an implemented collector |  |
| York | research | Vaughan planning | research only—not an implemented collector |  |
| York | research | Markham ePLAN | research only—not an implemented collector |  |
| York | research | YorkSafe | research only—not an implemented collector |  |
| Waterloo | research | Kitchener planning | research only—not an implemented collector |  |
| Waterloo | research | Cambridge permits | research only—not an implemented collector |  |
| Waterloo | research | Waterloo Region health inspections | research only—not an implemented collector |  |
| Niagara | research | Niagara Falls permits | research only—not an implemented collector |  |
| Niagara | research | Welland planning | research only—not an implemented collector |  |
| Niagara | research | Niagara regional public health | research only—not an implemented collector |  |
| Durham | configured | Durham PLANit Consent Applications | OFFICIAL_ARCGIS_SCHEMA_VERIFIED; collector configured and disabled; live poll/licence pending | https://maps.durham.ca/arcgis/rest/services/PLANit/PLANit/MapServer/1 |
| Durham | configured | Durham Regional Official Plan Applications | OFFICIAL_ARCGIS_SCHEMA_VERIFIED; collector configured and disabled; live poll/licence pending | https://maps.durham.ca/arcgis/rest/services/PLANit/PLANit/MapServer/2 |
| Durham | configured | Durham Business Sites | OFFICIAL_ARCGIS_SCHEMA_VERIFIED; collector configured and disabled; live poll/licence pending | https://maps.durham.ca/arcgis/rest/services/Open_Data/Durham_OpenData/MapServer/11 |
| Durham | configured | Durham Capital Project Boundaries | OFFICIAL_ARCGIS_SCHEMA_VERIFIED; collector configured and disabled; live poll/licence pending | https://maps.durham.ca/arcgis/rest/services/CDEAP2/MapServer/3 |

## Additional verified findings

- Hamilton publishes a Building and Demolition Permits 2017 to Present dataset through Open Hamilton; specific live layer mapping not yet validated (https://data.urbandatacentre.ca/en/catalogue/open-hamilton-dc7e86-building-and-demolition-permits-2017-to-present).
- Hamilton publishes open trade-licence data, but exact layer mapping must be checked (https://www.hamilton.ca/build-invest-grow/starting-small-business/business-licences/trade-licence).
- Halton public-health portal provides real-time inspection disclosures but no verified bulk/API access (https://www.halton.ca/for-residents/public-health/public-health-inspections-and-investigations).
- Niagara health-inspection dataset has an open licence and a published CSV but the publisher explicitly says data is currently unavailable during reporting-system changes (https://niagaraopendata.ca/dataset/niagara-health-inspection-results).
- Markham posts biweekly planning PDF dashboards: official but not a prevalidated machine-readable feed (https://www.markham.ca/economic-development-business/planning-development-services/current-planning-applications-and-agendas).
- Kitchener provides a GeoHub with CSV/REST/GeoJSON options, but exact permit/planning layers remain unverified (https://www.kitchener.ca/council-and-city-administration/data-and-maps/open-data/).
- Cambridge publishes current applications as webpages and supporting documents, not yet a validated bulk feed (https://www.cambridge.ca/business-building-development/building-planning/current-development-applications/).

**Why not enable all?** A named municipal portal is not equivalent to a working free commercial-use collector. Unverifiable URLs or guessed schemas could silently produce zero data or incorrect leads.

## Newly configured in expanded stage

- **Hamilton Building and Demolition Permits** — public official ArcGIS source; configured and disabled, **not live-imported**, licence and latest-record date must be validated. https://services.arcgis.com/rYz782eMbySr2srL/arcgis/rest/services/Building_and_Demolition_Permits_2017_to_Present/FeatureServer/6
- **Kitchener Active Planning Applications** — public official ArcGIS source; configured and disabled, **not live-imported**, licence and latest-record date must be validated. https://services1.arcgis.com/qAo1OsXi67t7XgmS/arcgis/rest/services/Planning_Applications_Active/FeatureServer/0

Hamilton source advertises issuance since 2017 but its ArcGIS layer metadata reported an old last-edit timestamp. Do not infer it is current until tested. Kitchener service advertises hourly refresh, but no safe date increment field is assumed.
