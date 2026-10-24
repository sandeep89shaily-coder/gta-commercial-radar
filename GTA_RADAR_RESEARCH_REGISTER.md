# GTA Radar — Research Register and Source Backlog
_Recorded 2026-10-24. This is the durable inventory of **all previously researched directions**, including lower-priority ideas. It is not a list of implemented APIs and does not guarantee scrape rights, feed stability, or present procurement availability._

## Purpose
Keep every researched public cue visible while prioritizing the few sources most likely to increase *measurable* time-to-discovery or qualified buyer identification.

**North Star:** discover commercial and industrial developments in GTA/Southern Ontario *before relevant vendors are selected*; independently verify a real buyer/operator and public business contact route; sell **10 evidence-backed actionable opportunities** to validate with **2 paying pilot customers**. No subscription search portal. Not just more GIS records.

**Scope discipline:** protect existing V8; US$0.25/day DeepSeek cap; use free official data/deterministic filters; do not add duplicate feeds, false source dates, scraped private numbers, invented procurement status, or unnecessary code upgrades.

**Status vocabulary:** `PILOT_ACTIVE_MANUAL` (exists and user tested); `EXISTING_NOT_YET_IMPROVED` (some collector already exists but enhancement needed); `RESEARCHED_UNBUILT` (public resource studied; new monitoring NOT built); `HYPOTHESIS_VALIDATE` (potential cue; endpoint/reuse/publication timing not confirmed); `LATER_STAGE_VALIDATION` (useful for verification, not earliest discovery).

## Current seven-source early planning baseline (do not mistake it for finished lead-generation)

| Municipal dataset | Location | Status | Distinctive value and caveat |
|---|---|---|---|
| Pre-consultation GIS | Brampton | PILOT_ACTIVE_MANUAL | Often precedes filing; publication date and active procurement still require verification |
| Rezoning / OPA | Brampton | PILOT_ACTIVE_MANUAL | Earlier entitlement interest; multiple phases |
| Site plans | Brampton | PILOT_ACTIVE_MANUAL | Trade-relevant scope; some source `DATE_RECEIVED` absent |
| Site plans | Mississauga | PILOT_ACTIVE_MANUAL | Planned industrial additions |
| Rezonings | Mississauga | PILOT_ACTIVE_MANUAL | Proposed land-use changes |
| Region development GIS | York Region including Vaughan | PILOT_ACTIVE_MANUAL | Some `APPL_GISID` are features, not distinct municipal projects |
| Development GIS | Toronto | PILOT_ACTIVE_MANUAL | Repeated map features grouped by application ID, not proof of unique projects |

**Measured October 24 baseline:** 32,269 official source rows; 94.2% valid application/source dates; 795 commercial review candidates; 165 research-first; just 53 had application dates within 90 days. These numbers are the uploaded CSV snapshot, not newly verified opportunities. A prior Brampton site-plan audit had 1,542 undated features; Toronto and York need identity caution. Candidate seller/buyer verification and whether trades are engaged remain unknown. V8 production has **not** been updated to use this pilot.

## Researched early-cue source catalogue — do not drop any item

### A. Planning **before** normal application or permit (highest early-stage potential)

