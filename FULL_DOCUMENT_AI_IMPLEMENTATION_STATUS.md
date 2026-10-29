# Full-document AI / multi-property pilot — implementation status

This module is **review-only** and not deployed to GTA Radar V8.

## New code
- `municipal_full_document_ai.py`: read all locally saved PDF pages, split
  into bounded sections, run non-thinking DeepSeek section extraction, preserve
  model and quote errors in `SECTION_AUDIT.json`.
- `municipal_property_reconciliation.py`: group only explicitly grounded
  address mentions into candidate property records, not confirmed projects.
- `MULTI_PROPERTY_EVIDENCE.csv`: sections, pages, address roles, evidence,
  grounded flags and source SHA.
- `MULTI_PROPERTY_RECONCILIATION.json`: possible properties and unresolved
  mentions.
- `FULL_DOCUMENT_COVERAGE.json`: total pages, total sections, attempted
  sections, unprocessed count. Missing page coverage is never called success.

## Known limitations and next implementation steps
- Pilot maximum is six sections by default. Longer reports are deliberately
  reported PARTIAL_REVIEW, not silently truncated.
- This is **not** yet document-level AI synthesis across sections. Grounded
  exact-address reconciliation is deliberately conservative and will miss
  aliases, complex parcels, ranges and unnamed sites.
- Exact quote presence is not sufficient for semantic support or correct
  organization role. Human validation remains required.
- No independent evaluation of 20 diverse real reports or legal approval for
  unattended collections has been completed.
- Scanned/unreadable pages need an OCR review path.
- Budget accounting conservatively reserves each attempt when usage is not
  reconciled. Previous UNKNOWN reservations remain counted.
- No existing V8 identities, buyer contacts or procurement verification
  have been merged automatically.

## CLI (preflight; zero AI costs)
`python municipal_full_document_ai.py --pdf saved.pdf --url https://www.toronto.ca/legdocs/mmis/2026/ph/bgrd/backgroundfile-287454.pdf --out review_folder --results path/to/GTA_RADAR_RESULTS`

Use `--paid` only after an explicit budget review and approval; each section
incurs a separate budgeted DeepSeek request. Run with `--max-sections 1`
for a tiny paid pilot. The existing PDF collection program is unchanged.

## Promotion criteria
At least 20 varied real reports manually labeled for section coverage,
all properties, stages, roles, contradictory evidence and negative examples.
Record per-field accuracy, false merged sites, missed sites, procurement
false positives and total AI cost before publishing any new leads.

The production V8 8:30 AM run, local database and ordinary lead feed remain
unchanged.
