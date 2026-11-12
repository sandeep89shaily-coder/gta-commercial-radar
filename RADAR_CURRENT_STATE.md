# Radar Current State — 2026-11-11 (current main release gates)

## November 11 — Regional source-to-shortlist repair and producer city truth MERGED

**Current main code:** [PR #177](https://github.com/sandeep89shaily-coder/gta-commercial-radar/pull/177) squash-merged as 917da54cc04381cca18c68cd17ed95b1f6694a6d, followed by [PR #178](https://github.com/sandeep89shaily-coder/gta-commercial-radar/pull/178) squash-merged as 601054ebcd652a2c3f99668e7b637820b529b424. Both PR-head test matrices passed four Windows/Linux Python 3.11/3.12 jobs. Primary source-file quality, urban-region ranking and executable manual integration are covered by tests, **not** proof of a new owner-side Windows run.

**Measured owner November 11 archive BEFORE these code changes:** 148 V6 newly observed/changed source rows (146 Toronto, 2 labelled Peel despite Brampton street addresses), 1,523 canonical application files across 14/16 main municipality candidates, and private top ten 8 Toronto + 2 Burlington. The existing V6 qualification queue also retained 37 Brampton, 11 Mississauga, 2 Peel-labelled Brampton and 2 Waterloo records; none verified as sale-ready.

**PR #177 fixed** the data-to-selection gap by using original official application/permit/site-plan identifiers from the existing V6 qualified source evidence in the PRIVATE **investigation** lane. AI contact names, sale-ready flags and source event dates are not promoted into buyer/publication verification. It also normalizes Peel-suffixed Brampton civic sites, selects a ten-project evidence-floor multi-region research shortlist with relaxed caps where necessary, and adds a read-only 16-city + separate experimental GGH/new-four municipal source failure/recovery scorecard. The integrated manual daily report now links the new source-health CSV and JSON. All new city pilots remain experimental and excluded from verified citywide coverage.

**PR #178 fixed** the true upstream locality problem in opportunity_engine.py: official region labels such as Peel are translated to Brampton only with an unambiguous municipal source ID or an explicitly named city in the address; unresolved regional labels remain regional. Covers original municipal current records and recorded updates, without rewriting historical SQLite source evidence.

**Remaining original-source gates:** User must run the updated one-click launcher once on the original Windows workspace and share the new dated GTA_RADAR_RESULTS ZIP. Compare the new PRIVATE_TOP_10 and MUNICIPAL_RECOVERY_SCORECARD with the original November 11 inputs; audit real source statuses and at least 20 original municipal files. Toronto AIC and Brampton planning feeds have restricted/failed source paths; Vaughan/Kitchener need permitted access. No exact buyer or currently available unawarded supplier contract verified, and no claim of improved conversion or additional citywide coverage yet. Manual-only schedule and the shared US$0.25/day DeepSeek ceiling remain unchanged.

[Detailed November 11 fix and acceptance notes](REGIONAL_COLLECTION_QUALITY_FIX_20261111.md).



## November 11 — full manual one-click integration COMPLETED in merged PR #174

**GitHub release code complete:** [PR #174](https://github.com/sandeep89shaily-coder/gta-commercial-radar/pull/174) merged into `main` at `f722cac70c51fb0c14bfdcbe1bb85d2ad35bbc6f`; the final PR-head [four-platform CI run #43031475039](https://github.com/sandeep89shaily-coder/gta-commercial-radar/actions/runs/43031475039) passed all Windows/Linux Python 3.11 and 3.12 jobs. `RUN_GTA_RADAR_TODAY.bat` is the canonical **manual** one-click entrypoint; the two older full-run shortcuts delegate to it. It safely fast-forwards ONLY code with the existing tested `desktop_update.py` origin/dirty/divergent/compile gate, then executes the existing six-stage full orchestrator in one separate Python process. Daily original collection occurs once, industrial ERO remains bounded at 10 permitted notices, commercial activation and facility/official evidence review remain read-only, and the AI harness remains free-only without exceeding the shared US$0.25/day paid AI budget.

**Dated handoff now built in:** `gta_daily_result_archive.py` creates a bounded timestamped review ZIP in the owner's `GTA_RADAR_EXPORTS` folder. It includes source ledger/CSV, reviewed PDF/HTML outputs, industrial and activation manual review and SHA-256 manifest, excludes original `radar.sqlite`, tokens and logs, and labels source verification honestly. A ZIP packaging failure returns nonzero and remains visible in full-run status. All CI tests passed.

**Execution distinction:** Today's **original full owner-side Windows collection has NOT been executed inside this GitHub connector session** (no access to PC's retained `radar.sqlite` and keys). Code and test completion are not a live daily report. The operator must manually launch the installed script to create a current dated ZIP; the assistant should not represent CI fixture runs as daily customer intelligence. Source policies Vaughan/Kitchener and independent buyer/actual opening validation remain external gates. [Operator runbook](RUN_GTA_RADAR_TODAY_20261111.md).

## November 11 — Today's one-click integration release candidate

User requested "integrate everything time to run for today." The existing six-stage manual `gta_monday_full_run.py` collector+pilot architecture remains preserved. A current-day manual launcher `RUN_GTA_RADAR_TODAY.bat` is being added to update the *installed code only* through the already-tested safe `desktop_update.py` fast-forward gate **before** opening the integrated runner. Existing shortcuts `RUN_TOTAL_INTELLIGENCE_TODAY.bat` and `RUN_ALL_GTA_RADAR_MONDAY.bat` delegate to the same launcher; no schedules, AI budget or Outreach changes.

The final manual orchestrator now packages the completed day's status, key source files and review-only pilot outputs into a **dated bounded ZIP under `GTA_RADAR_EXPORTS`**, with a SHA-256 file inventory, no original SQLite/secret keys/logs, and an honest freshness/failure label. A ZIP export error is surfaced and blocks a clean full-run exit. See [November 11 manual run instructions](RUN_GTA_RADAR_TODAY_20261111.md).

**Acceptance boundary:** New code and CI alone cannot execute today's user-local Windows collection; the retained original `radar.sqlite`, live data sources, and API settings stay on the PC. Official-source GitHub smoke checks prove only source-specific network access, never a full user run. Preserve 16-city source restrictions and original records. The work needs Windows/Linux CI at the PR head before declaring this a tested release.

## November 11 — P3/P4 verification and historical-run reconciliation merged

[PR #173](https://github.com/sandeep89shaily-coder/gta-commercial-radar/pull/173) **merged** at `a59a72bbd3208b7a63ef19ce9478d0ea6b12ee6c`. All four Windows/Linux Python 3.11/3.12 jobs passed in [Radar CI #43028553192](https://github.com/sandeep89shaily-coder/gta-commercial-radar/actions/runs/43028553192); bounded official five-city source acceptance passed in [#43028553034](https://github.com/sandeep89shaily-coder/gta-commercial-radar/actions/runs/43028553034).

**Actually completed externally:** Two separate government data-access requests sent from the connected Radar Gmail to official Vaughan and Kitchener contacts (Nov 11), both pending reply; weekday reply-only watch enabled, no automated Radar scheduling. Three original ERO notices and original sites/proposal stage/equipment scope independently checked; **not** verified purchasing contracts. Nov 9 vs 10 saved Windows ZIPs independently reconciled for **2,833 identical source hashes/stages/sites**, **1,365 Toronto licence records only in later accepted output**, and **4 equipment changes from 3 ERO notices**. This is archive continuity, not original-municipal-source authentication. The two archived Burlington runs were blocked; the new source parser's 10/10-page, 16-ID GitHub sample is **not** a substituted owner's two-run validation.

**Now merged:** `gta_pilot_archive_reconciliation.py` produces conservative cross-run 20 source and 10 facility audit queues without false opening/buyer claims. `gta_five_city_application_recovery.py` holds previously unseen but **undated** City planning file IDs on already baselined municipalities as `FIRST_OBSERVED_UNDATED_HELD`; these cannot become falsely dated new opportunity alerts after a parser repair. True previously recorded changes retain `RECORD_CHANGED` review events. Six new regression tests passed.

**Still blocked:** two post-fix owner Windows Burlington runs, municipal access grants and official exports, original 20 activation record / 10 facility tenant rechecks, fresh original ERO cursor batch and verified actual procurement packages. No lead/outreach automation. Full evidence: [Nov 11 source verification](PRIORITY_3_4_20261111_VERIFICATION.md).

## November 11 — remaining P3/P4 validation and official source access

**Public independent original-source checks:** Three industrial ERO equipment notices **026-1152, 026-1155, 026-1021** are verified against live original Environmental Registry pages as **Proposal** at their exact industrial sites, with specific dust collector/scrubber, two cremation units, and boiler/cooling-tower changes. Exact documentation at [2026-11-11 original verification](PRIORITY_3_4_20261111_VERIFICATION.md) and [ERO evidence CSV](evidence/ERO_3_SOURCE_RECHECK_20261111.csv). **0 buyer identities and 0 unawarded purchase packages independently verified.**

**Municipal access requests sent:** November 11 from the connected `gtaradar18@gmail.com` Gmail account to City of Vaughan Development Planning and City of Kitchener GIS. Both official recipients and sanctioned CSV/GeoJSON access paths are publisher-supported, but **0 replies / 0 access approvals** at checkpoint. Separate weekday Gmail reply watch created; no Radar collection schedule change or restricted crawling.

**Historical original Windows archives reconciled:** November 9 vs November 10 GTA_RADAR_RESULTS ZIPs show **2,833 common exact activation record keys with 2,833 stable source hashes, site and classification**, and **1,365 new-in-output Toronto licence records**, NOT new public notice dates. 4 equipment findings belong to 3 exact ERO notices. Both ZIPs' Burlington official collector is blocked despite their preserved 11-ID official seen ledger; **do not call the archives two successful post-fix runs**. Earlier GitHub source runner remains 10/10 current posts and 16 official IDs.

**Code protection in development:** Reproducible ZIP-to-ZIP evidence reconciliation generates a source-labelled 20-record, 10-facility and ERO queue with no false external verification. The five-city collector now holds *first detected* undated municipal application IDs on a previously baselined city instead of fabricating a fresh application notice after the parser was fixed; observed changes to previously tracked records still appear as changes. CI for this checkpoint is required before merge.

**Unfinished genuine external dependencies:** Two separately dated owner Windows post-fix Burlington collections, actual authorized Vaughan/Kitchener exports, at least 20 verified original municipality record checks and 10 tenant/activation dossiers, fresh bounded ERO cursor sample and independently evidenced buyer/procurement stages. No automatic outreach or paid-AI budget changes.

## November 10 owner priority 3+4 — PR #172 merged, verified source sample

**Completed development:** [PR #172](https://github.com/sandeep89shaily-coder/gta-commercial-radar/pull/172) was squash-merged into main at `a141120c078007feb2b0c33cc8befa79c2f67669`. Latest PR-head [cross-platform CI #42952904773](https://github.com/sandeep89shaily-coder/gta-commercial-radar/actions/runs/42952904773) passed all four Windows/Linux Python 3.11/3.12 jobs. [Five-city official live source CI #42952904795](https://github.com/sandeep89shaily-coder/gta-commercial-radar/actions/runs/42952904795) passed, following the prior source sample #42952671824 which showed Burlington **10/10** official current pages parsed, **16** original application-ID candidates, 0 page failures/conflicting IDs, 0 first-baseline newly published alerts and 0 verified commercial leads. Vaughan robots denied; Kitchener not re-collected.

**User November 10 archived actual results (not a fresh Windows collection):** Commercial activation: **4,198** candidate events, **139** same-site cross-source rows, **0** verified business openings. Industrial ERO: **156** ledger cards, **19** prior detail successes, **4** equipment-change findings from **3** distinct original notices, **0** independently verified buyers/open supplier contracts. The newest signals supersede the older two-signal historical checkpoint; do not erase either historical audit.

**Now on main:** Burlington parser handles exact `File Numbers` labels in the current page templates; original-file source validation remains strict. ERO cursor suppresses proven non-site policy bulletins unless publisher card changes. Both existing manual pilot launchers create an isolated **20-source-row activation, 10 distinct facility, and exact ERO notice human-review queue**, all `NOT_YET_RECHECKED`; no source, tenant, purchaser or business opening is promoted. Canonical details: [priority 3+4 continued acceptance](PRIORITY_3_4_CONTINUED_ACCEPTANCE_20261110.md).

**Still incomplete:** two separate owner Windows Burlington collections, publisher-authorized Vaughan and Kitchener source access, independent 20-record/10-dossier human audit, original equipment stage and supplier-package verification, paid pilots. No changes to the manually controlled daily run, original SQLite, automatic outreach, nor shared AI US$0.25/day budget.

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
