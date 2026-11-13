# Toronto Current Planning Notices — original City source collector (November 13, 2026)

## Live official source checked

Toronto's [Current Public Notices register](https://secure.toronto.ca/nm/notices/current.do) contains planning-application notices with official **Notice Date**, source title and exact public notice URL. This is a separate original City source, not the TMMIS schedule or the restricted Application Information Centre (AIC).

Current original City examples examined:
- [November 6 application notice for 309 and 311 Augusta Avenue](https://secure.toronto.ca/nm/api/individual/notice/8004.do): official application `26 206718 STE 11 OZ`, six-storey hotel and restaurant, 2,194 m² of non-residential gross floor area, public City planner contact.
- [November 6 notice for 7 Labatt Avenue and 77 River Street](https://secure.toronto.ca/nm/api/individual/notice/8002.do): official application `26 246687 STE 13 OZ`, two residential buildings plus non-residential floor area.
- [Current Notices](https://secure.toronto.ca/nm/notices/current.do) also lists November 13 holding-symbol removal applications at 3307 and 3313 Ellesmere Road and at 701 Fleet Street. These are **later-stage planning matters**, not earlier-stage newly announced proposals.

**Notice Date** is a City-labelled *notice event date*, not proof of the first time a developer announced a project, when a page first went online, or a supplier opportunity opening. Project buyers and procurement stages remain **UNVERIFIED**.

## Collector integrated in the existing manually launched Radar

The new `gta_toronto_official_planning_notices.py` is designed to collect:
1. The exact City's official current notices index (`https://secure.toronto.ca/nm/notices/current.do`).
2. Up to **10 individual original official planning notice pages** discovered by anchor link on the live index, sorted by expressly recorded City Notice Date.
3. Only fully source-matched notice title, index/detail municipal date and **single original application number**, with original text excerpt, site from notice title and *public municipal planner* email if explicitly published.
4. SHA256 hashes for index and individual notice HTML and a notice-ID-keyed first local observation ledger, with changed/unchanged source event classifications. Existing source history is retained when collection or parsing fails.

All requests have public-DNS, robots, exact City URL/host/path, no-redirect, MIME and size gates. The source collector never enumerates notice IDs, bypasses blocked pages, processes private content, or requests additional paid AI. The existing one-click `RUN_GTA_RADAR_TODAY.bat` enables this only for operator-initiated *fresh collection*. It is skipped by historical `--skip-collection` review.

The separate review artifacts are:
- `GTA_RADAR_RESULTS/COUNCIL_INTELLIGENCE_REVIEW/TORONTO_OFFICIAL_PLANNING_NOTICES/TORONTO_CURRENT_PLANNING_NOTICES_REVIEW.csv`
- `TORONTO_CURRENT_PLANNING_NOTICE_LEDGER.json`
- `TORONTO_CURRENT_PLANNING_NOTICES_STATUS.json`

They are included in the existing bounded ZIP, while core `radar.sqlite` and original alert history remain untouched. They **are not** auto-promoted as fresh buyer leads or included in customer top-ten until original project/role/procurement stages are independently verified.

## Limits and next acceptance

- Real HTML can differ from the synthetic offline tests. Only a new owner's dated Windows ZIP showing actual document fetch/parse counts can prove live collection.
- This is only the **first page of current notices**, maximum ten original detail pages; no unrestricted paging or archive crawl.
- A notice may refer to an existing multiyear project, and a municipal planner is not an owner/GC/procurement buyer.
- The collector conservatively holds ambiguous application numbers, missing municipal notice date, conflicting index/details or inaccessible sources.
- A blocked source must not be translated into a zero-notices citywide coverage claim.

Priorities after acceptance remain: Brampton's comprehensive OPA/ZBA/site plans; Mississauga approved eSCRIBE calendar/agenda link access; Toronto original planning and permit joins; and a source-backed 20-case first-publication/project continuity audit.
