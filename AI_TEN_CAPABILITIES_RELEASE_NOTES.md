# GTA Radar: Ten AI capabilities in one commercial project dossier

Implemented in PR #231 (2026-11-15), integrated into the existing qualification worklist.
This document describes **code paths**, not a claim that ten live opportunities or
two paying pilot customers have been validated.

## Source of truth and launch

- User-facing Windows launcher: RUN_GTA_RADAR_AI_ALL_TEN.bat
- Existing qualification entrypoint: gta_commercial_qualification_review.py
- Shared analysis: gta_ai_ten_capabilities.py
- Source discovery: existing gta_top10_live_source_recheck.py
- Targeted independent source enrichment: gta_ai_ten_source_enrichment.py
- Durable output: GTA_RADAR_AI_TEN_CAPABILITIES_DOSSIERS/*.json
- Human-readable briefs: GTA_RADAR_AI_TEN_CAPABILITIES_BRIEFS/*.md
- Canonical read-through: GTA_RADAR_AI_TEN_CAPABILITIES_OVERLAY.json
- Existing canonical output: GTA_RADAR_COMMERCIAL_TOP10_ANALYST_REVIEW.csv

### Ten capabilities

1. company_entity_relationships — named entities and documented relationships
2. project_lifecycle_supersession — chronology and superseded-project proposals
3. buyer_contact_path — public company contact routes, distinct from purchasing authority
4. procurement_award_status — document-backed opportunity/tender/award stage
5. commercial_opportunity_qualification — commercial viability, conflicts and next checks
6. cross_source_project_matching — same-project proposals and version conflicts
7. technical_documents_equipment — specified equipment and works in available text
8. early_investment_signals — public announced events separate from filing dates
9. customer_specific_supplier_fit — compare evidence with a user-supplied customer profile
10. customer_brief_and_feedback — evidence-led brief and optional pilot feedback analysis

Each stage shares the same company/project evidence; it does not create a new AI database.
Actual customer feedback, when available, is taken ONLY from
GTA_RADAR_PILOT_CUSTOMER_FEEDBACK.csv (columns:
record_id,city,supplier_segment,useful,reason,follow_up).
Feedback is user-supplied, not inferred from unanswered sales emails.
A change to feedback triggers new dossier version; the old version is archived.

### Actual evidence policy

- Original project identity and city must match precisely; address similarity alone
  cannot join projects.
- Independent source passages must be fetched by the provider's Search/Fetch or
  previously preserved from the Top10 DeepSeek probe. AI summaries never count as evidence.
- A claimed fact must quote a literal contiguous passage in a fetched source.
- Fetched passages are limited and may lack decisive facts. Treat UNKNOWN as unknown.
- Same-address developer/tenant descriptions are NOT proof of the exact permit's
  company role. A company contact is NOT a verified buyer.
- A model's lifecycle classification alone never marks a project completed/cancelled.
  An explicit quoted status/change passage triggers only an analyst HOLD.
- No inferred open procurement, purchase authority, new public publication date,
  current award or outreach authorization is permitted.
- Non-HTML multimodal drawing extraction is NOT implemented in this release. The
  technical-documents stage analyzes currently available document text only.
  Missing technical pages are reported as source gaps, not invented equipment.

### Execution

- Manual no-spend status: py -3 gta_ai_ten_capabilities.py --results PATH
- Controlled two-project live investigation:
  py -3 gta_commercial_qualification_review.py --results PATH --paid-ai-ten --ai-limit 2
- Ten-project run: RUN_GTA_RADAR_AI_ALL_TEN.bat 10
- Additional known customer: use --customer-profile "Exact capabilities and territory" with
  gta_ai_ten_capabilities.py; the .bat launcher omits customer profile unless invoked separately.

All paid Search/Fetch/model calls use the same v5_ai_budget.sqlite plus legacy
ledger and existing radar_config daily software limit. Do not mistake an
application's budget limit for the provider account balance. The runner is
opt-in: a normal collector is not charged by this feature.

### Acceptance tests

- Ten separate stages dispatched with source-backed mock completions
- Exact-quote matching rejects fabricated evidence
- The same project checkpoint is reused without another paid request
- The canonical Top10 excludes a source-backed lifecycle review hold
- Contact Search/Fetch is independently fetched and never called proof of buyer
- No model spend when original project evidence is absent and discovery is disabled
- Cross-platform CI must pass before merge

### Still requires live product validation

- The user's local Windows/source database and DeepSeek key are not available on
  GitHub Actions, so passing CI is NOT a paid production acceptance.
- Independent human validation of company identity, actual contacts, buyer roles,
  procurement and award status remains required.
- Technical-PDF diagram or drawing-image recognition is future work.
- No verified trade purchasing authority, 10 sale-ready dossiers, or two paid
  customers is claimed by this merge.

**Success metric:** evidence-backed useful opportunities and paying pilots,
not project count, token consumption or number of Python modules.
