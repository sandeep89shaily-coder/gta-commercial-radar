# November 2026 — evidence-driven regional collector repairs

## Problems found in November 5 archive
- Toronto regional collector counted seven general procurement/menu links as project signals, while the city's official upcoming-capital-project index links to an actual table of planned construction and engineering scopes.
- Peel Region environmental-assessment index was searchable/dynamic, producing zero identifiable project records. Official current-construction project index publishes named roadway, water and sewer capital projects.
- Waterloo official project detail pages exposed PDF links hosted on a publisher-linked Govstack CDN. Radar counted the links but queued zero because it previously allowed only identical hostnames.

## Repairs integrated in the normal daily launcher
1. Peel Region: official `current-construction-projects` source, plus a separate Bolton Zone 7 early environmental assessment project page; supplemental source failures are explicit. Construction projects are not assumed to be unawarded.
2. Toronto: generic procurement navigation no longer gets classified as real project evidence. New `gta_toronto_capital_pipeline.py` dynamically discovers the official City of Toronto 2026 capital pipeline PDF, extracts official table rows and preserves published scope, owner division, sourcing/award target years, contract type, value band and term. The source is **planning notice**, NOT proof of a current open tender. Original publication dates are not invented.
3. Waterloo: `gta_regional_project_details.py` accepts only the exact publicly linked official document CDN host `media-003-ca.cdn.govstack.com` with path prefix `/regionofwaterloo-018-ca/media/`, only when linked from a fetched `www.regionofwaterloo.ca` official project page. Construction notices are queued ahead of old bulky appendices. `gta_regional_document_evidence.py` still requires public DNS, robots permission, HTTPS, no redirect, PDF signature, max 4.5MB, max 35 pages, and no scanning/OCR.
4. All collectors maintain first-seen baseline and content-digest change tracking; no source is promoted to verified tender or confirmed purchasing authority.

## New outputs
- `GTA_RADAR_TORONTO_CAPITAL_PIPELINE.csv`
- `GTA_RADAR_TORONTO_CAPITAL_NEW_OR_CHANGED.csv`
- `GTA_RADAR_TORONTO_CAPITAL_PIPELINE_STATUS.json`
- `GTA_RADAR_TORONTO_CAPITAL_PIPELINE_SEEN.json`
- Existing regional HTML detail, PDF evidence and source diagnostics.

## Installation and acceptance
After code fast-forward on Windows, install the one additional parsing dependency:

```powershell
python -m pip install -r requirements.txt
```

This adds `pdfplumber` to extract the City's grid-based contract table. The stage is optional and fails explicitly without the dependency; other collectors continue. In official-source testing, a minimum of ten fully typed PDF rows is required before first-seen state advances; failed or incomplete document extraction does not generate new leads.

Tests:

```powershell
python -m pytest -q tests/test_regional_capital_peel_recovery.py tests/test_regional_cdn_documents.py
```

A GitHub live audit checks official publisher access and parses the currently linked document without changing production ledgers. A green CI job means the code ran; source-level diagnostic results still determine whether actual live extraction was successful.

**Never label planned procurement as open solicitation.** Verify current Toronto bids, permit, contract award and buyer before offering any lead to suppliers.
