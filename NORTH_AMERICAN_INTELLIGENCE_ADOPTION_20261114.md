# North American Intelligence Architecture — Adoption Plan (2026-11-14)

## Product decision
The owner wants the entire research-derived methodology incorporated into GTA Radar, **not** a narrowed lead-only MVP or a single Datum clone. Preserve and extend the existing source collectors, 16-city configuration, original SQLite, first-observed ledgers, seven-stage daily manual orchestration, research register and north-star document. No reset, automated outreach, background schedule, or additional DeepSeek budget.

This is a **delivery plan and acceptance contract**, not a claim that all items below are built. Competitor public materials describe their advertised capabilities; internal architectures and data licensing are not independently known. Do not copy proprietary provider datasets. Do not assert parity based on marketing counts.

## Reference patterns and planned adoption

| Reference | Publicly described strength | Radar implementation | Evidence gate |
|---|---|---|---|
| Shovels | Large-scale standardized US permit/decision coverage, published freshness semantics | Source registry + normalized source-event contract + age/completeness metrics | Original-source completeness/freshness compared to known counts |
| MyTown | Aggregated local-government meetings, text, transcripts, platform-labelled records | Evaluate licensed/public supplemental data *without* treating it as authoritative | 16-city sample: provenance, rights, duplicates, original URL, timestamps |
| CivicWeb / eSCRIBE / Granicus / Legistar | Repeated government meeting-platform families | Config-driven source adapters, not one collector per city | Authorized paths only; refuse 403/robots restrictions; original document audit |
| Datum / Shovels decisions | Transcript and document-derived early project signals | Local speech-to-text, PDF/OCR, transcript timestamp and page evidence; provisional transcript followed by minutes and application reconciliation | Human-reviewed precision sample and traceable quote/time reference |
| Dodge / BuildCentral | Automated acquisition plus researcher verification and detailed project/company context | Entity graph with explicit owner/operator/applicant/agent/GC/buyer roles; human verification queue | 20 original projects and at least 10 actionable dossiers, no implied buyer |
| ConstructConnect / DataBid | Bid, tender, trade and revision lifecycle | Supplier taxonomy, stage changes, public tender/award links, alerts | Verify unawarded window and the actual solicitation URL |
| Industrial Info Resources | Plant/capex/equipment/project-stage intelligence | Plant/site/asset/equipment timeline, ERO and company-investment joins | Confirm equipment, plant and purchasing stage independently |
| GROUND | Local planning/permit company context | Local entity resolution and commercial prioritization | Compare shared exact projects with original-source citations |

## Common source ingestion contract (target)
Every collected item should have:
- source_provider, source_platform, municipality, jurisdiction_id, original_source_id, source_url, retrieval_status
- evidence_type (application, permit, agenda, report, minutes, video, transcript, ERO, tender, award, announcement)
- observed_at_utc (actual Radar timestamp), source_event_date, date_kind, publisher_first_publication_at (only when independently established)
- source_sha256, raw_record_path, licence_or_access_basis, retrieval_error, parser_version
- extraction_method, source_page_or_timestamp, exact_application_or_permit_id, normalized_site_id
- company role assertions linked to individual evidence assertions and verification state
- lifecycle classification and conflicts, including STOP/HOLD for stale, blocked or contradictory evidence

Important invariants: source filing/receipt date != publisher publication date != Radar first observation; applicant != buyer; same address != same project; a meeting mention != approval; an approval != open purchasing. Source failure must never erase earlier successful history.

## Delivery tracks (implement incrementally without rewriting current collectors)

### Track A — collection and coverage
A1. Read-only source quality report on current daily results: **implemented in this PR**. It is explicitly conservative (no citywide completeness or buyer truth claims).
A2. Official platform inventory for all 16 cities: ArcGIS, CKAN, open data, eSCRIBE, CivicWeb, Granicus, Legistar, custom, restricted or unknown. Different sources can coexist in one city.
A3. Source-adapter interface with typed results, source-policy authorization, retry/backoff, rate/size bounds, no redirect bypass, and atomic evidence-ledger updates.
A4. Migrate Brampton, Mississauga and Toronto *behind adapters* one by one, prove identical output on saved fixtures, then add supported provider platforms.
A5. Evaluate MyTown on 16 exact cities, with licensing, provenance and human sample; use as supplementary candidates only, not authoritative facts.
A6. Measure expected vs retrieved record counts only where a documented full official inventory exists. Publish UNKNOWN rather than a made-up denominator.

