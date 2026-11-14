# Project and Company Evidence Graph V1 — November 14, 2026

## Purpose

This increment **composes** existing Radar facility evidence, exact-project role research, permitted official CSV role overlays, and PR #208's cross-source council links. It deliberately does **not** create an unsupported master company registry.

The owner wants broad North American commercial project intelligence (industrial plants, commercial development, supplier work, early meeting disclosures, project lifecycle and company relationships). Source-specific role evidence is a prerequisite; it is not itself a buyer or sale-ready lead.

## Inputs already created by Radar

- `FACILITY_INTELLIGENCE_PILOT/GTA_RADAR_FACILITY_EVIDENCE_EVENTS.csv`: existing source events and site-context-only organization references.
- `FACILITY_DOSSIER_PILOT/GTA_RADAR_EXACT_PROJECT_ROLE_HINTS_TO_VERIFY.csv`: research role claims matched to exact Radar project IDs.
- `FACILITY_DOSSIER_PILOT/GTA_RADAR_OFFICIAL_APPLICATION_EXACT_SITE_ROLE_REVIEW.csv`: authorized municipal-export exact identity/site role review (currently Vaughan/Kitchener lane).
- `GTA_RADAR_CROSS_SOURCE_RECONCILIATION.json`: council-document, saved caption, and speech-to-text exact application-ID research links.

Missing sources are reported as **MISSING** and produce no claims. Unexpected source schema is held, not quietly interpreted as empty. Existing CSV/JSON and SQLite are read-only.

## Graph model

- `PROJECT_CANDIDATE`: ID scoped to **municipality plus exact project ID**, not verified legal project identity.
- `ORGANIZATION_MENTION`: name explicitly appearing as a named role in a research export, authorized application review, or site-source event. The same string across projects is **not** automatically the same company.
- `SOURCE_SITE_CONTEXT`: source-reported site identifier. Site organization references do **not** attach to projects.
- `PROJECT_ROLE_SOURCE_CLAIM`: applicant, property owner, developer, builder, operator, tenant, contractor or municipal planning reviewer, from the original role-labelled field, tied to its input source. The relationship is **unverified**.
- `SOURCE_SITE_ORGANIZATION_MENTION_NOT_PROJECT_ROLE`: a licence name or regulatory proponent at a site, **not** evidence that the named entity owns, operates or buys for a particular development project.
- `SOURCE_MENTIONS_EXACT_APPLICATION_ID_REVIEW_ONLY`: PR #208 evidence of an exact application ID in a meeting/report excerpt, preserving page or timestamp; **not a company relationship**.

Only exact project ID plus existing source event joins are accepted from research role hints. Ambiguous or absent project records do not become edges. The same project role claimed by different names emits a conflict needing manual review. Any unsupported role such as an inferred BUYER is held.

## Output and daily integration

The existing seven-stage manual launcher writes:

`GTA_RADAR_RESULTS/GTA_RADAR_PROJECT_COMPANY_EVIDENCE_GRAPH.json`

The ordinary dated `GTA_RADAR_EXPORTS` ZIP can include it through the existing `GTA_RADAR_*.json` allowlist, subject to size limits. The new daily status adds graph counts and role conflict totals. No extra paid DeepSeek calls, third-party accounts, email outreach or schedule changes.

## Acceptance gates / next increments

1. **Actual evidence quality**: inspect a fresh owner-side Windows archive and compare all role claims to real source documents; audit 20 independent cases across Toronto, Peel and other municipalities. CI alone doesn't verify a company, an application, or whether a buyer is still sourcing suppliers.
2. **Review and provenance**: attach page quote, company registration number or exact municipal applicant record as authoritative identity evidence, track reviewer, decision, date and source hash; store verified approvals separately from source hypotheses.
3. **Conflicts and project lifecycle**: reconcile developer/owner/operator/agent/contractor independently; track proposals, permits, awards, tenant activation and revisions as distinct *source-event* kinds with original timestamps.
4. **Supplier intelligence**: only after verification, connect the actual buying organization to sector-specific prospective packages and published tender/award status; prefer UNKNOWN over assumed open work.

**Explicit nonclaims:** legal company identity, vendor selection status, project buyer, procurement authority, first-publication dates, citywide coverage, live customer usefulness or paid pilot performance have not been established by the graph module. A source date is not a Radar first-seen timestamp. It is not an entity-resolution or purchasing-power verification engine yet.
