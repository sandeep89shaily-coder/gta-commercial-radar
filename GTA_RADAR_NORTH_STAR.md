# GTA Commercial Radar — North Star and Unfinished Work

> **Durable master copy on the default branch.** All researched public sources, including deferred and exploratory ideas, are recorded in [GTA_RADAR_RESEARCH_REGISTER.md](GTA_RADAR_RESEARCH_REGISTER.md). Do not narrow this roadmap to only the latest two or three sources. Future reminders should read both files. The early-signals pilot remains on a separate unmerged branch, not V8 production.

_Last foundational review: 2026-10-24. Strategic ambition and benchmark initiated 2026-11-01. Durable decision log for future AI work; keep this file visible in every major Radar review._

## November 1, 2026 — fixed long-term ambition (owner-confirmed)

**Build GTA Radar into a top-tier Canadian commercial construction and development intelligence company, beginning in Southern Ontario.** Serve ALL relevant suppliers and service providers: construction, specialty trades, engineering, equipment, insurance, security, facility services and others. Different customer segments can value different project lifecycle phases.

This *long-term destination* does not replace the immediate hard gates below: independently validated projects, actual buyer/role evidence, two paying pilot customers, and measured early detection. **Do not publicly assert "Canada's #1," "first to discover," an open supplier bid, or a verified purchasing authority without comparative proof.** A curated paid pilot is the first product/market test, not a cap on future services, dashboards, alerts, enterprise intelligence or geographic expansion.

For the first controlled evidence baseline, see [GTA_RADAR_COMPETITIVE_BENCHMARK_20261101.md](GTA_RADAR_COMPETITIVE_BENCHMARK_20261101.md). It documents the exact ten selected projects, known earlier public disclosures and competitor overlap, and explicitly marks unavailable first-detection timestamps **UNKNOWN**. No source-record date is a substitute for an actual Radar ingestion/publication timestamp. Keep development priorities bounded to verified gaps and customer needs.

## November 2, 2026 — sixteen-city early-application intake and November 2 repairs

**Owner-approved implementation:** Daily GTA Radar now attempts official early-development application indexes in **Toronto, Brampton, Mississauga, Hamilton, Burlington, Oakville, Vaughan, Kitchener, Markham, Oshawa, Milton, Halton Hills, Caledon, Cambridge, Waterloo and Guelph**. `gta_early_applications.py` saves one baseline, a persistent per-application content fingerprint, source URL, municipal file ID, observed timestamp and per-city source-access status. **Index registration != actual application coverage.** Dynamic maps, permission-blocked portals, bulk catalogue pages, and planning notices lacking stable application numbers must remain INDEX_ONLY, BLOCKED or LINK_REVIEW and may not be counted as confirmed projects. Actual portal access and counts must be validated on Windows and no first-publication date may be inferred from a municipal source-record age.

Fresh application changes appear in the **combined daily manual intelligence report**, separate from V4 permit projects. The commercial and application-ID extraction is conservative. They do **not** get merged into canonical permits or trigger DeepSeek spend until a specific supporting report can be validated. Initial live ingestion is baseline, not a claimed new lead. Any city portal requiring eSCRIBE, embedded GIS or dynamic front-end endpoints needs a policy-verified specialist adapter.

**November 2 repair requirements:** Apply `gta_document_priority.py` before DeepSeek PDF selection to reject condolence motions, procedural by-laws, meeting calendars and other irrelevant files using bounded local text extraction. Save every relevance score and pending source for audit. A blank `record_source_url` is **not repaired** by inventing a project-specific URL: secondary paid project research is held pending exact official source evidence and its skip reason is counted. First selective DeepSeek research is preserved. Legacy fingerprints without old field snapshots are labeled as undetermined rather than asserting an unknown revision was scope change. Graph counts must measure PDFs actually captured from the seven-city adapter and all configured meeting cities, not stale legacy paths.

**Acceptance not claimed:** live sixteen-city extraction rates, publication lead times, third-party meeting platforms, company contacts, developer identities, purchaser authority or GROUND/Datum parity. All stages retain original evidence, display blockers honestly and share the same **US$0.25/day** DeepSeek ceiling.

