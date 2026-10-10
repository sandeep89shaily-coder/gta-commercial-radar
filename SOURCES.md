# Source evidence — v0.5

Research date: 2026-10-08.

## v0.5 verified interfaces

AGCO's current page at https://www.agco.ca/en/cannabis/status-current-cannabis-retail-store-applications embeds a literal `csvUrl` for https://www.agco.ca/sites/default/files/opendata/AGCOWebSiteCRSANewProcessMapData.csv. The Download CSV control generates a browser blob; it is not a direct anchor. The live export has 2,658 Ontario rows, including 869 exact-municipality GTA rows at verification. Its Last-Modified was 2026-10-08 11:25:17 GMT. These counts are observations, not configured constants.

Peel's official health page, https://peelregion.ca/health/inspections-monitoring/health-inspections, links to https://rmop.hedgerowsoftware.com/Portal/. The public non-binding accuracy disclaimer posts `AcceptDisclaimerButton=Accept`. Each category has a server-rendered table at `/Portal/<ProgramArea>/Table`, with `SortBy=MostRecentlyInspected` and `pageNumber` pagination. The first pages were verified for Food, PersonalServicesSettings, ChildCare, PoolsHotTubsSplashPads, TanningBeds, RecreationalCamps and SmallDrinkingWaterSystem. Food and personal services expose image-labelled inspection results. The other directory tables omit that result column. Facility detail links expose durable facility UUIDs.

Daily Peel collection uses inspection-date ordering and a seven-day overlap. Full reconciliation is required to find undated facilities, older edits and directory removals. No directory result proves the date a business opened or closed. Full historical report/violation scraping is outside v0.5.

Source configurations retain official evidence and licence notes. Other source notes below are inherited from the earlier releases.

## Ready machine-readable sources

### Brampton Building Permits
Official ArcGIS Feature Layer:
https://maps1.brampton.ca/arcgis/rest/services/BuildingPermit/Building_Permits/FeatureServer/0

The service identifies itself as Building Permits for addresses within Brampton and says it is updated using a live service. It supports JSON/GeoJSON/PBF, advanced queries, ordering, and pagination.

### Mississauga Issued Building Permits
Official ArcGIS Feature Layer:
https://services6.arcgis.com/hM5ymMLbxIyWTjn2/arcgis/rest/services/Issued_Building_Permits/FeatureServer/0

Fields include BP number, status, address/unit, description, scope, file/building type, estimated construction value, application date, issue date, completion date, and coordinates.

### Toronto Open Data CKAN
API base:
https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action

v0.1 resolves resources by dataset title instead of freezing resource URLs, which lets Toronto replace a CSV/resource while the collector continues to follow the package metadata.

Toronto sources configured:
- Building Permits - Active Permits
- Municipal Licensing and Standards - Business Licences and Permits
- DineSafe
- Building Permits - Cleared Permits (backfill only)

Toronto's Business Licences dataset is refreshed daily and includes licence/permit category, licence number, operating name, issue date, client name, business address and applicable phone information.

Toronto separately publishes cleared building permits since 2017 and a 2000-2016 archive. The latter is not part of default v0.1 operation because it is historical backfill, not daily feed generation.

## Provincial registries wired

### Licensed child care facilities in Ontario
https://data.ontario.ca/dataset/licensed-child-care-facilities-in-ontario

Monthly bulk data; includes historical facilities active since 2014. Fields include licensee, facility/agency name, licence number, original issue date, status and address. Ontario also notes that its currently-active facility search is updated daily.

### Private school contact information
https://data.ontario.ca/dataset/private-school-contact-information

Monthly; school name/number, principal, address, phone, email, website, level/program information. Open Government Licence - Ontario.

### Integrated Community Health Services Centres
https://data.ontario.ca/dataset/integrated-community-health-services-centres-ichsc-locations

Monthly; address/contact information, OHIP-insured services and latest quality-assurance inspection information. Open Government Licence - Ontario.

## Confirmed public sources not yet wired

These are intentionally in the audit queue instead of pretending they are production-ready:

- Markham: MappiT/ePLAN and bi-weekly circulated planning-application dashboards.
- Richmond Hill: active development application map and permit portal.
- Burlington: Navigate Burlington can search issued building permits and active site plans.
- Oakville: open-data program plus monthly building-permit reports.
- Milton: public property permit search and open-data hub.
- Pickering: public permit portal plus a public ArcGIS OpenData service.
- Ajax: public eApply property/permit search.
- Oshawa: public ArcGIS OpenData service; current service inventory does not yet expose the building-permit dataset we need.
- YorkSafe, Check&GO Durham, and Halton public-health disclosure: collectors still need exact technical endpoint validation. Peel Health is wired in v0.5.
- Environmental Registry of Ontario: wired in v0.4 and retained in v0.5.
- AGCO liquor: remains queued. Cannabis is repaired in v0.5 using the verified public CSV widget.

The rule for this project is: a source does not become an enabled collector just because a webpage exists. It must have a reproducible retrieval method and clear enough terms for the intended use.


## Exact-source resolution

Ready CKAN feeds use stable package slugs/IDs. Toronto DineSafe is pinned to package
`b6b4f3fb-2e2c-47e7-931d-b87d22806948` and CSV resource
`af0f5b8a-4b73-4a50-8781-65e949792b40`. Fuzzy CKAN discovery is reserved for research-stage feeds.


### v0.1.4 collection policy
For ArcGIS permit sources, source-native use/type fields are preferred for server-side filtering. Zoning is enrichment, not the sole commercial gate. Brampton uses Building Code occupancy/use cues; Mississauga excludes explicit `RESIDENTIAL` via `FILE_TYPE` while retaining `UNKNOWN`.
