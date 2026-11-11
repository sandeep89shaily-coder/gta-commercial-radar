# Priority 3 + 4: source-backed pilot continuation — November 10, 2026

## Release checkpoint: merged PR #172

[PR #172](https://github.com/sandeep89shaily-coder/gta-commercial-radar/pull/172) was merged to main at `a141120c078007feb2b0c33cc8befa79c2f67669` after green [4/4 Windows/Linux CI jobs](https://github.com/sandeep89shaily-coder/gta-commercial-radar/actions/runs/42952904773) and passing [official five-city acceptance workflow](https://github.com/sandeep89shaily-coder/gta-commercial-radar/actions/runs/42952904795). The code is fit for **source-only manual pilot review**, not automatic sales lead publication or a declaration of completed restricted municipal feeds.

**Branch checkpoint: PR #172.** This document supersedes the earlier 8/10-page Burlington GitHub source sample, while preserving historical run manifests, the existing Windows daily runner, and the owner's collected local data.

## Evidence from prior owner archives (not a new Windows run)

Using the already shared November 10 `GTA_RADAR_RESULTS (15).zip`, the isolated commercial-activation pilot contains **4,198 candidate event records** and **139 same-civic-site links**. These include licence/permit activity, not 4,198 businesses actually opened. No tenant, true opening or purchaser verified.

The same owner's industrial pilot has **156 ERO ledger cards**, **19 prior successful official details**, **4 equipment-change findings across 3 exact original notices**. Two were detected in later owner data beyond the previously documented November 7 baseline. Zero verified open procurement and buyers. Preserve the older pilot cursor and archived `INDUSTRIAL_PILOT` files; do not rerun all 156 notices or overwrite the baseline. Some repeated rejected pages are explicit policy bulletins, lacking a physical proposed equipment site.

## Actual official Burlington live-source acceptance

On [PR #172 five-city source CI](https://github.com/sandeep89shaily-coder/gta-commercial-radar/actions/runs/42952671824), the policy-aware official current City index returned **10 selected official Burlington project post URLs; all 10 pages parsed; 16 application-ID rows; 0 held identity conflicts or page parse failures; 0 'new or changed' records on the first baseline**. This corrects the previous **8/10 and 13** result from PR #171. Original City links:
- [800 Burloak Dr.](https://www.burlington.ca/news-and-notices/posts/current-development-projects/800-burloak-dr/): IDs **505-13/26 and 520-16/26**.
- [Burlington Nelson Quarry Extension](https://www.burlington.ca/news-and-notices/posts/current-development-projects/burlington-nelson-quarry-extension/): ID **505-04/20**, historically dated; it is not a newly approved buyer's work package.

This measured success applies **only to ten selected current posts from the runner's source index**, NOT all Burlington applications or two successive Windows runs. The file IDs are initial-source candidates only, not first-publication claims, 16 distinct commercial projects, verified GCs or open tenders.

Vaughan remains `POLICY_DENIED:ROBOTS_ACCESS_DENIED` in the same CI source run. Kitchener was not live queried there; the earlier owner Windows observation was robots denied. No bypass is made. Continue the existing unsent publisher access requests, authorized GIS/CSV export route, site and applicant evidence; York Region records are not equivalent to Vaughan PLANit.

## Industrial source-review efficiency

`gta_ero_notice_detail.py` now uses the visible *combination* of exact `Bulletin summary` + `Bulletin details` headings and *absence* of labelled proposal details and site address to mark an ERO policy page `NON_INSTRUMENT_BULLETIN`. This is not a rejected equipment opportunity, and the cursor may suppress re-fetches **only while its original card fingerprint is unchanged**. Missing HTML, ambiguous documents, access errors and potential equipment-source pages remain retryable or held, never silently published.

The pilot reports **equipment findings and distinct exact ERO notice IDs** separately; do not claim four distinct buyer sites or four confirmed orders.

## Human-review acceptance tooling

New isolated `gta_pilot_acceptance_pack.py` ingests existing `GTA_RADAR_RESULTS/INDUSTRIAL_PILOT` and `COMMERCIAL_ACTIVATION_PILOT` CSV/JSON reports and writes only under `GTA_RADAR_RESULTS/PRIORITY_3_4_ACCEPTANCE_PACK`:
- `INDUSTRIAL_NOTICE_RECHECK.csv`: one exact ERO notice per row plus current source audit status, original evidence hash where recorded, equipment changes, buyer/contract UNKNOWN, and manual recheck fields.
- `ACTIVATION_SOURCE_SAMPLE_20.csv`: 20 recent existing source events, round-robin by original source (Toronto licensing and permits, Brampton and Mississauga building permits), all `NOT_YET_RECHECKED`.
- `ACTIVATION_FACILITY_DOSSIERS_10.csv`: 10 distinct civic address+unit groups, balanced across municipalities when possible. Co-location alone is NOT the same tenant.
- `ACCEPTANCE_PACK_STATUS.json`: existing counts, available report file paths and explicitly **0** verified original openings, buyers or supplier contracts.

The isolated launchers generate the pack automatically *only after the user manually starts each pilot*. Existing production collector, original `radar.sqlite`, 16-city source configuration, paid AI US$0.25/day ceiling and outreach schedule are unchanged.

## Next acceptance gates, not yet finished

1. Two **separately dated original Windows** Burlington manual runs, preserve original manifest/ledger, measure stable file IDs, missing past development pages, status changes and first-publication evidence without calling baselines new leads.
2. Publisher-permitted Vaughan/Kitchener original file-ID feeds or exports, source terms, exact ID+site comparisons; no 403/robots bypass.
3. Pilot original-source recheck: no more than ten distinct unreviewed/changed ERO notices, confirm equipment/site/stage/prior approval and actual vendor purchasing process separately.
4. Original commercial activation sample: at least 20 individually rechecked original records and 10 human-reviewed facility dossiers, including cancellations, renewals, unit conflicts, tenants and actual opening evidence. Source-backed queue generation is **not** the human audit itself.

**Completion classification:** code/test checkpoint only. Not a verified 16-city production operation, 10 sale-ready opportunities, confirmed unawarded purchasing contract, or paid commercial pilot acceptance.
