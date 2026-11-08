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

## November 8 development continuation — repeatable verification and acceptance

A hard-coded ten-record sample could never validate twenty records if successive runs
always queried the same ten. The optional source checker now offers
`--live-offset` to inspect **different** permitted records in bounded batches:

```powershell
# FUTURE human-authorized pilot acceptance ONLY; do not run during development.
py -3 gta_toronto_permit_evidence.py --results "PATH_TO_EXISTING_GTA_RADAR_RESULTS" --live-ckan --live-limit 10 --live-offset 0
py -3 gta_toronto_permit_evidence.py --results "PATH_TO_EXISTING_GTA_RADAR_RESULTS" --live-ckan --live-limit 10 --live-offset 10
```

The selector is deterministic for one unchanged export: first represent each
available City status category, then prefer recent source-event dates, prioritize
`BLD` within equally dated project folders, and select **different project folders**
before checking second permits at the same site. **Source event date is not an
official publication date.** The generated manifest records the attempted source
IDs, selection policy, original source metadata and next offset.

Every explicitly opted-in City query session preserves a **new unique JSON file**
under `TORONTO_PERMIT_EVIDENCE_PILOT/LIVE_VERIFICATION_BATCHES/`, including each
original publicly returned CKAN row, its canonical SHA-256, the exact filtered
query URL, the source-record stage/address, and whether the historic exported
stage differed. Older batch files are never overwritten by a new batch, even
though the latest CSV and top-level status JSON are replaced. A saved hash is a
tamper-evident local research checksum, **not** a cryptographic City signature
or third-party authenticity attestation.

`gta_toronto_permit_acceptance.py` reads these saved evidence batches **offline**
and creates two additional research audit files:

- `GTA_RADAR_TORONTO_SOURCE_ACCEPTANCE.json`: counts recent exact unique City
  permit/revision rows, independent project folders, physical sites and stage
  categories, rejects malformed/stale/contradictory/untrusted records, and
  explains why release is still blocked.
- `GTA_RADAR_TORONTO_ACCEPTANCE_RECORDS.csv`: exact primary-source evidence
  for repeatable spot-checking, with every buyer and supplier-contract claim
  explicitly `NO`.

The *source sample evidence gate* requires at least **20** recent unique permit
revision records, **15** distinct project folders, **10** distinct physical
street addresses and at least **2** municipal status categories. Hashes and
source key, query URL, reported status, physical address and original saved
CKAN row must agree. Any recent malformed batch or source integrity failure
blocks this gate even when twenty other records pass. The local saved hashes
are not City digital signatures. A pass means *sampled original-source evidence present
for further review*, **not** independent government authenticity, opening,
occupancy, vendor selection or production commercial acceptance.
`commercial_production_accepted` remains **false** and `user_outreach_authorized`
remains **false**, regardless of this source gate.

The combined manual offline review can summarize *previously saved* City batches,
but **never starts** an opt-in CKAN request or creates a schedule.

### Existing November 7 archive: reproducible baseline, not new collection

The user-supplied ZIP was locally inspected without running Radar's collector:
- Archive SHA-256:
  `decf2df6d535018a2f0c280c3127f4391de3a4a74d420c77b5cce509932486ea`
- Included daily CSV SHA-256:
  `a4d0f1ee098e30dd504dcb7aa00e8ee13471ba396e874e8748473f7ca118b13d`
- **151** Toronto project-folder records; **220** unique valid original
  permit/revision references, no malformed mixed-folder keys; **46** folders
  containing more than one original source record.
- Source date relative to November 8: **67** within 7 days, **28** 8–30 days,
  **34** 31–180 days, **22** older than 180 days. These are **source dates,
  not guaranteed first-publication dates**.
- Stages include 38 `Inspection`, 22 `Permit Issued`, 20 `Under Review`,
  8 `Application On Hold`, 2 `Refusal Notice`, 2
  `Revocation Pending`. None of these proves buying intent.
- **0** Toronto direct permit-record URLs in that daily export; the original
  collector `radar.sqlite` was **not included** in the ZIP; **0 live official
  CKAN rows** were independently fetched in this development session.

These numbers are historical snapshots and **not** claims of current open
supplier contracts, citywide permit coverage, or buyer verification.

## Acceptance before promotion

- CI: strict ID parsing, source SQLite read-only, payload-key matching, cross-address conflict, multiple permit stages, inactive history, failure isolation, network opt-in, bounded queries and explicit zero verified buyers/contracts.
- Check an actual local export/SQLite bundle and independently confirm a minimum of **20 individual permit records** and the status of their associated application folders with City original data.
- Verify source licence/terms and data refresh date before any client redistribution; preserve City attribution.
- Keep separate draft PR #155 and leave Industrial #152 / Activation #153 / normal daily runner unchanged until controlled field acceptance.

**A permit-level exact match is a materially stronger source citation than a generic portal URL, but it is not a buyer or procurement verification.**