| Cue | Geography / public lead | Status | Why investigate / what must be proven |
|---|---|---|---|
| Pre-application community meetings | Burlington https://www.burlington.ca/en/planning-and-development/burlington-planning-process.aspx | RESEARCHED_UNBUILT | Proposal surfaced before complete application; collect initial public agenda/post date, developer name, plans |
| Planning & Development Committee and council agenda packages | Brampton public meeting agendas (official portal endpoint to reconfirm) | RESEARCHED_UNBUILT | Project-specific presentations, attachments, proponent names; compare to Brampton GIS date and duplication |
| Council/planning agendas & committee reports | Toronto, Mississauga, Burlington and other GTA councils | RESEARCHED_UNBUILT | Public decision documents, planning studies, early site directions; relevant PDFs not all machine-readable |
| Toronto AIC updates, daily application map updates and ward subscriptions | Toronto https://www.toronto.ca/city-government/planning-development/application-information-centre/ | RESEARCHED_UNBUILT | Test whether alerts/document releases appear **before** existing Toronto GIS collector; don't duplicate |
| Development application notices / subscriptions | Milton https://www.milton.ca/business-development/planning-and-development/development-applications/development-application-notices/ | RESEARCHED_UNBUILT | Potential public notice/post date and project/applicant PDF |
| Current development proposals / subscriber updates | Pickering https://www.pickering.ca/business-building-development/planning-and-development/current-development-proposals/ | RESEARCHED_UNBUILT | Project posting date and supporting documents; don't equate date posted with opportunity open |
| Planning application dashboard | Ajax https://ajax.ca/build-invest/for-developers-builders/planning-development-applications/ | RESEARCHED_UNBUILT | Proposed floor areas, milestones and documents |
| Ward/site-plan and active application pages | Oakville https://www.oakville.ca/business-development/planning-development/active-development-applications/ward-1-development-and-site-plan-applications/ | RESEARCHED_UNBUILT | Applicant and early site plans; requires stable change tracking |
| MappiT | Markham https://www.markham.ca/economic-development-business/planning-development-services/mappit | RESEARCHED_UNBUILT | Municipality-specific planning identities; verify whether earlier than York Region layer |
| PLANit | Vaughan https://www.vaughan.ca/news/explore-enhanced-planit-mapping-tool | RESEARCHED_UNBUILT | Municipality-specific developments; compare against York Region, avoid double counting |
| Development status map | Richmond Hill https://www.richmondhill.ca/en/learn-more/Planning-Development.aspx | RESEARCHED_UNBUILT | Supplement York Region with local stage and site documents |
| Planning / active developments | Hamilton https://www.hamilton.ca/build-invest-grow/planning-development/planning-applications/where-development-happening-hamilton | RESEARCHED_UNBUILT | Southern Ontario expansion after GTA source advantage proven |
| Municipal planning expansion | Halton, Durham, Niagara, Waterloo, other Peel/York municipalities | HYPOTHESIS_VALIDATE | Examine per-municipality original first-publication evidence; expand only when unique value exceeds overlap |
| Zoning/community consultations and minor-variance pages | GTA municipalities | HYPOTHESIS_VALIDATE | May precede permits but predominantly residential or small changes; aggressive relevance filters required |
| Developer presentations and technical attachments | Public council agendas / planning application portals | RESEARCHED_UNBUILT | Identify refrigeration, generation, plant, data centres, loading docks, building areas, tenants, experts; extraction work may be noisy |

### B. Industrial investment and infrastructure intentions (possibly earlier than site plans)

