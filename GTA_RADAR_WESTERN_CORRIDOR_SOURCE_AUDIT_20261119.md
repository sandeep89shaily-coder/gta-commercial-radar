# GTA Radar — London / Sarnia / Chatham-Kent / Windsor evidence audit

**November 19, 2026 — western corridor research/implementation record.** This is a verified-source and rights review, not a declaration that the three new municipalities are fully covered by live collectors.

## Precise municipality count

The production repo already includes **Windsor** as one of the added four alongside Ajax, Newmarket and Pickering in `gta_four_city_live_daily.py`. The 24-city baseline plus four = **28**. Adding **London, Sarnia and Chatham-Kent** changes the **configured** research universe to **31**, not 32. Existing Windsor application records are never duplicated.

## City-by-city official source/field audit

### London — published technical schema, but missing essential sales fields and source-specific rights

**Actual official layers**: [London Planning Application Sites MapServer](https://maps.london.ca/server/rest/services/Planning_Application_Sites/MapServer) with:
- `/29` Site Plan Applications: fully qualified `PROPOSEDDEVELOPMENT.SitePlans.FileNumber`, `YearOpened`, `LastEditDate`, optional `SharePoint_URL`; unlike an application dossier, **no authoritative address, proposed use, construction value, floor area or buyer company** in the inspected schema.
- `/31` Official Plan / Zoning and `/30` Zoning: qualified `...PlanningApplicationSites.FileNumber`, `YearOpened`, `LastEditDate`, `SharePoint_URL`. Technical GIS_ID and OBJECTID are **not** planning file numbers.
- `/27` Subdivision: `FileNumber`, `Status`, `RegisteredDate`, `Phase` and `Planner`; some layers have ArcGIS attachments while 31 doesn't. The presence of attachments is **not** evidence that documents have been retrieved.
- `/10` PlanningApplicationSitesStatus is a table with `ReferenceFile`, `StatusCode`, `SubCode`; a GIS status code is not a validated construction phase.
- [City's ongoing planning applications](https://london.ca/business-development/planning-development-applications/planning-applications) links detailed individual project pages with file number, site address, what is proposed, notice milestones and documents. E.g. [3924 Colonel Talbot Road](https://london.ca/business-development/planning-development-applications/planning-applications/3924-colonel-talbot-0) has `O-26047` / `Z-26046` and [1944 Bradley Avenue](https://london.ca/business-development/planning-development-applications/planning-applications/1944-bradley-avenue) includes project scope.

**Rights:** [City Open Data licence](https://london.ca/government/council-civic-administration/open-data) allows lawful commercial reuse **of datasets released under that licence**. [City general website terms](https://london.ca/terms-use) separately limit website materials to non-commercial use and prohibit robots/data mining. No evidence yet that this specific `maps.london.ca/Planning_Application_Sites` layer or `london.ca/planning-applications` HTML is explicitly an Open Data-licensed dataset. Therefore the new software **does not automatically scrape the GIS or ordinary HTML**. A publisher-licensed export, when independently confirmed, can be imported via source-provenance manifest and counted as research evidence without claiming buyer or first publication.

### Sarnia — current planning portal is sparse, and website terms forbid automated mining

- [Active Planning Applications](https://www.speakupsarnia.ca/active-planning-applications) currently exposes only the **City Initiated Official Plan Amendment (city-wide)** in its rendered list; no basis for claiming broad active site-by-site planning application coverage.
- [Public Notices](https://www.sarnia.ca/category/public-notices/) is dominated by civic/governance notices; publication dates are not application dates. Sarnia's [Planning Data Reports](https://www.sarnia.ca/planning-data-reporting/) contain aggregate data, not identified industrial proposals. Zoning/development-charges datasets on [Sarnia GeoHub](https://city-of-sarnia.hub.arcgis.com/) can be valuable **context**, not substitute application IDs.
- [Sarnia website terms](https://www.sarnia.ca/terms-of-service/) section *Licence* expressly forbids robots/data mining, commercial reuse and redistribution absent authorization. The collector **does not mine the municipal website** or interpret a city-wide policy amendment as a commercial project.

**To activate** a fully automated Sarnia file-number feed, identify a separately OGL-licensed municipal planning dataset, a contractually allowed API/export, or written permission for the exact source.

### Chatham-Kent — official planning notices but explicitly non-commercial site terms

- [Official Planning Notices](https://www.chatham-kent.ca/business/planning/Pages/Planning%20Notices.aspx) lists a **November 23 Council Meeting**, with 220–222 St. Clair Street, 9295 Colborne Street, 7520 & 7522 Middle Line, 13752 Reeders Line and 7540 Middle Line and some planning-justification/parking/conceptual-plan links.
- The list **does not give all official file IDs**. Meeting date is **not** project announcement or first disclosure. Don't synthesize an application ID from an address or council agenda row.
- [Chatham-Kent website Terms of Use](https://www.chatham-kent.ca/Pages/Terms-of-Use.aspx) say the site's material may be downloaded or printed once for personal, non-commercial use only.
- [Municipal Open Data portal](https://opendata-chatham-kent.opendata.arcgis.com/) is separately published but a **currently licensed planning-applications dataset with actual file-number columns was not verified**. Therefore no automated municipal website scraping is enabled.

### Windsor — already integrated, re-use and audit

- Existing `gta_four_city_live_daily.py` uses `parse_windsor_index` on the Town's official [Current Development Applications](https://www.citywindsor.ca/residents/planning/land-development/development-applications/current-development-applications). The page lists current application numbers and addresses, including `Z-008/26` at 825 Cabana Road East and `Z-017/26` at 4470 North Service Road East, plus many project-specific document links.
- Windsor's [website privacy/terms](https://www.citywindsor.ca/Privacy) likewise limit reuse of ordinary site content; its separate [Open Government Licence](https://opendata.citywindsor.ca/Documents/OpenDataTermsofUse.pdf) applies to identified open-data records, not automatically every city website document.
- A city-level live source should only be recorded as successful if the existing four-city source report says `LIVE_APPLICATION_IDS_RETRIEVED_PARTIAL_COVERAGE` **AND** the live applications CSV contains actual Windsor file IDs and civic addresses. This is an **audit**, not a duplicate collector or independent claim of licensed commercial resale.

## Code: integration in normal manual launcher

New modules:
- `gta_western_corridor_source_audit.py`: source-specific restrictions, exact file-ID validation for publisher-authorized CSV exports with documented licence/provenance, and Windsor live-source consistency audit. **No disallowed automated HTTP attempts**.
- `gta_western_31_city_combined.py`: builds one **31-city configured** research master and 31-row coverage status from the same-run combined 28-city output, adding only provenance-backed records. Keeps the same 28-city Top 10/AI candidates until the new western records meet independently verified rights and qualification gates.
- `gta_monday_full_run.py`: runs the above **after the actual 28-city master** and before the existing shared-budget AI stage. Never performs a second Windsor fetch.
- `tests/test_western_corridor_31.py`: checks 31 vs 32 count, no duplicated Windsor, denied rights imports, record provenance, no dishonest promotion into AI.

ZIP additions:
`GTA_RADAR_WESTERN_CORRIDOR_SOURCE_STATUS.json`, `GTA_RADAR_WESTERN_3_AUTHORIZED_APPLICATIONS.csv`, `GTA_RADAR_COMBINED_31_CITY_PROJECT_MASTER.csv`, `GTA_RADAR_COMBINED_31_CITY_COVERAGE.csv`, `GTA_RADAR_COMBINED_31_CITY_RESEARCH_QUEUE.csv`, `GTA_RADAR_COMBINED_31_CITY_RESEARCH_TOP10.csv`, `GTA_RADAR_COMBINED_31_CITY_STATUS.json`.

The 31-city `Top 10` is initially a **copy of the existing 28-city qualified research Top 10**, not a claim that the three added cities produced validated prospects. The existing paid DeepSeek stage still uses the current 28-city scope. This is intentional until actual city rights, exact IDs, descriptions and application evidence are independently verified.

## Source activation gates, acceptance criteria and failures

- Confirm *dataset-specific* commercial reuse rights and robots/automated access permissions. Published HTML or GIS metadata by itself is not authorization.
- Confirm **actual application IDs** (not map object IDs) and address/project scope independently on 20 records across the selected new cities before promotion.
- Confirm original notice publication separately from `YearOpened`, `LastEditDate`, council meeting and first-seen timestamps.
- Distinguish developer, architect, municipal planner and prospective actual buyer. No supplier procurement inferred.
- For publisher-approved official exports, place CSV and JSON licence manifest under `GTA_RADAR_RESULTS/authorized_western_sources/<city-slug>.*`; fields: `application_id,address,scope,source_url`, optional `stage,category,applicant,source_date`. Manifest keys: `city,official_source_url,licence_evidence_url,rights_scope`; valid rights_scope `PUBLISHED_OPEN_DATA_LICENSED_FOR_COMMERCIAL_REUSE` or `WRITTEN_PUBLISHER_AUTHORIZATION` (plus an actual authorization reference for the latter). This is an operator attestation, **not an automatic legal verification** and imported records remain research-only.
- If the next run has 31 configured cities but only Windsor of the western corridor has confirmed live collection, report that openly rather than asserting 31 cities collecting records.

**The objective remains actual western industrial, manufacturing and supplier opportunities, not a municipality vanity count.**
