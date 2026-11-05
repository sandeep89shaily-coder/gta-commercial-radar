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
