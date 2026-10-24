# GTA Commercial Radar — Seven-Priority Closure Audit
_Updated October 24, 2026. Current prototype is NOT a marketable verified lead service. This report distinguishes research, implemented code, live-validated source access, human-verified procurement and paying customers._

## North star
**Before supplier selection**, find material nonresidential building, plant and infrastructure projects using free official public disclosures; prove buyer roles, actual purchasing needs and public contact routes; produce **10 independently actionable dossiers**, then obtain **2 paying pilots**. Existing production V8 and its scheduler remain untouched. New manual pilots cost US$0 in AI; retain the US$0.25/day cap on any future DeepSeek investigation.

## Acceptance criteria versus current evidence

| User priority | What must be proven to mark complete | Actual progress | Result |
|---|---|---|---|
| **1. Identify buyers and purchasing decision-makers** | Original municipal application/owner or operator documents, verified procuring organization **and business purchasing role/channel** for exact work package | Hamilton sources corroborate Alba developer, Venetian plant operator, HCT operator at 1133 and HOPA property/commercial organization; Markham new PDF has named applicants. Public general/sales/lease channels are NOT confirmed purchasing contacts. `early_buyer_evidence.py` preserves human notes. | **NOT COMPLETED**: 0 independently confirmed project-specific purchasing decision-makers |
| **2. Check supplier selection** | Active invitation/credible owner evidence for an exact still-unawarded relevant trade or equipment package, with stage and date | New `early_project_scope_audit.py` distinguishes 1133 withdrawn XCAVAC ECA (019-8711) from 2026 industrial planning (FC-2026-00239) and City demolition permit 26-101057. Enbridge 420 Garner under construction downgraded. City Hamilton and HOPA official tender channels verified, but no project-specific private bid confirmed. | **NOT COMPLETED**: 0 confirmed open private work packages |
| **3. Prove genuine earliest discovery** | Same physical project and scope, actual official first-published evidence for earliest and comparator sources, calculate positive days and show recorded first-observed proof | Hamilton notice dates, Pickering posted dates, Milton news and Markham circulation dates exist (but circulation != public posting). `early_evidence_match.py` now prohibits auto leadtime from same addresses, recognizes distinct file IDs; `early_leadtime_evidence.py` only counts reviewer-confirmed identical projects with source links. **Do not compare withdrawn 2024 waste ECA to unrelated 2026 demolition/new-build**. | **NOT COMPLETED**: no independent verified positive advance measurement |
| **4. Validate early source feeds** | Accessible/complete permitted public source, pagination/rate limits, first-seen history and no false NEW alerts | Official live: Hamilton full ArcGIS 5,237 features plus five original notice articles; Markham official index 63 circulated-report PDFs; Oakville 7 ward links; Milton 10 first-page notices; Pickering 27 active proposal rows; Brampton agenda calendar 1 linked planning meeting. IESO project table missing in automated HTML, Burlington wards GitHub runner HTTP 403, Ajax layout mismatch. First-run baseline is NOT NEW. | **PARTIAL** |
| **5. Other early sources** | Incremental confirmed advantage and reusable permitted free feed, not just more map rows | Official Markham biweekly PDF circulation reports now monitored. Source PDF 2026-09-28 to 2026-10-11 includes early industrial file SPC 26-134020 at 5500 19th Avenue and commercial SPC 26-135992 at 5000 Highway 7 East. Limited PDF first-page manual screen; not yet auto per-applicant extraction. Other sources preserved (IESO, environmental assessments, utility plans, leasing, AGCO, municipal/GC bids). | **PARTIAL** |
| **6. Fix data quality / entity duplication** | Correct role/date/feature identity with no false project uniqueness or cancellation; quantify missing data by source | Existing `early_signal_quality.py` groups applications, checks York published IDs and missing Brampton dates; new exact-project stage scope rules and strict file-ID matching prohibit automatically combining applications at the same address. The historical Brampton site-plan missing source dates and York application-vs-feature reconciliation still need live remediation. | **PARTIAL** |
| **7. Prove a customer-ready deliverable** | Sample verified evidence dossiers for at least 10 real open trade packages; provider feedback and two paid pilots, within CASL/consent requirements | `early_product_evidence_preview.py` now creates a genuine internal HTML sample and readiness scorecard from **22 researched Hamilton/Markham cases**, all explicitly labeled NOT SALE READY where buyers/contracts unproven. No unsolicited outreach has been sent or authorized. | **NOT COMPLETED** |

## Actual new cross-source facts (with source role boundaries)

**1133 Industrial Drive, Hamilton — A material correction to earlier hype.** The same address represents at least these different matters:

