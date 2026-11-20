# All-city quarterly reference reconciliation

Offline reconciliation now runs after the valid 31-city western combined master in the ordinary manual GTA Radar run. It does **not** fetch restricted city websites, assume Hamilton GIS covers Ontario, or insert missing records into AI Top 10 or commercial releases.

### Input
Place publisher-authorized or dataset-licensed reference CSVs under `GTA_RADAR_RESULTS/authorized_quarterly_reference_exports/`, e.g. `hamilton.csv`, with `city,application_id` (and optional `address,scope`). Each CSV must have `hamilton.source.json` with:
```json
{
  "city": "Hamilton",
  "source_url": "https://<actual publisher dataset>",
  "licence_evidence_url": "https://<specific evidence>",
  "rights_scope": "PUBLISHED_OPEN_DATA_LICENSED_FOR_COMMERCIAL_REUSE",
  "reference_period": "2026-Q3"
}
```
These example placeholders are not a real licensed feed. For written permission, use `WRITTEN_PUBLISHER_AUTHORIZATION` and a nonempty `authorization_reference`.

**Important:** rights manifests are operator attestations, not independently verified by this script. Do not claim commercial reuse is cleared simply by creating one. Confirm whether the precise dataset/API and intended downstream usage are licensed before import.

### Outputs
- `GTA_RADAR_31_CITY_QUARTERLY_GAPS.csv` identifies matched, reference-only and Radar-only exact application IDs, with discrepancy flags.
- `GTA_RADAR_31_CITY_QUARTERLY_COVERAGE.csv` reports all 31 configured municipalities; missing authorized references display `NO_AUTHORIZED_REFERENCE`, not zero-percent coverage.
- `GTA_RADAR_31_CITY_QUARTERLY_COVERAGE_STATUS.json` records eligibility, rejected inputs and non-promotion guarantees.

`REFERENCE_ONLY_REVIEW` represents a possible collector omission requiring review of periods, application types, ID format and source freshness. It is **not** a verified missing project, commercial buyer or a sales lead. Radar-only records may be older/newer than the quarterly reference. Address and scope differences are string-review flags rather than proof of factual error.

### Test / replay
```shell
python -m unittest tests.test_quarterly_application_reconciliation
python gta_quarterly_application_reconciliation.py --results GTA_RADAR_RESULTS
```
Manual standalone replay is supported on existing 31-city output. The integrated manual run invokes the audit only after a current valid 31-city master is generated. The comparison adds no HTTP calls or paid AI usage. It does not alter the 31-city commercial Top 10.

### Activation
Validate real application-level fields and precise commercial permissions separately for Hamilton, Guelph, Windsor, Burlington, London, Sarnia and Chatham-Kent, then add each authoritative reference export. No actual gap counts are claimed until such exports have been evaluated.
