# Mississauga city departments and source systems — Phase 1 inventory (2026-10-11)

This is a map of **public evidence channels**. No automated access to gated permit, property, bidding or ePlans accounts is presumed. Exact service schemas, completeness and commercial use terms must be confirmed at first desktop test.

| Department/function | Primary source | Relevant commercial signals | Collection state |
|---|---|---|---|
| Building Division | [Mississauga Building Permits](https://services6.arcgis.com/hM5ymMLbxIyWTjn2/ArcGIS/rest/services/Issued_Building_Permits/FeatureServer/0) | Issued permits, changes of use, commercial alterations, construction value | Existing main Radar enabled; non-residential filter may exclude other future uses, keep historical baseline |
| Development / City Planning | [Active development applications](https://www.mississauga.ca/services-and-programs/planning-and-development/development-applications/) | Site plans, rezoning, official plan amendments, subdivision | Two separate ArcGIS sources already configured but disabled; live test needed |
| Growth management / City Planning | [City planning data](https://www.mississauga.ca/our-organization/data-and-maps/city-planning-data/) | Project-level pipeline, approved vs proposed nonresidential floor area | Public data hub, separate from applications; investigate exact FeatureServer items |
| Purchasing / Finance | [City bid opportunities](https://www.mississauga.ca/services-and-programs/business/doing-business-with-the-city/bid-opportunities/) | Public solicitations and awards | Two eBidding portals; do not assume anonymous access to all documents |
| Procurement (legacy) | [bids&tenders](https://mississauga.bidsandtenders.ca/Module/Tenders/en/Home/BidsHomepage) | Public titles, closing dates, statuses, eventual award information | Transitioning during 2026; retain legacy event provenance |
| Procurement (new) | [Bonfire/Euna Procurement](https://mississauga.bonfirehub.ca/portal/?tab=openOpportunities) | New competition notices | City-announced migration, exact public interface to verify |
| Transportation / Works | [Current construction projects](https://www.mississauga.ca/projects-and-strategies/current-construction-projects/) | Roads, bridges, stormwater, sewer infrastructure | Public map and project lists; source-specific service verification needed |
| Council & committee services | [Council and Committees calendar](https://www.mississauga.ca/council/council-activities/council-and-committees-calendar/) | Decisions, budgets, planning hearings, procurement policy | Document portal; no validated machine-readable API yet |
| Property / zoning | [Planning and building online services](https://www.mississauga.ca/services-and-programs/building-and-renovating/planning-and-building-online-services/) | Property zoning, permit/inspection status | Some searches require owner/application IDs or payments; do not automate restricted access |
| Regulatory & licensing | [Open Data](https://data.mississauga.ca/) / business services | Business licensing categories and new activity | Catalogue search / feasibility research; bulk licence feed not confirmed |
| Public Health (regional) | Peel public disclosure | Food/personal services, pools, childcare | Shared regional feeds already configured in Radar; avoid double counting |

## Citywide discovery API

The Open Data portal documents an ArcGIS Hub Search API following OGC API — Records: `https://data.mississauga.ca/api/search/v1/collections`, with per-collection `/items` and server-provided pagination. This inventory workflow is independent of Toronto's CKAN API; they are not interchangeable.

Published dates require caution: Mississauga itself notes that some catalogue last-updated dates are incorrect. Treat observed **content/version changes** separately from publication timestamps and commercial events.

## Production safety

- Keep Phase 1 limited to Brampton, Toronto and Mississauga; Peel regional records are supporting evidence only.
- Do not enable disabled Mississauga site-plan/rezoning feeds or infer building inspection availability until official service identity and complete pagination succeed on desktop.
- Maintain source URL, publishing municipality, collection ID, item ID, retrieved UTC timestamp and raw record/version history where available.
- Do not sell baseline observations as new events, infer business closures from incomplete snapshots, or claim licensed access to confidential documents.
- Keep existing Radar SQLite databases intact; all new collectors are separate and additive.
