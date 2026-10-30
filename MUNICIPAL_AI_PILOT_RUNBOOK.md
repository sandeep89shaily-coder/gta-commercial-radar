# AI-first municipal report evaluation gate (PR #79)

This branch uses existing `v8_deepseek_native.request`, model, and existing
`v5_ai_budget.sqlite` ledger; it does not substitute new OpenAI accounts,
a second paid AI budget, or production scheduling.

## How to execute a real review (only with already-lawfully-saved report)

1. Use a source-specific collector to discover a genuine council agenda and
   report. Confirm access permission before downloading any PDF.
2. Put a local digitally readable PDF in a separate scratch folder.
3. Run `python municipal_ai_document_review.py --pdf report.pdf --out report_AI_REVIEW_ONLY.json --source-url https://www.toronto.ca/legdocs/mmis/2026/cc/bgrd/backgroundfile-287146.pdf --results path/to/GTA_RADAR_RESULTS --paid` to authorize **one paid call** subject to existing daily AI spend. No `--paid` makes no call.
4. Independently verify source and project facts and create a human gold file
   (a JSON object with `pages`, `expected`, `verified_real_pdf`).
5. Run `python municipal_ai_evaluation.py --result report_AI_REVIEW_ONLY.json --gold gold.json --out report_EVAL.json`.

## Promotion rules

- Quote occurrence on cited page is *necessary*, not sufficient: the quote
  may not entail the claim. Human gold review measures interpretation.
- Model output is untrusted; only supported_claims were checked for exact
  quote occurrence. No extracted facts automatically become a published lead.
- Measure field precision, field recall, project linkage and buyer accuracy
  separately; include negative/no-project meeting reports in the gold set.
- Compare source report date, first public publication date, first Radar
  observation date, and downstream permit date separately.
- Supplier selection defaults UNKNOWN. A lack of awards does not prove an
  unawarded contract.
- Do not promote to production while automated municipal PDF access is
  unvalidated or while real-report precision and recall are unmeasured.

## Current truth

Unit tests use controlled fixtures and mock-model outputs. **No real paid
DeepSeek municipality-report analysis has been performed or scored**.
The adapter remains a review-only development milestone.
