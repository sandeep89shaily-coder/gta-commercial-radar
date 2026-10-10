BRAMPTON DEPARTMENT COLLECTORS — ADDITIVE BUILD

Double-click START_RADAR.bat as before. The Brampton source collector runs automatically and generates data/brampton_collection_report.html. It writes ONLY to data/brampton_sources.sqlite. Original radar.sqlite and your previous Radar installs are not changed by the Brampton module.

Currently active adapters: production Brampton ArcGIS permit activity and upcoming inspections, and a conservative visible-page-only food-business licence extractor. Source-discovery monitors: stationary business licensing, planning, council and road construction. Discovery monitors index links; they DO NOT claim to collect the underlying records. The existing Brampton permit collector continues through normal Radar polling.

IMPORTANT: Brampton paginated licence listings are marked PARTIAL until all pages can be verified. ArcGIS tables cap first-run extraction to 5000 rows per source and report PARTIAL if more exist. No collector interprets missing/removed records from partial reads. Website failures show ERROR without damaging stored data. No AI or search API charges from this module.

Live testing was not possible in the build environment (DNS blocked). Check the report from your first local run; do not assume all feeds work until inspected.
