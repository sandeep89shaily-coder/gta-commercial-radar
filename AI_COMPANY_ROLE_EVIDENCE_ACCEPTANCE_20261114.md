# Source-backed DeepSeek company and buying-function intelligence — V1 acceptance

## Purpose

Directly address GTA Radar's biggest commercially useful evidence gap without a separate SaaS/AI subsystem. The existing up-to-24-project DeepSeek shortlist preselection now investigates companies and likely procurement decision-making functions while selecting the research top ten.

### Integration completed

1. Existing live Search/Fetch queries now target owner, developer, tenant, operator, contractor and architect mentions in addition to application dates/status.
2. Existing live-source checkpoints capture literal `role_excerpt` passages and, for exact-ID ArcGIS results, original applicant/owner/contractor/architect attribute values.
3. DeepSeek returns up to two roles per project with company name, canonical role, source index and a **literal citation quote**; absence of evidence requires an empty roles array.
4. `gta_ai_company_role_evidence.check_roles` refuses unsupported or invented names, roles, indices and quotes. A sourced page containing the exact application ID creates `EXACT_APPLICATION_ROLE_SOURCE_REVIEW_ONLY`. A page mentioning only the site address creates `SAME_ADDRESS_SITE_CONTEXT_NOT_PROJECT_ROLE` — it cannot become a project role in the company graph.
5. DeepSeek also suggests a **purchasing function** (developer procurement, tenant facilities, general-contractor buyout, owner project team, property manager or unknown), always labelled `AI_HYPOTHESIS_NOT_BUYER_VERIFICATION`. Do not mistake the model's proposed title for a verified individual or organization.
6. `GTA_RADAR_COMMERCIAL_TOP10_ANALYST_REVIEW.csv` now includes `ai_company_roles_review`, role counts, quote-rejection diagnostics and `ai_buying_function_hypothesis`.
7. On a successful paid shortlist review, the existing read-only project/company graph and supplier gate refresh. The graph stores only **exact-ID** company-role claims, with source URL and quote hash. Graph edges, legal identity, actual purchasing authority and supplier award status remain **review-only and unverified**.
8. All work reuses existing bounded Search/Fetch and up-to-three DeepSeek Flash batch model calls, the **same US$1/day budget ledger**, saved evidence, HTTP402 stop, paid-call idempotency and the seven-stage manual Radar launcher. No new paid integrations, hidden crawlers, outreach, new model provider, municipal collection, CRM records or invented business contacts.

### Fixed acceptance test

- DeepSeek must extract a literal project-associated company role, source and quote in a synthetic end-to-end example.
- A same-address but different-application page must **not** create a project/company graph edge.
- A role/name without literal source support must be rejected and its count recorded.
- A buyer-function hypothesis can be displayed but never become a verified buyer.
- Outputs must be visible in the existing analyst CSV, project/company graph and procurement-review queue.
- Existing Windows 3.11/3.12 and Linux 3.11/3.12 tests must pass.

### One normal command (after merge)

```powershell
cd "C:\Users\sande\Desktop\GTA_RADAR_INSTALL\GTA_RADAR_MONDAY"
git pull --ff-only
py -3 .\gta_ai_top10_reranker.py --results "C:\Users\sande\Desktop\new data\GTA_RADAR_RESULTS" --paid
```

This **does not** rerun municipal collection, but it **can make paid model and Search/Fetch requests** within the same existing US$1 daily software limit. If the same inputs and date have already been reviewed with older model outputs, existing immutable model batch checkpoints may be reused; full extraction of new role fields requires a fresh version of the model task fingerprint or new dated source-evidence inputs.

The actual number of source-supported roles found must be measured on the real saved data. Unit tests do not prove that GTA Radar has gained verified purchasing organizations, customer contacts or available bid packages. **No new sales-readiness claim** follows from these AI hypotheses.
