# Peel integration and department audit — October 2026

## What changed
- Peel Caledon development and Peel Flow infrastructure **post-baseline observations** are now visible in the main opportunity selection stage (`opportunity_engine.py`).
- The existing 81 Caledon and 87 Peel observations reported by the user are **historical source baselines**, NOT 168 new business leads. They remain available in `data/peel_pilot_observations.csv`.
- A later newly observed or changed source record can enter the research queue if detected in today's/previous two calendar days. Its event date is explicitly marked **observation/change date, NOT official project application/issue date**.
- Caledon private development and Peel public infrastructure procurement have different buyer categories; no sale-ready claims are generated.
- `collector_opportunity_audit.csv` includes pilot sources even when they have zero eligible new observations.
- Existing municipal and business collectors, local budget rules, and Windows launcher remain present. Original working installations are not edited.

## Peel departmental-source audit / next access checks
| Body / department | Official access point | Access status | Next technical research |
|---|---|---|---|
| Region of Peel / Public Works | https://peelregion.ca/construction/projects/current-construction-projects | Public project index verified | Inspect details and stable project keys; avoid duplicating Flow |
| Region of Peel / Flow | https://peelregion.ca/construction/watermain-construction/flow-program/flow-program-map | Parser live on Windows; 87 observed records | Date/change semantics, avoid false rekeys |
| Town of Caledon / Planning | https://www.caledon.ca/en/town-services/current-applications.aspx | Parser live on Windows; 81 observed records | Extract application dates from linked individual notices, if available |
| Town of Caledon / Planning GIS | https://www.caledon.ca/en/town-services/development-applications.aspx | Public application-map entry point | Determine legal accessible GIS endpoint |
| Region of Peel / Procurement | https://peelregion.bidsandtenders.ca/ | Official tender portal | Verify machine access/licence before building collector |
| Peel District School Board / Capital & Purchasing | https://www.peelschools.org/ | Official site; feed not audited | Identify specific approved tender and capital plan endpoints |
| Dufferin-Peel Catholic board / Purchasing | https://dpcdsb.bidsandtenders.ca/ | Official portal | Verify access and reuse rules |
| Credit Valley Conservation / Regulation | https://cvc.ca/for-land-developers/ | Official permit guidance, not confirmed bulk permit registry | Check individual application publication availability |
| TRCA / Regulation | https://trca.ca/planning-permits/ | Official permit guidance, not confirmed bulk permit registry | Check individual application publication availability |

This audit is **not** a claim of comprehensive Peel departmental coverage. No new procurement/board/conservation collectors have been activated. Keep public infrastructure opportunities separate from private-business leads.

## Running
Extract to the same `new data` parent folder as your older Radar folders. Double-click `START_RADAR.bat`. The app copies earlier data into its own directory if required. Do not copy, delete, or change old folders. Do not enable DeepSeek until the new selection and source evidence have been reviewed.

## Tests
110 automated tests passed locally. Real external integration of the new Peel project events cannot be confirmed until a *post-baseline change* is actually observed on your computer.
