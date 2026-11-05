# Official York GGH application feeds

Daily Radar now runs two additional structured sources after the twelve-city GGH
HTML/notice collector:

- Richmond Hill: City-maintained Active Applications view, FeatureServer/0,
  published FILENUMBER, ADDRESS, OWNER, DESCRIPTIONOFAPPLICATION, STATUS.
- Newmarket: Town-maintained Active Developments layer, FeatureServer/23,
  published FILE_NUM, LOCATION, OWNER, DESCRIPTION, APP_STATUS, land use.

Both are official public ArcGIS services (not secondary aggregator datasets).
They are polled through the shared policy-aware bounded GIS client. The
metadata schema and object-ID pagination must pass before any application
records are published.

Outputs in GTA_RADAR_RESULTS:
- GTA_RADAR_GGH_OFFICIAL_GIS_APPLICATIONS.csv
- GTA_RADAR_GGH_OFFICIAL_GIS_NEW_OR_CHANGED.csv
- GTA_RADAR_GGH_OFFICIAL_GIS_STATUS.json
- GTA_RADAR_GGH_OFFICIAL_GIS_SEEN.json

First extraction is a historical baseline, **never a fresh sales lead**.
Even if an application received date is supplied, it is not treated as the
municipality's first-publication date. Distinct city-case numbers, not
ArcGIS OBJECTIDs, are stable IDs. Owner names represent GIS publisher labels
and still need buyer/GC verification.

Innisfil currently publishes project descriptions and annual status updates
but no verified open application-ID GIS endpoint in this implementation.
New Tecumseth still publishes inaccessible old linked notice PDFs and cannot
be called covered until a functional file-level source is established. Both
remain reported by the existing twelve-city GGH source audit as unresolved.

Test (network-free):
python -m pytest -q tests/test_ggh_york_official_gis.py

Live source acceptance occurs in GitHub Actions and tomorrow's normal Radar
run, and is diagnostic, not a substitute for source freshness validation.


## Live source acceptance (November 4, 2026)

Official field schemas were independently inspected, but the CI runner's
policy-aware automated ArcGIS fetch returned `ROBOTS_ACCESS_DENIED` for both
Richmond Hill and Newmarket. The collectors correctly produce zero records
and source-level `FAILED` status, rather than claiming usable coverage.
This remains a source access blocker until an explicitly permitted endpoint
or publisher-authorized export becomes available.

## Existing assisted official-export intake

The normal daily Radar runner also runs `gta_three_city_official_csv.py`,
whose assisted input directory is `GTA_RADAR_RESULTS/official_exports`.
For these two additional sources, manually download a CSV through the
publisher's normal export interface (do not bypass any access restrictions).
Preserve the official column names and filenames:

- `RICHMOND_HILL_ACTIVE_APPLICATIONS_OFFICIAL.csv`
  required: FILENUMBER, ADDRESS, DESCRIPTIONOFAPPLICATION.
- `NEWMARKET_ACTIVE_DEVELOPMENTS_OFFICIAL.csv`
  required: FILE_NUM, LOCATION, DESCRIPTION.

The existing importer verifies schema and stable case IDs, generates
`GTA_RADAR_OFFICIAL_CSV_IMPORT_APPLICATIONS.csv`,
`GTA_RADAR_OFFICIAL_CSV_IMPORT_STATUS.json` and its own first-seen ledger.
CSV source provenance is still user-supplied, not independently
authenticated, and **never becomes automated source coverage**.

Innisfil and New Tecumseth also remain blocked on a suitable stable
application-level feed, despite their official index visibility.
