# GGH official source-access recovery — four blocked municipalities

This stage does not attempt a robots bypass, spoof publisher credentials,
scrape private portals, or claim publisher approval. It converts the existing
live collector diagnostics into municipality-specific access requests for
Richmond Hill, Newmarket, Innisfil and New Tecumseth.

Current documented access problems:

- Richmond Hill: official active development application ArcGIS map includes
  application file numbers but the policy-aware API returned ROBOTS_ACCESS_DENIED.
- Newmarket: official active developments FeatureServer includes FILE_NUM but
  the policy-aware API returned ROBOTS_ACCESS_DENIED.
- Innisfil: official proposed-developments webpage and Cloudpermit application
  system do not establish a public machine-readable list of application IDs.
- New Tecumseth: official planning-notice page links to PDFs that returned
  HTTP 404 in the current live acceptance check.

The official publisher contact routes are:

- Richmond Hill: planning@richmondhill.ca
  https://www.richmondhill.ca/en/learn-more/Planning-Development.aspx
- Newmarket: planning@newmarket.ca
  https://www.newmarket.ca/business-development/development-planning/development-applications/current-applications
- Innisfil: planningservices@innisfil.ca
  https://www.innisfil.ca/building-development/planning-development/proposed-developments
- New Tecumseth: planning@newtecumseth.ca
  https://www.newtecumseth.ca/build-here/development/proposed-developments/

The existing daily runner now writes:
- GTA_RADAR_GGH_SOURCE_ACCESS_REQUESTS.csv: current blocker, official source,
  missing fields, requested access route, recipient, email subject and draft.
- GTA_RADAR_GGH_SOURCE_ACCESS_REQUESTS.md: four human-readable email drafts.
- GTA_RADAR_GGH_SOURCE_ACCESS_RECOVERY_STATUS.json: stage diagnostics.

**Nothing is sent by Radar.** The user must review and send each municipal
request. Responses, authorization conditions, fees and publisher-provided
files must be reviewed before turning on a live source. Assisted CSV imports
already exist for Richmond Hill and Newmarket but do not count as automated
application coverage.

Run the normal Windows daily launcher; the request packet is generated
after GGH GIS and HTML diagnostic collection. The dashboard links to the
new files. Testing: `python -m pytest -q tests/test_ggh_source_access_recovery.py`.

Source contacts and official records were reviewed November 4, 2026.
