# Vaughan / Kitchener — authorized application-source recovery (2026-11-10)

This release adds **no new automated portal scraping**. Radar's last Windows run
recorded Vaughan's HTTP 403 and Kitchener's robots-denied ArcGIS queries. Neither
may be bypassed. The existing manually obtained, source-labelled CSV import
and its prior database/first-observation ledger are preserved.

## New functions

- Every normal run already writes the `GTA_RADAR_GGH_SOURCE_ACCESS_REQUESTS.md`
  and `.csv` packet under `GTA_RADAR_RESULTS`. It now includes **Vaughan**
  and **Kitchener** in addition to four existing municipalities, with
  source-specific, **unsent** access requests.
- Recipients and official sources:
  - Kitchener: **gis@kitchener.ca**,
    https://www.kitchener.ca/council-and-city-administration/data-and-maps/open-data/
    (request permitted source access or official public CSV).
  - Vaughan: **developmentplanning@vaughan.ca**,
    https://www.vaughan.ca/about-city-vaughan/departments/development-and-parks-planning
    (request PLANit access/notice registry and file-numbered public notices).
- If the user legitimately downloads official public CSVs using a publisher's
  normal UI, place the unaltered copies in:
  `GTA_RADAR_RESULTS/official_exports/KITCHENER_PLANNING_ACTIVE_OFFICIAL.csv`
  and `GTA_RADAR_RESULTS/official_exports/YORK_REGION_ACTIVE_DEVELOPMENT_OFFICIAL.csv`.
  Existing `gta_three_city_official_csv.py` validates the expected columns,
  requires file IDs, de-duplicates, preserves original source-labelled records
  and independently audits assisted exports without falsely calling them
  automatically collected applications. **York Region** data is a regional
  planning-review record for Vaughan, not an exact substitute for City PLANit.
- The import now retains `APPLICANT`, `PROPERTY_OWNER` and `ISSUED_BY`
  from Kitchener records as **unverified role fields**, and distinguishes
  `LOCALLEAD`/`REGIONALLEAD` on York Regional records as planning-review
  contacts, not purchasers. It also outputs per-export role-completeness counts.
  Their changes do not yet advance the historical lead freshness indicator.
- No paid model call or new daily collection schedule, no API/robots bypass, no
  automatic sales or emails, no invented tender, contractor or buyer.

## Live acceptance

1. Use the next manual Windows run and inspect:
   `GTA_RADAR_ADDITIONAL_CITY_GIS_STATUS.json`,
   `GTA_RADAR_FIVE_CITY_RECOVERY_STATUS.json`,
   `GTA_RADAR_OFFICIAL_CSV_IMPORT_STATUS.json`, and
   `GTA_RADAR_GGH_SOURCE_ACCESS_REQUESTS.md`.
2. If a permitted live source returns records, perform at least two successful
   collections and compare exact application IDs, address, scope and source
   timestamps. An initial baseline must **not** turn into fresh daily leads.
3. Validate company roles and actual procurement separately before publishing.
   `CREATE_DATE`/`UPDATE_DATE` are GIS metadata, and `INDATE` or
   `DATE_RECVD` may be application intake—not first public publication.
4. If blocked, contact the official published address or subscribe to the
   notification registry. Do not bypass or retry via proxies/headless sessions.

Reference datasets: Kitchener GeoHub Planning Applications Active
https://services1.arcgis.com/qAo1OsXi67t7XgmS/arcgis/rest/services/Planning_Applications_Active/FeatureServer/0
and York Region Hosted Development Application Status and Teams
https://services1.arcgis.com/GzvOwaQBbX7KLiuG/ArcGIS/rest/services/Hosted_Development_Application_Status_And_Teams/FeatureServer/0 .

Next development: once verified data is returned, cross-source applicant/owner
identity joining, exact permit-number source integrity, buyer qualification,
and then staged Pickering / Ajax / Niagara Falls / Barrie pilots. Do not claim
20-city verified production coverage from this release alone.