## November 2, 2026 — official PDF retrieval beyond Toronto (first bounded adapter)

The normal daily collector now includes `municipal_document_capture.py`: for **Brampton, Mississauga, Hamilton, Burlington, Oakville, Vaughan and Kitchener**, try a bounded number of publicly available same-official-host agenda pages and direct PDF links, with DNS/robots/redirect/content-size/signature/PDF validation. Each attempt is recorded per city and source page; **none of these cities is accepted as reliably documented until actual live captured PDFs are verified**. Dynamic eSCRIBE/Laserfiche portals remain blocked pending municipal-specific, policy-checked adapters; a zero-PDF result is not evidence that the city has no projects.

Captured non-Toronto documents flow through the *same* DeepSeek document review and shared **US$0.25/day ledger** with Toronto, preserving source municipality and original agenda URL. A persistent pending-PDF queue prevents budget-deferred municipal reports from vanishing on subsequent days. A separate permanent `GTA_RADAR_DOCUMENT_PROJECT_CANDIDATES.csv` captures AI-suggested developments, source PDF SHA, agenda provenance, page-quote evidence counts and manual review notes. **This is not an automatic project merge into the canonical permit database**; exact permit/application IDs and independent review must validate the match before publication.

All PDF model suggestions, business roles, first-published dates and potential awards remain *unverified*. Existing manual worklists and competitor benchmark are preserved. Next acceptance gate: prove retrieval completeness with recorded official, dated documents per city, then implement reviewed third-party meeting-platform adapters and exact-ID project promotion.

## November 2, 2026 — eight-city municipal coverage and AI routing

**Owner direction: connect more municipalities and use AI at every stage where required to deliver earlier, evidence-backed project intelligence.** Prioritize depth of information and freshness, not superficial URL counts.

- Eight official municipal meeting entrypoints in the *default daily workflow*: **Toronto, Brampton, Mississauga, Hamilton, Burlington, Oakville, Vaughan, Kitchener**. Track index access, newly observed official agenda links, portal failures and exact observed timestamps; never conflate a first-seen link with its first publication.
- **Only Toronto** currently has the bounded, policy-checked automated agenda/PDF capture and model document review. Every other city remains **INDEX_MONITORING_ONLY** until actual licensed/allowed document fetch and content validation succeeds. Dynamic calendars can hide documents from an HTML index; zero links does not prove zero meetings.
- Registered document index sources now cover eight municipalities, but registry registration is not retrieval, extraction, or verified project coverage. Run safe source-by-source retrieval pilots (Mississauga/Hamilton/Brampton first, then Burlington/Oakville/Vaughan/Kitchener); audit completeness and publication dates, expand only with working evidence.
- **AI routing rule**: low-cost code for official URL index checks, deduplication, dates and schema extraction; AI for unstructured meeting reports/PDF extraction, authorized/local captions, ambiguous project and organization matching, cross-source contradiction resolution, and deeper researched high-value projects. Source quotations, exact permit IDs, official publication dates and supplier status must be evidenced independently; never let AI create procurement certainty.
- All optional paid AI analysis shares the established **US$0.25/day** ceiling. If budget exhausted, queue and label work for future runs, not false-complete. Never auto-download restricted meeting recordings or use platform bypasses. Human review of purchasing authority, live awards and outreach remains mandatory.

Technical sources: [municipal_meeting_capture.py](municipal_meeting_capture.py), [gta_early_signal_feed_monitor.py](gta_early_signal_feed_monitor.py), [gta_daily_intelligence.py](gta_daily_intelligence.py), and [municipal document source registry](config/municipal_document_sources.csv). **No eight-city full-document or Datum-equivalent operational coverage claim** until Windows live collection and per-city quality acceptance.

## November 2, 2026 — integrated daily intelligence is the default

