# GTA Radar — 10-Priority Completion and Release Gate
Date: 2026-10-29. Development branch only: `dev/municipal-document-registry-20261027`. No V8 production merge.

**North Star:** Identify new Southern Ontario commercial/industrial projects *before suppliers have been selected*, prove a purchasing entity and public business contact path, deliver 10 independently evidenced opportunities, and secure 2 paying pilot customers. **This list is not completed simply because code exists.**

## Verified today
- Toronto CKAN open-solicitation API fetched **854 source rows**, normalized **804 distinct documents** and yielded **40 future-closing review candidates** in a full dataset scan; GitHub Actions source audit 40872646478.
- New conservative trade ranking found **8 research candidates** matching HVAC/refrigeration, security/fire, electrical/power or industrial-equipment terms; GitHub Actions live source audit 40876387287.
- A separate historic Toronto OData feed's old `OPEN` statuses were properly marked stale, not current (the user's 2010 screenshot). The City procurement lane is procurement-stage, not the earliest private project opportunity.
- Local user's Toronto dashboard visually shows 40 future-closing candidates, 0 meeting references; a screenshot proves local operation, not independent verification of any private buyer.

## Objective-by-objective acceptance ledger

| # | Requirement | Actual evidence | Status | Mandatory next proof |
|---|---|---|---|---|
| 1 | Real buyer and decision-maker | Official City procurement buyer name/email fields retrieved; no verified *private-project* purchasing authority | PARTIAL | 10 specific private developer/operator organization and buying-authority proofs |
| 2 | Supplier selected/unselected | Public City tender/award data; no independently verified private unawarded trade scope | PARTIAL | Original tender/award/contract evidence for each prospective work package; UNKNOWN if unavailable |
| 3 | Earlier discovery advantage | `gta_lead_time_proof.py` checks three separate timestamps and same-project identity; no real cohort measured | UNPROVEN | Verified first public announcement, Radar first-seen, later permit for matched cohort |
| 4 | Brampton/Burlington agendas, IESO, ERO | Research catalog and early-signals baseline; no full live-quality new feed integration shown | UNFINISHED | Working official source collectors, publication timestamps, overlap audits |
| 5 | Full document extraction and merges | Multi-section DeepSeek, page OCR, reconciliation modules with mocks; one earlier live partial analysis | PARTIAL | Real multi-property report recall, complete page coverage, semantic quote checks |
| 6 | Meeting recordings | Official Toronto/Brampton indices fetched but 0 video references in static HTML; YouTube Data API metadata path, local captions/Whisper modules | PARTIAL | 3 actual permitted recordings matched to official agendas, timestamped transcript verification |
| 7 | Southern Ontario expansion | Historical Hamilton/Markham pilot samples in North Star; not in today's production-grade intelligence | PARTIAL | Halton/Durham/Hamilton/Waterloo/Niagara source tests with independent dates and buyer evidence |
| 8 | Commercial relevance and ranking | `gta_commercial_qualification.py`; 8 live City-tender research candidates; no private lead validation | IMPLEMENTED PILOT | Review all 8 against current portal and supplier fit, measure precision |
| 9 | Integrated daily production/dashboard | Isolated Windows review HTML, separate ZIP + branch; V8 deliberately unchanged | PILOT ONLY | Prove no regression, repeatability, 10 verified dossiers, then staged rollout |
| 10 | 10 verified leads / 2 paying pilots | 0 independently verified private leads; 0 paid pilots established | NOT ACHIEVED | Real verified dossiers and explicit customer transactions |

## Deliverables from today's changes
- `gta_commercial_qualification.py`: transparent research scoring, strict sale-ready criteria requiring official URL, excerpt and human confirmation for every critical field.
- `RANKED_SUPPLIER_REVIEW.json` + `RANKED_SUPPLIER_REVIEW.csv`: generated alongside the Toronto open-source collection, top trade categories identified without inventing opportunity availability.
- `municipal_intelligence_dashboard.py`: ranked relevant City procurement candidates appear above the full list.
- `gta_lead_time_proof.py`: correct publication/observation/permit metric with chronology and identity gates.
- Tests for ranking, false-positive blocking and lead-time integrity.
- Existing `RUN_MEETING_BUYER_ONE_CLICK.bat` remains the manual Windows entry point; DeepSeek US$0.25/day ceiling remains unchanged.

## Do NOT claim
- **8 supplier fit matches** are not 8 independently verified private opportunities, nor are 40 future dates proof that 40 contracts are still open.
- The first public application date is not automatically the first public posting date.
- A developer's planning agent is not the purchasing decision-maker.
- Existing government tender contacts are not purchasers for unrelated private projects.
- Running mock tests does not prove live municipal meeting transcription accuracy.

## Highest value remaining closure sequence
1. Select ten named commercial/industrial projects from the existing 795 planning review candidates and independently confirm their owners/operators. Audit actual work-package status and business contact paths. Where evidence is absent, output UNKNOWN.
2. Add two high-priority **pre-application** feeds (Brampton agendas and Burlington pre-application notices), preserve first observed timestamps, and compare to the existing seven GIS collections.
3. Run a real 3-meeting/20-PDF evaluation, source-match and verify quotes; expand coverage only if new facts arrive earlier than traditional planning or permit signals.
4. Promote verified dossiers through the user-reviewed quality gate; only after acceptable pilot accuracy consider V8 integration and commercial customer pilots.

## Blockers outside remote GitHub engineering
- Private purchasing responsibility and supplier-selection status require original evidence and possibly direct confirmation with organizations.
- Two *paying* pilot customers require actual outreach and agreed payment; no such transaction can be inferred from source data.
- Live local Windows DeepSeek calls need the user's existing DPAPI key and execution environment; never upload secrets.
- Authorized meeting audio/captions and reuse permission may be unavailable from third-party video platforms.

**Today's outcome: engineering progress and a live-ranked procurement review queue; business success targets remain not achieved.**
