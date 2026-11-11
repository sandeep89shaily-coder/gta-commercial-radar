# Radar Current State — 2026-11-08 (draft PR #155)

## November 10 continued priority 3 + 4 source acceptance — PR #172

Owner historical November 10 results ZIP was recovered and reviewed: **4,198 commercial activation review candidates**, **139 same-site links**, **zero independently verified openings**; industrial ERO ledger **156 cards**, prior cursor **19 successfully parsed**, **4 equipment findings across 3 distinct original notices**, **0** proven open procurement or specific buyers. Do not replace these with the older November 7 two-signal baseline.

The latest GitHub live official [five-city workflow #42952671824](https://github.com/sandeep89shaily-coder/gta-commercial-radar/actions/runs/42952671824) passed its targeted regressions and observed **10/10** current Burlington posts parsed, **16** exact source file-ID candidates, **zero** parse failures and **zero** new-on-baseline alerts. The two pages previously excluded (800 Burloak, Nelson Quarry) now provide three additional exact City IDs. No citywide, first-publication, procurement or independent Windows repeated-run acceptance is conferred. Vaughan still robots denied; Kitchener not refetched.

PR #172 introduces an evidence-only, offline manual pilot acceptance pack with balanced **20-record activation source queue**, **10 different exact-site/unit dossier queue entries**, and exact ERO notice recheck queue; all unverified. It also excludes unambiguous non-site ERO policy bulletins from unchanged cursor retries while preserving revisits after source changes. Keep all earlier manual schedule and source access restrictions. See [continued priority 3+4 checkpoint](PRIORITY_3_4_CONTINUED_ACCEPTANCE_20261110.md).

## November 10 completed owner-priorities 3 + 4 checkpoint

**Merged:** [PR #171](https://github.com/sandeep89shaily-coder/gta-commercial-radar/pull/171) at `ee6e829d2e361ef1c23db410255767c2e7869245`. [Windows/Linux 3.11/3.12 all four CI jobs passed](https://github.com/sandeep89shaily-coder/gta-commercial-radar/actions/runs/42929549982); separate [five-city live-source acceptance workflow](https://github.com/sandeep89shaily-coder/gta-commercial-radar/actions/runs/42929550077) passed its 16 targeted tests.

**First post-repair, official-source GitHub sample, not owner's Windows:** Burlington index selected 10 permitted city project pages; 8 parsed with 13 application-ID rows; 2 (`800-burloak-dr`, `burlington-nelson-quarry-extension`) lacked recognized file-number sections. Status `PARTIAL_OFFICIAL_PAGE_COLLECTION`, 0 conflicting IDs, 0 `new_or_changed` on baseline, 0 verified new opportunities or citywide completeness. Old Burlington `.aspx` still redirects. Vaughan blocked by `POLICY_DENIED:ROBOTS_ACCESS_DENIED`; Kitchener not recollected in this scoped workflow (prior Windows robots denial still applies).

**Merged source guards:** duplicated official municipal IDs with conflicting pages now receive full HOLD; industrial ERO current official notice overrides stale manual excerpts and failed official rechecks preserve prior evidence under HOLD; activation rejects contradictory inline-suite/structured-UNIT sites. Buyer, procurement and actual opening remain unverified; manual only, no schedules/budget/outreach changes.

## November 10 — owner-prioritized municipal and two-pilot integrity checkpoint

User priority is **(3) Burlington/Vaughan/Kitchener reliability first**, followed by **(4) industrial equipment and commercial activation pilots**. The commercial lead-qualification/outreach expansion is not the immediate coding task. See [PRIORITY_3_4_SOURCE_AND_PILOT_GATES_20261110.md](PRIORITY_3_4_SOURCE_AND_PILOT_GATES_20261110.md).

- `gta_five_city_application_recovery.py`: conflicting official pages for one application ID now cause a full identity hold instead of choosing the first page; count only unambiguous application records and protect original first-observed ledger.
- `gta_industrial_equipment_pilot.py`: a successfully checked latest original ERO notice supersedes archived manual excerpts; failed/changed official rechecks cannot be cleared by a stale manual excerpt and preserve older evidence under HOLD.
- `gta_commercial_activation_pilot.py`: contradictory inline suite and separately published unit cannot generate a candidate or same-site link.
- These changes are being regression-tested in an isolated PR; no authorized new live source collection has been run in this GitHub-only checkpoint. Most recent actual Windows sources remain Burlington old-index redirect, Vaughan HTTP 403, Kitchener robots denied. Do not claim full city coverage, equipment procurement, business opening or buyer.

## November 10, 2026 — main-branch checkpoint (supersedes the November 8 branch-local snapshot)

- The verified current `main` head before this safety change was `bd96258475c355b54c14ec1028b8d06e93bc124b`. The `Radar tests` workflow completed successfully: [run 42922604522](https://github.com/sandeep89shaily-coder/gta-commercial-radar/actions/runs/42922604522). This is **code regression**, not live supplier/buyer acceptance.
- PRs #152 (industrial), #153 (activation), #154 (AI harness), #155 (facility graph) were **closed without merging** on November 9. Related manual pilot files now exist on main; source-controlled implementation does not confer pilot acceptance or confirm that those draft PRs were merged. Five older draft PRs #74–#78 remain open. Root `AGENTS.md` is absent; `GTA_RADAR_NORTH_STAR.md`, `GTA_RADAR_RESEARCH_REGISTER.md` and the current release gates remain authoritative.
- New main features by November 10: canonical Burlington index repair and strict official post validation; permission-gated Vaughan/Kitchener CSV role recovery; manual exact application ID/civic-site role reconciliation; controlled Pickering/Ajax/Niagara Falls/Barrie expansion-readiness audit. All are **source/evidence research**, not a claim of 20-city verified production coverage.
- The latest available Windows ZIP before the repair showed Burlington redirect, Vaughan 403 and Kitchener robots denial; post-repair two-run official collection acceptance is **still missing**. No bypass or change to the manual daily schedule is authorized.
- **P0 safety fix MERGED via PR #170** (squash `a04e32aea489f670bcdc5245c61c9a0c5bdab0fa`): Toronto source-to-dossier overlay now checks the actual separate `site_unit` column, conflicting inline/address suites, exact source key versus permit/revision components and duplicate accepted constituent keys. Eight added regression cases; [CI #42925874196](https://github.com/sandeep89shaily-coder/gta-commercial-radar/actions/runs/42925874196) passed **all four** Windows/Linux Python 3.11/3.12 jobs at final PR head `e4a73a4f`. This is an offline evidence-integrity checkpoint only, not a buyer, project or live source acceptance.
- The industrial ERO pilot's last user evidence remains 5/5 parsed notices and 2 distinct equipment findings, **0 verified purchasers and 0 verified open packages**; next broader official, permitted manual evidence batch has not been accepted. Toronto 20-record proof remains source/sample-only, not buyer or procurement validation.

**Release boundary:** Preserve working main and the original snapshots. Keep the shared US$0.25/day DeepSeek ceiling, read-only/manual isolated pilots, hold reason provenance, source date versus Radar observation date, no automatic outreach, and independent purchaser/work-package checks. Do not increase advertised municipal coverage or commercial claims without live acceptance.

This checkpoint is branch-local and is **not** production release acceptance. The default branch remains `main`; the canonical strategic scope is `GTA_RADAR_NORTH_STAR.md` and the full source backlog is `GTA_RADAR_RESEARCH_REGISTER.md`.

## Implemented and demonstrated
- Default main has source-aware regional commercial review, private vs government opportunity ranking, original-source exclusion and hold classifications, five-city evidence/recovery reporting and manual daily desktop runner.
- Draft PR #155 has an **isolated/manual-only** facility evidence graph, exact-site research dossiers, role review, Toronto source identity acceptance, 20 original City-rechecked individual permit keys, 44 constituent keys underlying 20 original folders, and 20 City-scoped commercial qualification records. Do not mistake sampled permit verification for full project verification.
- Official City CKAN sample and integrated 20-dossier recheck succeeded in isolated GitHub Actions (see `TORONTO_20_LIVE_SOURCE_ACCEPTANCE_20261108.md`). The City cost fields provide 14 numeric estimates totaling CAD 6,525,090, not current tenders.
- 12 publicly documented business routes across 11 dossiers are research contacts only; **0** project-specific buying authorities, specific GCs, open supplier work packages or outreach authorizations are verified.
- Import gate added on PR #155: each City scope source URL must have the official expected resource, exact individual permit and revision filters, and matching project folder/site evidence. Imported research rows no longer receive unconditional verification flags. Negative regression tests cover mismatches.

## Unfinished / blocked
- Complete current CI of PR #155 before any merge decision; qualification report run at commit `5d490012` passed, full multi-platform tests were pending at this checkpoint.
- Independently verify the permit-specific applicant/tenant and GC, current unawarded supplier packages and deadlines; public property-manager/leasing routes alone are insufficient.
- All 13 multi-key dossier folders need constituent completeness checks before folder-level certainty. The original local `radar.sqlite` and current Windows live run are not accessible in this branch-level work.
- PRs #152 and #153 remain separate research pilots; PR #154 AI harness is separately draft. Do not merge overlapping architectures without review.
- Municipal restrictions (Richmond Hill/Newmarket and unreliable GIS pages), source timestamp attribution, real pilot-customer demand, and two paying customers remain unresolved.

## Non-negotiable boundaries
Evidence-first, original source and observation timestamps; source age != Radar first publication. No inferred buyer or open supplier contract, no unrestricted portal access, no paid-AI budget change (US$0.25/day shared ceiling), no default-run/scheduling changes, and no automatic sales outreach.

## Resume
Read `RADAR_NEXT_ACTIONS.md`, PR #155 description and recent CI before editing. Preserve the working code and original source exports. Do not restart completed City CKAN or public business contact research absent concrete contradictory evidence.
