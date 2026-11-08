# Toronto exact-permit source acceptance — November 8, 2026

**Status: PASS for 20 sampled official source rows; NOT passed for full GTA Radar commercial release.**

## Evidence

- Archived source: user-provided `GTA_RADAR_RESULTS (13).zip`, previously exported on November 7; daily CSV SHA-256
  `a4d0f1ee098e30dd504dcb7aa00e8ee13471ba396e874e8748473f7ca118b13d`.
- Curated fixture: `tests/fixtures/toronto_archived_20_permits_20261107.csv`; 20 distinct Toronto project folders, 20 original individual permit/revision keys, and 20 distinct civic sites. Public permit metadata only; no builder or user contact information.
- **Real GitHub Actions run:** [Toronto 20 archived permit source acceptance #42493200636](https://github.com/sandeep89shaily-coder/gta-commercial-radar/actions/runs/42493200636).
- **Saved source evidence:** [artifact #13622606473](https://github.com/sandeep89shaily-coder/gta-commercial-radar/actions/runs/42493200636/artifacts/13622606473).
- Retrieved on **2026-11-08 at 15:07:44–15:07:46 UTC**.
- The isolated job made two bounded **10-record** checks against the official Toronto **Active Permits** CKAN DataStore, with strict exact `PERMIT_NUM`+`REVISION_NUM` filters and original City row projections. It never ran the production collector or changed `radar.sqlite`.
- Both source-package identities, resource metadata and exact-key filtered DataStore query mechanism had already passed the separate [live schema smoke workflow #42492652821](https://github.com/sandeep89shaily-coder/gta-commercial-radar/actions/runs/42492652821).

## Measured source-validation results

| Check | Result |
| --- | ---: |
| Original archived permit/revision keys tested | **20** |
| Unique projects and distinct civic sites | **20 / 20** |
| Exact City active-dataset records returned | **20 / 20** |
| Original IDs, revision, source addresses and saved field hashes consistent | **20 / 20** |
| Official source sample gate | **PASS** |
| Rejected/contradictory records | **0** |
| Historical/cleared fallbacks needed in this sample | **0** |
| Commercial supplier contracts independently verified | **0** |
| Buyer or public purchasing contact independently verified | **0** |

City status values in the checked 20 constituent permit records:
- **8** `Permit Issued`
- **5** `Application Acceptable`
- **4** `Not Started`
- **2** `Revision Issued`
- **1** `Refusal Notice`

### Six source-stage differences versus archived PROJECT summaries

| Site | Permit folder | November 7 project-summary status | November 8 exact constituent-permit status | Additional interpretation |
| --- | --- | --- | --- | --- |
| 333 Bay St | `26 265225` | Issuance Pending | **Permit Issued** | Project folder includes **2** original permit keys; do not automatically call this an individual-stage transition |
| 220 Yonge St | `26 265617` | Pending Parent Folder Review | **Permit Issued** | **3** original keys; aggregate project status differs from one checked `BLD` permit |
| 568 Passmore Ave | `26 265861` | Application Acceptable | **Not Started** | **3** keys; do not infer construction has not started or infer a true historical status transition |
| 673 Yonge St | `26 265928` | Application Acceptable | **Not Started** | One original permit key; the same permit's published stage differs between snapshots |
| 33 Bay St | `26 266222` | Application Acceptable | **Not Started** | One original permit key; the same permit's published stage differs between snapshots |
| 250 The East Mall | `26 266229` | Application Acceptable | **Not Started** | **3** keys; project summary cannot establish which individual permit changed |

**Important:** Four of the six differences involve multi-permit project folders. The old project summary is an aggregation and should **not** be described as direct proof of a temporal stage change for the checked constituent. This is why we created `gta_toronto_dossier_source_overlay.py` with exact ID/revision/site matching and explicit `PROJECT_AGGREGATE_DIFFERS_NOT_PROOF_OF_INDIVIDUAL_STAGE_CHANGE` labels.

The `Refusal Notice` record at **29 Jutland Rd** remained in the blocked stage and cannot be labelled an active sales opportunity.

## Follow-up: validated source-to-dossier handoff

The subsequent end-to-end GitHub Actions run [#42494508977](https://github.com/sandeep89shaily-coder/gta-commercial-radar/actions/runs/42494508977) independently rechecked the same original 20 archived permit/revision keys on November 8, 2026, then reconstructed the facility graph and research dossiers using **all 44 constituent permit/revision keys** from their 20 original project folders.

Its [saved live evidence artifact #13623051547](https://github.com/sandeep89shaily-coder/gta-commercial-radar/actions/runs/42494508977/artifacts/13623051547) contains the City acceptance records, original safe CKAN source projections, a graph, 20 research dossiers and the new **`GTA_RADAR_TORONTO_DOSSIER_SOURCE_EVIDENCE.csv`**.

| End-to-end measure | Verified result |
| --- | ---: |
| Original project folders reconstructed | **20** |
| All underlying constituent permit/revision keys | **44** |
| Exact *individual* City keys rechecked live | **20** |
| Dossiers correctly linked to the checked source record | **20** |
| Checked permits from multi-key project folders | **13** |
| Distinct source-summary/individual-stage differences | **6** |
| Blocked/refusal permit stages correctly held | **1** |
| Full project-folder permit completeness asserted | **0** |
| Independently established buyers or open contracts | **0** |

The handoff refuses to join a City source record to a dossier unless the exact project ID, original included permit key, civic address, time freshness, source query, accepted CSV SHA-256 and source sample gate all agree. It writes **an overlay**, never silently changes the original project/dossier status or authorizes outreach. All thirteen multi-permit dossiers remain only **partially checked**.

**The source gate is a meaningful technical acceptance achievement, not a commercial launch gate.** Actual company and buyer relationships, current procurement opportunities, public business contacts, a ten-lead customer-ready sample and two paying pilot customers remain outstanding.

## Product implications and next acceptance

**Confirmed:** The City endpoint is reachable from a GitHub Actions environment, the original twenty IDs are found in its active permit DataStore, their civic locations agree with Radar, and exact-key queries can populate reproducible source-evidence records.

**Not established:** The City's dataset updates in real time; every project permit/revision is present; construction actually started; an owner/tenant/operator is independently identified; an unawarded supplier work package exists; a public buyer contact has purchasing authority; ten commercially actionable opportunities exist; or two paying pilots exist.

Next steps should focus on linking this sampled verified source to the actual facility dossiers while retaining separate constituent-permit stages, then checking operator/buyer and procurement availability for the most promising recent issued and planning cases. No changes to scheduled runs, main daily collector, pilot PRs #152/#153 or default branch.

### Licence

Contains information licensed under the Open Government Licence – Toronto.

Official licence: https://open.toronto.ca/open-data-licence/

This is an independent research audit. The City of Toronto does not endorse GTA Radar.
