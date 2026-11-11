# GTA Radar — priority 3 and 4 original-evidence checkpoint (2026-11-11)

**Owner goal:** finish the remaining Burlington/Vaughan/Kitchener source-access and industrial/activation evidence acceptance, without discarding the verified GitHub implementation or automatic promotion of commercial leads.

## Source access — action taken

On November 11 the connected `gtaradar18@gmail.com` Gmail account sent two direct, non-marketing **official access requests**:

| Agency | Published recipient | Request | Status |
| --- | --- | --- | --- |
| City of Vaughan, Development and Parks Planning | `developmentplanning@vaughan.ca` | A permitted PLANit/planning public application register or file-ID/status/notice-date export, plus reuse rules and statutory notice subscription | Sent; approval and reply pending |
| City of Kitchener GIS/Open Data | `gis@kitchener.ca` | Planning Applications Active open data: official CSV/GeoJSON/approved ArcGIS access, refresh and licensing conditions, individual public notice dates if published | Sent; approval and reply pending |

Recipients are grounded in the municipalities' official published contact pages. Kitchener's official Open Data page and GeoHub explicitly describe publicly downloadable CSV/GIS datasets and API integrations under their licence; this does not override the previous robots-policy denial on automated queries. Vaughan's official Public Meetings page has a public-notification registry; a subscription is not equivalent to complete automated PLANit coverage.

An independent Gmail reply watch now checks on weekdays. The manually run Radar daily schedule is unchanged, and this watch does not access blocked endpoints or send unsolicited follow-up messages. Never mark either municipal source `COLLECTED` until permitted exact City file IDs are independently reconciled.

Source references:
- [Kitchener Open Data](https://www.kitchener.ca/council-and-city-administration/data-and-maps/open-data/)
- [Kitchener Planning Applications Active source layer](https://services1.arcgis.com/qAo1OsXi67t7XgmS/arcgis/rest/services/Planning_Applications_Active/FeatureServer)
- [Vaughan Planning Department](https://www.vaughan.ca/about-city-vaughan/departments/development-and-parks-planning)
- [Vaughan Public Meetings notification registry](https://www.vaughan.ca/residential/building-and-construction/vaughans-planning-process/public-meetings)

## Original industrial notice audit — 3/3 source-checked

The [source verification rows](evidence/ERO_3_SOURCE_RECHECK_20261111.csv) were checked directly against three official Environmental Registry of Ontario notices, on November 11:

| Original ERO ID | Official stage as checked | Physical project site | Specific proposed change | Official comment close |
| --- | --- | --- | --- | --- |
| [026-1152](https://ero.ontario.ca/notice/026-1152) | Proposal, posted Nov 6 | Pinty's, 2714 Bristol Circle, Oakville | Replace Line 3 dust collector with a scrubber | Dec 21, 2026 |
| [026-1155](https://ero.ontario.ca/notice/026-1155) | Proposal, posted Nov 6 | 1000792458 Ontario Ltd., 890 Harrington Court, Burlington | Install two human cremation units | Dec 21, 2026 |
| [026-1021](https://ero.ontario.ca/notice/026-1021) | Proposal, posted Oct 6 | Kristofoam, **120 and 160 Planchet Road**, Vaughan | Add boiler/cooling tower and replace other processing equipment | Nov 20, 2026 |

This closes **source existence, stage, site and equipment change verification for the three already-extracted notices**. It does not verify an open tender, engineering scope, a purchase order, equipment delivery dates, supplier contact, buyer authority or an unawarded commercial package. Environmental comment-period deadlines are **not** equipment bidding deadlines. All remain `buyer_verified=NO`, `supplier_package_available=UNKNOWN`. Recheck stages when next collected because official notices may advance.

## Two real historical Windows output archives reconciled

The user-supplied original daily result ZIPs `GTA_RADAR_RESULTS (14).zip` (Nov 9) and `GTA_RADAR_RESULTS (15).zip` (Nov 10) contain:

- 2,833 exact activation source-record keys in common; **2,833/2,833 have identical preserved source payload hashes and classified stages/sites**.
- 1,365 additional records in the Nov 10 archive, all from the Toronto municipal business-licence dataset. They were not in the prior accepted pilot list, **not necessarily newly published licences**.
- Industrial pilot changed from two source-backed equipment findings on two notices to four equipment findings on three notices (two new equipment categories on existing Kristofoam notice).
- Burlington `GTA_RADAR_FIVE_CITY_OFFICIAL_SEEN.json`: **11 exact City application-ID ledger entries** were preserved unchanged in both historical archives, but both archived runs had *blocked official-page collection*, so these archives do **not** constitute two successful post-fix Windows source collections. The latest independently checked official GitHub source workflow instead parsed 10/10 selected pages with 16 application IDs.

New `gta_pilot_archive_reconciliation.py` makes this audit reproducible from supplied ZIPs, emits balanced 20-source-record/10-site review queues and per-notice equipment source differences, and **never claims original-source authenticity** from matching snapshots.

## New source-age safety gate

`gta_five_city_application_recovery.py` now differentiates a genuinely observed change to an already tracked file from a historically published City file number that became readable *only because the parser improved*. Previously a previously-undetected file on a preexisting Burlington dataset could be counted as `FIRST_OBSERVED` with an artificial fresh-opportunity alert. Such undated files now become `FIRST_OBSERVED_UNDATED_HELD`, are retained in the full source output and ledger, and are **excluded from the changes/alert CSV until public posting age is independently checked**. Old known IDs that truly change scope/status still receive `RECORD_CHANGED` review events.

## What remains genuinely blocked

1. Two successful, separate, independently dated **owner Windows post-fix collector runs** with the currently installed 16-ID Burlington parser, preserved original source pages and exact-file ledger comparison. Source-only GitHub runner validation and older blocked archives do not meet this user-local release condition.
2. An authorized publisher response/export for Vaughan and Kitchener; requests sent, permission and files not yet provided. Do not evade prior HTTP 403/robots restrictions.
3. At least 20 **original municipality source records** individually rechecked with exact record IDs, date, status and unit, and 10 facility dossiers independently tied to a business tenant or verified absence of such a relationship. The historical 2,833-row hash stability check is not original-source revalidation.
4. At most ten additional **unreviewed or changed** original ERO notices through the pre-existing robots-checked user manual pilot, preserving the 19 previously fetched notices, and independent supplier purchase/work-package validation. This requires current Windows workspace state and any new official permission.
5. Any fresh commercial qualification, outreach or 2 paying customers. All amounts and dates must be independently sourced.

The manually controlled daily collector and shared US$0.25/day paid AI ceiling are unchanged. No buyer or supplier lead was automatically promoted and no restricted endpoint was accessed in this checkpoint.
