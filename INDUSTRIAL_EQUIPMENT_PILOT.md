# Industrial equipment intelligence — isolated evidence pilot (2026-11-07)

**Status: manual-review prototype, NOT production lead discovery.** This does not edit the daily Windows launcher, alter the ERO collector, raise the shared AI budget, publish leads, or contact suppliers.

## Why this approach

The existing enabled source `ero_gta_environmental_instruments` stores ERO search cards in Radar's normal `data/radar.sqlite` database. Search cards contain the ERO number, title, notice stage and source dates but **not necessarily the proposal details**, so detecting a specific scrubber/boiler change from the existing `SUMMARY` would be misleading. This pilot requires a separate, manually checked, exact official ERO notice excerpt.

## Easiest Windows test

Double-click **`RUN_INDUSTRIAL_EQUIPMENT_PILOT.bat`** in the updated Radar code folder. This is a separate manual pilot launcher, **not** your normal daily GTA Radar runner.

It locates the existing Desktop/OneDrive `new data` workspace using Radar's established discovery code, opens the compatible `radar.sqlite` read-only, checks official robots rules and requests at most **ten** distinct full ERO notices. It creates only separate CSV/HTML/JSON reports under `GTA_RADAR_RESULTS/INDUSTRIAL_PILOT`.

If your workspace is elsewhere, call `py -3 gta_industrial_equipment_run.py --workspace "D:\Your\Existing\Radar\new data"`. Failure to locate an existing compatible database stops the run rather than creating a new one. If robots access is denied or unavailable, no ERO notices are fetched and the reason is written to the audit.

## First run on Windows

From the installed Radar code directory, open a command prompt:

```bat
py -3 gta_industrial_equipment_pilot.py --db "%USERPROFILE%\Desktop\new data\data\radar.sqlite" --results "%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS" --notice-csv "samples\industrial_equipment_notice_example.csv" --out "%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS\INDUSTRIAL_PILOT"
```

If the Radar workspace is in OneDrive or another directory, replace the paths accordingly. You can omit `--db` to test a notice CSV alone; those rows will correctly show `radar_record_present=NO` and no Radar first-observed timestamp. You can omit `--notice-csv` to count source cards, but **no equipment change signals should be generated**: the search cards alone are insufficient.

Input notice CSV required fields:

- `ero_number`: exact NNN-NNNN form.
- `official_notice_url`: matching HTTPS `ero.ontario.ca/notice/<number>`.
- `proposal_details`: accurate text excerpt **from that official notice**, not a generated summary.

Recommended fields: `proponent,site_address,city,proposal_posted,notice_stage`. Enter the verified physical site address and city, **not registered office address**. The pilot accepts only an explicit Southern Ontario target-city list and records missing/out-of-area site cities as exclusions. This addresses a real false positive in the November 7 ERO output: York1's Dresden facility was treated as GTA-related by the upstream broad text filter. Do not import ERO's operator/proponent mailing address as the physical site without explicit location evidence.

The sample includes short official excerpts from <https://ero.ontario.ca/notice/026-1152> (Pinty's Delicious Foods Inc., Oakville; proposal posted 2026-11-06) and <https://ero.ontario.ca/notice/026-0424> (Bunge Loders Croklaan Canada Inc., Toronto; originally proposed 2026-04-17 and **decision already granted** on 2026-08-13). These are **two research examples**, not a live test of coverage or verified supplier opportunities.

## Opt-in official notice retrieval (experimental)

The pilot can now request up to **10 full ERO notices per run** from exact notice URLs already in Radar's read-only ERO ledger. It checks `https://ero.ontario.ca/robots.txt` first and **refuses all notice requests if robots policy is unavailable or disallows access**. It does not follow redirects, bypass restrictions, scrape search-engine results, fetch attachments or run AI. Its page requests are capped and delayed.

```bat
py -3 gta_industrial_equipment_pilot.py --db "%USERPROFILE%\Desktop\new data\data\radar.sqlite" --results "%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS" --fetch-official --fetch-limit 5 --out "%USERPROFILE%\Desktop\new data\GTA_RADAR_RESULTS\INDUSTRIAL_PILOT"
```