| Cue | Public starting point | Status | Why investigate / what must be proven |
|---|---|---|---|
| Large load and generation connection applications, status changes | IESO https://www.ieso.ca/en/Sector-Participants/Connection-Process/Application-Status | RESEARCHED_UNBUILT | Potential early data-centre, electrical, plant and utility projects; identify locality, named company, queue entry date, already-selected vendors |
| Environmental Registry proposal-stage industrial ECA/EASR | ERO https://ero.ontario.ca/search | EXISTING_NOT_YET_IMPROVED | Radar already has ERO; enhance first-proposal detection and match operators to GIS, avoid duplicate collector |
| Environmental approval decisions / active filings | Ontario Access Environment https://www.ontario.ca/page/list-environmental-approvals-and-registrations | RESEARCHED_UNBUILT | Industrial equipment, water/air/waste permits; many approvals later than planning |
| Environmental Assessment **Notice of Study Commencement**, consultations | Ontario https://www.ontario.ca/page/environmental-assessments and regional/municipal EA notices | RESEARCHED_UNBUILT | Public infrastructure years before construction; distinguish study/proposal from funded tender |
| Public utility capital plans, capacity and infrastructure consultations | Hydro/utility public postings in GTA (provider pages to verify) | HYPOTHESIS_VALIDATE | Possible expansion and load signal; not every planning consultation reveals a customer site |
| Municipal wastewater, water, transit, public works studies | Peel, Toronto, Durham, Halton, Hamilton | RESEARCHED_UNBUILT | Early design/engineering signals and subsequent work-package milestones |
| Economic development investment/relocation announcements | Municipal investment offices, federal/provincial economic development announcements | RESEARCHED_UNBUILT | Company announces plants, major facilities, data centres or relocation prior to permit; news may arrive after vendor decisions |
| Company press releases / industrial tenant expansion plans | Company newsroom and public investor releases | RESEARCHED_UNBUILT | Named organization, spending and capacity; track verified source/public date |
| Industrial/commercial property sales and land acquisitions | Public land/disposition notices and developer releases | HYPOTHESIS_VALIDATE | Possible precursor to development, but many transactions have no construction plans; avoid personal-property data |
| Commercial leasing / pre-leasing / tenant relocation announcements | Public developer/broker/tenant announcements | HYPOTHESIS_VALIDATE | Identify fit-out needs and end tenant; avoid paid/restricted MLS sources and implied buyer claims |
| AGCO public liquor licence applications / data inventory | https://www.agco.ca/en/general/data-inventory | RESEARCHED_UNBUILT | Potential hospitality/restaurant fit-out before opening; test date and false-positive volume |
| Business licensing / occupancy / business registry updates | Municipality-specific public business licences | HYPOTHESIS_VALIDATE | Tenant openings and fit-outs, likely closer to opening than earliest planning |
| Industrial incentives, grants, investment commitments | Provincial/federal economic development announcements | HYPOTHESIS_VALIDATE | Named capital deployments; verify whether factory/office/new build vs headcount only |

### C. Buyer / tender / work-package availability (often later, but actionable)

| Cue | Public starting point | Status | Why investigate / what must be proven |
|---|---|---|---|
| Federal public tenders/new tender files | CanadaBuys https://canadabuys.canada.ca/en | LATER_STAGE_VALIDATION | Clearly procuring entity and response deadlines; useful buyer signal, but not early private industrial procurement |
| Municipal / provincial purchasing RFIs, RFQs, RFPs, pre-qualifications | GTA public procurement pages/portals | LATER_STAGE_VALIDATION | Explicit work scope and deadlines; only if public feed and reuse allowed |
| Tender awards and public contract disclosures | Public-sector buyer award/meeting reports | LATER_STAGE_VALIDATION | Confirm a supplier has already been chosen; avoid offering closed work as an open opportunity |
| General-contractor expressions of interest / trade bid notices | Public developer/general contractor procurement notices | HYPOTHESIS_VALIDATE | May disclose upcoming subcontract awards and trade scopes; don't infer open bids without notice |
| Public planning project developer/owner/agent names | GIS + attached official report | PILOT_ACTIVE_MANUAL | Crucial role disambiguation. Agent/architect `!=` purchasing authority |
| Public business contact route and procurement status | Official business websites, notices, tender contact, company publications | HYPOTHESIS_VALIDATE | Essential for sale-ready lead; verify organization affiliation, lawful public channels and whether vendor selection remains open |

### D. Validation / comparison feeds already in Radar

- Existing building permit feeds in Toronto, Brampton, Mississauga and other locations: **use as LATE comparison**, not default early lead.
- Existing Toronto application feed, York planning, Brampton pre-consultations and staged Mississauga layers: compare every new source against these before adding duplication.
- Existing GTA Radar business discovery, operator/contact attempts and change-based selector: quality and traceable role evidence are the priority; don't process 578k old records just for scale.
- Buyer benchmark products researched in earlier comparisons: Building Radar, GroundIntel, Builtie, BuildMapper, ConstructConnect, Data Axle and Streetwire. Their lessons to test, not claims of equivalent datasets: decision-maker mapping, verified procurement stage, earliest evidence and supplier-specific relevance.

