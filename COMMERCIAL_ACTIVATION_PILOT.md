# Commercial Opening and Facility Activation — pilot 2

**Status: isolated research pilot / manual use only / draft PR.** This module is independent of the industrial equipment pilot and the scheduled GTA Radar daily runner. It reuses the existing verified source-history infrastructure, not paid AI or a new general-purpose scraper.

## What it does

The purpose is to identify **early business activation indicators** and make them useful to relevant service providers, without confusing paperwork with physical opening.

V1 looks only at existing Radar snapshots from:

| Radar source ID | Geography | Original dataset |
| --- | --- | --- |
| `toronto_business_licences` | Toronto | https://open.toronto.ca/dataset/municipal-licensing-and-standards-business-licences-and-permits/ |
| `toronto_active_building_permits` | Toronto | https://open.toronto.ca/dataset/building-permits-active-permits/ |
| `brampton_building_permits` | Brampton | City of Brampton official Building Permits ArcGIS |
| `mississauga_issued_building_permits` | Mississauga | City of Mississauga official Issued Building Permits ArcGIS |

These sources **already exist** in main `config/sources.json`. Nothing changes that configuration, the collector, the daily scheduler, or the US$0.25/day shared DeepSeek limit. The program reads the existing `radar.sqlite` via SQLite `mode=ro`, and it never accesses the internet.

The Toronto licence data explicitly contains operating names, licence categories, issue dates and business addresses. The official Toronto permit service distinguishes `Permit Issued` from `Inspection`, but neither proves a trading opening or occupancy:
- https://open.toronto.ca/dataset/municipal-licensing-and-standards-business-licences-and-permits/
- https://www.toronto.ca/services-payments/building-construction/building-permit/after-you-apply-for-a-building-permit/search-the-status-of-a-building-permit-application/

## Manual Windows use

1. Open the code folder from the **second pilot branch**.
2. Double-click **`RUN_COMMERCIAL_ACTIVATION_PILOT.bat`**.
3. If Radar is not stored in one of its supported existing Desktop/OneDrive locations, run:
   `py -3 gta_commercial_activation_run.py --workspace "D:\existing\new data"`
4. Outputs are written under your existing `GTA_RADAR_RESULTS/COMMERCIAL_ACTIVATION_PILOT/` directory:
   - `GTA_RADAR_COMMERCIAL_ACTIVATION_REVIEW.csv` (full review list)
   - `GTA_RADAR_COMMERCIAL_ACTIVATION_REVIEW.html` (first 500 rows in a readable table)
   - `GTA_RADAR_COMMERCIAL_ACTIVATION_STATUS.json` (counts, exclusions, limitations)

Defaults: source event window **120 days**, at most **40,000 most recent source-dated records per source**. The cap is intentionally explicit: this pilot does **not** claim exhaustive source coverage or all Ontario commercial openings. Limit can be changed with `--max-per-source`, up to 100,000, subject to local memory/processing constraints.

## Evidence gates and intended customer value

| Data event | What the pilot may say | What it must NOT say |
| --- | --- | --- |
| Recent Toronto business licence issue | Licence issued; operating name/category/address; source date | A new business has opened or its opening date is known |
| Commercial tenant fit-out or change-of-use permit under review | Preparation-stage commercial work at address | Construction started or tenant identified |
| Fit-out/building permit issued | Authorized construction at address | Equipment needed / open procurement |
| Inspection-stage permit | Permit undergoing inspection activity | Occupied, handed over or trading |
| Licence + permit at exactly same civic address | Same-site evidence for manual review | Same tenant or same project is confirmed |
| Different suite/unit | Different units, no presumed link | Same facility business or supplier contract |

Source date and **Radar first seen** are stored separately to avoid labeling an old licence as new just because its source was imported yesterday. Non-target licence categories (for example, temporary signs), permit closures, residential-only work and unsupported/missing date records are excluded and counted in JSON. Civic street number is mandatory; corporate names and contractor names are not substituted for business location or operator identity. Unit mismatches are explicitly flagged.

Service-provider categories in the report are **possible buyers of Radar intelligence**: security installers, HVAC-maintenance firms, commercial cleaning, POS distributors, commercial insurers, foodservice equipment suppliers, etc. They are not verified suppliers or evidence that the applicant intends to buy their services. There are no personal-email harvesting, communications or automated outreach features.

## Acceptance criteria to move beyond pilot

- Offline unit tests and GitHub Actions Windows/Linux test matrix pass.
- Inspect a recent local Radar export and record actual source rows scanned and usable signal counts.
- For at least **20 sampled candidates**, verify exact official evidence, dates, stage, organization and location. Investigate renewals/duplicate licences and same-site but different-tenant cases.
- Validate whether signals precede actual business openings and by how much. Require independently sourced **opening evidence** before calling anything an opening.
- Produce at least **10 human-reviewed activation dossiers** with relevant supplier segments and genuinely public business contacts, then obtain feedback from several potential paying customers.
- Maintain a separate production acceptance gate and do not merge or schedule collection based solely on tests.

V1 does **not** add new data connectors, scrape individual business websites, infer owners, assert opening dates, predict sales probability, or combine this with the industrial equipment pilot's release. It should only be promoted after evidence and customer-value validation.
