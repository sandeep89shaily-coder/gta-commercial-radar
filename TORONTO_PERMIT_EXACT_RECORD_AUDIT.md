# Toronto exact permit/revision audit — isolated pilot

**Status: development / acceptance pending. No automatic collection or sales lead promotion.**

This is the next evidence-verification layer on top of GTA Radar's already collected Toronto building-permit records, not a replacement source collector.

## Verified source design and provenance

Toronto's published City **Building Permits – Active Permits** dataset contains individual `PERMIT_NUM` and `REVISION_NUM` records. The City also operates a separate permit-status search application. The two data surfaces do not have identical freshness guarantees; the City states the status-search app is updated **as of the previous business day**.

- https://open.toronto.ca/dataset/building-permits-active-permits/
- https://www.toronto.ca/services-payments/building-construction/building-permit/after-you-apply-for-a-building-permit/search-the-status-of-a-building-permit-application/
- Official CKAN API: `https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/`
- Package slug: `building-permits-active-permits`.
- Previously published English active-permit DataStore resource ID: `6d0229af-bc54-46de-9c2b-26759b01dd05`. **Never assume it is permanently current**: the live checker first resolves official package metadata and refuses to continue if the expected resource is not active. The actual resource metadata response and exact API results have not been independently retrieved in this chat.

The latest previously uploaded **November 7** `GTA_RADAR_RESULTS (13).zip` contains **151 Toronto project-folder records corresponding to 220 exact permit/revision source keys**, e.g.

```text
project_id:  toronto_active_building_permits:26 265617
source_keys: 26 265617 HVA|00 | 26 265617 BLD|00 | 26 265617 PLB|00
```

A project folder is not itself an individual permit. `BLD`, `HVA` and `PLB` are **distinct** permit records that can have different statuses.

## New module

`gta_toronto_permit_evidence.py`:

1. Requires existing `GTA_RADAR_DAILY_NEW_DEVELOPMENTS.csv`. Only reads rows with the exact Toronto permits source ID.
2. Parses the original composite folder/source-key references with strict validation. Mixed folders, malformed keys, duplicates or more than 12 keys per folder are refused and counted.
3. If an existing collector `radar.sqlite` is provided, opens it **read-only** and checks each source key against the latest original saved `records_current` / `record_versions` payload, requiring matching `PERMIT_NUM` and `REVISION_NUM`. Preserves first seen, source date, payload hash, individual `STATUS`, active flag and civic address.
4. Compares each constituent record's physical address and municipal status with the exported folder. Flags missing/contradictory addresses, inactive records, and different stages across constituent permits.
5. **Offline by default**: no external calls. Reports `LOCAL_EXACT_PERMIT_REVISION_PAYLOAD_MATCH_NOT_LIVE_RECHECKED`, **never** a confirmed open procurement.
6. Optional **manual** `--live-ckan` explicitly queries up to **10** exact `PERMIT_NUM` + `REVISION_NUM` pairs through the official City CKAN `datastore_search` API, after resolving the expected active resource in `package_show`. Redirects/other hosts/unexpected resource IDs and oversized responses are prohibited; no token or paid AI.
7. Missing active DataStore records are marked `NOT_PRESENT_IN_ACTIVE_DATASTORE_NOT_PROOF_OF_CLOSURE` because older, closed or cancelled permits can move into Toronto's **separately published cleared permits** dataset. A mismatch, missing active record or incomplete API access does not become a false project cancellation, purchase order or vendor award.
8. Source and HTTP errors are recorded; the audit never claims a buyer, available contract, commercial opening or occupancy.

## Use in the isolated manual review (not needed today)

The existing `RUN_FACILITY_EVIDENCE_REVIEW.bat` now also creates the **offline-only** Toronto permit record audit when a daily export exists. It attempts to use your **existing** collector SQLite from the established workspace, never creating a new one. If unavailable, the output states that exact local payload verification is missing.

Standalone local snapshot audit:

```powershell
py -3 gta_toronto_permit_evidence.py --results "%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS" --db "%USERPROFILE%\Desktop\new data\data\radar.sqlite"
```

Explicitly opt-in, bounded **official public CKAN** recheck for a small sample (not used by the combined runner):

```powershell
py -3 gta_toronto_permit_evidence.py --results "%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS" --live-ckan --live-limit 10
```

No automatic live querying has been enabled. Do not run either command just for code development.

### Isolated outputs

Under `GTA_RADAR_RESULTS/TORONTO_PERMIT_EVIDENCE_PILOT/`:
- `GTA_RADAR_TORONTO_PERMIT_EXACT_RECORD_AUDIT.csv`: one row per constituent permit/revision, with local evidence hash and optional official CKAN exact-match status.
- `GTA_RADAR_TORONTO_PROJECT_PERMIT_RECONCILIATION.csv`: one row per Radar project folder, with constituent counts, stage conflicts and outstanding checks.
- `GTA_RADAR_TORONTO_PERMIT_EVIDENCE_STATUS.json`: exactly which sources could be inspected; missing database, metadata failure and unqueried records remain visible.

## Acceptance before promotion

- CI: strict ID parsing, source SQLite read-only, payload-key matching, cross-address conflict, multiple permit stages, inactive history, failure isolation, network opt-in, bounded queries and explicit zero verified buyers/contracts.
- Check an actual local export/SQLite bundle and independently confirm a minimum of **20 individual permit records** and the status of their associated application folders with City original data.
- Verify source licence/terms and data refresh date before any client redistribution; preserve City attribution.
- Keep separate draft PR #155 and leave Industrial #152 / Activation #153 / normal daily runner unchanged until controlled field acceptance.

**A permit-level exact match is a materially stronger source citation than a generic portal URL, but it is not a buyer or procurement verification.**
