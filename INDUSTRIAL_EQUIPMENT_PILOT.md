# Industrial equipment intelligence — isolated evidence pilot (2026-11-07)

**Status: manual-review prototype, NOT production lead discovery.** This does not edit the daily Windows launcher, alter the ERO collector, raise the shared AI budget, publish leads, or contact suppliers.

## Why this approach

The existing enabled source `ero_gta_environmental_instruments` stores ERO search cards in Radar's normal `data/radar.sqlite` database. Search cards contain the ERO number, title, notice stage and source dates but **not necessarily the proposal details**, so detecting a specific scrubber/boiler change from the existing `SUMMARY` would be misleading. This pilot requires a separate, manually checked, exact official ERO notice excerpt.

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

## Required acceptance gates before production

1. Validate original ERO record and the **full notice text** with an approved, lawful retrieval process and document evidence hashes. No assumption that the ERO search result contains the entire proposal.
2. Backtest on a fixed human-labeled sample of new, existing-only, cancelled and decision-stage records. Report precision and recall; no auto-promotion.
3. Measure exact-site and same-entity matches against the local Radar project ledger, rejecting multiple-tenant and company-headquarters false joins.
4. Verify at least ten commercially relevant *distinct* industrial changes, separate the proposal/decision stage from an open purchase, and benchmark against Industrial Info and accessible alternatives.
5. Interview specialist industrial suppliers and seek two paying pilot customers before integrating with the normal daily launcher.

**No procurement, contract, supplier need, funding, installation or construction start is asserted by an ERO equipment mention.**