- **ERO 019-8711:** waste ECA proponent **2388455 Ontario Inc., operating as XCAVAC Ontario**. Official initial proposal posted **May 21, 2024**, and original application **withdrawn** at its proponent's request, decision posted **August 13, 2026**. That exact ECA scope is no longer an open environmental application. https://ero.ontario.ca/notice/019-8711
- **Municipal Planning Committee PED25091, April 8, 2025:** refers to the XCAVAC waste application; it does not establish the buyer of later industrial redevelopment. https://pub-hamilton.escribemeetings.com/Meeting.aspx?Agenda=Merged&Id=cf3a20fa-3ce3-442b-89b2-5212e3f40c94&Item=25&Tab=attachments&lang=English
- **City May 2026 issued permit 26-101057:** demolition of a **404 m² Building G** at 1133 Industrial Drive. This proves there was already permitted site work but **does not mean all future construction has been contracted**. It is a month-level issuer fact, not an exact daily first-public posting date. https://www.hamilton.ca/sites/default/files/2026-06/building-activity-may2026-statscan.pdf (page 9 of 27)
- **2026 Formal Consultation FC-2026-00239:** City GIS describes industrial redevelopment/port loading/storage at 1133, without named owner in the extracted fields and without exact application date or tender status. https://services.arcgis.com/rYz782eMbySr2srL/ArcGIS/rest/services/Development_Applications/FeatureServer/2
- **HOPA:** the property is advertised for lease with a **commercial leasing team**; separately its official organizational tenders route is https://www.hopaports.ca/tenders/. HCT is a tenant/operator at this address. Neither is automatically the FC applicant or a project-specific subcontract purchaser.

The withdrawal is a **scope-level adverse decision**, never a reason to cancel unrelated developments at the same site. These distinctions are enforced by `early_project_scope_audit.py` and tested.

**Markham new early channel:**

- Official source index: https://www.markham.ca/economic-development-business/planning-development-services/current-planning-applications-and-agendas
- Live one-shot index fetched **63** biweekly/archived official PDFs. The latest inspected summary `Sep 28–Oct 11, 2026` has five individual application rows on its table even though the summary banner says **2**; trust original file rows, not banner totals.
- Three potential nonresidential rows reviewed: **SPC 26-137507** (4412 14th Ave, parking expansion, Neamsby Investments); **SPC 26-134020** (5500 19th Ave, industrial, Orca Communities); **SPC 26-135992** (5000 Highway 7 East, commercial, Cadillac Fairview). Dates on the table are **circulation**, not first public-posted dates; the PDF does not establish buyer/procurement status. Source PDF: https://www.markham.ca/sites/default/files/2026-10/Circulated%20Planning%20Development%20Applications%20September%2028%20to%20October%2011_AOD.pdf
- These are **three research candidates**, not verified procurement leads. The Markville Mall address appears in many prior applications from earlier decades; compare exact SPC file number, don't call an old master project new.

## Operational status and output
- All new additions on draft `feature/gta-early-signals-pilot-20261024` / PR #74, no production merge or V8 scheduling.
- One manual launcher: `RUN_EARLY_CUES_PREVIEW.bat`. New source isolated DB: `data/early_markham_reports_review.sqlite`.
- New outputs: `HAMILTON_EXACT_SCOPE_STAGE_AUDIT.csv`, `HAMILTON_SCOPE_EVIDENCE_EVENTS.csv`, `EARLY_OFFICIAL_PUBLIC_PROCUREMENT_CHANNELS.csv`, `EARLY_MARKHAM_CIRCULATION_REPORT_INDEX.csv`, `EARLY_MARKHAM_REPORT_SOURCE_STATUS.csv`, `GTA_RADAR_INTERNAL_EVIDENCE_DOSSIERS.html`, `GTA_RADAR_INTERNAL_QUALIFICATION_SCORECARD.json`.
- Markham link watcher first successful run establishes **baseline**, not false new projects. No automatic PDF application extraction or recipient contact list created.
- Code and tests are additive, human-evidence gated, and free of paid AI. A green offline unit test is distinct from live-source stability and verified business value.

## Next implementation / research gates (no new speculative upgrades)
1. For **Alba 844 Glancaster**, find actual procurement package channel/owner's construction team and active bid stage; make *one fully validated* industrial dossier.
2. For **Venetian 1119 Barton** verify the exact 2026 planning applicant and facility purchasing role; don't treat an old 2021 ERO permit as a new expansion.
3. For **HOPA/HCT/1133**, reconcile landlord, tenant, withdrawn XCAVAC ECA and issued demolition permit, then verify distinct future phase and sourcing.
4. For **Markham SPC 26-134020 industrial**, inspect exact MappiT file and drawings, identify real developer/site buyer and packages; no user outreach.
5. Fix first-seen/official posted date comparisons on **the same exact project IDs** and run only source pilots with publisher terms/permissions checked.
6. Once independent buyer and unawarded scope proof exist, prioritize 10 dossiers, collect honest supplier feedback (no unsolicited teaser campaign), and measure two paid pilots.

**Do not ship the demo to suppliers or imply a ready lead product.**
