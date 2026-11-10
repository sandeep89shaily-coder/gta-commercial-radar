# GTA Radar — Phase 1 municipal source repair, 2026-11-10

Scope: **Burlington, Vaughan, Kitchener**. This branch is a conservative
collector repair, not a claim of complete municipal coverage or new qualified leads.

## Evidence: Nov 10 Windows ZIP `GTA_RADAR_RESULTS (15).zip`

| Source | Observed result | Interpretation |
| --- | --- | --- |
| Burlington early application | `HTTP_301_OR_REDIRECT`; 0 file IDs | Outdated `/Modules/News/en/Development` index was redirected. Redirect denial worked correctly. |
| Burlington five-city recovery | 0 official links from current index; 0 file IDs | The legacy source route could not seed exact-file pages. |
| Vaughan | `HTTP_403_OR_REDIRECT`; 0 file IDs | Do not bypass. The official notice page exists, but automated access is not established. |
| Kitchener GIS | `ROBOTS_BLOCKED:ROBOTS_ACCESS_DENIED`; 0 file IDs | City-owned ArcGIS metadata is visible, but permitted live query access is not yet established. |
| Three-city gate | 0/3 cities with application candidates | Historical GIS project-only signals (Burlington 93; Kitchener 14) were correctly excluded from project-file counts. |
| Sixteen-city early-application summary | 48 candidate rows in four cities | These are candidate file IDs, not verified citywide coverage, source-publication dates, or open bids. |

## Delivered repairs

1. Switch Burlington's *index URL* to the current, official
   `https://www.burlington.ca/news-and-notices/news-views/current-development-projects/`.
   The city currently exposes post URLs shaped as
   `/news-and-notices/posts/current-development-projects/{slug}/`.
2. Allow only those exact official Burlington project-post paths, plus prior
   official `/en/news/current-development-projects/*.aspx` paths for historical
   evidence. Reject wrong host, HTTP, unrelated news paths, queries and fragments.
3. Try the current official index before legacy GIS-supplied URLs; on failure,
   permit bounded fallbacks with **explicit index failure audit**. Never follow
   redirects, ignore robots, or attempt to access blocked sources.
4. Preserve the existing application-ID parser, data-state schema,
   first-seen history, output filenames and manual daily runner.
5. Keep recovery status explicitly gated: individual IDs are not proof of
   citywide completeness, a new public notice, an unawarded contract or a buyer.
6. Add offline unit tests for canonical link selection, false links, initial
   baseline, repeat stability, blocked Vaughan and fallback failure visibility.

The canonical index and example post were independently checked in the official
City of Burlington public website on 2026-11-10:

- https://www.burlington.ca/news-and-notices/news-views/current-development-projects/
- https://www.burlington.ca/news-and-notices/posts/current-development-projects/1376-1382-plains-rd-e-bousfields-inc/

**The code has not yet demonstrated successful automated live collection from
the user's Windows installation.** The user must run the next manual collector
and share the new status ZIP before a coverage-acceptance statement.

## Remaining P0 city gates

**Burlington:** Run two permitted consecutive live collections against the
canonical index. Check `GTA_RADAR_FIVE_CITY_RECOVERY_STATUS.json` for
`links_selected`, `links_parsed`, exact `application_id_rows_this_stage`,
source URL and failures. A first successful file-ID extraction is a baseline,
not a freshly announced public project. Evaluate scope relevance and duplicates.

**Vaughan:** City planning and public notices are publicly visible in a
browser at https://www.vaughan.ca/about-city-vaughan/departments/office-city-clerk/public-notices ,
but the Radar HTTP client was blocked. Do not rotate user agents, use proxies,
headless anti-bot workarounds or scrape restricted endpoints. Request a permitted
structured public-notice feed or authorized city export, preserving official
file number and publication evidence. The city's public notification registry
is an alternative consent-based channel for a later authorized email importer.

**Kitchener:** City's active planning GeoHub dataset metadata lists
`APPLICATION_NO`, `ADDRESS`, `APPLICANT`, `PROPERTY_OWNER`,
`DESCRIPTION`, `CREATE_DATE` and `UPDATE_DATE`. Official service:
https://services1.arcgis.com/qAo1OsXi67t7XgmS/arcgis/rest/services/Planning_Applications_Active/FeatureServer/0 .
This does **not** authorize bypass of the ROBOTS denial the last Windows run
encountered. Request a City-approved CSV/GeoJSON export or documented,
robots-permitted ArcGIS REST path from gis@kitchener.ca.
Treat feature create/update dates as GIS timestamps, not first public posting.
Source: https://www.kitchener.ca/council-and-city-administration/data-and-maps/open-data/

## Acceptance before Phase 2

- No new city is marked verified citywide on the strength of an index alone.
- No false FIRST_OBSERVED alerts from a previously blocked city catching up.
- File IDs and exact official source URLs retained, with explicit 403, 301
  and robots errors still visible.
- Linux/Windows repository tests pass on the current commit.
- The owner's next Windows manual run shows whether the repaired source is
  actually accessible; only then measure useful newly observed projects.
- Follow phases in `GTA_RADAR_NORTH_STAR.md` and
  `GTA_RADAR_RESEARCH_REGISTER.md`. After repairing the original 16,
  assess Pickering, Niagara Falls, Barrie and Ajax as **controlled pilots**,
  not immediate production promises.