## Why timing isn't proof of an available lead

For **every prospective project**, separately store:
1. `official_document_url` or exact GIS feature
2. `project_or_application_identity` (with grouping confidence)
3. `application_date` (source-supplied, nullable)
4. `official_publication_date` (if published and attributable, otherwise unknown)
5. `radar_first_seen_at` (immutable first observation)
6. `developer_owner_tenant_operator_agent_roles` (each with evidence)
7. `commercial_scope_and_supplier_fit` (evidence, not guessed contract value)
8. `procurement_status` (OPEN / AWARDED / UNKNOWN only when supported)
9. `public_business_contact_route` (not an unverified private number)
10. `cross_source_history`, `reviewer_decision`, `AI_cost`, and `confidence`.

## Source intake gates before adding any feed to daily collection

- Can we lawfully collect it without paid access? What machine-readable endpoint / PDF and update interval exist?
- Do original documents expose a **first public posting date**, not just a submission date?
- Does it reveal a non-residential investment **earlier** than 7 existing planning sources and existing permits?
- How many **new**, unique, substantial, verified potential opportunities per 14-day window?
- Can we identify a real organization and public business contact path without claiming contractors are unselected?
- What operational burden, duplicates, update failure rate, and DeepSeek cost does it impose?
- Do not turn pilot on in unattended V8 or let it spend tokens before it passes these tests.

## Build increment — October 24, 2026 (pilot branch PR #74; NOT V8)

- **Implemented offline-testable watcher:** `early_cue_watch.py` tracks published IESO connection application entries by CAA ID. Marks province-wide location and buyer/procurement status **unverified**. Visible-table pagination/full extraction **not yet live validated**.
- **Implemented limited Burlington source-page watcher:** three identified official development pages, including pre-application references. This does **not** discover all future Burlington proposals yet; an official complete index is the next dependency.
- **Manual Windows launch:** `RUN_EARLY_CUES_PREVIEW.bat`. Outputs new isolated `early_cues_review.sqlite`, source status, research queue, and real post-baseline changes. **No DeepSeek use; no V8 integration.**
- **Brampton eSCRIBE agendas:** official detailed application-item page verified, but automatic current-meeting discovery is still **RESEARCHED_UNBUILT**. ERO proposal enhancements, Toronto AIC and all other catalogued sources are unchanged.
- **Evidence still needed:** successful live execution against publisher pages, pagination/discovery validation, source terms, comparison with the original seven feeds, and any demonstrated unawarded real buyer and 10-lead/two-pilot progress. No historical baseline suddenly becomes new lead.

## Additional build increment — 2026-10-24: Milton / Pickering / ERO proposal pilot

- **Milton:** Official `/news/development-notices/` listing exposes dated public notices with `/news/posts/` project pages. New **manual pilot adapter** `early_public_notices.py` watches the visible first page, captures source-published dates and optionally reads up to 12 newest details. **Not yet live collection verified; later listing pages unimplemented.**
- **Pickering:** Official active development proposal list exposes applicant, address, exact **Date Posted**, project links and supporting descriptions. Same pilot records each published application URL and new changes while respecting roles. **Not yet live collection verified; not a full site plan/permit index.**
- **ERO:** New isolated `ero_proposal_watch` reuses the existing `radar._parse_ero_search_cards` logic to screen bounded recent search pages for industrial/environmental notices *explicitly at Proposal stage*, preserving proposal dates. **Not a change to V8's enabled ERO source, not a guarantee of GTA location or full feed coverage.**
- **Manual combined runner:** `RUN_EARLY_CUES_PREVIEW.bat` now launches the existing IESO/Burlington watcher plus the new Milton/Pickering/ERO watcher. It does **not** rerun the seven GIS baselines. New independent `early_public_notices_review.sqlite` database; no DeepSeek.
- **Not solved by code yet:** Brampton eSCRIBE calendar/agenda discovery can return 403 to non-browser clients; do not bypass restrictions or label it automated. Burlington citywide preapplication discovery, exact first-posting-date comparison, verified operator/buyer and tender availability, early source rights and two paying pilots remain unmet.
- Review the pilot limits and test checklist in `EARLY_PUBLIC_NOTICES_PILOT.md`. This entry updates status without removing any earlier researched categories.