Owner-approved: the standard Windows `RUN_GTA_RADAR_DISCOVERY.bat` run must now orchestrate (a) live V6 permits/planning/business and DeepSeek/contact checks, (b) Toronto/Brampton official meeting index discovery, (c) bounded, policy-checked Toronto municipal PDFs, (d) source-backed PDF analysis and supplemental fresh-project/buyer-role investigation under the **same shared US$0.25/day ledger**, and (e) free evidence checks and a single integrated CSV/HTML worklist. Old projects and undated meeting links are not new public announcements. PDF/model hints never establish exact project identity or open supplier packages. Keep buyer/award/physical checks and sales manual.

**Actual live deployment and document retrieval success on the owner's Windows desktop remain to be confirmed.** Stage failures and source coverage gaps must be visible in the integrated manifest. Do not claim full Datum/ GROUND parity or verification without independently measured output. No unchecked archival/backlog paid sweep, no extra collector DB or video capture.

Implementation: [gta_daily_intelligence.py](gta_daily_intelligence.py) and [gta_discovery_run.py](gta_discovery_run.py). Historical `--full-intelligence` remains a separate legacy research mode, not necessary for the normal integrated daily launcher.

## November 2, 2026 — GROUND and Datum are primary external benchmarks

**Owner-approved goal: develop capabilities comparable to GROUND / GroundIntel and Datum, without copying their protected data.** Evaluate real-time early discovery, council/meeting document intelligence, exact-project lifecycle joins, source attribution, company-role resolution, supplier-sector usefulness and customer value. Treat published competitor capabilities as reference standards, **not** evidence of Radar parity or measured earlier detection.

Each default daily manual-review run now emits **GROUND and Datum per-project manual comparison sheets** with source/date provenance, preserved researcher notes and strictly evidence-gated observation-time comparisons. No scraping, extra AI costs or automatic sales. See [GTA_RADAR_GROUND_DATUM_PARITY.md](GTA_RADAR_GROUND_DATUM_PARITY.md). Do not expand the roadmap endlessly: close proven gaps through focused research → implementation → tests → measured acceptance.

## November 2, 2026 — freshness-first intelligence policy

**Owner-confirmed motto: freshness first.** The default daily project list and selective paid-DeepSeek gate must favor newly source-dated, commercially meaningful developments, **not** old public permits merely indexed by Radar for the first time. First observed by Radar is not first publicly announced.

- Date bands: **0–7 days**, **8–30 days**, **31–90 days**, then historical/unknown (manual review). These are **source-date bands, not verified first-publication bands** unless independently supported. Never use municipal-change detection timestamps as project publication timestamps.
- Historical projects with a **tracked description/scope change** can re-enter research as **older-project scope-change review**. Do not state the change was freshly published or the supplier package is open. Status-only legacy changes do not automatically consume the selective AI budget.
- Keep the full historical database and free manual review list; label every candidate's freshness class and date basis. Don't silently erase records or invent publication dates.
- Research ordering is **freshness, then lifecycle, then commercial relevance/other queue factors**. Preserve existing same-band regional balancing and DeepSeek's source-specific research and public business-contact search.
- Hard guardrails unchanged: selective DeepSeek **US$0.25/day**, existing Gemini pilot manual and separate, no automatic procurement/outreach/sales or buyer verification.
- Measure first-publication and actual first-observation dates independently in future benchmarks; do not confuse a rolling change date with either.

See [gta_freshness.py](gta_freshness.py), [free_daily_report.py](free_daily_report.py) and [selective_daily_ai.py](selective_daily_ai.py) for implementation.

## ONE business objective — do not lose sight of this

**Discover credible GTA / Southern Ontario commercial and industrial investments before suppliers are selected, identify the real buying organization and a lawful public contact path, and sell evidence-backed opportunities to relevant service providers.** Examples: commercial HVAC/refrigeration, industrial equipment, security/fire systems and other specialist vendors. This is a **qualified lead-intelligence business**, not a subscription search engine or a contest to accumulate permit rows.

Success benchmarks:
1. **10 individually validated, currently actionable opportunities** with original-source evidence, project identity, commercial scope, buyer/operator/developer relationship, public business contact/procurement path, procurement-stage assessment, and honest confidence labels.
2. **Two paying pilot customers** who find the intelligence timely and worthwhile.
3. Measure **lead-time advantage**, i.e. actual first public disclosure and first observed-by-Radar timestamps vs later planning/permit milestones. Never substitute an application submission date for publication date.

