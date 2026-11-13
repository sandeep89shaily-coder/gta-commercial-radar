# Customer-product readiness: freshness-first non-repeating lead research (November 12)

**Problem measured in owner ZIPs:** Municipal results contain substantive industrial/project candidates but the legacy regional opportunity top ten can be dominated by older official pages and repeat items from previously delivered client reports. On Nov 12, **none** of the private-top-ten projects had independently verified new-publication evidence. A first Radar observation is never an announcement; a permit/source record date is not automatically the date of first publication.

## Implemented and integrated

- Manual integrated pipeline produces `GTA_RADAR_CLIENT_FRESH_NONREPEAT_TOP_10.csv` and a linked `GTA_RADAR_CLIENT_FRESHNESS_REVIEW.html` after existing source-backed private opportunity processing.
- Primary ranking sorts by **source freshness tier before scope-size score**: verified recent first publication (rare); dated official application/permit event 0–7 days; 8–30 days; then 31–90 days. Large historical projects cannot displace recent projects. Undated, historical, blocked and already-featured projects are *not* padded into a made-up client top ten. Source events are prominently marked **not verified new publications**.
- Within a freshness tier, 100-point weights are: **freshness 50, project scope/size 25, planning/award stage 15, verified contact 10**. Company and contact fields are never promoted by mere site proximity, old brochures or an AI guess. Lack of a verified current buyer explicitly stays unknown.
- `config/client_reported_sites_20261112.csv` lists the specific sites in the verified November 10 expanded 13-project dossier and daily report, the November 11 client PDF, and the November 12 freshly prepared project/contact PDF. It contains 38 site rows including multi-address projects. They remain inspectable via `GTA_RADAR_CLIENT_PREVIOUSLY_REPORTED.csv`.
- Owner-approved *additional* reports may be recorded in `GTA_RADAR_RESULTS/GTA_RADAR_CLIENT_REPORT_HISTORY.csv` with columns `report_date,city,address,report_name`. A daily run **never automatically flags internal candidate output as delivered to clients**; only explicit report history can make a project ineligible for further client reports.
- The full historic private-development investigation queue and existing regional analyst top ten remain preserved and separately visible. No paid AI, network collection, email sends, CASL determinations, project-ledger resets or SQLite writes are introduced by the new client review.

## Quality gates

1. Run CI on both Windows/Linux and release only when all tests pass.
2. Fresh run on owner Windows workstation, then inspect `GTA_RADAR_CLIENT_FRESHNESS_STATUS.json` for number of new, non-repeating, actually source-dated review candidates and why exclusions occurred.
3. Audit original municipal publication versus permit-event dates; confirm stage, projects previously seen, verified company role and whether buyer still needs suppliers. No invented open-bid claim or guarantee of 10.
4. If enough prospects cannot be found, report fewer than 10. Next developer work should strengthen verifiable sources and company-role enrichment before any new mass-email attempt.

## User value

This closes a specific quality gap. It does **not** demonstrate product/market fit or a confirmed purchasing decision-maker. Two paying pilots and verified actionable sources are the next business validation milestone.
