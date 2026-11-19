# November 19, 2026 — alternative official sources before access requests

**Evidence baseline:** GTA_RADAR_RESULTS_2026-11-19_082638.zip is a PRE-28-city collection run, not evidence about the new four cities. Its municipal recovery scorecard reports 15/24 cities with live application-ID source rows. Its cross-collector failure CSV contains 7 failures (two Mississauga, three Brampton, Oakville meeting TLS, Vaughan meeting HTTP 403). The broader recovery scorecard also reports additional source-specific problems. None should be categorized as a failed entire city if an alternate official source continues to function.

## Alternative routing decisions

| Municipality | Original problem | Verified official alternate route | Action in PR #260 | Next verification |
| --- | --- | --- | --- | --- |
| Kitchener | Existing active planning GIS robots-denied; 0 application IDs | City of Kitchener open-data ArcGIS `Planning_Applications_Active/FeatureServer/0`; fields `APPLICATION_NO,ADDRESS,DESCRIPTION,APPLICANT,STATUS,FOLDERTYPE,INDATE`. https://services1.arcgis.com/qAo1OsXi67t7XgmS/arcgis/rest/services/Planning_Applications_Active/FeatureServer/0 | **Automatic alternate collector implemented** under the City's published open-data commercial-reuse licence, conditional on source robots allowing query | Actual Windows query, pagination, application-ID health and spot-check originals |
| Caledon | Landing URL 404/redirect | https://www.caledon.ca/en/town-services/current-applications includes actual `RZ 2025-0026` and addresses | **Automatic index collector implemented**, reuse marked unverified and records research-only | Confirm permitted crawler and commercial reuse; fetch actual rows and verify underlying application documents |
| Vaughan | HTML and meetings HTTP 403 | York Region's open-data `Active Development Application Boundaries` layer 0: https://services1.arcgis.com/GzvOwaQBbX7KLiuG/ArcGIS/rest/services/Hosted_Active_Development_Application/FeatureServer/0 | Source researched, **not auto-enabled**; avoid publisher rights assumptions | Verify this exact dataset is York Region Open Data, inspect its licence for commercial use and public query rights; only then implement |
| Markham | Very sparse IDs from existing notice collector | Same York Region regional official open-data candidate, plus City's MappiT/ePLAN public interface | Not auto-enabled | Licence, matching local municipal IDs, source-level counts |
| Richmond Hill | Local GIS access denied/index-only | Same York Region candidate, and City's official development planning status page | Not auto-enabled | Verify source rights, municipal identifiers and current stage |
| Brampton | 5 planning layers robots-denied | City's official Accela/Accela_Apps MapServer/10 with `APPLICATION_TYPE` etc. https://mapsdev.brampton.ca/arcgis/rest/services/Accela/Accela_Apps/MapServer/layers | Not auto-enabled; developer GIS endpoint is not automatically permission to scrape | Confirm data currency, owner-approved commercial reuse and robots for actual endpoint; preserve functioning other Brampton collector |
| Mississauga | 2 structured GIS layers robots-denied | City already publishes active application HTML and its planning-data hub; existing 30-row HTML feed works | Preserve and improve existing HTML; no denied-GIS bypass | Validate latest notices, exact IDs, dates and downloadable city open-data licences |
| Toronto | AIC blocked, CKAN still works (1261 applications) | Official City Toronto Open Data/CKAN | Retain working original lane | Evaluate whether additional AIC-equivalent fields exist in permitted bulk open data |
| Hamilton | One development application GIS robots-denied | Current partial application records from separate sources | No new feed enabled without verified official replacement | Evaluate municipal catalogue and published planning notices |
| St. Catharines | Permit export robots denial in pre-28 report | Permit-specific historical source is not equal to current planning applications | No bypass | Identify licensed official open permit report; separate historical permit data |

## Rules for all substitutes

1. An alternate route is legitimate only if it is separately authorized. Changing host/path does not override an explicit robots or legal prohibition covering the same content.
2. `IN DATE`/application receipt, edit timestamp, publisher article date and Radar's first observed day are distinct. No proposed date is certified first publication.
3. Source coverage and project eligibility are different metrics. Record ID count does not verify citywide completeness or active/open supplier work.
4. Failed optional source collection cannot overwrite previously saved historical evidence; neither may old rows be passed off as retrieved during this run.
5. Use zero paid DeepSeek calls for this work; later combined candidate review uses the shared V5 budget.
6. Priority is Kitchener and Caledon live recovery first; only after actual evidence audit, add licensed York Region regional feed and other municipal replacements.

Official references:
- Kitchener dataset: https://services1.arcgis.com/qAo1OsXi67t7XgmS/arcgis/rest/services/Planning_Applications_Active/FeatureServer/0
- Kitchener open-data licence: https://www.kitchener.ca/council-and-city-administration/data-and-maps/open-data-licence
- Caledon current applications: https://www.caledon.ca/en/town-services/current-applications
- York Region official active applications: https://services1.arcgis.com/GzvOwaQBbX7KLiuG/ArcGIS/rest/services/Hosted_Active_Development_Application/FeatureServer/0
- York Region website terms (open-data exception): https://www.york.ca/york-region/privacy-and-disclaimer/website-terms-use