Use the **actual** established workspace path if it differs. The command is intentionally separate from the normal one-click daily launcher and **must not be scheduled** before site permissions, HTML field extraction, and coverage have been checked live. Both successful and failed URL attempts are included in the status JSON. A successful GET does not mean equipment extraction succeeded.

The extractor takes only the ERO page's labelled **Proposal details**, exact notice identity, explicit **Site address**, current stage and posted dates; it never treats the proponent's mailing address as the facility. An already-decided notice is marked `HISTORICAL_DECISION_REVIEW_ONLY`, not a newly available equipment purchase. ERO page layouts can change, so unrecognized pages fail closed. It also rejects out-of-scope cities such as Dresden even if a company name contains "York".

**Live-source acceptance remains unverified until the command succeeds on your Windows workspace with current robots access and the resulting original ERO pages have been manually checked.** Offline parser tests are not a substitute for live source coverage.

## Outputs

In the separate `INDUSTRIAL_PILOT` output directory:

- `GTA_RADAR_INDUSTRIAL_EQUIPMENT_REVIEW.csv`: one candidate per notice/equipment/action with specific source excerpt, ERO URL, proposal date, existing Radar observation timestamp when present, and any candidate same-site project link.
- `GTA_RADAR_INDUSTRIAL_EQUIPMENT_REVIEW.html`: review-only reader.
- `GTA_RADAR_INDUSTRIAL_EQUIPMENT_STATUS.json`: counters, rejected input, remaining limitations.

Same address + municipality yields **unverified candidate** only. Missing address, conflicting address, multiple projects, and missing project IDs never create verified links. Supplier availability and purchasing authority always remain **UNKNOWN** and **NO**.

## Test

```bat
py -3 -m unittest tests.test_industrial_equipment_pilot -v
```

Or use unittest discovery when `tests` is not an importable package:

```bat
py -3 -m unittest discover -s tests -p "test_industrial_equipment_pilot.py" -v
```

## November 7: third live run and distinct-notice review cursor

The third user-uploaded pilot returned **5/5 parsed ERO pages**, two distinct correct equipment findings, two explicitly excluded out-of-area facilities, and **zero verified purchasing contracts**. It also exposed a separate data join gap: Oakville's `GTA_RADAR_COLLECTION_MASTER.csv` describes **Pinty's Delicious Foods Inc. - 2714 Bristol Circle - 1403.071/01** but leaves the structured `address` field blank. The official Oakville record describes a proposed **254.4 m² expansion for processing equipment utilities**, with plans submitted in December 2025, February 2026 and May 2026. This is valid **same-site historical context**, not proof the ERO dust collector/scrubber proposal belongs to the municipal development scope.

The next manual Windows run selects up to **10 distinct unreviewed ERO notices** from the existing 155-card ledger rather than fetching the same five. The pilot saves its review cursor separately as `GTA_RADAR_ERO_REVIEW_CURSOR.json`. For backward compatibility, when that file is absent it seeds successfully reviewed notice IDs from the previous `GTA_RADAR_INDUSTRIAL_EQUIPMENT_STATUS.json`. Previously generated evidence rows are retained in the review CSV while new findings are appended, with a separate `new_equipment_candidates_this_run` metric. Failed retrievals do not silently become successes, and a changed source notice stage/last-updated timestamp makes a previously checked notice eligible for recheck.

Description-only municipal matches have separate `same_site_history_*` fields and carry the `UNVERIFIED_DESCRIPTION_ONLY_SITE_CONTEXT` label. This must **never** be treated as project-scope confirmation or an open supplier contract. Production collectors and the shared DeepSeek cap are unchanged.

**Run:** Double-click `RUN_INDUSTRIAL_EQUIPMENT_PILOT.bat` from the latest pilot branch. Reuse the SAME `GTA_RADAR_RESULTS/INDUSTRIAL_PILOT` folder so the previous status/rows can seed the new persistent cursor.

## Required acceptance gates before production

