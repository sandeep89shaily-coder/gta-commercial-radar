# v0.7 — Southern Ontario Expansion (staging release)

**Geography:** GTA, Hamilton, Halton, Durham, Waterloo and Niagara. No federal collectors added.

This extends the working v0.6 easy-setup source code. Existing collectors and lead candidate engine are retained. New feeds are **disabled** pending live `doctor` validation, licensing review, and careful date-field mapping. Source existence is not evidence of a production-ready collector.

## Three staged additions
- Hamilton Development Applications — official ArcGIS FeatureServer, layer 2; schema/date mapping pending.
- City of Waterloo Building Permits — official ArcGIS FeatureServer, fields documented.
- St. Catharines Building Permits — official ArcGIS FeatureServer, nightly dataset advertised under City open-government licence.

## Critical protection
DO NOT poll or adopt into this downloaded source-only folder before installing. Your working `gta_commercial_radar_v06_easy_setup/data` database remains the source of truth. Use the included `SETUP_ONCE.bat` only after extracting beside the working v0.6 folder. It copies the data by SQLite backup into a fresh folder and never overwrites an existing destination. No automatic new feed polling.

## Check later (not required now)
`python main.py doctor --source hamilton_development_applications --source waterloo_city_building_permits --source st_catharines_building_permits`

A `doctor` check is not proof of incremental correctness. New sources remain disabled until live records, field mappings, licence and commercial classification are assessed.

## Research register
`config/southern_ontario_feed_queue.csv` distinguishes 3 configured sources from additional candidates that have not yet been coded.