Hard operating principles:
- Start with Brampton, Mississauga and Toronto; expand to other GTA/Southern Ontario areas only when a feed demonstrates unique early value.
- **Earlier and more actionable beats larger datasets.** Favor pre-application investment clues over late-stage building permits where justified.
- Existing V8 desktop runner must remain unchanged until proven pilot value. Keep pilots isolated, manual and review-only.
- Use public free data and deterministic screening first; DeepSeek only for high-value questions, with a **US$0.25/day budget ceiling**, not on every row.
- Keep stable collectors; do not "upgrade in the name of upgrading." Never report candidate records as verified unique projects, genuine demand, an open contract or a qualified buyer.
- Avoid scraping that breaches terms; inspect public information, access methods and reuse restrictions.

## Existing baseline / implemented work (NOT evidence of sales readiness)

**October 24, 2026 early-signals pilot branch:** `feature/gta-early-signals-pilot-20261024`; GitHub PR #74; separate `data/early_signals_review.sqlite`; V8 not merged/changed.

Seven public ArcGIS sources: Brampton pre-consultations, Brampton rezoning/OPA, Brampton site plans, Mississauga site plans, Mississauga rezonings, York Region development applications, Toronto development applications.

Last *user-uploaded* V3 audit (2026-10-24): **32,269 GIS/source records**, **94.2% valid source dates**, **795 commercially plausible research candidates**; 165 research-first under pilot heuristic; **53 applications within 90 days**; 567 over a year old. These are historical application dates, not verified public notice timestamps. **No verified sales-ready opportunities or paying pilot customers shown.** The numbers are a snapshot, not live dashboard.

Date epoch parsing and source-date provenance, commercial-text tagging, conservative application grouping, source-quality audits, possible cross-stage address links, and evidence-gated buyer research queues are in pilot code. Brampton site plan still had **1,542 undated GIS features** in last audit; don't invent missing dates. York source record count was **6,773 features** with **6,756 published-reference/feature groups**, **not** 6,756 proven projects. Toronto 15,695 GIS features grouped to about 7,517 application groups; grouping is not proof of one project per group.

## Highest-value **unbuilt** earlier public cue feeds to investigate/pilot

Prioritized source discoveries from October 24 research (links are starting points, not guarantees of APIs or permissible bulk access):

1. **Municipal pre-application / public consultation meeting announcements and planning/council agendas**. First pilot: Burlington pre-application meeting notices; Brampton planning and development committee agenda items with developer and project PDFs. Could precede formal application and capture named investors and technical reports. Need determine stable feed/HTML/PDF access, publication timestamp, reuse rules, overlap vs existing permits.
   - Burlington planning process: https://www.burlington.ca/en/planning-and-development/burlington-planning-process.aspx
   - Existing Brampton council/public agenda portal needs current source endpoint verification.
2. **IESO connection application / assessment status** for new high-load users, plant expansions, substations and electricity infrastructure. High potential relevance for industrial HVAC/cooling, electrical and equipment suppliers. Need test whether actual project identity and first public disclosure are available; projects may already have suppliers.
   - https://www.ieso.ca/en/Sector-Participants/Connection-Process/Application-Status
3. **Improve the EXISTING ERO pipeline** rather than duplicate it; focus on *proposal-stage* ECA/EASR/industrial environmental approvals, plus Ontario environmental assessment commencement notices and Access Environment. Need operator/address matching with planning.
   - https://ero.ontario.ca/search
4. **Toronto Application Information Centre daily updates, public notice subscriptions**, check if earlier/different than already collected official Toronto ArcGIS feed, not a redundant collector.
   - https://www.toronto.ca/city-government/planning-development/application-information-centre/
5. **Milton, Pickering and Ajax** initial public planning notices, public posting dates, open documents and applicant contacts; Burlington/Oakville/Markham/Vaughan/Richmond Hill for later staged geographic expansion, **only after demonstrating unique lead time**.
   - https://www.milton.ca/business-development/planning-and-development/development-applications/development-application-notices/
   - https://www.pickering.ca/business-building-development/planning-and-development/current-development-proposals/
   - https://ajax.ca/build-invest/for-developers-builders/planning-development-applications/
