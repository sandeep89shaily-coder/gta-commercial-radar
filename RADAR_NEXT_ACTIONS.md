# Radar Next Actions — checkpoint 2026-11-08

## Pilot delivery priority — owner direction 2026-11-08

The core goal is to **ship bounded, verified pilot capability**, not keep tested modules indefinitely in draft. Latest Linux/Windows Radar test workflows on PRs #152, #153, #154 and #155 are all green; green CI alone does not establish source or buyer validation.

1. **Industrial equipment PR #152 — first controlled release candidate.** Preserve successful 5/5 official notice parsing and 2 distinct equipment signals from the third live ZIP. Run a wider capped, permission-checked live evidence sample; cross-check equipment change, location, stage and old/new notices, then measure supplier relevance and duplicates. Keep buyer/open-contract fields unverified. Move from draft only after specific acceptance checks, and merge manual pilot only (not scheduled sales automation).
2. **Commercial opening / activation PR #153 — second controlled candidate, parallel evidence lane.** Run its read-only pilot against the real current Radar SQLite on Windows; audit at least 20 individual source records, rejection counts and 10 source-backed dossiers, distinguishing licence issuance, permitting, occupancy and actual opening. No tenant assumption from same address. Merge isolated manual pilot after a passing real acceptance, before claiming opening predictions.
3. **Shared facility graph PR #155 — enabling dependency, not a reason to block pilots.** Maintain exact-ID/unit/site protections and source-age distinctions. Integrate reused components via reviewed incremental work, not by merging 126 commits into production without dependency tests. Its 20 Toronto permit sample is verified; its buyer and procurement validation is not.
4. **AI harness PR #154 — defer promotion until pilot signals are accepted.** Run free/no-spend actual-data preflight, validate shared US$0.25/day budget, lock, safe resume and evidence gating. No new autonomous outreach, daily scheduling or paid research path.

**Release policy:** Draft is a review state, not proof of broken software. Promote a *manual, isolated pilot* once code CI, permitted live source sampling and auditable rejection/hold handling pass. Production daily workflow and commercial lead claims require stronger separate gates. Do not conflate a tested pilot with 10 qualified sales opportunities or two paying customers.


## P0 — Close the source-import safety checkpoint (draft PR #155)
1. Confirm all GitHub CI jobs green at latest branch head, not merely an earlier successful workflow. Verify the isolated 20-row qualification CSV and status JSON still reproduce the 20/14/12/11 counts; never infer new live customer value from these fixed-source fixtures.
2. Verify missing/invalid source permit key, exact-revision filters, resource ID, source site or source validation marker cause fail-closed import and no output files. This is research evidence reconciliation, not official cryptographic authentication.
3. Preserve PR #155 as draft until cross-platform test and full end-to-end commercial acceptance. Do not merge the other pilots blindly.

## P1 — Advance permit-specific commercial qualification
1. Select the best **preapproval / pre-start** Toronto dossiers and track the original permit ID, exact unit/address, official scope, date checked, project applicant, proposed buyer organization, the source for each role, current GC/contractor, work package, sourcing owner and any actual tender/award/deadline.
2. Every role/contract claim requires independently checked **project-specific** evidence. Keep `UNKNOWN` distinct from `NO` and `NOT_YET_CHECKED`. Leasing agents, landlord review contacts, and municipal estimates do not meet a sales-ready standard.
3. Make the review artifacts auditable and conservative; prioritize an actual current unawarded opportunity rather than increasing the count of superficial contacts. No outreach until the owner's release criteria are met.

## P2 — Resolve source reliability and geography gaps
- Inspect the real latest Windows collector manifest for Burlington, Vaughan, Kitchener, Richmond Hill and Newmarket; use authorized official exports and exact IDs, no restriction bypass. Compare source freshness to the November 7 archived baseline.
- Integrate PR #152 industrial equipment and #153 commercial activation pilots into the shared facility graph only after identity, duplication, evidence and end-to-end tests; keep PR #154 AI harness opt-in and within shared US$0.25/day budget.

## Product acceptance (still NOT met)
- At least 10 independently verified, actionable, source-dated dossiers with actual roles/available work independently checked and defensible detection time.
- Two paying pilots; measured recall, precision, lead time and customer outcome versus independent alternatives.

Sources of truth: `GTA_RADAR_NORTH_STAR.md`, `GTA_RADAR_RESEARCH_REGISTER.md`, PR #155 and this checkpoint. Existing working stages are to be preserved.
