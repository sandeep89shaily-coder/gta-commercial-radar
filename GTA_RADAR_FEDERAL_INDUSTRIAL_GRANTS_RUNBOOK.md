# Federal industrial CapEx: official snapshot intake

This stage is invoked by the existing `gta_equipment_commercial_daily.py` daily pipeline (after the current industrial index), with no extra paid AI calls.

Official resource: https://open.canada.ca/data/en/dataset/432527ab-7aac-45b5-81d6-7597107a7013

Official full CSV: https://open.canada.ca/data/dataset/432527ab-7aac-45b5-81d6-7597107a7013/resource/1d15a62f-5656-49ad-8c88-f40ce689d831/download/grants.csv

**This file is approximately 2.3 GB and updated quarterly. Do not fetch it daily.** Download it manually or using an expressly authorized refresh schedule and place it at `GTA_RADAR_RESULTS/OFFICIAL_FEDERAL_GRANTS/grants.csv`. The official dataset is under Open Government Licence–Canada; maintain attribution and use the official original rather than third-party transformed copies unless separately verified.

On the next run, the existing equipment index stage streams Ontario rows, filters descriptions for explicit industrial/capex activity and writes:

- `GTA_RADAR_FEDERAL_INDUSTRIAL_FUNDING_CANDIDATES.csv`
- `GTA_RADAR_FEDERAL_INDUSTRIAL_FUNDING_STATUS.json`

Run standalone after a local snapshot exists:
```powershell
python gta_federal_industrial_funding.py --results "GTA_RADAR_RESULTS"
```

Data quality gates: The disclosed recipient city is **not** assumed to be the project site; the agreement date is **not** the original announcement or vendor selection; the grant amount is **not** equipment budget; a recipient-company match is **not** a proven same project; and an equipment keyword is **not** an RFQ. Missing original CSV is marked NO_LOCAL_OFFICIAL_SNAPSHOT. This is a research-stage intake, not a customer lead.

Further acceptance: validate the current publisher CSV schema (live download unavailable inside GitHub CI), inspect the first 20 true Ontario industrial candidate records and check 20 against Radar's saved project master. Collect original source context and buy-stage evidence before promoting any record. No hypothetical numbers are reported as discovered.