6. **Investment and business expansion announcements, land purchases/commercial leases, corporate relocations, AGCO public applications**. May precede planning or point to fit-outs; these are *research hypotheses*, not confirmed feeds. Watch noisy/consumer/residential signals and contact privacy.
7. **Actionability lane**: CanadaBuys and municipal early tenders/RFQs and contractor expressions of interest, useful for identifiable buying signals, although often later than preconsultation.
   - https://canadabuys.canada.ca/en

## Critical unmet gaps (not solved by installing another ZIP)

1. **Evidence-backed buyer/operator discovery**: planning file can list an agent, architect or named tenant, **not necessarily the person who buys**. Verify legal organization, developer, operator, work-package decision-maker and their lawful public business contact separately.
2. **Contract/vendor status**: determine whether relevant trades/consultants/contractors are already engaged, whether the project is active, and which supplier categories could actually bid. Mark UNKNOWN if unverified.
3. **Signal freshness**: distinguish application dates vs public *first-posted* dates vs Radar's *first-seen* dates; verify new notices independently and quantify advantage over permit-stage discovery.
4. **Commercial-fit precision**: exclude routine minor variances and residential-only projects; prioritize substantial equipment/building investment with concrete trade scope.
5. **History joins**: conservative same-project linking over pre-consultation, rezoning, site plan, permits and procurement using address, official file number, operator, description; never silently merge at the same address.
6. **Source economics and quality**: official URL/source event, source availability, duplicate rate, incremental new relevant projects/day, dates, collection rights, and AI dollars used.

## Near-term order of work

**Phase A — VERIFY source advantage (next):** Pilot only the top 2–3 early sources (Burlington/Brampton pre-application and agendas; IESO; existing ERO enhancement). Snapshot new items with first-seen history. Test source overlap with today's 7 feeds. Document actual early-versus-late disclosure for a small matched cohort. Avoid indiscriminate expansion.

**Phase B — VALIDATE 10 opportunities:** Investigate top recent industrial candidates plus compelling older projects; capture municipal evidence and current state, identifiable likely work packages, organization roles, contact path, procurement status and independent corroboration. Explicitly distinguish 'lead', 'research candidate' and 'sale-ready verified opportunity'.

**Phase C — SELL and learn:** Present a sample to targeted GTA suppliers, get **2 paid pilots**, track whether recipients found timely unawarded business and adjust selection criteria. Only automate/release into the daily production system after value is demonstrated.

## Reminder/review checklist

At each periodic review report:
- **North star** in one sentence; no technical detour.
- **What materially changed** (confirmed proof only, and since when).
- **What remains**, ranked by business impact, especially new early sources, buyer identity, vendor availability, 10-lead and 2-pilot targets.
- **Top three concrete next actions**, owner/blocker, and source-evidence links.
- **Avoid busywork:** Is there a demonstrated new lead-time or contact-quality advantage? If not, do not build more.
- Respect **US$0.25/day DeepSeek**, free public data, V8 isolation, no fake first-seen dates, no fabricated buyer data.

**Status reviewed 2026-10-24:** Multiple free early-feed pilot collectors are now **built on unmerged draft PR #74**, with tests on Windows/Linux. Verified live sample: Hamilton 5,237 GIS features/five original dated notices and Markham 63 circulated-report index links. Those are **baseline research records, not verified opportunities**. Priority closure matrix: `GTA_RADAR_SEVEN_PRIORITY_CLOSURE_20261024.md` in the pilot branch; permanent research inventory: `GTA_RADAR_RESEARCH_REGISTER.md` on main. **0 independently verified private unawarded trade packages, 0 established paid pilots, and 0 validated same-project date advantage.** Buyer role, contracting stage and source identity are the blockers. Do not send a product teaser until a demonstrably useful sample has sufficient verified buyer and procurement evidence. `GTA_RADAR_INTERNAL_EVIDENCE_DOSSIERS.html` is an INTERNAL prototype generated by the pilot only. V8/scheduler and DeepSeek US$0.25/day budget untouched.