## Further October 24 build on isolated draft branch (still not live validated)

**Phase 2A — Burlington and Brampton pre-application/committee discovery:**
- `early_discovery_watch.py` follows the official Burlington planning navigation to ward project lists and individual project pages, with bounded fetches and fail-closed behavior if municipal HTML becomes inaccessible.
- Brampton Planning & Development Committee eSCRIBE published meeting calendar is now linked from the official public site; extracts agenda application numbers, purpose, party descriptions and meeting dates from publicly accessible pages. Agenda publication dates are still unverified. 403/JS failures will be reported rather than worked around.
- **Source status:** adapters implemented / offline tests passed, **live publisher coverage NOT verified**.

**Phase 2B — new business-investment and direct buying-signal lanes:**
- `early_investment_tenders.py`: official Ontario all-news RSS news releases, screened for proposed manufacturing/facility investment, and the federal-only CanadaBuys open tender CSV. Open government tenders are source-snapshot open notices with deadlines to verify—not private unawarded GTA contracts.
- `toronto_aic_email_import.py`: voluntary, offline importer of official Toronto AIC e-update email files, WITHOUT accessing email or subscribing the user. Header dates are not official posting dates; requires original city application verification.
- **Source status:** implemented / offline tests added, **live RSS/CSV access and any subscriber input NOT verified**.

**Phase 2C — cross-source proof rather than record proliferation:**
- `early_evidence_match.py` loads only isolated pilot SQLite history, proposes **same-city and exact-numbered street** evidence pairs for human review, and distinguishes publisher posting date from receipt date vs Radar's first-seen date. Matches do not establish one project, contractor availability, or true permit lead-time advantage.
- `early_pilot_summary.py` writes `EARLY_PILOT_RUN_SUMMARY.txt` and `EARLY_TOP_RESEARCH_PREVIEW.csv` as RESEARCH-ONLY outputs.
- One manual `RUN_EARLY_CUES_PREVIEW.bat` runs the new collectors and analysis without recollecting 32k original GIS rows or altering V8 / the US$0.25/day DeepSeek budget.
- **Current source status remains NOT LIVE TESTED.** User is away from their PC; do not turn adapters into scheduled production feeds merely because CI passes.

**Deferred researched sources are NOT forgotten:** individual planning portal adapters for Ajax, Oakville, Markham, Vaughan, Richmond Hill, Hamilton, Niagara and Waterloo; municipal/provincial tenders and award feeds, prequalified GC bid invitations, Access Environment, environmental assessments, AGCO opening clues, utility capital planning beyond IESO, property leasing/acquisitions and company tenant moves. Their official endpoint schemas and incremental edge require evidence before building specific live collectors.

### Ajax official planning index — new review-only pilot, October 24, 2026

