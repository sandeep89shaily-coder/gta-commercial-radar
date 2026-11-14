# AI project evidence integration — November 14, 2026

## Why this exists

The Nov 14 manual AI harness successfully attempted and completed 2 source-backed investigations within the shared DeepSeek guard. Its archived reviews included four saved current-input checkpoints but **zero verified commercial buyer or open supplier packages**. The older standalone company graph had site-only mentions and zero project-linked roles, so useful source-linked AI evidence never reached the project/company and supplier review queues.

This increment is **a connected review-only data bridge**, not another source collector, model, CRM, or buyer-verification claim.

## What is connected

1. `gta_ai_project_evidence_bridge.py` reads the existing `GTA_RADAR_RESULTS/AGENT_HARNESS_REVIEW/PROJECT_RESEARCH/AI_PROJECT_*.json` review checkpoints. A real exact application ID must appear in both the officially recorded Toronto planning attributes and an exact-ID evidence excerpt. Saved AI text alone, same address, model-declared page_identity alone, and free-form company names are never proof.
2. Roles enter the graph only when a saved exact-ID source excerpt *literally names the entity and uses nearby role language*. It is still a claim requiring independent review, not an authenticated corporate identity, verified buyer or purchaser. Different roles stay different nodes; an owner does not automatically become a developer or operator.
3. The bridge records the official municipal application status and milestone separately from the AI narrative, and holds contradictory accounts. An official *application milestone* is not a first publication timestamp and a rezoning approval does not prove construction or procurement.
4. Candidate street-address differences vs official `FULL_ADDRESS` are emitted as unresolved address variants, not silently auto-merged.
5. `gta_project_company_evidence_graph.py` now includes source-linked AI role mentions and project nodes with the same review-only strict evidence gate as earlier facility claims. The existing `gta_supplier_verification_gate.py` produces a role review queue and unchanged strict human procurement verification. No contact harvest or automatic outreach.
6. Review priority is a transparent *sector-and-stage heuristic*: industrial and warehouse evidence first, then commercial/mixed-use, unknown, residential-dominant; planning-stage ahead of post-approval, with unresolved contradictions visible. It does **not** infer open bids, supplier selection, actual project freshness or opportunity profitability.
7. `gta_ai_project_intelligence_refresh.py` refreshes all three existing outputs from saved data, with **zero paid calls, zero source fetches and zero extra collection**. The paid AI harness now invokes this refresh under the same process lock after real execution; the normal full-run summary also reports AI bridge metrics.

## Acceptance cases from the real November 14 review export

- **690–720 Sheppard Avenue East**, file `22217053NNY17OZ`: council excerpt explicitly describes **Burbank Heights Development Inc.** as *registered owner* and contains the exact current application ID. Owner becomes a **source-supported project role REVIEW claim**. Its developer role lacks an explicit developer passage and stays held. Municipal attributes say **OMB Approved**, while the AI narrative discusses an ongoing OLT case; both are retained with a contradiction flag, and no automatic chronological inference is made. Address variant (690 vs 692) held.
- **2250/2290 Markham Road**, file `26107153ESC23SA`: the saved review candidate is 2290 but exact official attributes say 2250; create an **address variant hold**. The official milestone is NOAC Issued on a site plan amendment; it must not be promoted as a freshly available building procurement.
- **2363/2365 Eglinton Avenue East**, file `26151476ESC20OZ`: public municipal planner `Tyler Hughes` is not a commercial buyer. Status and address variation stay explicit, and no company is fabricated.
- **166 Dundas Street East**, file `20198309STE13SA`: no accepted corroborating source page in saved review, so it **does not enter** the new source-supported project graph merely because AI produced a summary.
  
The actual uploaded JSON evidence remains local to the user and is **not committed to the public repository**. Offline synthetic regression fixtures represent these risk patterns.

## Operator: refresh results without collecting again

In the code folder:

    git pull --ff-only
    py -3 .\gta_ai_project_intelligence_refresh.py --results "C:\Users\sande\Desktop\new data\GTA_RADAR_RESULTS"

The output files in the user's existing results folder are:

- `GTA_RADAR_AI_PROJECT_EVIDENCE_BRIDGE.json` — exact-ID evidence, role passages, official status, source address conflicts, review priorities
- `GTA_RADAR_PROJECT_COMPANY_EVIDENCE_GRAPH.json` — existing typed graph with new project-level AI role claims
- `GTA_RADAR_COMPANY_ROLE_REVIEW_QUEUE.csv` and `GTA_RADAR_SUPPLIER_PACKAGE_REVIEW.csv` — existing human review/verification queues
- `GTA_RADAR_COMPANY_PROCUREMENT_REVIEW_STATUS.json` — gating and counts
- `GTA_RADAR_AI_PROJECT_INTEGRATION_STATUS.json` — concise zero-cost status

**No official data is fetched and no model is called** by this refresh. Company identities, availability, purchasing authority and legal sales use remain unverified; a reviewer must examine the original sources.

## Limitations / future controlled work

- The strict direct-attribute adapter supports Toronto application IDs in the November case. Other municipal schemas require their own exact-ID offline tests and official role field provenance.
- This release identifies contradictions and address variants but does **not** independently fetch newer architect/developer pages or decide which project version is authoritative. Validated newer source files should enter a source-version review workflow with explicit source timestamp and project IDs. No assumed "830 units" newer fact is embedded.
- Sector relevance does not replace first-publication evidence, bid status or actual customer validation. A future ranked client list must still pass the supplier verification gate before sale.
- The existing local daily AI limit is US$1; this integration adds **US$0**.
