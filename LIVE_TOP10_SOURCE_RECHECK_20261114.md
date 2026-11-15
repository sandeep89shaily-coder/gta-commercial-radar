# Live source recheck before DeepSeek top-ten selection — November 2026

## Why this increment matters

Prior top-ten AI reranking interpreted only previously saved municipal data. It could not discover that a newer official approval, construction/completion notice, revised scheme, or same-address development page had emerged after a filing. The analyst review uncovered precisely this issue at 1200 King Road Burlington, 611 Keele Street Toronto, and 1430 Birchmount Road Toronto.

## New preselection pipeline

The original collector still supplies the initial bounded source-backed candidate pool (up to 24 projects, municipally diversified). On an operator-initiated paid assessment, *before asking DeepSeek to score candidates*, Radar now:

1. Attempts to **read the exact municipal application attributes** from an allowlisted ArcGIS query using the existing no-cost exact-key reader. A changed literal `STATUS_DESC`, `STATUS`, or milestone is marked as an official application-status difference, but it is NOT converted to construction or contract status.
2. Re-fetches the source project page where the previous record supplied a distinct project-specific URL (not just a generic portal).
3. Searches for the exact application ID and the project street address using the existing provider DeepSeek Search service. Search snippets are **discovery hints only**; they never establish a new project fact. Selected official or project-relevant pages are retrieved through DeepSeek Fetch and the fetched page text is checked.
4. Accepts evidence for model review only with the exact current application ID **or** a specific same-address project/development statement. These are distinguishable levels. A new proposal at the same address but under another file number is **not** automatically linked or treated as superseding the original.
5. Records original URL, fetched excerpt, identity level, retrieval day and source errors in dated, immutable per-project checkpoints. Source retrieval date is not publication date; an older article fetched today is still an older article.
6. Passes this **newly retrieved project evidence** to the existing small-batch DeepSeek preselection reviewer. Where the model cites a live source, the quoted text MUST literally appear in the accepted fetched excerpt; fabricated citations invalidate the batch. The AI still cannot create a buyer, open procurement, new publication or verified current project stage.
7. Applies only a *complete source-input-fingerprinted* batch of model reviews to the internal research worklist. If a batch fails, the model's suggested scores are not used. Saved AI reviews expire after their local review date. Inaccessible municipal sources are labelled as evidence gaps; they do not become false current evidence or prevent unrelated reviews.

## Cost and safety

- Up to two DeepSeek Search requests and two DeepSeek Fetch requests **per candidate** plus the pre-existing up-to-three model ranking batches. Maximum new tool-call reservation for 24 candidates is 96 × $0.00075 = US$0.072. Model calls also reserve from the **same existing shared US$1/day** ledger; no new provider API key or account.
- Existing HTTP 402 handling stops subsequent paid calls and releases the explicitly rejected request reservation. Unknown-charge failures retain ledger reservations. Repeat same-day exact-input checks reuse saved checkpoints; source-input changes invalidate checkpoints.
- Official ArcGIS network retrieval, where supported, is a read-only exact application lookup, subject to the existing allowlist. No generalized crawling, rate-unbounded scraping or new municipal access-bypass code.
- Running the regular offline refresh remains free and does not fetch sources or invoke the model; a paid run is explicit or part of the user's existing manual full-run action.
- No automatic outreach, supplier contracts, verified purchasing authorities, first-publication claims or CRM promotion.

## New artifacts

- `AI_TOP10_LIVE_SOURCE_CHECKS/LIVE_<hash>.json` — per-record, dated, retrievable evidence checkpoints, including official-status differences and unlinked-address context.
- `GTA_RADAR_AI_TOP10_REVIEW_STATUS.json` — complete candidate preselection with reviewed quote/source citations and source-check metadata.
- `GTA_RADAR_AI_TOP10_ATTEMPT_STATUS.json` — blocked/incomplete/source-retrieval counts and budget-safe execution.
- `GTA_RADAR_COMMERCIAL_TOP10_ANALYST_REVIEW.csv` — adds live checked date, source count, cited URL/quote, exact-ID/address-context grade, and project-version conflict flag.
  
## Commands after merge

Paid research on the **existing collected records only**, no second municipal collection:

    cd "C:\Users\sande\Desktop\GTA_RADAR_INSTALL\GTA_RADAR_MONDAY"
    git pull --ff-only
    py -3 .\gta_ai_top10_reranker.py --results "C:\Users\sande\Desktop\new data\GTA_RADAR_RESULTS" --paid

Read `GTA_RADAR_COMMERCIAL_TOP10_ANALYST_REVIEW.csv` and `GTA_RADAR_AI_TOP10_ATTEMPT_STATUS.json`. The existing seven-stage manual run now invokes the revised live check as part of its preselection step; no extra collection stage is needed.

## Limitations remaining

A current fetched page may still contain historical information or a publisher may update without a visible date. We can now discover and attach **newer available evidence**, but cannot promise every municipal portal will return its latest full application files or assert that an address-level match is the same project. True current contract availability needs independent purchasing or tender evidence. These uncertainties are made explicit in the shortlist rather than presented as verified facts.