1. Validate original ERO record and the **full notice text** with an approved, lawful retrieval process and document evidence hashes. No assumption that the ERO search result contains the entire proposal.
2. Backtest on a fixed human-labeled sample of new, existing-only, cancelled and decision-stage records. Report precision and recall; no auto-promotion.
3. Measure exact-site and same-entity matches against the local Radar project ledger, rejecting multiple-tenant and company-headquarters false joins.
4. Verify at least ten commercially relevant *distinct* industrial changes, separate the proposal/decision stage from an open purchase, and benchmark against Industrial Info and accessible alternatives.
5. Interview specialist industrial suppliers and seek two paying pilot customers before integrating with the normal daily launcher.

**No procurement, contract, supplier need, funding, installation or construction start is asserted by an ERO equipment mention.**

## November 7 second live pilot audit

The user-provided `INDUSTRIAL_PILOT (2).zip` contained **155 source cards**, **5 attempted notices**, **4 successfully parsed notices**, and **two initially generated equipment rows** from Pinty's Oakville notice `026-1152`. The second generated row was incorrect: the source says **replace Line 3 dust collector with a scrubber** and separately **remove the limited operational flexibility condition**. The old regex incorrectly attributed the conditional removal to the scrubber.

The reviewed correction now emits **one replacement event** with `equipment=Dust collection`, `action=REPLACEMENT`, and `replacement_equipment=Scrubber`. This retains the evidence of a prospective scrubber at the facility without double-counting the change or inventing a scrubber removal.

The fifth notice, Five Star Farms `026-1160`, was incorrectly rejected for a missing site city. Its site-address section has an extra **Lots 9 & 10, Concession 1** line before **Kingsville, ON**. The parser now searches within that labelled address section for the actual city, and the target-area gate correctly excludes Kingsville as out of scope.

No verified purchasing opportunity or proven project join was established. These fixes require a fresh live check before production acceptance.


## November 8 continuation — source-change hold protection (PR #152)

The original 5/5 official source-parsing acceptance from the November 7 uploaded ZIP is preserved; no new live source claim is made here. The manual run now explicitly marks a **carried-forward** equipment row `SOURCE_CHANGED_OR_RECHECK_FAILED_HOLD` when its notice changes stage/source publication fingerprint but the new official detail has not been successfully recovered, or when an attempted exact-notice refresh fails (HTTP, source restriction or parser failure). Its buyer and procurement statuses stay `NO`/`UNKNOWN`.

- A successfully rechecked source still replaces earlier findings as before; a page with no supported equipment text does not leave an obsolete old finding.
- An unchanged previously verified notice can be carried forward as historical review evidence, not a fresh lead; the new status JSON counts `carried_forward_source_recheck_holds` and the HTML report shows **Evidence status**.
- The review cursor keeps failed IDs retryable; it does not mark failed requests as completed.
- Added mocked end-to-end regression for an ERO Proposal-to-Decision change followed by HTTP failure, plus unaffected previous evidence and retry behavior.

**Acceptance remains pending:** no fresh authorized 10-notice live run in this checkpoint, no confirmation of current equipment purchasing or buyers, and no automatic commercial promotion. Production manual daily launcher and shared AI budget unchanged. This is a source safety fix on the draft branch.


## November 8 source-payload acceptance hardening

The bounded manual ERO fetch now reconciles the fetcher's `DETAIL_RETRIEVED` audit with an **actual parsed source record** for the selected notice. The record must carry the exact selected official HTTPS notice URL, the source parser's explicit official-fetch provenance, a nonempty proposal, site address, and site city. Invalid or missing payloads become `DETAIL_REJECTED` with `SUCCESS_AUDIT_WITHOUT_VALID_SOURCE_PAYLOAD`, rather than contaminating the permanent review cursor.

This closes an important audit/results split: a source might appear checked in the cursor even though its usable evidence was absent, causing subsequent manual runs to skip that notice. Rejected items remain retryable; original evidence rows remain available and changed-source holds remain in force. Also reject URL query/fragment suffixes when importing stored source evidence.

Regression checks include successful audit with no payload and source ID/URL disagreement. This is **not** a new live ERO acceptance run and does not establish an open contract.
