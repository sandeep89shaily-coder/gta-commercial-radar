# Regional project-detail evidence pilot

This is an integrated first-stage deep-link pilot for York, Peel and Waterloo,
not a claim of complete regional planning, procurement or application coverage.

After the existing nine-authority index collector writes the CSV, the daily
intelligence runner follows up to six distinct official HTML detail links per
pilot authority. Requests use the existing official-host, robots-policy, DNS,
no-redirect and bounded-download controls.

Files in the existing GTA_RADAR_RESULTS directory:
- GTA_RADAR_REGIONAL_PROJECT_DETAILS.csv: source URLs, project-scope excerpt,
  stage, optional budget evidence, explicit webpage dates, PDF-link counts.
- GTA_RADAR_REGIONAL_PROJECT_DETAILS_NEW_OR_CHANGED.csv: observed changes,
  with first-run snapshot excluded as baseline.
- GTA_RADAR_REGIONAL_PROJECT_DETAILS_STATUS.json: counts and failures.
- GTA_RADAR_REGIONAL_PROJECT_DETAIL_SEEN.json: persistent first-seen ledger.

No new database, paid AI, automatic procurement assumptions, or invented
publication dates. A webpage date is not verified first-publication. No PDF
downloads are performed in this phase. No project lead is sale-ready.

Local test: python -m pytest -q tests/test_regional_project_details.py
Standalone pilot: python -c "from gta_regional_project_details import run; print(run('GTA_RADAR_RESULTS'))"

Next acceptance: verify real project detail HTML and budgets, validate
two consecutive live runs, then scale document collection and change
detection to the remaining six authorities. PDF ingestion, cross-source
deduplication and evidence-aware AI triage remain later phases.


## Phase 2 — bounded official PDF document evidence

The daily runner now also executes `regional_official_pdf_project_evidence_three_authority_pilot`
after the regional detail-page stage.

For each pilot project, up to two linked PDFs are selected, with an overall
limit of twelve documents per daily run. Only PDFs hosted on the same official
HTTPS hostname as the verified project page are eligible. Every request
enforces public DNS, robots policy, no redirects, a 4.5 MB raw-download bound,
a 35-page limit, a text size limit, and an explicit PDF signature check.
Scanned or image-only PDFs are flagged unreadable; OCR is not attempted.

Outputs in the existing `GTA_RADAR_RESULTS` directory:

- `GTA_RADAR_REGIONAL_DOCUMENT_EVIDENCE.csv` — bounded evidence passages,
  project-document source links, source-stage/budget context and review flags.
- `GTA_RADAR_REGIONAL_DOCUMENT_EVIDENCE_NEW_OR_CHANGED.csv` — changes
  observed after the initial baseline; not verified newly published documents.
- `GTA_RADAR_REGIONAL_DOCUMENT_EVIDENCE_STATUS.json` — total PDF links,
  successfully text-extracted documents, individual source/policy failures.
- `GTA_RADAR_REGIONAL_DOCUMENT_EVIDENCE_SEEN.json` — independent
  first-observed, content-digest ledger.

This is **source evidence**, not validated financial budgets, confirmed
contract packages, purchasing authority, or proof of publication dates.
Where budget evidence is present, it is a literal source passage for review.

Tests:

```powershell
python -m pytest -q tests/test_regional_project_details.py tests/test_regional_document_evidence.py
```

Tomorrow's installed Windows run is the first actual source acceptance check.
If the upstream HTML stage cannot fetch any eligible pages or PDFs, this
document stage correctly reports zero, with separate diagnostics rather than
silently claiming nine-region coverage. AI remains disabled in this evidence
extraction stage; the existing paid AI daily ceiling is unchanged.
