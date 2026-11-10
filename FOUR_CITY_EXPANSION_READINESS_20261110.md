# GTA Commercial Radar — Four-city controlled expansion gate (November 10, 2026)

**Business goal:** grow from the configured 16 municipalities only when new
sources generate distinct, early, commercially relevant, auditable project
information. A registered municipal index, ArcGIS layer, or historical project
row is not verified current coverage or a lead.

## What is already implemented

The separate **manual/experimental GGH pilot** already registers:
- **Pickering** — City current development proposals, https://www.pickering.ca/devapp
- **Niagara Falls** — City planning applications, https://webpublic.niagarafalls.ca/Planning/
- **Barrie** — City public active-application ArcGIS, https://gispublic.barrie.ca/arcgis/rest/services/Public/AnnexedLand_ActiveApplications_WA_Static/MapServer/4

These are NOT new 2026-11-10 collectors or verified additional production
municipalities. They are experimental sources already in
`gta_ggh_early_planning.SOURCES`.

**Ajax is different:** its official Planning Application Dashboard
https://ajax.ca/build-invest/for-developers-builders/planning-development-applications/
exposes application search, status and source documents in a public interface.
The Town's public service directory lists
https://ajaxmaps.ajax.ca/gisernie/rest/services/Planning/Apps_Dev/MapServer
and active planning layers 1 and 3. **Field-level schema, permitted query
frequency, API reuse and complete application coverage are not verified.**
It is intentionally **not enabled** as a live Radar collector by this PR.
Request an authorized CSV/export or API information from
planningservices@ajax.ca before building the separate Ajax pilot.

## Delivered code

- `gta_four_city_expansion_gate.py` reads previously saved
  `GTA_RADAR_GGH_EXPANSION_SOURCE_STATUS.json` and writes:
  `GTA_RADAR_FOUR_CITY_EXPANSION_ACCEPTANCE.csv` and
  `GTA_RADAR_FOUR_CITY_EXPANSION_ACCEPTANCE_STATUS.json`.
- The new manual launcher is
  `RUN_FOUR_CITY_EXPANSION_REVIEW.bat "C:\path\to\GTA_RADAR_RESULTS"`.
  This does **not** launch collection, modify databases or spend AI budget.
- No successful configured index, raw application count, or source-date field
  can set `verified_citywide_coverage`, source public dates, new sales leads
  or open contracts to a verified state; all those claims stay zero.
- Barrie's GIS parser now accepts an *injected test-only JSON fetcher* in the
  experimental run. Default live operation still uses the existing
  DNS/robots/no-redirect checked ArcGIS JSON transport.
- Tests cover a successful Barrie initial baseline and repeat, and a denied
  GIS source that never manufactures a new lead.

## Acceptance before adding to daily production

1. **Permissions:** check current official API/export terms and permitted
   frequency; do not circumvent robots, authentication or dynamic restrictions.
2. **Complete extraction:** verify all pages / layers and exact file IDs. No
   generic maps, metadata views or identifiers built from addresses.
3. **Identity:** record official original source URLs, street and suite;
   compare potential duplicates to existing Durham, Niagara and planning
   records without silently merging.
4. **Freshness:** compare independent publisher first-publication dates and
   actual immutable Radar first-observed times across at least two successful
   manual runs. Submission, GIS edit and first discovery dates differ.
5. **Commercial value:** audit at least 20 individual source records per
   promising city, track rejections, source-age and trade relevance; show
   genuinely distinct actionable prospects and a documented contact role.
6. **Release:** only then consider promoting one city and updating the
   public advertised coverage number; preserve existing stable 16-city runner.

Next in priority: an approved Ajax source export/permission route and
independent Pickering/Barrie/Niagara samples. Later qualify prospect buyers
and test with two paying pilots. This work does not authorize automated
outreach or publication of unverified claims.
