# Ajax + Newmarket source adapter pilot — November 19, 2026

## Status
IMPLEMENTED_ISOLATED_RESEARCH_ONLY. This is NOT a 26-city production
collector. No change to the 24-city launcher, main database, or paid DeepSeek.
The source field schema is verified from official ArcGIS REST layer metadata.
No real live application sample or publisher approval is claimed yet.

## Official layers
- Ajax: https://ajaxmaps.ajax.ca/gisernie/rest/services/Planning/Apps_Dev/FeatureServer/3
  - REF_ID, ADDRESS, DESCRIPTION, APPLICANT, TYPE, STATUS,
    SUBMISSION_DATE, APP_SUBTYPE, OBJECTID
  - Reference: https://opendata.ajax.ca/
- Newmarket: https://services3.arcgis.com/tSwsWwbYRimLwcCZ/ArcGIS/rest/services/OpenNewmarket_Developments/FeatureServer/23
  - FILE_NUM, LOCATION, DESCRIPTION, OWNER, PROPOSE_LAND_USE,
    APP_STATUS, EDIT_WHEN, OBJECTID
  - Newmarket open-data licence:
    https://www.newmarket.ca/TownGovernment/Documents/Newmarket_OpenData_Licence.pdf
  - Town portal: https://www.newmarket.ca/resident-services/maps-gis-open-data/open-data

### Running without network (default)
Save publisher-approved JSON feature snapshots in a local folder as
ajax.json and newmarket.json. The files must contain a top-level features
array with ArcGIS attributes. Command:

    py -3 gta_ajax_newmarket_source_pilot.py --results "GTA_RADAR_RESULTS" --snapshot-dir "approved_snapshots"

Without snapshots, the default only writes a zero-row preflight and does
not make external requests:

    py -3 gta_ajax_newmarket_source_pilot.py --results "GTA_RADAR_RESULTS"

### Approved bounded source fetch (opt-in only)
After checking the specific feature layer is within the publisher's reusable
dataset licence and the robots policy allows the query route:

    py -3 gta_ajax_newmarket_source_pilot.py --results "GTA_RADAR_RESULTS" --fetch-approved

That mode requests up to 300 attributes-only records per municipality with
100-record pages. It refuses duplicate ObjectIDs across pages and failed
ArcGIS responses. It is NOT a guarantee of citywide completeness. Never
run around a restricted robots or authentication policy.

## Acceptance conditions before production integration
1. Independently verify query permission and the licence scope covering the
   actual layers (portal existence is insufficient). Attribute the publisher.
2. Capture a lawful bounded test sample (ideally >=20 actual source rows
   where available), retain JSON and confirm stable unique REF_ID and FILE_NUM;
   do not mistake GIS OBJECTID or GlobalID for application ID.
3. Audit duplicate geometries, mixed land use, preconsultation and
   invalid/closed applications; compare a 20-file sample with official portals.
4. Keep application-submission, GIS edit, first observed and original publisher
   notice dates SEPARATE. Neither SUBMISSION_DATE nor EDIT_WHEN is proof of
   original project announcement.
5. Confirm buying-role, developer, active scope and unawarded work separately.
6. Only then propose adding live collectors to the existing manual launcher,
   with source health and fail-closed sampling/quality checks.

Outputs from the isolated pilot:
- GTA_RADAR_AJAX_NEWMARKET_RESEARCH_APPLICATIONS.csv
- GTA_RADAR_AJAX_NEWMARKET_RESEARCH_STATUS.json

All leads remain RESEARCH_ONLY. Planner emails or source applicants are not
verified purchasing contacts.
