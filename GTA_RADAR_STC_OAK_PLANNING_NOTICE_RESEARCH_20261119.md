# St. Catharines and Oakville — actual official planning notices fallback (November 19, 2026)

## Root-cause findings

**St. Catharines:** The City's public CIVIC map explicitly lists *active planning applications* as a **future enhancement**, not current GIS data. The official [Public Notices](https://www.stcatharines.ca/news/public-notices/?page=1) pages publish actual planning proposals and file identifiers; example [8 Gale Crescent](https://www.stcatharines.ca/news/posts/notice-of-complete-applications-and-open-house-8-gale-crescent/) identifies `26 112777 OP`, `26 112778 ZA`, the October 22 application completeness milestone, and commercial/residential scope. The City describes `www.stcatharines.ca/development` as the project-materials route, but that redirects to an inaccessible SugarSync link under current web research. This is a separate document-source failure, not evidence that no planning notice exists.

**Oakville:** The official [Agendas and Meetings page](https://www.oakville.ca/town-hall/mayor-council-administration/agendas-meetings/) links to eSCRIBE. The calendar page returns 403 to ordinary inspection, whereas some official `FileStream.ashx?DocumentId=...` PDF links are indexed and retrievable; access is document-specific, not a reason to disable SSL. The City's [2026 Planning Public Notices Archive](https://www.oakville.ca/town-hall/news-notices/2026-planning-public-notices-archive/) is a richer independently accessible route: example [118-132 Cross Avenue](https://www.oakville.ca/town-hall/news-notices/2026-planning-public-notices-archive/notice-of-complete-application-for-a-proposed-opa-and-zba-for-118-132-cross-avenue/) provides file numbers `OPA1614.84` and `Z.1614.84`, an applicant, development scale, explicit issued date, and linked application materials. The November 17 notice for 2250 Speers Road identifies `Z.1628.33` and its December 7 public meeting.

## New collector

`gta_stc_oak_planning_notices.py` is now an automatic stage in the normal daily full-run launcher. Bounded to 3 official St Catharines listing pages and 15 notice pages per city; Oakville 2026 archive, 15 pages. Retrieves only robots-permitted publisher-domain HTML without proxy/impersonation, and records each city's source access separately.

Official notice IDs, addresses, applicant labels, explicit notice issue dates and linked application document pages are recorded in:
- `GTA_RADAR_STC_OAK_OFFICIAL_PLANNING_NOTICES.csv`
- `GTA_RADAR_STC_OAK_PLANNING_DOCUMENT_PAGES.csv`
- `GTA_RADAR_STC_OAK_PLANNING_NOTICES_STATUS.json`

**Restrictions:** Does not assert first-ever disclosure, developer procurement intent or real buying contacts. Publisher commercial-resale/reuse licences not yet verified, so keep output **research-only** and do not merge into commercial AI candidate selection until permissions are established. Document links are not downloaded and are not equivalent to retrieved agendas. Actual nonzero source output and publisher policy are required to claim live operation.

The old St Catharines permit collector and Oakville TLS/meeting diagnostic are preserved; this new stage adds higher-value planning notices, not fake calendar success.

## Still open

1. Confirm publisher permissions for automated commercial reuse of news and notices.
2. Verify collector has nonzero exact IDs in actual Windows output; inspect output source HTML changes.
3. For Oakville, use explicit public application-page links from notices; retrieve reports only where access/reuse permitted. Do not generate or guess `FileStream.ashx` IDs.
4. For St Catharines, resolve the official SugarSync redirect or obtain another authorized document location for supporting planning materials.
5. Do not relabel an application notice's date or meeting date as project launch/first-ever public announcement.