- `early_ajax_watch.py` reads the official Ajax public planning property/application index (https://ajaxmaps.ajax.ca/bootrest/planningapps/property.html), capturing indexed civic addresses, planning file IDs and publicly displayed application status.
- This is **code implemented / offline test PASSED / live Ajax website NOT YET VALIDATED**. It does **not** infer project use, buyer identity, submission/publication dates or open procurement from the index.
- History stored separately in `data/early_ajax_review.sqlite`; first-run entries are baselines rather than "NEW" opportunities, and incomplete/blocked indexes fail closed.
- `RUN_EARLY_CUES_PREVIEW.bat` now invokes Ajax along with the earlier collectors, evidence matcher and combined health report. CI run `40116559904` passed Windows/Linux on the Ajax implementation snapshot.
- Other researched municipal sources remain in the register, not discarded merely because Ajax now has a first adapter.

## October 24 later expansion: Oakville, real live checks and business evidence gates

**New implementation, draft PR #74 only:**
- `early_oakville_watch.py`: discovers seven official Oakville development/site-plan ward lists and records application-level history, with bounded separate project descriptions and labeled supporting-document months. Official project pages often show company, street, scope, and multiple submissions. **Document month is NOT an attributable first-public-posted date.** Planning office email is not the purchasing contact.
- `early_buyer_evidence.py`: preserves annotated buyer/operator and open-procurement evidence in reviewer worksheets; requires original citations and current proof before formal case completeness. **The code never claims an auto-verified sales-ready lead.**
- `early_leadtime_evidence.py`: requires human confirmation of SAME project plus public notice evidence before measuring source lead-time, instead of calculating a spurious date advantage from application receipt dates.
- `early_live_source_probe.py`: bounded public source read-only smoke checks from GitHub Actions, no DeepSeek, login, private contact acquisition or V8 changes.

**Observed source-health on October 24 (GitHub one-shot run `40117942636`):**
- Oakville seven official ward links PASSED; Milton initial news listings parsed 10; Pickering current-applications table parsed 27; Brampton published calendar parsed 1 planning-meeting link. These are not proven live projects/lead counts, and each source still requires full collection and rights review.
- IESO status HTML project table NOT present in GitHub response; source may be browser-rendered. Burlington planning ward index returned HTTP 403 on GitHub; no bypass. Ajax applications index response did not expose expected markup. **Those adapters must remain pilot-only and must not be called operational until their access is resolved legally.**
- Ontario investment RSS and CanadaBuys CSV were not included in the same one-shot seven-source probe; existing code tests only synthetic fixtures.

**Still researched, not built as verified usable collectors:** Markham MappiT and Vaughan PLANit GIS dashboard, Richmond Hill planning/status GIS, Hamilton interactive planning map, later Niagara/Waterloo geographies, land sales/commercial leasing, AGCO-specific fit-out inference, Ontario environmental assessment commencements, municipal public procurement/awards and supplier/vendor contact validation. AGCO and ERO already have collectors in the legacy V8 source config; do not duplicate merely to increase collection totals.

The short-term priority remains measuring whether existing new early sources expose an actual official public notice **before** later site plan/permit milestones, plus independently verifying the first 10 paying-customer-worthy leads. Do not add more unstable map scrapers until sources pass publisher access, documentation rights and demonstrated incremental information gates.

## Priority windows without losing lower-priority sources

**Now:** source-age advantage comparison for Burlington preapplication/Brampton agendas, IESO connection queue, and existing ERO enhancement; alongside verification of the strongest 10–15 recent industrial opportunities.

**Then:** Toronto AIC and Milton/Pickering/Ajax original posting dates; check whether they beat already collected GIS sources.

**Later / conditional:** Oakville, Markham, Vaughan, Richmond Hill, Hamilton, additional Southern Ontario, AGCO, leasing/land, investment announcements, environmental assessments, tenders and procurement availability.

**Every biweekly review:** scan *all* catalogue rows for newly actionable/overdue items; spotlight 3 best actions but also mention deferred areas and their reason. Don't silently erase or replace older research when adding new findings. Mark each item `not tested / tested-no edge / pilot / production` and record the evidence when status changes.

## Success measures
- `verified_actionable_opportunities`: target **10**, require work scope, current project stage, responsible buyer, public channel, and unawarded-work evidence or clearly bounded uncertainty.
- `paying_pilot_customers`: target **2**.
- `documented_early_advantage_days` on same identified projects and sources.
- `qualified_new_projects_per_week` and `provider_feedback`.
- `AI_spend_usd_per_day`: at or below **$0.25**.

**Do not confuse sourced possibility, implementation, and verified lead. The research register is complete as a catalogue, not a guarantee that every public page has a tested feed.**