### Track B — documents, recordings and evidence
B1. Reuse digital PDF parsers; add scanned-page OCR when text is missing, with confidence/rotation/page-level audit.
B2. Official authorized audio/video record inventory with explicit license and access checks; no platform bypass.
B3. Local transcription (e.g. faster-whisper) and timestamped segments; CPU fallback, optional GPU, no automatic bulk downloads.
B4. Candidate project detection with page/quote/timecode and original URL; low-confidence claims go to manual HOLD.
B5. Reconcile provisional meeting discussion to official minutes, applications and permits, preserving disagreements. No transcript-based approval assertion.

### Track C — entity resolution and lifecycle
C1. Preserve exact source IDs; deterministic ID links first, address/name fuzzy hints second.
C2. Separate project, site, owner, operator, applicant, agent, architect, general contractor, purchaser, supplier and government planner.
C3. Track planning -> approval -> permit -> tender -> award -> construction -> activation as evidence-based events with independent timestamps.
C4. Store rejected/conflicting joins with reason; do not silently merge historical records.
C5. Preserve source provenance with every AI-produced field; source material is untrusted input to the LLM.

### Track D — commercial intelligence and delivery
D1. Build industrial plant, equipment/capex/ERO and data-centre cooling/supplier-specific inference as distinct research lanes.
D2. Build facility activation and tenant change lane from licensing/occupancy/opening evidence, not from an assumption that a permit means an opening.
D3. Add trade taxonomy and customer profile filters for HVAC, industrial equipment, insurance, security, electrical and facility services.
D4. Research verified company roles, procurement authority, contact routes, tender open/close status; explicit UNKNOWN if unsupported.
D5. Create evidence-backed dossiers, CSV/PDF/dashboard/map; keep manual outreach until consent/compliance reviewed.
D6. Measure conversion with two paying pilot customers; no revenue or competitive edge claims until observed.

### Track E — operational quality and commercial benchmarking
E1. Source health: permitted access, completeness, freshness, deduplication, late updates, field-level reliability and last successful run.
E2. Twenty-project independent evidence audit across multiple cities, not twenty rows from one source.
E3. Ten shared project competitor comparisons where public visibility is available; UNKNOWN if competitor detection timestamps are private.
E4. Explicit quality gates in daily report: stage PASS is execution health, never full source/lead verification.
E5. Regression and Windows/Linux CI on every integration; production owner ZIP acceptance afterwards.

## Implementation order, without narrowing overall scope
1. Common contract + source-health transparency (first shipped slice, not the destination).
2. Provider inventory + compliant reusable adapters + supplementary dataset experiment.
3. PDF/OCR + recording transcription and transcript/minutes validation.
4. Project/site/organization-role evidence graph.
5. Industrial equipment, activation, verified procurement and trade-specific ranking.
6. Competitor measured benchmarks and recurring client delivery.

Tracks may advance in parallel where changes are isolated and testable.

## Acceptance conditions for claiming operational completion
- Actual owner-side Windows collection extracts real permitted source records across nominated providers; API existence or test fixtures are insufficient.
- No erasure of original SQLite or historical ledgers; no side-effect paid AI calls from added stages.
- Source histories and timestamps survive partial failures and are clearly labeled.
- Project-to-buyer links are independently evidenced, not just inferred.
- Coverage reports distinguish source reachable, records retrieved, source completeness and commercial yield.
- All changed code passes tests on Windows/Linux, plus owner archive validation.
- At least 20 original records, 10 commercial dossiers and real customer feedback underpin commercial readiness claims.

## First implementation in this branch
`gta_source_quality_v1.py` consumes the existing `GTA_RADAR_COLLECTION_HEALTH.csv` after the main daily collector and emits `GTA_RADAR_SOURCE_QUALITY_V1.json`. It never claims citywide completeness or verified buyer leads. The output is included by the existing safe archive policy because it is a root `GTA_RADAR_*.json` file. This is an intentionally limited, zero-cost step toward the full source quality architecture.

**Known limitation:** Earlier or missing CSV input cannot establish current source freshness; stage status and source reality remain distinct. This report does not replace the existing richer source health/status reports.
