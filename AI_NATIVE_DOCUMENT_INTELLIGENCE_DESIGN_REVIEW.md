# GTA Radar — AI-native municipal intelligence design gate (2026-10-28)

**Status: architecture/research decision only. NOT implementation or production approval.**

## Primary business objective

Use early, publicly available Southern Ontario documents and other signals to find
evidence-backed commercial or industrial investment projects, identify the actual
buying organization and legitimate business contact route, and determine whether
suppliers have already been selected. Avoid conflating activity with sale-ready
leads. This explicitly follows `GTA_RADAR_NORTH_STAR.md`.

## Evidence from real pilot

Toronto TMMIS report `backgroundfile-287454.pdf` was successfully downloaded
by the Windows collector and analyzed using DeepSeek once, with output in the
user's local `TORONTO_AI_SAME_DAY_RECOVERY` folder. The result included 175 Oak
Street and 130 Augusta Avenue within one document-level object. It supplied two
claim quotes but only one passed exact text matching. This source primarily
addressed existing housing tax exemptions and agreements: **not evidence of
an unawarded service or construction contract**.

No statistically valid precision/recall benchmark has been obtained.

## External research

- Datum public methodology: https://datumai.ca/
- Datum source licensing and robots policy: https://datumai.ca/attribution
- DeepSeek thinking mode: https://api-docs.deepseek.com/guides/thinking_mode/
- DeepSeek JSON mode: https://api-docs.deepseek.com/guides/json_mode/
- DeepSeek Responses API: https://api-docs.deepseek.com/api/create-response/
- Additional meeting-AI example and its known error modes:
  https://counciloris.com/methodology

These are public product descriptions and specifications, not disclosure of
Datum's private code or measured model accuracy.

## Core architectural decision: source → event → project → opportunity

Never force a document into a single project row.

**Document**: official source URL, municipal publisher, meeting/item URL,
content SHA256, document type, download observed_at, publisher published_at
(if independently evidenced), event/source date, license and access status.

**Event**: one decision, submission, application, permit, contract award,
tax exemption, financing, renovation, or announcement; verb-specific status,
date, linked evidence spans; multiple events may arise from one document.

**Project**: one physically/logically identifiable proposed development,
including independent property/site identities, project roles, application ID,
stable location, development scope; may have many events over time.

**Opportunity**: a specific service need and plausible lawful buyer route,
supported by relevant project-stage and procurement evidence. A positive
opportunity requires more than AI conjecture. Supplier selection UNKNOWN
unless evidenced.

## AI pipeline, not an all-purpose 2-claim prompt

1. Parse **entire PDF**, retain page boundaries and tables, detect unreadable
   pages and explicitly route scans to OCR review. Keep original bytes.
2. Split using document headings, sections, page boundaries and semantic
   overlap, not arbitrary first three pages. Maintain a coverage manifest
   and per-page processing status.
3. AI **classifies each section** into report type and event type; include
   a no-project/no-commercial-opportunity category.
4. AI **extracts all property and project mentions per section**, each fact
   with exact page quotation, evidence field and uncertainty. Never assume
   owner/operator/developer/tenant are the same entity.
5. Merge section outputs with another AI **document-level synthesis**
   stage that can detect five properties in one report and preserve all
   original source citations. Conflicting claims remain unresolved.
6. Link with prior records: stable application IDs and parcel identifiers
   are strong matches; ambiguous addresses/names generate candidate
   graph edges requiring review. Record why merged.
7. Separate **commercial investigation**: ownership/operation, relevant
   services, purchasing route, procurement and supplier award status,
   freshness, and earliest public signal. AI can search for hypotheses,
   but sale-readiness requires corroborated evidence.
8. Gate final publication by per-field evidence, document coverage, identity
   confidence, commercial-stage relevance and verified buyer route.

## Cheap and accurate AI usage

- First pass non-thinking DeepSeek Flash for structure and event triage.
- Escalate complex multi-site or conflicting cases to higher reasoning only
  after filtering and explicit budget check.
- Do not discard pages merely to fit a fixed model request; use chunked
  extraction plus a cited synthesis step.
- Output JSON Schema/validated objects; invalid or truncated output is
  kept as failure, not a half-valid lead.
- Record prompt version, model, token usage, provider request ID when
  available, response finish reason, retry status and budget reservation.
- Retain conservative uncertain-charge holds; idempotency key should
  include source SHA, section, prompt version, and stage.
- **Budget conflict to resolve before any automatic paid runs:** the
  repository North Star says US$0.25/day while previous V8 files refer
  to US$1/day. Do not silently increase spending. Verify and enforce
  the intended ceiling consistently across every AI stage.

## Acceptance gates before scaling beyond Toronto

1. Evaluation set includes multiple sites in one document, new-build,
   existing-building operations, tax agreements, amendments, awarded
   procurement, no-project records, table-heavy PDF, and scanned PDF.
2. All pages accounted for; full document coverage or explicit exceptions.
3. Section→document reconciliation: no silent dropped addresses/projects.
4. Grounding audit: page spans contain quotation **and** quote semantically
   entails the claim. Separate these measures.
5. Project-match false merges separately measured; false merges must not
   auto-publish.
6. Commercial classification must distinguish a documented procurement
   from a plausible but unverified services hypothesis.
7. Date audit: source report date, publication date and Radar first observed
   are distinct fields, never substituted.
8. Test budget and request outcomes including failure, truncation, timeout,
   duplicate, unknown charge and replay.
9. Real-world pilot evaluates at least 20 varied municipal reports, with
   labeled complete coverage and false positives/negatives, BEFORE daily
   unattended scaling. Then add a second municipality to test portability.
10. Production rollout gated on manual review results and evidence-backed
    lead quality, not simply successful AI API calls.

## Explicit non-goals

- No municipality-specific regex collection of developer names as main AI
  engine.
- No assertion that an approved/exempted facility has unawarded contracts.
- No claim that matching 1 of 2 quotes is measured model accuracy.
- No merge into V8 or automated DeepSeek runs based solely on this design.
