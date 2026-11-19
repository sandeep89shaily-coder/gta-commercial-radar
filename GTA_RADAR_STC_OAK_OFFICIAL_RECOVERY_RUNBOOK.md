# St. Catharines & Oakville collector recovery — November 19, 2026

## St. Catharines: licensed public permit feed instead of restricted export
The Niagara Open Data catalogue lists [Building Permits Public](https://niagaraopendata.ca/dataset/building-permits-public), maintained by the City of St. Catharines, **updated nightly**, licensed **Open Government License 2.0 (Corporation of the City of St. Catharines)**. It links both public ArcGIS GeoService and CSV/GeoJSON downloads.
Published feature layer: https://services6.arcgis.com/Yx1h0qHJ9wIpQWuU/arcgis/rest/services/Building_Permits_Public/FeatureServer/0

Layer 0 is **Building Permits (2010-Present)**, so this is permit HISTORY, not a stream of all active development applications or necessarily open work. The official fields include `OBJECTID0`, `FOLDERYEAR`, `FOLDERSEQUENCE`, `FOLDERDESC`, `FOLDERDESCRIPTION`, `PROPERTYNAME`, `INDATE`, `ISSUEDATE`, `STATUSDESC`. Construct a source-backed composite folder identifier only when its components exist; DO NOT treat `OBJECTID0` as a business permit number. Source dates are not publication dates.

The City's official [public notices](https://www.stcatharines.ca/news?category=Public+Notices) are a second, more leading source; note that individual application notices often contain proposals and site addresses. Existing municipal notice collection remains and must not be replaced by historical permits.

## Oakville: secure SSL trust-store diagnostic + distinct official alternative pages
The official [Agendas & Meetings](https://www.oakville.ca/town-hall/mayor-council-administration/agendas-meetings/) page links [pub-oakville.escribemeetings.com](https://pub-oakville.escribemeetings.com/?meetingviewid=2) and documents that agendas/minutes are available 2010-present. When independently accessed, that eSCRIBE entry can return HTTP 403. A 403 **cannot** be corrected by ignoring TLS validation, changing user agents, proxies or guessing a private API.

The recovery layer first loads the official Town-hosted agenda page and [Town News & Notices](https://www.oakville.ca/town-hall/news-notices/). An SSL certificate-chain error on the host may be caused by the system's stale trust chain. It retries **only** with `certifi`'s validated CA trust store if available, with `CERT_REQUIRED` and hostname checking still ON. If verification still fails or the portal returns HTTP 403, the source is flagged blocked and all existing Oakville planning records remain untouched. The found official links are labelled **not verified agendas**; only verified meeting-page documents can count as a successful meeting recovery in future releases.

## Daily launcher outputs
- `GTA_RADAR_STC_OAK_OFFICIAL_RECORDS.csv`: newly fetched St. Catharines official permit records, explicitly labelled historical/issued; separate from planning applications
- `GTA_RADAR_OAKVILLE_CIVIC_LINKS.csv`: official Town references, not claimed agenda items or retrieved PDFs
- `GTA_RADAR_STC_OAK_OFFICIAL_RECOVERY_STATUS.json`: per-source status, exact permit IDs, pagination completion, TLS source trust evidence and blocked page reason

## Acceptance criteria
1. Nonzero actual `permit_ids` and independently licensed permitted source are needed to call the St. Catharines permit collector live.
2. No Oakville meeting collector success claim without downloaded, matched **actual meeting agenda item records**.
3. If old Oakville meeting TLS failure persists, inspect the certificate issuer, valid chain and OS trust store; use Python's standard SSL or updated certifi validation. Never use `verify=False`.
4. Neither a permit record nor a council news hyperlink establishes an early project or real buying opportunity.
5. Source-specific failures never remove pre-existing validated Oakville planning application data.
