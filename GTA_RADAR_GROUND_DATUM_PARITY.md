# GROUND / Datum competitive parity — GTA Radar quality plan

Status: 2026-11-02. Owner's durable product destination: a **top-tier Canadian commercial construction and development intelligence company**, Southern Ontario first. Fixed motto: **Freshness First. Evidence Always.** This is a capability-and-measurement plan, not a claim of competitive equivalence.

## Public, vendor-described reference standards

- [GROUND / GroundIntel](https://groundintel.ca/): early planning/license signals, linked permits and companies, tenders and prices, activity wire, market benchmarks, trade-fit and project dossiers; Pro has drawings intelligence on selected tenders. Its published counts and lead times are vendor claims, not independently audited here.
- [Datum](https://datumai.ca/): council/committee/minutes/video ingestion, staff-report extraction, project/entity resolution, field-level evidence and confidence, daily feed and mapping; reports matched council/planning-to-permit examples. Its published median is based on its verified subset, not a per-project promise.
- [GROUND terms](https://groundintel.ca/terms) expressly distinguish reusable original municipal open data from proprietary derived compilations, and restrict systematic derived-data scraping. **Do not scrape or mirror GROUND or Datum data.** Use original permitted municipal data for our product and human reviews of permitted public vendor pages for comparisons.

## Capability assessment of checked `main` as of 2026-11-02

| Capability | Radar state | Evidence and next gate |
|---|---|---|
| Newly source-dated project prioritization | **Implemented** | `gta_freshness.py`, `selective_daily_ai.py`; filing/status dates still distinct from proven public publication dates. |
| Genuine earlier-than-permit discovery | **Partial, advantage unproved** | `gta_early_signal_feed_monitor.py` plus `gta_discovery_tracking.py`; require measured real earliest public disclosure and observed timestamp across a validated cohort. |
| Early municipal document/meeting intelligence, like Datum | **Code exists, separate integration** | `municipal_meeting_capture.py`, `municipal_document_registry.py`, `municipal_cross_source_synthesis.py`, `gta_total_intelligence_run.py`; do not call it live production parity until collectors execute and evidence gate passes. |
| Project/entity resolution and lifecycle | **Partial** | `municipal_evidence_graph.py`, `gta_unified_intelligence.py`, `commercial_selector_v4.py`; exact-project identity still needs manual verification. |
| Field-level evidence and freshness provenance | **Partial** | Source links and date-basis labels exist; a per-field evidence-first dossier with reviewed identity remains a higher bar. |
| Supplier/trade scope fit | **Implemented as suggestions** | `gta_supplier_scope.py`; not bids, unawarded packages or verified demand. |
| Company/person purchasing authority | **Unproven** | Public business-contact hints from DeepSeek; owner, operator, developer and purchaser must be distinguished. |
| Tender package/bid-tab/price benchmarking like GROUND | **Not proven comparable** | Existing procurement modules run in optional paths; do not claim public commercial pricing models. |
| Customer product quality and coverage | **Partial** | Local CSV/HTML dashboards exist; not a validated enterprise product or comparable national footprint. |

## What is now added to the default daily manual handoff

The free `gta_competitor_matchup.py` generates two separate rows per locally selected project:

1. **GROUND** research row linking to the known public GROUND Places page.
2. **Datum** research row linking to Datum's known official site.

Each row keeps Radar's own source description, reported source-record date and its *basis*, source freshness classification and first-observed date; it has empty manually reviewable fields for same-project/exact-permit overlap, source evidence, competitor first-observed time, and reviewer notes. **No absence is treated as absence of competitor coverage**; status starts `NOT_CHECKED`.

Outputs in existing `GTA_RADAR_RESULTS`:
- `GTA_RADAR_GROUND_DATUM_COMPARISON_<timestamp>.csv` and `.html` — dated immutable snapshots.
- `GTA_RADAR_COMPETITOR_MANUAL_REVIEWS.csv` — stable manually edited research ledger, with notes preserved on every daily run.

Lead-time numbers are **not computed** until both observations have exact same-project/exact-permit evidence, independent competitor timestamp proof, and precise offset-aware Radar and competitor observations. Then `radar_lead_days_if_verified` is measured **observed detection difference** in days, not earliest public discovery, procurement lead time, or evidence of supplier availability. If the competitor does not publish its first-detected timestamp, leave that blank and do not claim an advantage.

This implementation creates an ethical evidence-based competitive research workflow; it **does not** turn GROUND or Datum into a new data source, automatically look up their projects, add AI spending, or enable buyer outreach.

## Fixed order of capability acceptance — bounded by evidence

1. **Freshness truth:** For exact project IDs, link dated earliest public notice, municipal filing/status date, and Radar actual observed timestamp separately. Never infer publication from a permit year or first ingestion.
2. **Project and entity truth:** Prove same project across council/planning/permit using exact ID or reviewed multi-source linkage; company-role candidates must have project-specific support.
3. **Document coverage:** Measure successful retrieval of meeting minutes, reports and plans plus source citations, and false-positive/missed-record rates for a 10-project controlled cohort, before enabling separate pipeline by default.
4. **Trade actionability:** Show source-backed reasons for supplier categories and check whether the relevant work remains prospective, procurement-unknown, contracted or already complete; no guessed 'open bid'.
5. **Customer utility:** Two paid validation customers, with feedback on timeliness and information they did not have. Product features and additional geographies must earn expansion through these gates.

**Pass/fail for 'match GROUND and Datum':** not a vanity count or duplicated website. Only label a named capability **COMPARABLE** after measuring matching task, data geography, quality, source traceability, precision, coverage, latency and customer usefulness against accessible, permitted product observations. Protected/non-public competitor information is **UNKNOWN**, not inferior.

Original ten-project dated evidence baseline: [GTA_RADAR_COMPETITIVE_BENCHMARK_20261101.md](GTA_RADAR_COMPETITIVE_BENCHMARK_20261101.md). Preserve the original ten selected IDs in [config/google_pilot_reviewed_projects_20261101.txt](config/google_pilot_reviewed_projects_20261101.txt).
