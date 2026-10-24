# Hamilton — verified public planning sources, October 24, 2026

**Pilot status: OFFICIAL LIVE DATA RETRIEVAL PASSED.** Collector integrated into draft early-signals PR #74; isolated database only. Does not merge into V8, schedule, call DeepSeek, infer buying authority, or produce qualified saleable leads.

## Why Hamilton matters

Hamilton has two complementary **FREE official** early-planning sources:

1. **City of Hamilton Open Data — Development Applications feature layer 2**
   - https://services.arcgis.com/rYz782eMbySr2srL/ArcGIS/rest/services/Development_Applications/FeatureServer/2
   - Source exposes `OBJECTID`, `FILE_NUM`, `FILE_TYPE`, `ADDRESS`, `FILE_YEAR`, `DESCRIP`.
   - Includes `Formal Consultation` application types (an early cue that can precede rezoning/site plans), though consultation is not mandatory.
   - There are **no precise application received dates, public posting dates, status, approved work packages or buyer contacts** in these six fields. `FILE_YEAR` is year only. `OBJECTID` is a GIS feature identity, NOT proof of one unique development project.
   - Production-safe retrieval: read exact published ID list then query every ID via official ArcGIS REST in bounded POST batches, with GET fallback when necessary; reject incomplete ID coverage and preserve prior history.
   - **Live one-shot GitHub check on October 24, 2026 succeeded: 5,237 GIS features.** First-run baseline correctly produced 0 NEW alerts.

2. **City of Hamilton Planning Committee / Complete Application public notices**
   - https://www.hamilton.ca/city-council/news-notices/news-releases?category=143&sort_bef_combine=date_DESC&tags=594
   - Individual municipal notice pages publish actual **Published** dates and original file references, often the applicant/proponent (not verified buyer), purpose/scope and civic address.
   - The collector starts with the **first currently visible results page**, follows at most 20 recent articles by default and keeps only ones with official `DPA-`, `SUB-`, or `FC-` application numbers. City-wide rule changes without project IDs are skipped rather than misrepresented as buyer opportunities. Later paginated history is unimplemented.
   - **Live one-shot GitHub check on October 24, 2026 succeeded: 5 dated, file-specific notices parsed from the first 8 linked articles.** The other three did not meet exact file-reference requirements, not a proven lack of development.
   - Page's notice `Published` date is recorded as source posting date; meeting date, application number year, FILE_YEAR and first Radar observation remain separate.

**One-shot run:** GitHub Actions `Hamilton early public sources one-shot check` run **40119237492**, manual pilot source `early_hamilton_watch.py`. This was an actual live connection to both sources; full Windows desktop and future reliability still need confirmation.

## Example official planning records to investigate (NOT verified open supplier contracts)

- **844 Glancaster Road, Ancaster** — published May 11, 2026, **Alba Developments** proposed an industrial subdivision in the Airport Employment Growth District, with new municipal road, stormwater management and future employment blocks. City files `DPA-2026-00043` and `SUB-2026-00044`. Source: https://www.hamilton.ca/city-council/news-notices/news-releases/complete-application-844-glancaster-road-ancaster
- **1310 South Service Road, Stoney Creek** — published September 18, 2026, **Forum Properties** notice for proposed Costco-adjacent parking expansion alongside separate residential project considerations; municipal file `DPA-2026-00343`. Source: https://www.hamilton.ca/city-council/news-notices/news-releases/complete-application-1310-south-service-road-stoney-creek

Do not interpret applicant, municipality's planning officer or architect as the purchaser. Neither early public notice establishes an unawarded HVAC/equipment/security contract.

## Commercial-use licence and privacy

Hamilton's official Open Data Licence expressly allows lawful commercial data reuse with attribution. Include the City's requested statement:

> Contains public sector Data made available under the City of Hamilton’s Open Data Licence

See https://www.hamilton.ca/city-council/data-maps/open-data/open-data-licence-terms-and-conditions .

Respect the linked Acceptable Use Agreement, privacy exclusions, third-party content limitations, and no official-endorsement condition. **The City's open dataset licence should not be assumed to cover every third-party linked news image/report or all site HTML content.** Keep only source links and source-grounded text excerpts; review rights before resale.

## Integration and output

The manual combined pilot runner `RUN_EARLY_CUES_PREVIEW.bat` now executes `early_hamilton_watch.py` before read-only cross-source evidence matching. It does NOT reread/reprocess the original seven GIS sources; Hamilton has its own `data/early_hamilton_review.sqlite` database.

Reports:
- `GTA_RADAR_RESULTS/EARLY_HAMILTON_SOURCE_STATUS.csv`
- `GTA_RADAR_RESULTS/EARLY_HAMILTON_RESEARCH_QUEUE.csv`
- `GTA_RADAR_RESULTS/EARLY_HAMILTON_CHANGES_REVIEW_ONLY.csv`

The independent matcher imports this database; `hamilton_` source IDs have explicit Hamilton location, and ONLY records with `date_basis=OFFICIAL_NOTICE_PUBLISHED_DATE` count toward publication-date comparisons. GIS `FILE_YEAR` is NEVER treated as a posted date. Same numbered civic address across GIS and notice merely flags possible linkage; matching `FILE_NUM` and documents should be manually verified before claiming one physical project.

All files are review only; no AI spend, customer outreach, source scheduler, or production V8 changes.

## Next Hamilton-specific value gates

1. **Measure added value:** Compare notice `Published` dates vs GIS first observable timestamps / permits for the SAME file. Do not infer a date from `FILE_YEAR`.
2. **Prioritize likely buyers:** Extract bounded industrial-specific descriptions and formal consultations; confirm the actual owner/developer/operator and procurement status independently.
3. **Improve notice coverage carefully:** page 2+ public notice pagination only after live index shape and terms validation; current bounded first-page test is honest about its limits.
4. **Verify 10 quality leads and two paying pilot customers.** Never call the 5,237 GIS features separate commercial prospects.

## Source testing

```sh
python -m unittest tests.test_early_hamilton_watch
python early_hamilton_watch.py --data-dir data --output-dir GTA_RADAR_RESULTS
```

Do not schedule or merge the collector until tests and incremental business value are confirmed.
