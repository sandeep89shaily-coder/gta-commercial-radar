# Toronto municipal source inventory — initial verified research (2026-10-11)

Scope: Toronto only in this inventory. Phase 1 cities: Toronto, Brampton, Mississauga.
This is source discovery, NOT a claim of production ingestion, complete departmental coverage, or permission to scrape gated systems.

## Foundational systems
- Toronto Open Data: https://open.toronto.ca/ ; catalogue has over 500 datasets. Public CKAN API metadata and resource discovery; locate resource IDs dynamically with package_search/package_show. Categorize resources by publishing division, geography, formats, licence and refresh cadence.
- Toronto Council TMMIS: https://secure.toronto.ca/council/ ; agendas, meeting items, committee recommendations, decisions, linked reports and PDFs. Meeting schedule dataset: https://open.toronto.ca/dataset/3bfab808-105b-45ab-8d92-cf1916594653/
- Development AIC: https://www.toronto.ca/city-government/planning-development/application-information-centre/ ; active applications for Community Planning, Committee of Adjustment and Toronto Local Appeal Body, application status/milestones, public supporting documents. Daily refreshed portal; machine interface not yet verified; avoid claiming full historical coverage.
- Toronto Bids / SAP Ariba: https://www.toronto.ca/business-economy/doing-business-with-the-city/understanding-the-procurement-process/ ; official solicitation system. Public bid notices and procurement awards need independent endpoint and access assessment; supplier account needed for bidding and some solicitation materials.

## Department-to-feed candidates (discovery only unless separately validated)
| Priority | Publisher / division | Feed family | Official reference | Interface status |
|---|---|---|---|---|
| P0 | Toronto Building | Active building permits | https://open.toronto.ca/dataset/building-permits-active-permits/ | CKAN dataset; verify current resource ID, PK, daily refresh |
| P0 | Toronto Building | Cleared building permits | https://open.toronto.ca/dataset/building-permits-cleared-permits/ | CKAN dataset; compare active vs cleared identifiers |
| P0 | Development Review / City Planning | Application-level OPA, rezoning, site plan, subdivision, C of A | https://www.toronto.ca/city-government/planning-development/application-information-centre/ | Public portal, automation interface TBD |
| P0 | City Planning | Development Pipeline / five-year reconciled project analytics | https://www.toronto.ca/city-government/data-research-maps/research-reports/planning-development/development-pipeline/ | Dashboard, reports and open data downloads |
| P0 | Municipal Licensing & Standards | Business licences and permits | https://open.toronto.ca/ | CKAN dataset identified in city quarterly update; resolve exact package ID |
| P0 | Purchasing & Finance | Solicitations, tenders, awards and suppliers | https://www.toronto.ca/business-economy/doing-business-with-the-city/understanding-the-procurement-process/ | Toronto Bids / Ariba; structured public access TBD |
| P1 | City Clerk | Council agenda items, decisions, committee reports | https://secure.toronto.ca/council/ | TMMIS pages and linked documents |
| P1 | City Clerk | Council meeting schedules | https://open.toronto.ca/dataset/3bfab808-105b-45ab-8d92-cf1916594653/ | Published open dataset |
| P1 | Toronto Public Health | DineSafe inspection histories | https://open.toronto.ca/dataset/dinesafe/ | CKAN; inspect event IDs and repeat inspections |
| P1 | Transportation Services | Restrictions, closures, roadworks, right-of-way permits | https://open.toronto.ca/ | Inventory catalogue datasets separately; street occupation permit dataset request listed as pending in 2026 |
| P1 | Technology Services | Municipal address points | https://open.toronto.ca/ | CKAN; geocoding/address join evidence |
| P1 | City Planning / Geospatial | Zoning and parcel or land-use layers | https://open.toronto.ca/ | CKAN/GIS; assess zoning version timeline |
| P1 | Housing / CreateTO / Toronto Community Housing | Redevelopment, construction, capital procurements | https://open.toronto.ca/ | Multiple corporate systems; assess individually |
| P1 | TTC / Transportation | Capital project and procurement announcements | https://open.toronto.ca/ | Distinguish agency from City-wide records |
| P2 | Toronto Water | Utility capital and infrastructure projects | https://www.toronto.ca/ | Source discovery needed |
| P2 | Solid Waste Management Services | Facilities, waste contracts, capital programs | https://www.toronto.ca/ | Source discovery needed |
| P2 | Economic Development & Culture | Employment areas and business development | https://www.toronto.ca/ | Source discovery needed |
| P2 | Revenue Services / Finance | Budget, capital allocations, taxes and published financials | https://www.toronto.ca/ | Source discovery and licence assessment needed |
| P2 | Parks, Forestry & Recreation | Facility investments and tree permits | https://open.toronto.ca/ | Source discovery; tree removal/injury open data request unresolved in 2026 |
| P2 | Toronto Fire Services | Public incident and regulatory outputs | https://open.toronto.ca/ | Assess publicness and aggregation/privacy |

## Collector acceptance conditions
For each verified candidate, store dataset/package and resource IDs, source URL, licence, publisher, update cadence, initial/last observed dates, key fields, data format, incremental change capability, rate limitations, completeness, and exact record evidence URLs.
Differentiate baseline/first-seen observations from a genuine official event; never infer deletions from a partial read.
Use full snapshots where incremental access is absent; fingerprint resources and maintain history. Preserve records in the existing desktop DB; no destructive migrations.
Do not claim all procurement documents are freely retrievable; registration may be necessary.
Do not conflate departmental datasets with their agency's public website, or infer that a portal implies a bulk API.

## Initial cross-check of existing code
The repository already contains Toronto CKAN/permits/licences/DineSafe and other feeds (per prior desktop runs). The next implementation must compare this inventory to live configured code/DB manifests before duplicating collectors. This research file does not change runtime code.

## Primary references
https://open.toronto.ca/
https://open.toronto.ca/docs/staff-guidance/introduction-to-open-data/
https://open.toronto.ca/quarterly-update-q3-2026/
https://www.toronto.ca/city-government/planning-development/application-information-centre/
https://www.toronto.ca/city-government/planning-development/application-information-centre/application-information-centre-user-guide/
https://www.toronto.ca/city-government/data-research-maps/research-reports/planning-development/development-pipeline/
https://www.toronto.ca/business-economy/doing-business-with-the-city/understanding-the-procurement-process/
https://www.toronto.ca/city-government/council/council-committee-meetings/
