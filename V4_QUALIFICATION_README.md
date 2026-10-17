# V4 evidence-first commercial qualification — October 2026

V4 is an additive, read-only review layer. Existing collectors, source definitions, SQLite databases and V2/V3 outputs are preserved. It runs as an optional step in `daily_radar.py`; a failure marks the run PARTIAL without interrupting other collectors.

## Run on the existing Windows installation

Update your code files from GitHub **without deleting or replacing your existing `data` folder**. Double-click `RUN_COMMERCIAL_SELECTOR_V4.bat` after the normal collection. This opens `data/commercial_candidates_v4.html`.

The same review runs automatically after V2 during the daily pipeline, without DeepSeek or any paid calls. Inputs: `data/opportunities_ALL_REVIEW_ONLY.csv` and optional read-only `data/radar.sqlite`.

Outputs:
- `data/CANDIDATES_V4_ALL_REVIEW_ONLY.csv`: unique commercial research projects, grouped trades
- `data/CANDIDATES_V4_EXCLUDED_AUDIT.csv`: traceable excluded rows
- `data/CANDIDATES_V4_COUNTS.csv`: lane summary
- `data/commercial_candidates_v4.html`: human review

## Interpretation and safeguards

1. `SOURCE_UPDATE_WATCH` means Radar detected an update; **not** a newly issued permit, opening, or verified opportunity. These records are capped at low research priority.
2. `PERMIT_REVIEW` and `BUSINESS_REVIEW` still require source-record verification and a confirmed business/operator. Nothing is sale-ready automatically.
3. Residential-led towers, small dwelling projects, garden suites and explicitly no-work documentation are excluded; mixed-use projects led by apartment construction are not relabeled commercial.
4. Related Toronto BLD/HVA/PLB/FSU permits using the same year/permit number count as **one project**; original source keys are all retained. Other sources are grouped only by their stable source key, to avoid merging unrelated businesses by street address.
5. Only service hypotheses supported by project descriptions/trade permit types are shown. No universal HVAC/security/insurance labels.
6. When available, status and collector-preferred source date are read from existing SQLite metadata. A preferred source date may be a status date, not an issuance date. The detector timestamp is separately labeled. No modified baseline or broad database migration is attempted, because modifying normalized collector records could create artificial UPDATED events.

## Remaining business gate

The outputs are **research queues**, not verified leads for resale. Before selling: open the official record, verify real event and dates, identify tenant/operator/owner, establish genuine service demand and buyer relevance, and verify appropriate business contact details. Never treat linked permits as unawarded trade contracts.

## Test evidence

Five regression tests cover source updates, residential/no-work rejection, three permits becoming one project, optional read-only status enrichment, and >100 output without quotas. The uploaded V3 export (244 rows) was dry-run locally: 128 distinct research projects remained after filtering and grouping; 106 were `SOURCE_UPDATE_WATCH`, 21 `PLANNING_WATCH` and one `PERMIT_REVIEW`. These figures describe the uploaded historical sample, not the next daily run or verified sales leads.
