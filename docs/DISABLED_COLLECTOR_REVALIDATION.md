# Disabled collector revalidation — 2026-10-24

**Purpose:** Discover actionable commercial investment signals *earlier* than ordinary permits. This is a **review plan**, not evidence that disabled endpoints are operational. Nothing is enabled here.

## Priority 1 — planning stage, early buying window
| Source ID | Why check first | Validation needed |
|---|---|---|
| mississauga_site_plan_applications | Site plans may precede construction permits | Official endpoint responds, project ID stable, application/submission dates differentiated from first-seen |
| mississauga_rezoning_applications | Potentially earlier intent | Commercial/non-residential separation; exclude residential-only; dedupe site plans |
| york_region_active_development_applications | Expands planning coverage across York | Verify municipality scope and fields; avoid overlap with municipal collectors |
| richmond_hill_active_development_applications | Local early planning stage | Stable application keys, observed changes, avoid duplicate York projects |
| hamilton_development_applications | New geography before construction | Compare existing early Hamilton pilot; no double counting |
| kitchener_active_planning_applications | Early Waterloo-region project indications | Check feed freshness, stage and source-record timestamps |

## Priority 2 — early-adjacent opportunity and scope
| Source ID | Why test | Caveat |
|---|---|---|
| durham_planit_opa | Long-lead land-use changes | OPA does not establish a commercial buyer or contract |
| durham_planit_consents | Land transactions/lot changes | Many residential/low-intent cases |
| durham_capital_projects | Potential upcoming public-sector work | Public procurement is distinct from private lead qualification |
| waterloo_city_building_permits | Expands geographical coverage | Later than planning |
| st_catharines_building_permits | Expands Niagara coverage | Later than planning |
| hamilton_building_demolition_permits | Renovation/redevelopment clues | Overlap with development applications and Hamilton pilot |

## Priority 3 — historical / enrichment, not early private-contract signals
| Source ID | Reason |
|---|---|
| toronto_cleared_building_permits | Historical/backfill; avoid manufacturing false NEW events |
| durham_business_sites | Company directory/enrichment, not an independently verified buying event |

## Required gates BEFORE enabling any feed
1. Check official endpoint, licensing, response status, field schema, pagination and update cadence.
2. Snapshot as **BASELINE_ONLY** on first import, with no buyer alerts or DeepSeek charges.
3. Persist IDs and source state; alert only on demonstrable NEW/UPDATED events **after baseline**.
4. Verify origin/source date separately from Radar observation time. Label missing dates honestly.
5. Commercial/use screening, residential exclusion, evidence URL and cross-source project deduplication.
6. Buyer/supplier-award facts must be corroborated. Planning listing alone is not sale-ready.
7. Run isolated fixtures and Windows/Linux CI; then live-source read-only probe; only then opt in production.
8. Respect existing DeepSeek budget ceiling **US$0.25/day** and never claim an early-discovery lead-time advantage without evidence.

## Release status
- No source enabled by this audit.
- The nine independent early collector groups wired into the development pipeline are **not equivalent to nine validated commercially actionable sources**.
- Development branch only; original desktop/production unchanged.
