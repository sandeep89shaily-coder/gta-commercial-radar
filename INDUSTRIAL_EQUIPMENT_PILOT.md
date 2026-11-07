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

Recommended fields: `proponent,site_address,city,proposal_posted,notice_stage`. Enter site address, **not registered office address**. Do not import ERO's operator/proponent mailing address as the physical site without explicit location evidence.

The included example has a short official excerpt from <https://ero.ontario.ca/notice/026-1152> (Pinty's Delicious Foods Inc., Oakville; proposal posted 2026-11-06). It is a **single research example**, not a live test of coverage or a verified supplier opportunity.

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
